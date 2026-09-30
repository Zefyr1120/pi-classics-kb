# -*- coding: utf-8 -*-
"""穷通宝鉴 条目级再切分 v3（一次性脚本，用后即删）
规则：
1) 标题正则：论X / 三季X总论 / 三季X / N月X（允许标题后紧接正文，如"四月甲木退气"）
2) "三季X总论"后跟以"三季X"开头的段落 → 并入总论条目
3) 同标题重复段落 → 并入当前条目
4) 空的"三季X"分组标题 → 并入下一条目；空的"论X" → 独立成文件
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'古籍\子平'
OUT = os.path.join(BASE, '穷通宝鉴')
src = open(os.path.join(BASE, '穷通宝鉴-全文.md'), encoding='utf-8').read().split('\n')
i = 0
while i < len(src) and (src[i].startswith('>') or not src[i].strip()):
    i += 1
content = src[i:]

GAN = '[甲乙丙丁戊己庚辛壬癸]'
ELEM = '[木火土金水]'
TITLE = re.compile(
    r'^(论(?:[木火土金水]|[戊己][土]|[辛壬癸][金水]|[丙丁][火])'
    + r'|三[春夏秋冬]' + GAN + ELEM + r'总论'
    + r'|三[春夏秋冬]' + GAN + ELEM
    + r'|[正一二三四五六七八九十]{1,2}月' + GAN + ELEM + r')')

SECTIONS = [('02-甲木', '论木'), ('03-乙木', '三春乙木总论'), ('04-丙火', '论丙火'), ('05-丁火', '论丁火'),
            ('06-戊土', '论土'), ('07-己土', '论己土'), ('08-庚金', '论金'), ('09-辛金', '论辛金'),
            ('10-壬水', '论水'), ('11-癸水', '论癸水')]

MONTH = {'正月': '寅', '二月': '卯', '三月': '辰', '四月': '巳', '五月': '午', '六月': '未', '七月': '申',
         '八月': '酉', '九月': '戌', '十月': '亥', '十一月': '子', '十二月': '丑',
         '正二月': '寅卯', '五六月': '午未', '八九月': '酉戌'}


def coverage(t):
    m = re.match(r'^([正一二三四五六七八九十]{1,2}月)', t)
    if m and m.group(1) in MONTH:
        return MONTH[m.group(1)]
    m = re.match(r'^三([春夏秋冬])', t)
    if m:
        return {'春': '寅卯辰', '夏': '巳午未', '秋': '申酉戌', '冬': '亥子丑'}[m.group(1)]
    return '总纲'


def find_line(text):
    for k in range(len(content)):
        if content[k].strip() == text:
            return k
    return -1


idxs = [find_line(t) for _, t in SECTIONS]
assert all(x >= 0 for x in idxs), [(SECTIONS[k], idxs[k]) for k in range(len(idxs)) if idxs[k] < 0]
ranges = [(SECTIONS[n][0], idxs[n], idxs[n + 1] if n + 1 < len(idxs) else len(content))
          for n in range(len(SECTIONS))]

SEASON_GROUP = re.compile(r'^三[春夏秋冬]' + GAN + ELEM + r'$')


def parse_entries(lines):
    entries, cur = [], None
    for l in lines:
        s = l.rstrip()
        st = s.strip()
        m = TITLE.match(st) if st else None
        if m:
            t = m.group(1)
            if cur is not None and (cur[0] == t or cur[0] == t + '总论'):
                cur[1].append(s)
            else:
                cur = [t, [s]]
                entries.append(cur)
        elif cur is not None:
            cur[1].append(s)
    out = []
    for k, (t, ls) in enumerate(entries):
        body = [x for x in ls[1:] if x.strip()]
        if not body and SEASON_GROUP.match(t) and k + 1 < len(entries):
            entries[k + 1][1] = [ls[0], ''] + entries[k + 1][1]
        else:
            out.append((t, ls))
    return out


log = []
grand = 0
for name, start, end in ranges:
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    ents = parse_entries(content[start:end])
    used = {}
    rows = []
    for k, (t, ls) in enumerate(ents, 1):
        used[t] = used.get(t, 0) + 1
        safe = re.sub(r'[\\/:*?"<>|]', '_', t if used[t] == 1 else f'{t}-{used[t]}')
        fn = f'{k:02d}-{safe}.md'
        cov = coverage(t)
        hdr = (f'# {t}\n\n> 书名：穷通宝鉴｜底本：古籍/子平/穷通宝鉴-全文.md\n'
               f'> 父索引：../AGENTS.md（{name.split("-", 1)[1]}·条目索引）\n'
               f'> 条目：{k:02d}/{len(ents)}｜覆盖月令：{cov}\n> 拆分：2026-09-15（条目级）\n\n')
        open(os.path.join(d, fn), 'w', encoding='utf-8').write(hdr + '\n'.join(ls).strip() + '\n')
        rows.append((f'{k:02d}', t, cov, fn))
    grand += len(ents)
    tbl = '\n'.join(f'| {a} | {b} | {c} | `{d}` |' for a, b, c, d in rows)
    gname = name.split('-', 1)[1]
    idx = (f'# AGENTS.md — 穷通宝鉴·{gname}（条目索引）\n\n'
           f'> 本目录是《穷通宝鉴》{gname}篇的**条目拆分**：一条原文（及所附命例）一个文件。\n'
           f'> 父导航：`../AGENTS.md`｜底本：`古籍/子平/穷通宝鉴-全文.md`｜拆分：2026-09-15（条目级）。\n'
           f'> 检索入口：**月令 → 条目文件**（见下表「覆盖月令」）；条目注解见各条目文件。\n\n'
           f'## 条目清单\n\n| # | 条目 | 覆盖月令 | 文件 |\n|---|---|---|---|\n{tbl}\n')
    open(os.path.join(d, 'AGENTS.md'), 'w', encoding='utf-8').write(idx)
    log.append(f'{name}: {len(ents)} 条目 → ' + '、'.join(t for _, t, _, _ in rows))

print(f'=== 切分完成：共 {grand} 条目 ===')
for l in log:
    print(' ', l)
