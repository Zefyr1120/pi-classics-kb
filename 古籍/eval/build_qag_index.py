# -*- coding: utf-8 -*-
"""QAG 基线索引构建（红线 R1 的落地点）

输入：corpus.json 的**原文层**（section["orig"] + 底本自带原注 section["note"]）
处理：节内定长切块（≈500 字，重叠 80） → LLM 为每块生成 3 个问答对
输出：data/qag_index.jsonl  每行 {section_id, chunk_no, chunk, q, a}

红线断言（任一违反即中止）：
  P1 只读 orig/note 两个键——注解层（章旨/疏解/检索词）在代码路径上不可达；
  P2 每块文本必须是对应全文的子串（证明无拼接、无注入）；
  P3 块文本不得含注解层标记词。
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

OUT = os.path.join(DATA, "qag_index.jsonl")
WORKERS = 6
_lock = threading.Lock()
CHUNK, OVERLAP = 500, 80
NQ = 3
# 注解层标记词：出现即说明把项目加工层混进了原文（R1 违例）
FORBIDDEN = ["章旨", "疏解", "检索词", "关联章节", "关联条目", "何时调用", "判定链位置", "注解：2026"]

SYS = "你是知识库索引构建员，只输出 JSON，不解释。"

PROMPT = """为古籍知识库做问答式索引。下面是某节古文的第 {i} 段原文，请生成 {n} 个「用户可能提出的问题」，并为每个问题写一个基于该段的回答。

原文片段：
---
{chunk}
---

要求（{n} 个问题分别对应下列三种类型，覆盖该段不同要点）：
1. 分析师式短问句（含关键术语，像检索式）；
2. 普通用户口语长问句（可以是一两句话描述情境与困惑）；
3. 换一个角度的问句（问机制/条件/对比，与前两问不重复）。

每个问题都必须能由**这一段**完整回答，不依赖其他段落；用现代汉语转述，不要整句照抄古文；回答一两句话即可。

只输出 JSON：{{"qa": [{{"q": "问题", "a": "回答"}}, ...]}}"""


def chunk_text(text: str) -> list[str]:
    """节内定长切块（字符窗口）。"""
    text = text.strip()
    if len(text) <= CHUNK:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        piece = text[start:start + CHUNK].strip()
        if piece:
            out.append(piece)
        if start + CHUNK >= len(text):
            break
        start += CHUNK - OVERLAP
    return out


def gen_qa(chunk: str, i: int) -> list[dict]:
    for attempt in range(3):
        raw = chat([{"role": "system", "content": SYS},
                    {"role": "user", "content": PROMPT.format(chunk=chunk, i=i, n=NQ)}],
                   temperature=0.5 + attempt * 0.2, max_tokens=1200,
                   model=GEN_MODEL, extra=NO_THINK)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            continue
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        qa = [x for x in (o.get("qa") or []) if (x.get("q") or "").strip()]
        if qa:
            return qa[:NQ]
    return []


def main() -> None:
    sections = load_json(os.path.join(DATA, "corpus.json"))["sections"]
    done = {(r["section_id"], r["chunk_no"]) for r in load_jsonl(OUT)}
    todo = []
    for s in sections:
        full = s["orig"] + (("\n\n【原注】" + s["note"]) if s["note"] else "")
        # P3：原文层不得含注解层标记
        hit = [w for w in FORBIDDEN if w in full]
        assert not hit, f"R1 违例：{s['id']} 原文层出现注解标记 {hit}"
        for i, c in enumerate(chunk_text(full)):
            # P2：块必须是全文子串
            assert c in full, f"R1 违例：{s['id']} 块 {i} 非原文子串"
            if (s["id"], i) not in done:
                todo.append((s, i, c, full))
    print(f"待处理块：{len(todo)}（已完成 {len(done)}）")

    def work(item):
        s, i, c, full = item
        qa = gen_qa(c, i)
        with _lock:
            for x in qa:
                append_jsonl(OUT, {"section_id": s["id"], "book": s["book"], "chunk_no": i,
                                   "chunk": c, "q": x["q"].strip(), "a": (x.get("a") or "").strip()})
        return s["id"], i

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, it) for it in todo]
        for j, f in enumerate(as_completed(futs), 1):
            f.result()
            if j % 10 == 0:
                print(f"  {j}/{len(todo)}", flush=True)
    rows = load_jsonl(OUT)
    print(f"完成：{len(rows)} 个问答对，覆盖 {len({r['section_id'] for r in rows})} 节")


if __name__ == "__main__":
    main()
