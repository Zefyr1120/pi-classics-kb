# -*- coding: utf-8 -*-
"""四臂检索评测：raw-emb / qag-emb / struct-thin / struct-full

- 单元：节（section）。多块/多问命中同一节只算一次。
- 指标：Recall@1/3/5、MRR@5；分书、分问法（user/analyst）报告。
- 产物：data/results.json（含每条 query 的 gold rank 与 top5，供失败案例复核）

红线：本脚本构造 index 文本时——
  raw-emb 只用 section["orig"]/["note"]；
  qag-emb 只用 qag_index.jsonl（其构建已由 build_qag_index.py 断言 R1）；
  struct-* 才使用 章旨/检索词/疏解。
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, embed, load_json, load_jsonl, save_json  # noqa: E402
from build_qag_index import chunk_text  # noqa: E402

K_MAX = 10


def rank_unique(items: list[tuple[str, str]]) -> list[str]:
    """(index_text, section_id) 按相似度降序 → 去重后的 section 序列"""
    seen, out = set(), []
    for sid in items:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def build_indexes(sections: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """返回 {arm: [(index_text, section_id), ...]}"""
    idx: dict[str, list[tuple[str, str]]] = {"raw-emb": [], "struct-thin": [], "struct-full": []}
    for s in sections:
        full = s["orig"] + (("\n\n【原注】" + s["note"]) if s["note"] else "")
        for c in chunk_text(full):
            idx["raw-emb"].append((c, s["id"]))
        thin = "\n".join(x for x in [s["title"], s["zhangzhi"], s["jianci"]] if x)
        idx["struct-thin"].append((thin, s["id"]))
        idx["struct-full"].append((thin + "\n" + s["shujie"], s["id"]))
    # QAG 臂来自独立产物（R1 隔离）
    qag = load_jsonl(os.path.join(DATA, "qag_index.jsonl"))
    if qag:
        for r in qag:
            idx.setdefault("qag-emb", []).append((r["q"], r["section_id"]))
            idx.setdefault("qag-ema", []).append((r["q"] + "\n" + r["a"], r["section_id"]))
    return idx


def valid_queries(queries: list[dict], sections: list[dict], qrels: dict | None) -> tuple[list[dict], list[dict]]:
    """过滤无效题（IR 标准做法，须在报告中声明）：
    - 占位节（原文仅标题行）产出的 query；
    - 判定为零可答（gold 被否且池内无替代）的漂移 query。
    返回 (保留, 排除)。
    """
    ph = {s["id"] for s in sections if s.get("placeholder")}
    ok, drop = [], []
    for q in queries:
        key = f"{q['id']}|{q['style']}"
        v = (qrels or {}).get(key)
        if q["id"] in ph:
            drop.append({**q, "drop_reason": "占位节"})
        elif v is not None and not v["accept"] and not v["gold_accepted"]:
            drop.append({**q, "drop_reason": "零可答（池内无节能答）"})
        else:
            ok.append(q)
    return ok, drop


def evaluate(idx: dict[str, list[tuple[str, str]]], queries: list[dict], qrels: dict | None = None) -> dict:
    qtexts = [q["query"] for q in queries]
    qvec = np.asarray(embed(qtexts))
    res: dict[str, dict] = {}
    for arm, items in idx.items():
        if not items:
            print(f"  [skip] {arm} 索引为空")
            continue
        texts = [t for t, _ in items]
        sids = [s for _, s in items]
        vec = np.asarray(embed(texts))
        sims = qvec @ vec.T                      # bge-m3 已归一化
        ranks = []
        detail = []
        for qi, q in enumerate(queries):
            order = np.argsort(-sims[qi])[: K_MAX * 4]
            ranked = rank_unique([sids[j] for j in order])[:K_MAX]
            key = f"{q['id']}|{q['style']}"
            gold = set((qrels or {}).get(key, {}).get("accept") or [q["id"]])
            gold.add(q["id"])
            hit = next((i + 1 for i, sid in enumerate(ranked) if sid in gold), None)
            ranks.append(hit)
            detail.append({"query": q["query"], "style": q["style"], "gold_id": q["id"],
                           "n_gold": len(gold), "rank": hit, "top5": ranked[:5]})
        res[arm] = {"ranks": ranks, "detail": detail, "index_size": len(items)}
    return res


def metrics(ranks: list[int | None], k: int) -> tuple[float, float]:
    rec = sum(1 for r in ranks if r is not None and r <= k) / len(ranks)
    mrr = sum((1.0 / r) for r in ranks if r is not None and r <= 5) / len(ranks)
    return rec, mrr


def fmt_table(res: dict, queries: list[dict], key_fn) -> str:
    lines = ["| 臂 | n | R@1 | R@3 | R@5 | MRR@5 |", "|---|---|---|---|---|---|"]
    for arm, d in res.items():
        m = [m for m, q in zip(d["ranks"], queries) if key_fn(q)]
        if not m:
            continue
        r1, _ = metrics(m, 1)
        r3, _ = metrics(m, 3)
        r5, mrr = metrics(m, 5)
        lines.append(f"| {arm} | {len(m)} | {r1:.1%} | {r3:.1%} | {r5:.1%} | {mrr:.3f} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run1")
    args = ap.parse_args()

    sections = load_json(os.path.join(DATA, "corpus.json"))["sections"]
    queries = load_jsonl(os.path.join(DATA, "queries.jsonl"))
    print(f"语料 {len(sections)} 节；query {len(queries)} 条")

    idx = build_indexes(sections)
    for arm, items in idx.items():
        print(f"  索引[{arm}] {len(items)} 条")

    qrels = None
    qrels_path = os.path.join(DATA, "qrels.json")
    if os.path.exists(qrels_path):
        qrels = load_json(qrels_path)
        print(f"  qrels：{len(qrels)} 条（gold 集已按 TREC pooling 扩展）")

    queries, dropped = valid_queries(queries, sections, qrels)
    if dropped:
        save_json(os.path.join(DATA, "excluded_queries.json"), dropped)
        n_ph = sum(1 for d in dropped if d["drop_reason"] == "占位节")
        print(f"  有效 query：{len(queries)}；已排除 {len(dropped)}（占位节 {n_ph} / 零可答 {len(dropped) - n_ph}）→ data/excluded_queries.json")

    res = evaluate(idx, queries, qrels)
    out = {"tag": args.tag, "n_sections": len(sections), "n_queries": len(queries),
           "arms": {a: {"index_size": d["index_size"]} for a, d in res.items()},
           "detail": {a: d["detail"] for a, d in res.items()}}
    for a, d in res.items():
        for k in (1, 3, 5):
            out["arms"][a][f"recall@{k}"] = metrics(d["ranks"], k)[0]
        out["arms"][a]["mrr@5"] = metrics(d["ranks"], 5)[1]
    save_json(os.path.join(DATA, f"results_{args.tag}.json"), out)

    print("\n## 全量（user+analyst）")
    print(fmt_table(res, queries, lambda q: True))
    for style in ("user", "analyst"):
        print(f"\n## {style}")
        print(fmt_table(res, queries, lambda q, s=style: q["style"] == s))
    for book in sorted({q["book"] for q in queries}):
        print(f"\n## {book}")
        print(fmt_table(res, queries, lambda q, b=book: q["book"] == b))

    # 命中率差异最大的失败案例（结构法没进前5）供人工复核
    bad = [d for d in res.get("struct-full", {}).get("detail", []) if d["rank"] is None or d["rank"] > 5]
    print(f"\nstruct-full 未进前5：{len(bad)}/{len(queries)}（明细见 results_{args.tag}.json，供 gold 复核）")

    # 稳健性：剔除「query 字面含标题」子集后重算（防标题泄漏虚高）
    titles = {s["id"]: s["title"] for s in sections}
    clean = [q for q in queries if titles.get(q["id"], "") not in q["query"]]
    if len(clean) < len(queries):
        print(f"\n## 稳健性：剔除标题泄漏子集（{len(queries) - len(clean)} 条剔除，剩 {len(clean)}）")
        mask = {id(q) for q in clean}
        res2 = {a: {**d, "ranks": [r for r, q in zip(d["ranks"], queries) if id(q) in mask]}
                for a, d in res.items()}
        print(fmt_table(res2, clean, lambda q: True))


if __name__ == "__main__":
    main()
