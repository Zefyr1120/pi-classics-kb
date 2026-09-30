# -*- coding: utf-8 -*-
"""抓取清洗用源：国学3000 三命通会全书 + 走进国学网 五行精纪(四库本) txt。

用法（需联网提权）：
  python 古籍/tools/fetch_clean_sources.py

输出：
  1) 古籍/子平/三命通会-国学3000-全书.md   —— 按章落盘（## 标题），供本地拆卷清洗
  2) %TEMP%/五行精纪-skqs.txt              —— 四库本 txt（UTF-8），供本地校验补卷
"""

import os
import re
import sys
import tempfile
import urllib.request

BASE = "https://guoxue3000.com/books/330"
OUT_SANMING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "子平", "三命通会-国学3000-全书.md")
OUT_WXJJ = os.path.join(tempfile.gettempdir(), "五行精纪-skqs.txt")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    ct = r.headers.get("Content-Type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    encs = ([m.group(1)] if m else []) + ["utf-8", "gb18030"]
    last = None
    for enc in encs:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError) as e:
            last = e
    raise last


def fetch_sanming():
    html = fetch(BASE)
    links = []
    for mm in re.finditer(r'href="(/books/330/chapters/(\d+))"[^>]*>([^<]+)<', html):
        links.append((int(mm.group(2)), mm.group(3).strip()))
    seen = set()
    uniq = []
    for num, name in links:
        if num not in seen and name and not re.search(r"上一章|下一章|目录|图片", name):
            seen.add(num)
            uniq.append((num, name))
    uniq.sort()
    print(f"三命通会章节数: {len(uniq)}")
    parts = []
    vol_h2 = 0
    for num, name in uniq:
        body = fetch(f"{BASE}/chapters/{num}")
        mh = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S)
        title = re.sub(r"<[^>]+>", "", mh.group(1)).strip() if mh else name
        if re.match(r"^卷[一二三四五六七八九十]+$", title):
            vol_h2 += 1
        paras = re.findall(r'<p class="indented">(.*?)</p>', body, re.S)
        texts = []
        for p in paras:
            txt = re.sub(r"<br\s*/?>", "\n", p)
            txt = re.sub(r"<[^>]+>", "", txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                texts.append(txt)
        parts.append(f"## {title}\n\n" + "\n\n".join(texts))
        print(f"  ch {num}: {title} 段数={len(texts)}")
    out = "\n\n".join(parts)
    out_path = os.path.normpath(OUT_SANMING)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"三命通会落盘: {out_path} 字符={len(out)} 卷标记数={vol_h2}")


def fetch_wxjj():
    url = ("http://zoujinguoxue.com/data/skqs/"
           "%E5%AD%90%E9%83%A8/12%E6%9C%AF%E6%95%B0-146%E9%83%A8/"
           "%E4%BA%94%E8%A1%8C%E7%B2%BE%E7%BA%AA-%E5%AE%8B-%E5%BB%96%E4%B8%AD.txt")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    text = raw.decode("utf-8-sig", errors="replace")
    with open(OUT_WXJJ, "w", encoding="utf-8") as f:
        f.write(text)
    marks = ["卷二十", "第二十卷", "第廿卷", "卷三十", "第三十卷", "第卅卷", "卷三十五", "第三十五卷", "第卅五卷"]
    print(f"五行精纪 skqs 落盘: {OUT_WXJJ} 字符={len(text)}")
    for mk in marks:
        print(f"  contains {mk}: {mk in text}")
    for pat in [r"第[二三四五]?十[一二三四五]?卷", r"第廿[一二三四五]?卷", r"第卅[一二三四五]?卷", r"第三[一二三四五]?十卷"]:
        found = sorted(set(re.findall(pat, text)))
        print(f"  卷标记 {pat}: {found}")


if __name__ == "__main__":
    fetch_sanming()
    fetch_wxjj()
