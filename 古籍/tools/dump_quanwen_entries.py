# -*- coding: utf-8 -*-
"""临时：打印指定干目录下全部条目文件（含分隔）"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BOOK = r'古籍\子平\穷通宝鉴'
for gname in sys.argv[1:]:
    d = os.path.join(BOOK, gname)
    print(f'################ {gname} ################')
    for f in sorted(os.listdir(d)):
        if not f.endswith('.md') or f == 'AGENTS.md':
            continue
        print(f'===== {d} -> {f} =====')
        print(open(os.path.join(d, f), encoding='utf-8').read())
