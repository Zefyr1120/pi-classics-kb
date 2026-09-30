# -*- coding: utf-8 -*-
"""跨派重排：把三派导航召回的候选统一排序（对应报告合成层的真实动作）

输入：nav_results_<tag>_all.json 的 per_book（三派各自的 top-5 原始列表）
处理：候选并集（≤15）→ LLM 统一排序 → top-5
指标：① 并集召回（gold 在并集中出现 = 三派并行检索的召回上限）
      ② 重排后 R@1/3/5（可比的单列表指标）
产出：data/nav_rerank_<tag>.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, chat, load_json, save_json  # noqa: E402

WORKERS = 6
MODEL = "deepseek-chat"
PROVIDER = "deepseek"
EXCERPT = 220
SYS = "你是检索结果的跨派重排员，只输出 JSON。"

PROMPT = """下面是用户问题，以及三个流派各自检索出的候选节（标题＋原文节选）。请把这些候选统一排序，选出最可能**直接回答该问题**的 5 节，按可能性从高到低。

问题：{query}

候选：
{cands}

只输出 JSON：{{"top": ["A", "C", ...]}}（用候选编号，最多 5 个，按可能性排序，不存在的编号不要输出）"""


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "final2"
    src = os.path.join(DATA, f"nav_results_{tag}_all.json")
    out = os.path.join(DATA, f"nav_rerank_{tag}.json")
    sections = {s["id"]: s for s in load_json(os.path.join(DATA, "corpus.json"))["sections"]}
    qrels = load_json(os.path.join(DATA, "qrels.json"))
    queries = {f"{q['id']}|{q['style']}": q for q in
               (json.loads(l) for l in open(os.path.join(DATA, "queries.jsonl"), encoding="utf-8"))}
    nav = [r for r in json.load(open(src, encoding="utf-8")) if r.get("top5")]
    print(f"导航结果 {len(nav)} 条")

    def excerpt(sid: str) -> str:
        s = sections[sid]
        t = re.sub(r"\s+", " ", s["orig"] + (("\n【原注】" + s["note"]) if s["note"] else "")).strip()
        return t[:EXCERPT] + ("…" if len(t) > EXCERPT else "")

    def build(r: dict) -> tuple[list[str], str]:
        cands: list[str] = []
        for blk in r.get("per_book") or []:
            for sid in blk.get("ids") or []:
                if sid in sections and sid not in cands:
                    cands.append(sid)
        blocks = []
        for i, sid in enumerate(cands):
            s = sections[sid]
            blocks.append(f"[{chr(65 + i)}][{s['book']}·{s['title']}] {excerpt(sid)}")
        return cands, "\n".join(blocks)

    def work(r: dict) -> dict:
        cands, blocks = build(r)
        if not cands:
            return {**r, "cands": [], "top5": []}
        msgs = [{"role": "system", "content": SYS},
                {"role": "user", "content": PROMPT.format(query=r["query"], cands=blocks)}]
        for attempt in range(3):
            raw = chat(msgs, temperature=0.0, max_tokens=300, model=MODEL, provider=PROVIDER)
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                continue
            try:
                idxs = json.loads(m.group(0)).get("top") or []
            except json.JSONDecodeError:
                continue
            ranked = []
            for x in idxs:
                x = str(x).strip().upper()
                if len(x) == 1 and "A" <= x <= "Z":
                    j = ord(x) - 65
                    if 0 <= j < len(cands) and cands[j] not in ranked:
                        ranked.append(cands[j])
            if ranked:
                return {**r, "cands": cands, "top5": ranked[:5]}
        return {**r, "cands": cands, "top5": []}

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, r) for r in nav]
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            if i % 20 == 0:
                print(f"  {i}/{len(nav)}", flush=True)
                save_json(out, results)
    save_json(out, results)

    # ---- 指标 ----
    def gold_of(r: dict) -> set[str]:
        key = f"{r['gold_id']}|{r['style']}"
        return set(qrels.get(key, {}).get("accept") or []) | {r["gold_id"]}

    n = len(results)
    union = sum(1 for r in results if gold_of(r) & set(r["cands"]))
    ranks = [next((i + 1 for i, sid in enumerate(r["top5"]) if sid in gold_of(r)), None) for r in results]
    print(f"\n三派并集召回（上限）: {union/n:.1%}  平均候选数 {sum(len(r['cands']) for r in results)/n:.1f}")
    for k in (1, 3, 5):
        print(f"重排后 R@{k}: {sum(1 for x in ranks if x and x <= k)/n:.1%}")
    print(f"重排后 MRR@5: {sum(1/x for x in ranks if x and x <= 5)/n:.3f}")


if __name__ == "__main__":
    main()
