# -*- coding: utf-8 -*-
"""生成评测 query（防循环论证设计）

纪律：
- 生成器**只见 `## 原文`（＋原注）**，绝不见 章旨/疏解/检索词/标题——否则等于拿答案出题。
- 每节生成两种风格：
  A. user   —— 现代口语，普通用户问性格/处境结构，禁用古文词与章节名
  B. analyst—— 分析师检索式（含日主/月令/结构条件），但禁止与章节标题逐字相同
- 输出 data/queries.jsonl，可断点续跑（已完成 (id,style) 跳过）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, GEN_MODEL, NO_THINK, chat, append_jsonl, load_json, load_jsonl  # noqa: E402

OUT = os.path.join(DATA, "queries.jsonl")
WORKERS = 6
_lock = threading.Lock()

SYS = "你是评测数据构造员，只输出 JSON，不解释。"

PROMPT_USER = """下面是一部中国古代命理／哲学古籍中某一节的原文（可能附原注）。请基于它的核心论点，写一个**现代普通用户**会问的问题。

原文：
---
{text}
---

要求：
1. 口语化，像用户在向分析师描述自己的困惑或性格处境；
2. 这个问题应当指向上面这段文字**独有的论点**（换一段文字就答不上来）；
3. 禁止出现：书名、章节名、生僻古文词、原文中的判词原话；
4. 禁止出现"这段文字""原文""作者"等元话语；
5. 允许常识词（五行、金木水火土、性格、工作、关系等）。

只输出 JSON，格式：{{"query": "问题", "focus": "锁定的是哪个论点（≤12字）"}}"""

PROMPT_ANALYST = """下面是一部中国古代命理／哲学古籍中某一节的原文（可能附原注）。请写一个**命理分析师在工作中会用的检索式提问**。

原文：
---
{text}
---

要求：
1. 带上该节适用的关键条件（日主、月令、十神、结构等，按原文实际情况写）；
2. 目标是"拿这个问题去知识库里找依据"，应明确指向上面这段文字**独有的论点**；
3. 禁止与章节标题逐字相同；禁止出现书名；
4. 不要照抄原文句子，用分析师的问法转述。

只输出 JSON，格式：{{"query": "检索式问题", "focus": "锁定的是哪个论点（≤12字）"}}"""

STYLES = {"user": PROMPT_USER, "analyst": PROMPT_ANALYST}


def gen_one(section: dict, style: str) -> dict | None:
    text = section["orig"]
    if section.get("note"):
        text += "\n\n【原注】" + section["note"]
    prompt = STYLES[style].format(text=text)
    for attempt in range(3):
        raw = chat([{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
                   temperature=0.6 + attempt * 0.2, max_tokens=800,
                   model=GEN_MODEL, extra=NO_THINK)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            continue
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        q = (o.get("query") or "").strip()
        if 6 <= len(q) <= 120:
            return {"query": q, "focus": (o.get("focus") or "").strip()}
    return None


def main() -> None:
    sections = load_json(os.path.join(DATA, "corpus.json"))["sections"]
    done = {(r["id"], r["style"]) for r in load_jsonl(OUT)}
    todo = [(s, st) for s in sections for st in STYLES if (s["id"], st) not in done]
    print(f"共 {len(sections)} 节 × {len(STYLES)} 风格，待生成 {len(todo)}")
    fail = []

    def work(item):
        s, st = item
        r = gen_one(s, st)
        if r is None:
            return item, None
        with _lock:
            append_jsonl(OUT, {"id": s["id"], "book": s["book"], "style": st, "title": s["title"], **r})
        return item, r

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, it) for it in todo]
        for i, f in enumerate(as_completed(futs), 1):
            (s, st), r = f.result()
            if r is None:
                fail.append((s["id"], st))
                print(f"  [FAIL] {s['id']} {st}")
            if i % 20 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    print(f"完成。失败 {len(fail)} 条：{fail}")


if __name__ == "__main__":
    main()
