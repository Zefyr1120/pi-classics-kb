# -*- coding: utf-8 -*-
"""古籍库统一繁→简转换。
- 范围：古籍/**/*.md（含底本/全本/分章/索引/README）。
- 工具：OpenCC t2s（opencc-python-reimplemented）。
- 保护：易学/命理语境中的"乾"（乾下乾上、乾宫、乾为天、乾位、乾方、乾象、乾金、乾阳、
  乾元、乾道、乾卦、乾坤、乾造、乾隆、乾乾、乾健 等）不得转为"干"；"乾燥/干旱"等仍正常转。
- 输出：UTF-8 无 BOM。
"""
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from opencc import OpenCC

ROOT = r'古籍'

# 乾 保护模式：后随易学/命理高频搭配字时保持"乾"
PROTECT_QIAN = re.compile(r'乾(?=[下上宫为位方象金阳元道卦坤造隆乾健龙清])')
SENT_A = '\ue000'
SENT_B = '\ue001'

def protect(text):
    holder = {}
    def rep(m):
        idx = len(holder)
        holder[idx] = m.group(0)
        return SENT_A + str(idx) + SENT_B
    return PROTECT_QIAN.sub(rep, text), holder

def restore(text, holder):
    for idx, orig in holder.items():
        text = text.replace(SENT_A + str(idx) + SENT_B, orig)
    return text

def main():
    cc = OpenCC('t2s')
    files = []
    for dirpath, _, names in os.walk(ROOT):
        for n in names:
            if n.endswith('.md'):
                files.append(os.path.join(dirpath, n))
    files.sort()
    total_changed = 0
    for f in files:
        with open(f, encoding='utf-8-sig') as fh:
            text = fh.read()
        protected, holder = protect(text)
        converted = cc.convert(protected)
        converted = restore(converted, holder)
        if converted != text:
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(converted)
            total_changed += 1
    print('已转换文件数:', total_changed, '/', len(files))

if __name__ == '__main__':
    main()
