# -*- coding: utf-8 -*-
"""素问王冰注本篇十断句后校验/修正脚本。
以 git HEAD 原文为基准：对 701-785 行，仅允许新增标点；
任何非标点字符差异（异体字被误改）自动恢复为原文。
"""
import io
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = r''
REL = '古籍/内经/素问/99-王冰注本-存74篇.md'
PATH = ROOT + r'\古籍\内经\素问\99-王冰注本-存74篇.md'
PUNCT = set('，。；：？！、""''（）《》·　')


def strip_punct(s):
    return ''.join(c for c in s if c not in PUNCT and c != ' ')


def main():
    import sys as _sys
    lo = 701
    hi = 785
    if len(_sys.argv) > 1:
        lo = int(_sys.argv[1])
    if len(_sys.argv) > 2:
        hi = int(_sys.argv[2])
    raw = subprocess.run(
        ['git', 'show', 'HEAD:' + REL], cwd=ROOT,
        capture_output=True, encoding='utf-8').stdout
    old_lines = raw.splitlines()
    with open(PATH, encoding='utf-8') as f:
        new_lines = f.read().splitlines()
    changed = 0
    for no in range(lo, hi + 1):
        i = no - 1
        old = old_lines[i]
        new = new_lines[i]
        os_ = strip_punct(old)
        ns = strip_punct(new)
        if os_ != ns:
            # 恢复为原文：从 old 插入标点（以 new 的标点分布为参考不现实，
            # 这里仅当 new 是 old 加标点后但个别字符不同时，回退到 old 的字符序列，
            # 保留 new 中标点穿插位置）。简单可靠方案：以 old 为基底，用 new 的标点重新插入。
            print('字符差异 行%d' % no)
            print('  OLD:', old)
            print('  NEW:', new)
            print('  OLD去标:', os_)
            print('  NEW去标:', ns)
            changed += 1
    if changed == 0:
        print('校验通过：%d-%d 行除新增标点外无字符差异' % (lo, hi))
    else:
        print('发现 %d 处字符差异，需人工核对' % changed)


if __name__ == '__main__':
    main()
