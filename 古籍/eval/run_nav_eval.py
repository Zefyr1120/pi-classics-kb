# -*- coding: utf-8 -*-
"""生产路径臂：LLM 走结构化导航索引（三级渐进式披露）

与嵌入臂的区别：这不是"把注解嵌入"，而是**复现 agent 的真实检索动作**——
先看书级导航 → 再缩小到干/篇 → 在条目索引（含「何时调用」）里定位。

流程（每 query）：
  1. 路由：给三本书的书级摘要，选书（可多选）；
  2. 书内：给该书的完整导航（章目录/检索表/干索引），选 top-5 节；
  3. 穷通宝鉴多一层：先在 14 个组（论木/论土/论金/论水/卷首/十干）里选 top-2，再进组选条目。

产出 data/nav_results_<tag>.json（结构同 run_eval 的 detail，含路由诊断）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, GUJI, NO_THINK, chat, load_json, load_jsonl, save_json  # noqa: E402
from run_eval import valid_queries  # noqa: E402

WORKERS = 4
K = 5
NAV_PROVIDER = os.environ.get("NAV_PROVIDER", "deepseek")          # siliconflow 余额不足，导航臂走直连 DeepSeek
NAV_MODEL = os.environ.get("NAV_MODEL", "deepseek-chat")
_lock = threading.Lock()
GU = os.path.join(GUJI, "子平")
SYS = "你是古籍知识库的检索导航员，只输出 JSON，不解释。"


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def block(text: str, name: str) -> str:
    m = re.search(rf"^## +{re.escape(name)} *$([\s\S]*?)(?=^## |\Z)", text, flags=re.M)
    return m.group(1).strip() if m else ""


# ---------- 书级路由 ----------
def router_index() -> str:
    parts = []
    for bk, p in [("子平真诠", os.path.join(GU, "子平真诠", "AGENTS.md")),
                  ("滴天髓", os.path.join(GU, "滴天髓", "AGENTS.md")),
                  ("穷通宝鉴", os.path.join(GU, "穷通宝鉴", "AGENTS.md"))]:
        head = "\n".join(read(p).splitlines()[:14])
        parts.append(f"### 《{bk}》\n{head}")
    return "\n\n".join(parts)


ROUTER_PROMPT = """用户提出一个问题。请判断该问题需要查阅下列哪本书（可多选，最多 2 本）。

{index}

问题：{query}

只输出 JSON：{{"books": ["子平真诠"]}}"""


# ---------- 书内导航 ----------
def zip_index() -> str:
    return read(os.path.join(GU, "子平真诠", "AGENTS.md"))


def dts_index() -> str:
    return read(os.path.join(GU, "滴天髓", "AGENTS.md")) + "\n\n" + read(os.path.join(GU, "滴天髓", "检索表.md"))


QT_GROUPS = ["00-总论/论木", "00-总论/论土", "00-总论/论金", "00-总论/论水",
             "01-卷首", "02-甲木", "03-乙木", "04-丙火", "05-丁火", "06-戊土",
             "07-己土", "08-庚金", "09-辛金", "10-壬水", "11-癸水"]


def qt_group_index() -> str:
    """穷通宝鉴：组级索引 = 书级 AGENTS + 总论 AGENTS + 各组章旨（紧凑）"""
    parts = [read(os.path.join(GU, "穷通宝鉴", "AGENTS.md")),
             read(os.path.join(GU, "穷通宝鉴", "00-总论", "AGENTS.md"))]
    for g in QT_GROUPS:
        p = os.path.join(GU, "穷通宝鉴", g, "AGENTS.md")
        if not os.path.exists(p):
            continue
        t = read(p)
        zz = block(t, "章旨")
        parts.append(f"### {g}\n{zz[:400]}")
    return "\n\n".join(parts)


def qt_entry_index(group: str) -> str:
    return read(os.path.join(GU, "穷通宝鉴", group, "AGENTS.md"))


INBOOK_PROMPT = """下面是《{book}》的检索导航（章目录/检索表）。用户问题如下，请选出最可能包含回答依据的 {k} 节，按可能性从高到低排序。

问题：{query}

导航：
{index}

只输出 JSON：{{"top": ["文件标识1", "文件标识2", ...]}}
（最多 {k} 个；标识必须严格取自导航中出现的文件名，如 `01-天道.md`；不要输出其他文字）"""

GROUP_PROMPT = """下面是《穷通宝鉴》的组级索引。用户问题如下，请选出最可能包含回答依据的 2 个组（组的标识如 `03-乙木`、`00-总论/论木`）。

问题：{query}

索引：
{index}

只输出 JSON：{{"groups": ["03-乙木"]}}"""


def parse_json(raw: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def ask(prompt: str, max_tokens: int = 400) -> dict:
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}]
    extra = NO_THINK if NAV_PROVIDER == "siliconflow" else None
    raw = chat(msgs, temperature=0.0, max_tokens=max_tokens, model=NAV_MODEL,
               extra=extra, provider=NAV_PROVIDER)
    return parse_json(raw)


# ---------- 标识 → 语料节 id ----------
def build_name_map(sections: list[dict]) -> dict[str, str]:
    m = {}
    for s in sections:
        rel = s["path"].split("子平/")[-1]                 # 如 穷通宝鉴/03-乙木/02-正月乙木.md
        m[rel] = s["id"]
        m[rel.split("/", 1)[1]] = s["id"]                  # 如 03-乙木/02-正月乙木.md
        m[os.path.basename(rel)] = m.get(os.path.basename(rel), s["id"]) if os.path.basename(rel) not in m else m[os.path.basename(rel)]
    # basename 冲突（如两个 AGENTS 不会出现；正文文件名在同书内唯一）——保留首个
    return m


def resolve(names: list[str], book: str, name_map: dict[str, str], sections_by_id: dict) -> list[str]:
    out = []
    for n in names:
        n = str(n).strip().strip("`").replace("\\", "/")
        for cand in (f"{book}/{n}", n, os.path.basename(n)):
            sid = name_map.get(cand)
            if sid and sid not in out and sections_by_id[sid]["book"] == book.split("/")[0]:
                out.append(sid)
                break
    return out


def nav_one(q: dict, sections: list[dict], name_map: dict[str, str], by_id: dict,
            all_books: bool = False) -> dict:
    if all_books:
        books = ["子平真诠", "滴天髓", "穷通宝鉴"]
    else:
        books = ask(ROUTER_PROMPT.format(index=router_index(), query=q["query"]), 200).get("books") or []
        books = [b for b in books if b in ("子平真诠", "滴天髓", "穷通宝鉴")][:2]
        if not books:                                   # 兜底
            books = ["子平真诠"]
    picked: list[str] = []
    detail_books = []
    per_book: list[dict] = []
    for bk in books:
        detail_books.append(bk)
        if bk == "子平真诠":
            ids = resolve(ask(INBOOK_PROMPT.format(book=bk, query=q["query"], index=zip_index(), k=K)).get("top") or [],
                          bk, name_map, by_id)
            per_book.append({"book": bk, "ids": ids})
        elif bk == "滴天髓":
            ids = resolve(ask(INBOOK_PROMPT.format(book=bk, query=q["query"], index=dts_index(), k=K)).get("top") or [],
                          bk, name_map, by_id)
            per_book.append({"book": bk, "ids": ids})
        else:
            groups = ask(GROUP_PROMPT.format(query=q["query"], index=qt_group_index())).get("groups") or []
            groups = [g for g in groups if g in QT_GROUPS][:2]
            if not groups:
                groups = ["03-乙木"]
            ids: list[str] = []
            for g in groups:
                top = ask(INBOOK_PROMPT.format(book="穷通宝鉴", query=q["query"],
                                               index=qt_entry_index(g), k=K)).get("top") or []
                for x in resolve(top, f"穷通宝鉴/{g}", name_map, by_id) + resolve(top, "穷通宝鉴", name_map, by_id):
                    if x not in ids:
                        ids.append(x)
            per_book.append({"book": "穷通宝鉴", "ids": ids})
    # 多书结果交叉合并（避免后一书被前书的 5 条挤掉）；同时保留每书原始列表供重排
    book_lists = [x["ids"] for x in per_book]
    for i in range(max((len(x) for x in book_lists), default=0)):
        for ids in book_lists:
            if i < len(ids):
                picked.append(ids[i])
    # 去重保序
    seen, ranked = set(), []
    for sid in picked:
        if sid not in seen:
            seen.add(sid)
            ranked.append(sid)
    return {"query": q["query"], "style": q["style"], "gold_id": q["id"], "route": detail_books,
            "top5": ranked[:K], "per_book": per_book}


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "run1"
    all_books = os.environ.get("NAV_MODE", "router") == "all"
    sections = load_json(os.path.join(DATA, "corpus.json"))["sections"]
    by_id = {s["id"]: s for s in sections}
    name_map = build_name_map(sections)
    queries = load_jsonl(os.path.join(DATA, "queries.jsonl"))
    qrels = load_json(os.path.join(DATA, "qrels.json")) if os.path.exists(os.path.join(DATA, "qrels.json")) else None
    queries, dropped = valid_queries(queries, sections, qrels)
    print(f"有效 query {len(queries)}（排除 {len(dropped)}）")
    out_path = os.path.join(DATA, f"nav_results_{tag}{'_all' if all_books else ''}.json")
    done = {}
    if os.path.exists(out_path):
        for d in json.load(open(out_path, encoding="utf-8")):
            if d.get("top5"):          # 失败条目（空 top5）不算完成，重跑
                done[f"{d['gold_id']}|{d['style']}"] = d
    todo = [q for q in queries if f"{q['id']}|{q['style']}" not in done]
    print(f"待跑 {len(todo)}/{len(queries)}")
    results = list(done.values())

    def work(q):
        try:
            return nav_one(q, sections, name_map, by_id, all_books=all_books)
        except Exception as e:  # noqa: BLE001
            return {"query": q["query"], "style": q["style"], "gold_id": q["id"], "route": [],
                    "top5": [], "error": repr(e)[:200]}

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, q) for q in todo]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            with _lock:
                results.append(r)
                if i % 10 == 0:
                    save_json(out_path, results)
            if i % 20 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    save_json(out_path, results)
    # 指标（gold 集与嵌入臂一致：qrels 扩展 + 生成出处）
    ranks = []
    for r in results:
        key = f"{r['gold_id']}|{r['style']}"
        gold = set((qrels or {}).get(key, {}).get("accept") or [r["gold_id"]]) | {r["gold_id"]}
        rank = next((i + 1 for i, sid in enumerate(r["top5"]) if sid in gold), None)
        r["rank"] = rank
        ranks.append(rank)
    n = len(ranks)
    for k in (1, 3, 5):
        print(f"nav-LLM R@{k}: {sum(1 for x in ranks if x and x <= k)/n:.1%}")
    print(f"nav-LLM MRR@5: {sum(1/x for x in ranks if x and x <= 5)/n:.3f}")
    save_json(out_path, results)


if __name__ == "__main__":
    main()
