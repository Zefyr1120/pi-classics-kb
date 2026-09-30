# -*- coding: utf-8 -*-
"""抓取三命通会国学3000版的12个卷首页，输出卷号->章节号映射。"""

import json
import re
import urllib.request

VOL_NUMS = [1, 15, 42, 66, 75, 95, 169, 192, 253, 314, 357, 379]
BASE = "https://guoxue3000.com/books/330/chapters"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


out = {}
for n in VOL_NUMS:
    body = fetch(f"{BASE}/{n}")
    mh = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S)
    title = re.sub(r"<[^>]+>", "", mh.group(1)).strip() if mh else "(none)"
    paras = len(re.findall(r'<p class="indented">(.*?)</p>', body, re.S))
    out[str(n)] = {"h2": title, "paras": paras}
    print(f"ch {n}: h2={title} 段数={paras}")
with open("古籍/tools/sanming_vols.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
