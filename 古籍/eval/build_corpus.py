# -*- coding: utf-8 -*-
"""构建评测语料：把三本书的「节」抽成统一结构。

输出 data/corpus.json：
  sections[]: {id, book, path, title, orig, note, zhangzhi, jianci, shujie, related, nav}
- orig    = `## 原文`（含命例表）
- note    = `## 原注`（滴天髓 刘基原注；其余书一般无）
- zhangzhi= `## 章旨`（项目自撰检索层）
- jianci  = 章旨内「检索词：」行
- shujie  = `## 疏解`
- nav     = 书内导航表里的「何时调用」（穷通宝鉴干索引；无则空）
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BOOKS, DATA, GUJI, save_json  # noqa: E402

SKIP = re.compile(r"(AGENTS\.md$|README|检索表\.md$|^目录\.md$)", re.I)


def split_blocks(text: str) -> dict[str, str]:
    """按 `## ` 切块。返回 {节名: 正文}（同名取首个）。"""
    parts = re.split(r"^## +(.+?) *$", text, flags=re.M)
    # parts = [前言, 名1, 正文1, 名2, 正文2, ...]
    out: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        name = parts[i].strip()
        if name not in out:
            out[name] = parts[i + 1].strip()
    return out


def first_title(text: str) -> str:
    m = re.search(r"^# +(.+?) *$", text, flags=re.M)
    return m.group(1).strip() if m else ""


def parse_file(path: str, book: str) -> dict | None:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    blocks = split_blocks(text)
    orig = blocks.get("原文", "")
    if not orig:
        return None
    zz = blocks.get("章旨", "")
    jc = ""
    m = re.search(r"检索词：[ \t]*(.*)$", zz, flags=re.M)
    if m:
        jc = m.group(1).strip()
        # 检索词行从章旨正文里去掉，避免重复计入
        zz = zz.replace(m.group(0), "").strip()
    return {
        "id": os.path.relpath(path, GUJI).replace("\\", "/")[:-3],
        "book": book,
        "path": os.path.relpath(path, GUJI).replace("\\", "/"),
        "title": first_title(text),
        # 占位节：原文仅为标题行（如「论丁火」），KB 自述不构成可引用条文——不入评测
        "placeholder": bool(re.fullmatch(r"论[甲乙丙丁戊己庚辛壬癸][火土金水]", orig.strip())),
        "orig": orig,
        "note": blocks.get("原注", ""),
        "zhangzhi": zz,
        "jianci": jc,
        "shujie": blocks.get("疏解", ""),
        "related": blocks.get("关联章节", "") or blocks.get("关联条目", ""),
        "nav": "",
    }


def collect_nav() -> dict[str, str]:
    """从各 AGENTS.md 的表格里抽「何时调用」列，键=文件名。"""
    nav: dict[str, str] = {}
    for root, _dirs, files in os.walk(GUJI):
        for fn in files:
            if fn != "AGENTS.md":
                continue
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()
            header = None
            for ln in lines:
                if not ln.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if header is None:
                    if any("何时调用" in c for c in cells):
                        header = cells
                    continue
                if set("".join(cells)) <= set("-: "):
                    continue
                # 找行内文件名链接
                m = re.search(r"`([^`]+?\.md)`", ln)
                if not m:
                    continue
                fname = os.path.basename(m.group(1))
                for c in cells:
                    if "何时调用" in (header or []):
                        idx = [i for i, h in enumerate(header) if "何时调用" in h][0]
                        if idx < len(cells) and cells[idx] not in ("", "—"):
                            nav.setdefault(fname, cells[idx])
        return_nav = nav
    return return_nav


def main() -> None:
    nav = collect_nav()
    sections = []
    for bk, info in BOOKS.items():
        d = info["dir"]
        for root, _dirs, files in os.walk(d):
            for fn in sorted(files):
                if not fn.endswith(".md") or SKIP.search(fn):
                    continue
                p = os.path.join(root, fn)
                s = parse_file(p, info["name"])
                if s is None:
                    print(f"  [skip·无原文] {s and ''}{os.path.relpath(p, GUJI)}")
                    continue
                s["nav"] = nav.get(fn, "")
                sections.append(s)
    stats = {}
    for s in sections:
        st = stats.setdefault(s["book"], {"n": 0, "orig": 0, "zz": 0, "sh": 0, "jc": 0, "no_zz": 0, "no_sh": 0})
        st["n"] += 1
        st["orig"] += len(s["orig"])
        st["zz"] += len(s["zhangzhi"])
        st["sh"] += len(s["shujie"])
        st["jc"] += 1 if s["jianci"] else 0
        st["no_zz"] += 0 if s["zhangzhi"] else 1
        st["no_sh"] += 0 if s["shujie"] else 1
    save_json(os.path.join(DATA, "corpus.json"), {"meta": {"model": "见 common.py"}, "stats": stats, "sections": sections})
    ph = [s["id"] for s in sections if s["placeholder"]]
    print(f"\n共 {len(sections)} 节（占位节 {len(ph)}，不入评测：{[x.split('/')[-1] for x in ph]}）")
    for bk, st in stats.items():
        print(f"  {bk}: {st['n']} 节 | 原文 {st['orig']} 字 | 章旨 {st['zz']} | 检索词 {st['jc']}/{st['n']} | "
              f"缺章旨 {st['no_zz']} | 缺疏解 {st['no_sh']} | 疏解 {st['sh']} 字")


if __name__ == "__main__":
    main()
