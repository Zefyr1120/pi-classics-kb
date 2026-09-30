# -*- coding: utf-8 -*-
"""古籍检索评测 · 公共工具（API 调用 / 缓存 / IO）

设计纪律
- 所有 HTTP 调用走 Python（curl 在 Windows Git Bash 下会毁掉中文编码）。
- 嵌入结果落盘缓存（sha1(model+text)），重跑不重复烧 token。
- 只有本文件碰网络；其余脚本可离线复跑。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

# ---------- 路径 ----------
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(EVAL_DIR, "..", ".."))          # 仓库根目录/
GUJI = os.path.join(REPO, "古籍")
DATA = os.path.join(EVAL_DIR, "data")
os.makedirs(DATA, exist_ok=True)

BOOKS = {
    "zipingzhenquan": {"dir": os.path.join(GUJI, "子平", "子平真诠"), "name": "子平真诠"},
    "ditianshui":     {"dir": os.path.join(GUJI, "子平", "滴天髓"),   "name": "滴天髓"},
    "qiongtongbaojian": {"dir": os.path.join(GUJI, "子平", "穷通宝鉴"), "name": "穷通宝鉴"},
}

AUTH = os.path.expanduser("~/.pi/agent/auth.json")
EMB_MODEL = "BAAI/bge-m3"
EMB_DIM = 1024
CHAT_MODEL = "Qwen/Qwen3-8B"          # 免费通道；批量生成用（关思考）
GEN_MODEL = "deepseek-ai/DeepSeek-V3.2"  # 测试集生成用（质量优先）
NO_THINK = {"enable_thinking": False}    # 关思考：默认思考态会超时（实测 5min→1s）
PROVIDERS = {
    "siliconflow": "https://api.siliconflow.cn/v1",
    "deepseek": "https://api.deepseek.com/v1",      # 直连 DeepSeek（独立余额）
}
DS_MODEL = "deepseek-chat"
BASE_URL = "https://api.siliconflow.cn/v1"


def _key(provider: str = "siliconflow") -> str:
    env = os.environ.get(f"{provider.upper()}_API_KEY")
    if env:
        return env
    with open(AUTH, encoding="utf-8") as f:
        return json.load(f)[provider]["key"]


def _post(path: str, payload: dict, timeout: int = 180, retries: int = 6, provider: str = "siliconflow") -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for i in range(retries):
        req = urllib.request.Request(
            f"{PROVIDERS[provider]}{path}", data=body,
            headers={"Authorization": f"Bearer {_key(provider)}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}"
            if e.code == 429:
                time.sleep(min(5 * (i + 1) ** 2, 60))   # TPM 限流：阶梯退避
                continue
            if e.code in (500, 502, 503):
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(last)
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"post {path} failed: {last}")


# ---------- 聊天 / 嵌入 ----------
def chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000,
         model: str | None = None, extra: dict | None = None, provider: str = "siliconflow") -> str:
    payload = {
        "model": model or CHAT_MODEL, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens,
    }
    if extra:
        payload.update(extra)
    r = _post("/chat/completions", payload, provider=provider)
    return r["choices"][0]["message"]["content"]


def embed(texts: list[str], cache_path: str | None = None) -> list[list[float]]:
    """批量嵌入（带磁盘缓存）。返回与 texts 等长的向量列表。"""
    cache_path = cache_path or os.path.join(DATA, "emb_cache.jsonl")
    cache: dict[str, list[float]] = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                cache[o["k"]] = o["v"]

    keys = [hashlib.sha1(f"{EMB_MODEL}|{t}".encode("utf-8")).hexdigest() for t in texts]
    todo = sorted({k for k, t in zip(keys, texts) if k not in cache})
    if todo:
        k2t = {k: t for k, t in zip(keys, texts)}
        B = 24
        for i in range(0, len(todo), B):
            batch = todo[i:i + B]
            r = _post("/embeddings", {"model": EMB_MODEL, "input": [k2t[k] for k in batch]})
            for k, d in zip(batch, r["data"]):
                cache[k] = d["embedding"]
            print(f"  embedded {min(i+B, len(todo))}/{len(todo)}", flush=True)
        with open(cache_path, "a", encoding="utf-8") as f:
            for k in todo:
                f.write(json.dumps({"k": k, "v": cache[k]}, ensure_ascii=False) + "\n")
    return [cache[k] for k in keys]


# ---------- IO ----------
def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_jsonl(path: str) -> list[dict]:
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def append_jsonl(path: str, obj) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
