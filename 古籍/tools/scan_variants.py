# -*- coding: utf-8 -*-
"""扫描文本中的非常见字（异体/生僻），用于构建素问注文繁简转换映射。"""
import os
import io
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TMP = os.path.join(os.environ['TEMP'], 'suwen_buyi')
OUT = os.path.join(TMP, 'variant_report.txt')

def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()

raw = ''
for j in ('juan23', 'juan24'):
    raw += read(os.path.join(TMP, j + '.txt'))

cnt = collections.Counter(ch for ch in raw if ord(ch) > 0x2E80)
lines = ['total unique chars: %d' % len(cnt), '']
for ch, n in cnt.most_common():
    lines.append('%s U+%04X x%d' % (ch, ord(ch), n))
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('report ->', OUT, ' unique=', len(cnt))
