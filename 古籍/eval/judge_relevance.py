# -*- coding: utf-8 -*-
"""相关性判定（TREC pooling）→ 修正 gold 的保守偏差

背景：gold 初值是"query 的生成出处节"（严格单 gold）。但存在跨书/跨节可答的情况
（如"丙火特性"两本书都答得上），严格单 gold 会低估所有臂。按 IR 标准做法：
  1. 汇集各臂 top-5 组成候选池（pooling）；
  2. 用 LLM 对池内每个候选中立判定"能否直接作为回答依据"（只给原文，不给任何注解，防偏袒）；
  3. gold 集 = {生成出处节} ∪ {判定为可接受的节}；
  4. 各臂在扩展 gold 上重算指标。

判定纪律（写进 prompt）：相邻月令/不同日主条目不可代替（知识库自身纪律：同干不同月令不可串读）；
仅沾边/只提供背景的不算；宁严勿宽。

产出：data/qrels.json  { "<id>|<style>": [可接受的节 id, ...] }
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, chat, load_json, load_jsonl, save_json  # noqa: E402

OUT = os.path.join(DATA, "qrels.json")
WORKERS = 6
EXCERPT = 320
MODEL = "deepseek-chat"          # 直连 DeepSeek（SiliconFlow 余额耗尽）
PROVIDER = "deepseek"
POOL_RESULTS = ["results_final.json", "nav_results_final.json", "nav_results_final_all.json"]
_lock = threading.Lock()

SYS = "你是检索评测的相关性判定员，只输出 JSON。"

PROMPT = """给定一个问题，以及若干候选节（标题＋原文节选），判断每个候选节能否**直接作为回答该问题的依据**。

判定规则：
- 日主、月令、具体条件必须吻合；相邻月令或不同日主的条目【不能】替代（本知识库纪律：同一日主不同月令的取用不可串读）；
- 覆盖该问题的总论/通例条目可以接受；仅沾边、只提供背景的不算；
- 不同书中内容等价（都能回答该问题）的节都算可接受；
- 宁严勿宽：拿不准就判否。

问题：{query}

候选节：
{cands}

只输出 JSON：{{"accept": [可接受的候选编号]}}"""


def excerpt(s: dict) -> str:
    t = s["orig"] + (("\n【原注】" + s["note"]) if s["note"] else "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:EXCERPT] + ("…" if len(t) > EXCERPT else "")


def judge(q: dict, cands: list[dict], sections: dict) -> tuple[list[str], bool]:
    blocks = [f"[{i}] 《{sections[c]['book']}·{sections[c]['title']}》：{excerpt(sections[c])}"
              for i, c in enumerate(cands)]
    raw = chat([{"role": "system", "content": SYS},
                {"role": "user", "content": PROMPT.format(query=q["query"], cands="\n\n".join(blocks))}],
               temperature=0.0, max_tokens=600, model=MODEL, provider=PROVIDER)
    m = re.search(r"\{[\s\S]*\}", raw)
    acc: list[str] = []
    if m:
        try:
            idxs = json.loads(m.group(0)).get("accept") or []
            acc = [cands[i] for i in idxs if isinstance(i, int) and 0 <= i < len(cands)]
        except json.JSONDecodeError:
            pass
    gold_ok = q["id"] in acc          # 判定器是否也认可生成出处——不认可说明该 query 质量存疑
    return acc, gold_ok


def build_pool(queries: list[dict], sections: dict) -> dict[str, list[str]]:
    """候选池 = 全部参评系统 top5 的并集（TREC 规范：池必须覆盖每个参评系统，
    否则未进池的系统会被系统性低估）"""
    pool: dict[str, list[str]] = {}
    for q in queries:
        key = f"{q['id']}|{q['style']}"
        cands: list[str] = []
        for fn in POOL_RESULTS:
            p = os.path.join(DATA, fn)
            if not os.path.exists(p):
                continue
            data = json.load(open(p, encoding="utf-8"))
            if "detail" in data:                      # run_eval 格式：按 (gold_id,style) 建映射
                for arm in data["detail"]:
                    for d in data["detail"][arm]:
                        if f"{d['gold_id']}|{d['style']}" != key:
                            continue
                        for sid in d["top5"]:
                            if sid in sections and sid not in cands:
                                cands.append(sid)
            else:                                     # nav 格式（列表）
                for d in data:
                    if f"{d['gold_id']}|{d['style']}" != key:
                        continue
                    for sid in d.get("top5") or []:
                        if sid in sections and sid not in cands:
                            cands.append(sid)
        if q["id"] not in cands:
            cands.append(q["id"])
        pool[key] = cands
    return pool


def main() -> None:
    sections = {s["id"]: s for s in load_json(os.path.join(DATA, "corpus.json"))["sections"]}
    queries = load_jsonl(os.path.join(DATA, "queries.jsonl"))
    qrels = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if qrels:                                    # 旧判定另存，便于对比
        save_json(os.path.join(DATA, "qrels_prev.json"), qrels)

    pool = build_pool(queries, sections)
    todo = pool          # 池变了，全部重判（旧结果已备份为 qrels_prev.json）
    print(f"待判定 query：{len(todo)}，候选池均长 {sum(len(v) for v in todo.values())/max(len(todo),1):.1f}")
    qmap = {f"{q['id']}|{q['style']}": q for q in queries}
    weak_gold = []

    def work(key: str):
        q = qmap[key]
        acc, gold_ok = judge(q, pool[key], sections)
        return key, q["id"], acc, gold_ok

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, k) for k in todo]
        for i, f in enumerate(as_completed(futs), 1):
            key, gid, acc, gold_ok = f.result()
            with _lock:
                qrels[key] = {"gold": gid, "accept": acc, "gold_accepted": gold_ok}
                if i % 20 == 0:
                    save_json(OUT, qrels)
            if not gold_ok:
                weak_gold.append(key)
            if i % 20 == 0:
                print(f"  {i}/{len(todo)}", flush=True)

    save_json(OUT, qrels)
    n = len(qrels)
    multi = sum(1 for v in qrels.values() if len(v["accept"]) > 1)
    print(f"完成 {n} 条；判定为多 gold 的 {multi} 条；生成出处在判定中被否 {len(weak_gold)} 条")
    print(f"  弱 gold 清单（需人工复核 query 质量）：{weak_gold[:20]}")


if __name__ == "__main__":
    main()
