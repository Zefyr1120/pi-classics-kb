# -*- coding: utf-8 -*-
"""把国学3000版三命通会全书按已验证卷边界拆为 古籍/子平/三命通会/卷一.md…卷十二.md。

卷边界（国学3000 站点卷首页章号，h2 已验证）：
ch1=卷一, ch15=卷二, ch42=卷三, ch66=卷四, ch75=卷五, ch95=卷六,
ch169=卷七, ch192=卷八, ch253=卷九, ch314=卷十, ch357=卷十一, ch379=卷十二。
"""

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "古籍", "子平", "三命通会-国学3000-全书.md")
OUT_DIR = os.path.join(ROOT, "古籍", "子平", "三命通会")

BOUNDARIES = [1, 15, 42, 66, 75, 95, 169, 192, 253, 314, 357, 379]
VOL_NAMES = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]


def main():
    text = io.open(SRC, encoding="utf-8").read()
    # 按 "## " 分章
    chunks = re.split(r"(?m)^## ", text)
    assert chunks[0].strip() == "", f"文件头异常: {chunks[0][:80]!r}"
    chapters = []
    for c in chunks[1:]:
        nl = c.find("\n")
        title = c[:nl].strip() if nl >= 0 else c.strip()
        body = c[nl + 1:].strip() if nl >= 0 else ""
        chapters.append((title, body))
    print(f"总章数: {len(chapters)}")

    # 站内正文章号：2..395 中剔除卷首页号
    content_nums = [n for n in range(2, 396) if n not in BOUNDARIES]
    assert len(content_nums) == len(chapters), f"章数不符 {len(content_nums)} vs {len(chapters)}"

    # 按卷边界分组
    groups = []
    start = 0
    for k in range(12):
        end_num = BOUNDARIES[k + 1] if k + 1 < 12 else 396
        # 该卷正文章号范围：BOUNDARIES[k]+1 .. end_num-1
        lo, hi = BOUNDARIES[k] + 1, end_num - 1
        # 对应 chapters 索引区间：content_nums 中 lo..hi
        idxs = [i for i, n in enumerate(content_nums) if lo <= n <= hi]
        groups.append((VOL_NAMES[k], idxs))

    os.makedirs(OUT_DIR, exist_ok=True)
    for vol, idxs in groups:
        body_parts = []
        for i in idxs:
            title, body = chapters[i]
            body_parts.append(f"## {title}\n\n{body}".rstrip())
        content = "\n\n".join(body_parts) + "\n"
        header = (
            "> 书名：三命通会｜作者：明·万民英｜朝代：明\n"
            "> 版本说明：国学3000 网页整理本（章节正文，简体+现代标点；逐章抓取，原书十二卷）\n"
            "> 来源：https://guoxue3000.com/books/330\n"
            "> 抓取日期：2026-08-12\n"
            f"> 完整性：卷{vol}全文（全书十二卷；本卷 {len(idxs)} 章）\n"
            f"> 分层：原文=卷{vol}正文\n\n"
        )
        out = os.path.join(OUT_DIR, f"卷{vol}.md")
        io.open(out, "w", encoding="utf-8").write(header + f"## 卷{vol}\n\n" + content)
        first = chapters[idxs[0]][0]
        last = chapters[idxs[-1]][0]
        print(f"卷{vol}: {len(idxs)} 章 | 首章={first} | 末章={last} | {os.path.getsize(out)}B")


if __name__ == "__main__":
    main()
