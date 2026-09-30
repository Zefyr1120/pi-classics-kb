# -*- coding: utf-8 -*-
"""抓中华文库四库本三命通会卷七，抽出子平说辩/论贫贱凶恶/论寿夭三篇到临时文件。"""

import html as html_mod
import http.client
import os
import re
import tempfile
import urllib.parse
import urllib.request

URL = "https://www.zhonghuashu.com/wiki/" + urllib.parse.quote("三命通會_(四庫全書本)/卷07")


def fetch(url: str) -> str:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
            for enc in ("utf-8", "gb18030"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except http.client.IncompleteRead as e:
            # 站点稳定截断在约 98KB，所需三篇均在前半段，用已读部分即可
            raw = e.partial
            print(f"  第{attempt + 1}次: 截断，使用 partial {len(raw)} 字节")
            for enc in ("utf-8", "gb18030"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  第{attempt + 1}次失败: {e}")
    raise last


def to_text(html: str) -> str:
    html = re.sub(r"(?s)<script.*?</script>", "", html)
    html = re.sub(r"(?s)<style.*?</style>", "", html)
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"</p>|</div>|</h[1-6]>", "\n", html)
    html = re.sub(r"<[^>]+>", "", html)
    return html_mod.unescape(html)


raw = fetch(URL)
text = to_text(raw)
print("页面文本长度:", len(text))

marks = ["子平说辩", "子平説辩", "论贫贱凶恶", "论寿夭", "论女命", "论性情相貌", "论疾病先知五脏六腑所属干支"]
for m in marks:
    print(f"  含[{m}]: {m in text} @ {text.find(m)}")

start = text.find("子平说辩")
if start < 0:
    start = text.find("子平説辩")
end = text.find("论女命")
if start < 0 or end < 0 or end <= start:
    raise SystemExit("未找到节边界")

segment = text[start:end]
seg1 = segment[: segment.find("论性情相貌")]
seg2_start = segment.find("论贫贱凶恶")
seg2_end = segment.find("论寿夭")
seg3_start = seg2_end
seg3_end = len(segment)

out = {
    "子平说辩": seg1.strip(),
    "论贫贱凶恶": segment[seg2_start:seg2_end].strip(),
    "论寿夭": segment[seg3_start:seg3_end].strip(),
}
out_path = os.path.join(tempfile.gettempdir(), "sanming_juan7_supp.json")
with open(out_path, "w", encoding="utf-8") as f:
    import json
    json.dump(out, f, ensure_ascii=False, indent=2)
for k, v in out.items():
    print(f"{k}: {len(v)} 字符 | 头: {v[:40]!r} | 尾: {v[-40:]!r}")
print("落盘:", out_path)
