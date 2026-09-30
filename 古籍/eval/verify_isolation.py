# -*- coding: utf-8 -*-
"""红线合规验证：QAG 索引是否严格隔离在原文层

产出 data/isolation_report.md，含逐项断言结果与样本哈希。
面试/复核时用：证明"结构法的注解层没有进 QAG 的库"。
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, load_json, load_jsonl  # noqa: E402
from build_qag_index import FORBIDDEN  # noqa: E402


def main() -> None:
    sections = {s["id"]: s for s in load_json(os.path.join(DATA, "corpus.json"))["sections"]}
    qag = load_jsonl(os.path.join(DATA, "qag_index.jsonl"))
    lines = ["# QAG 隔离验证报告", "", f"- qag_index 行数：{len(qag)}", ""]
    fail = 0
    for r in qag:
        s = sections[r["section_id"]]
        full = s["orig"] + (("\n\n【原注】" + s["note"]) if s["note"] else "")
        if r["chunk"] not in full:
            lines.append(f"- ❌ P2 块非原文子串：{r['section_id']} #{r['chunk_no']}")
            fail += 1
        hit = [w for w in FORBIDDEN if w in r["chunk"]]
        if hit:
            lines.append(f"- ❌ P3 块含注解标记 {hit}：{r['section_id']} #{r['chunk_no']}")
            fail += 1
        # 问题文本不得是注解层的逐字复制
        for field in ("zhangzhi", "shujie", "jianci"):
            if r["q"] and r["q"] in s[field]:
                lines.append(f"- ❌ P4 问题逐字出自 {field}：{r['section_id']}｜{r['q'][:40]}")
                fail += 1
    # 索引指纹（可复算）
    h = hashlib.sha1("".join(sorted(r["section_id"] + "|" + r["q"] for r in qag)).encode("utf-8")).hexdigest()
    lines += ["", f"- 断言结果：{'✅ 全部通过' if fail == 0 else f'❌ {fail} 处违例'}", f"- 问题集指纹 sha1：`{h}`", ""]
    out = os.path.join(DATA, "isolation_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"fail={fail} -> {out}")


if __name__ == "__main__":
    main()
