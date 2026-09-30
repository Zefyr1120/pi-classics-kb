# -*- coding: utf-8 -*-
"""方案 B 第二步：干目录去掉 论X 条目并重编号；更新各索引/书导航/规范/README"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BOOK = r'古籍\子平\穷通宝鉴'

AFFECTED = {'02-甲木': '论木', '06-戊土': '论土', '08-庚金': '论金', '10-壬水': '论水'}
NEWCOUNT = {}

# ---- 1. 删除旧 论X 条目文件并重编号 ----
for d, zl in AFFECTED.items():
    dirpath = os.path.join(BOOK, d)
    files = sorted(f for f in os.listdir(dirpath) if f.endswith('.md') and f != 'AGENTS.md')
    old = [f for f in files if f.endswith(zl + '.md')]
    assert len(old) == 1, (d, old)
    os.remove(os.path.join(dirpath, old[0]))
    files.remove(old[0])
    NEWCOUNT[d] = len(files)
    for i, fn in enumerate(files, 1):
        m = re.match(r'(\d+)-(.+)\.md$', fn)
        new_fn = f'{i:02d}-{m.group(2)}.md'
        p_old = os.path.join(dirpath, fn)
        p_new = os.path.join(dirpath, new_fn)
        if new_fn != fn:
            os.rename(p_old, p_new)
        t = open(p_new, encoding='utf-8').read()
        t = re.sub(r'> 条目：\d+/\d+', f'> 条目：{i:02d}/{len(files)}', t)
        open(p_new, 'w', encoding='utf-8').write(t)
    print(f'{d}: 删除 01-{zl}.md，重编号 {len(files)} 个条目')

# ---- 2. 甲木索引：删论木行、文件名偏移、共用说明、计数 ----
p = os.path.join(BOOK, '02-甲木', 'AGENTS.md')
t = open(p, encoding='utf-8').read()
t = '\n'.join(l for l in t.split('\n') if '01-论木.md' not in l)
t = re.sub(r'> 共用说明：「论木」为\*\*甲乙共用\*\*的材质总论（乙木索引互链）。',
           '> 共用说明：「论木」已拆分为独立总论目录 → `../00-总论/论木/AGENTS.md`（甲乙共用）。', t)
t = re.sub(r'`(\d{2})-', lambda m: '`%02d-' % (int(m.group(1)) - 1) if int(m.group(1)) >= 2 else m.group(0), t)
t = t.replace('> 共 15 条目（含总论 3）', '> 共 14 条目（含季节总论 2）。「论木」见 ../00-总论/论木/。')
open(p, 'w', encoding='utf-8').write(t)
print('02-甲木/AGENTS.md 已更新')

# ---- 3. 戊土/庚金/壬水索引：重生成（条目清单 + 共用说明） ----
for d, zl in [('06-戊土', '论土'), ('08-庚金', '论金'), ('10-壬水', '论水')]:
    dirpath = os.path.join(BOOK, d)
    files = sorted(f for f in os.listdir(dirpath) if f.endswith('.md') and f != 'AGENTS.md')
    rows = []
    for i, fn in enumerate(files, 1):
        m = re.match(r'(\d+)-(.+)\.md$', fn)
        name = m.group(2)
        mm = re.match(r'^([正一二三四五六七八九十]{1,2}月)', name)
        cov = {'正月': '寅', '二月': '卯', '三月': '辰', '四月': '巳', '五月': '午', '六月': '未',
               '七月': '申', '八月': '酉', '九月': '戌', '十月': '亥', '十一月': '子', '十二月': '丑',
               '正二月': '寅卯', '五六月': '午未', '八九月': '酉戌'}.get(mm.group(1), '总纲') if mm else '总纲'
        if name.startswith('三春'):
            cov = '寅卯辰'
        if name.startswith('三夏'):
            cov = '巳午未'
        if name.startswith('三秋'):
            cov = '申酉戌'
        if name.startswith('三冬'):
            cov = '亥子丑'
        rows.append(f'| {i:02d} | {name} | {cov} | `{fn}` |')
    gname = d.split('-', 1)[1]
    idx = (f'# AGENTS.md — 穷通宝鉴·{gname}（条目索引）\n\n'
           f'> 本目录是《穷通宝鉴》{gname}篇的**条目拆分**：一条原文（及所附命例）一个文件。\n'
           f'> 父导航：`../AGENTS.md`｜底本：`古籍/子平/穷通宝鉴-全文.md`｜拆分：2026-09-15（条目级）。\n'
           f'> 共用说明：「{zl}」已拆分为独立总论目录 → `../00-总论/{zl}/AGENTS.md`。\n'
           f'> 检索入口：**月令 → 条目文件**（见下表「覆盖月令」）。\n\n'
           f'## 条目清单\n\n| # | 条目 | 覆盖月令 | 文件 |\n|---|---|---|---|\n' + '\n'.join(rows) + '\n')
    open(os.path.join(dirpath, 'AGENTS.md'), 'w', encoding='utf-8').write(idx)
    print(f'{d}/AGENTS.md 已重生成（{len(files)} 条目）')

# ---- 4. 使用方索引：共用总论路径更新 ----
for f, zl in [('03-乙木', '论木'), ('07-己土', '论土'), ('09-辛金', '论金'), ('11-癸水', '论水')]:
    p = os.path.join(BOOK, f, 'AGENTS.md')
    t = open(p, encoding='utf-8').read()
    t = re.sub(r'`\.\./\d{2}-[^`]+/01-' + zl + r'\.md`', f'`../00-总论/{zl}/AGENTS.md`', t)
    open(p, 'w', encoding='utf-8').write(t)
    print(f'{f}/AGENTS.md 共用总论路径已更新')

# ---- 5. 书级 AGENTS.md ----
p = os.path.join(BOOK, 'AGENTS.md')
t = open(p, encoding='utf-8').read()
t = t.replace('> **共享总论**：「论木／论土／论金／论水」为跨干共用（甲乙／戊己／庚辛／壬癸），存放于各五行首干目录：`02-甲木/01-论木.md`、`06-戊土/01-论土.md`、`08-庚金/01-论金.md`、`10-壬水/01-论水.md`。',
              '> **共享总论**：「论木／论土／论金／论水」为跨干共用（甲乙／戊己／庚辛／壬癸），已独立为 `00-总论/`（分节结构：总纲＋四季，索引见 `00-总论/AGENTS.md`）。')
t = t.replace('| 01 | 卷首（五行总论） | 1 | `01-卷首（五行总论）.md` |',
              '| 00 | 总论（共享） | 论木／论土／论金／论水 | `00-总论/AGENTS.md` |\n| 01 | 卷首（五行总论） | 1 | `01-卷首（五行总论）.md` |')
t = t.replace('| 02 | 甲木 | 15 |', '| 02 | 甲木 | 14 |').replace('| 06 | 戊土 | 12 |', '| 06 | 戊土 | 11 |')
t = t.replace('| 08 | 庚金 | 13 |', '| 08 | 庚金 | 12 |').replace('| 10 | 壬水 | 14 |', '| 10 | 壬水 | 13 |')
open(p, 'w', encoding='utf-8').write(t)
print('书级 AGENTS.md 已更新')
