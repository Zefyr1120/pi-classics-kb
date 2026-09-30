# -*- coding: utf-8 -*-
"""同预算对照：所有嵌入臂也走「top-20 召回 + 同一个 LLM 重排器」

为什么必须做：导航臂的 87.9% 是「三派召回 + 重排」的产物。若不给 QAG 同样的重排，
比较就不公平。本脚本对每个嵌入臂：
  1. 用缓存嵌入算 top-20（无 API 成本）；
  2. 用与 rerank_nav.py **完全相同**的重排 prompt 与模型重排 → top-5；
  3. 输出与导航臂同口径的 R@1/3/5、MRR，并给出各臂候选池上限（gold 在候选池中的比例）。

产出 data/rerank_compare.json + data/pools_<arm>.jsonl
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, chat, embed, load_json, load_jsonl, save_json  # noqa: E402
from run_eval import build_indexes, valid_queries  # noqa: E402

WORKERS = 6
MODEL = "deepseek-chat"
PROVIDER = "deepseek"
TOPN = 20
EXCERPT = 220
SYS = "你是检索结果的跨派重排员，只输出 JSON。"
PROMPT = """下面是用户问题，以及若干候选节（标题＋原文节选）。请把这些候选统一排序，选出最可能**直接回答该问题**的 5 节，按可能性从高到低。

问题：{query}

候选：
{cands}

只输出 JSON：{{"top": ["A", "C", ...]}}（用候选编号，最多 5 个，按可能性排序，不存在的编号不要输出）"""


def build_pools(idx: dict, queries: list[dict]) -> dict[str, dict]:
    qvec = np.asarray(embed([q["query"] for q in queries]))
    pools = {}
    for arm, items in idx.items():
        if not items:
            continue
        vec = np.asarray(embed([t for t, _ in items]))
        sids = [s for _, s in items]
        sims = qvec @ vec.T
        rows = []
        for qi, q in enumerate(queries):
            order = np.argsort(-sims[qi])
            seen, cands = set(), []
            for j in order:
                sid = sids[j]
                if sid in seen:
                    continue
                seen.add(sid)
                cands.append(sid)
                if len(cands) >= TOPN:
                    break
            rows.append({"gold_id": q["id"], "style": q["style"], "query": q["query"], "cands": cands})
        pools[arm] = rows
    return pools


def rerank(rows: list[dict], sections: dict) -> list[dict]:
    def excerpt(sid: str) -> str:
        s = sections[sid]
        t = re.sub(r"\s+", " ", s["orig"] + (("\n【原注】" + s["note"]) if s["note"] else "")).strip()
        return t[:EXCERPT] + ("…" if len(t) > EXCERPT else "")

    def work(r: dict) -> dict:
        blocks = [f"[{chr(65 + i)}][{sections[sid]['book']}·{sections[sid]['title']}] {excerpt(sid)}"
                  for i, sid in enumerate(r["cands"])]
        msgs = [{"role": "system", "content": SYS},
                {"role": "user", "content": PROMPT.format(query=r["query"], cands="\n".join(blocks))}]
        for _ in range(3):
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
                    if 0 <= j < len(r["cands"]) and r["cands"][j] not in ranked:
                        ranked.append(r["cands"][j])
            if ranked:
                return {**r, "top5": ranked[:5]}
        return {**r, "top5": []}

    out = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, r) for r in rows]
        for i, f in enumerate(as_completed(futs), 1):
            out.append(f.result())
            if i % 40 == 0:
                print(f"    {i}/{len(rows)}", flush=True)
    return out


def main() -> None:
    sections_list = load_json(os.path.join(DATA, "corpus.json"))["sections"]
    sections = {s["id"]: s for s in sections_list}
    qrels = load_json(os.path.join(DATA, "qrels.json"))
    queries, dropped = valid_queries(load_jsonl(os.path.join(DATA, "queries.jsonl")), sections_list, qrels)
    print(f"有效 query {len(queries)}")
    idx = build_indexes(sections_list)
    idx.pop("struct-thin", None)
    pools = build_pools(idx, queries)

    def gold_of(r):
        key = f"{r['gold_id']}|{r['style']}"
        return set(qrels.get(key, {}).get("accept") or []) | {r["gold_id"]}

    summary = {}
    for arm, rows in pools.items():
        print(f"== {arm} 重排中（{len(rows)}）==")
        with open(os.path.join(DATA, f"pools_{arm}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        rr = rerank(rows, sections)
        n = len(rr)
        ceiling = sum(1 for r in rr if gold_of(r) & set(r["cands"])) / n
        ranks = [next((i + 1 for i, sid in enumerate(r["top5"]) if sid in gold_of(r)), None) for r in rr]
        summary[arm] = {
            "n": n, "pool_ceiling": ceiling, "avg_cands": sum(len(r["cands"]) for r in rr) / n,
            "recall@1": sum(1 for x in ranks if x and x <= 1) / n,
            "recall@3": sum(1 for x in ranks if x and x <= 3) / n,
            "recall@5": sum(1 for x in ranks if x and x <= 5) / n,
            "mrr@5": sum(1 / x for x in ranks if x and x <= 5) / n,
        }
        print(f"  池上限 {ceiling:.1%} | R@1 {summary[arm]['recall@1']:.1%} | R@3 {summary[arm]['recall@3']:.1%} | R@5 {summary[arm]['recall@5']:.1%} | MRR {summary[arm]['mrr@5']:.3f}")
        save_json(os.path.join(DATA, "rerank_compare.json"), summary)
    print("\n完成 → data/rerank_compare.json")


if __name__ == "__main__":
    main()
