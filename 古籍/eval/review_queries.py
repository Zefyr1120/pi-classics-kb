# -*- coding: utf-8 -*-
"""测试集泄漏审查：query 是否含标题/书名/章节号、是否过短过长、是否重复

产出 data/query_review.md：可疑清单（人工复核）+ 统计。复核结论回写本文件后即为定稿依据。
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, load_json, load_jsonl  # noqa: E402


def main() -> None:
    secs = {s["id"]: s for s in load_json(os.path.join(DATA, "corpus.json"))["sections"]}
    qs = load_jsonl(os.path.join(DATA, "queries.jsonl"))
    titles = {s["title"] for s in secs.values()}
    books = {"子平真诠", "滴天髓", "穷通宝鉴"}
    flags = []
    dup = Counter(q["query"] for q in qs)
    for q in qs:
        s = secs[q["id"]]
        reasons = []
        if s["title"] and s["title"] in q["query"] and len(s["title"]) >= 3:
            reasons.append("含标题")
        if any(b in q["query"] for b in books):
            reasons.append("含书名")
        if len(q["query"]) < 8:
            reasons.append("过短")
        if len(q["query"]) > 90:
            reasons.append("过长")
        if dup[q["query"]] > 1:
            reasons.append("重复")
        # 与节标题的重合字数（≥60% 视为高重合）
        if s["title"]:
            common = sum(1 for ch in set(s["title"]) if ch in q["query"])
            if common / max(len(set(s["title"])), 1) >= 0.8 and len(set(s["title"])) >= 3:
                reasons.append("与标题字面高重合")
        if reasons:
            flags.append((q, reasons))
    lines = ["# 测试集泄漏审查", "",
             f"- 总 query：{len(qs)}（user {sum(1 for q in qs if q['style']=='user')} / "
             f"analyst {sum(1 for q in qs if q['style']=='analyst')}）",
             f"- 可疑：{len(flags)}", ""]
    for q, reasons in flags:
        lines.append(f"- `{q['id']}` [{q['style']}] {'/'.join(reasons)}｜{q['query']}")
    with open(os.path.join(DATA, "query_review.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"可疑 {len(flags)}/{len(qs)} → data/query_review.md")
    # 打印前 15 条供速览
    for q, reasons in flags[:15]:
        print(f"  {'/'.join(reasons)}: {q['query'][:60]}  <- {q['id']}")


if __name__ == "__main__":
    main()
