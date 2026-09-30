# -*- coding: utf-8 -*-
"""验证：全文 vs 穷通宝鉴新结构（含 00-总论 分节；注解层跳过；另采源条目单列校验）
用法：python verify_qiongtong_entries.py

两类校验（2026-09-15 加第 2 类）：
1) **底本序列比对**：`穷通宝鉴-全文.md` 非空行序列 == 各条目文件正文非空行序列
   - 注解层跳过：`## 原文` 之后为正文（标题行本身不计）；`## 章旨`／`## 疏解`／`## 另采源…` 等小节不计；无 `## 原文` 的旧文件仍按“首个 `## ` 之前”处理。
   - **另采源条目整条排除**：文件头（首个 `#` 之前的 `>` 行）含「另采源」者，正文不在底本内
     （现有 1 个：`03-乙木/15-十二月乙木.md`），单列第 2 类校验。
2) **另采源一致性**：另采源条目（文件头标明「另采源条目」）的正文、以及底本条目内 `## 另采源…` 小节的内容，
   逐行（空白归一化后）须出现在对照本原文层中——防手工转录走样。
   对照本：`_对照-徐乐吾评注本-问真版/*.md`（只取 `## 原文` 至 `## 徐乐吾注` 之间）。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'古籍\子平'
BOOK = os.path.join(BASE, '穷通宝鉴')
FULL = os.path.join(BASE, '穷通宝鉴-全文.md')
REF = os.path.join(BASE, '_对照-徐乐吾评注本-问真版')

ALT_MARK = '另采源'
ALT_ENTRY_MARK = '另采源条目'   # 文件头声明：整条为另采源（正文不在底本内）→ 只有此类整条排除

# ---------- 底本全文 ----------
full = open(FULL, encoding='utf-8').read().split('\n')
i = 0
while i < len(full) and (full[i].startswith('>') or not full[i].strip()):
    i += 1
exp = [l.strip() for l in full[i:] if l.strip()]


def dir_files(rel):
    d = os.path.join(BOOK, rel)
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.md') and f != 'AGENTS.md']


paths = [os.path.join(BOOK, '01-卷首（五行总论）.md')]
paths += dir_files(os.path.join('00-总论', '论木'))
paths += dir_files('02-甲木')
paths += dir_files('03-乙木') + dir_files('04-丙火') + dir_files('05-丁火')
paths += dir_files(os.path.join('00-总论', '论土'))
paths += dir_files('06-戊土') + dir_files('07-己土')
paths += dir_files(os.path.join('00-总论', '论金'))
paths += dir_files('08-庚金') + dir_files('09-辛金')
paths += dir_files(os.path.join('00-总论', '论水'))
paths += dir_files('10-壬水') + dir_files('11-癸水')


def split_file(path):
    """→ (header_lines, body_lines, alt_sections)
    body_lines：`## 原文` 之后、注解小节之前的正文（无 `## 原文` 的旧文件＝首个 `## ` 之前）；
    alt_sections：`## 另采源…` 小节的正文行。"""
    header, body, alts = [], [], []
    state = 'h1'
    for raw in open(path, encoding='utf-8').read().split('\n'):
        s = raw.rstrip()
        if s.startswith('## '):
            if s.strip() == '## 原文':      # 2026-09-15 起：正文由 `## 原文` 标题引导
                state = 'body'
            else:                            # 注解／另采源小节
                state = 'alt' if ALT_MARK in s else 'ann'
            continue
        if s.startswith('#'):            # 文件标题
            state = 'header'
            continue
        if not s.strip():
            continue
        if s.startswith('>'):            # 头注与块引用不参与正文比对
            if state in ('h1', 'header'):
                header.append(s)
            continue
        if state in ('h1', 'header'):
            state = 'body'
        if state == 'body':
            body.append(s.strip())
        elif state == 'alt':
            alts.append(s.strip())
    return header, body, alts


# ---------- 1) 底本序列比对 ----------
act, excluded = [], []
for p in paths:
    header, body, alts = split_file(p)
    if any(ALT_ENTRY_MARK in h for h in header):
        excluded.append((p, body, alts))
        continue
    act.extend(body)

print('全文非空行: %d ｜新结构（原文部分）非空行: %d' % (len(exp), len(act)))
if excluded:
    print('已排除另采源条目（不在底本内）:')
    for p, body, _ in excluded:
        print('  - %s（%d 行）' % (os.path.relpath(p, BOOK), len(body)))

bad = 0
for k in range(max(len(exp), len(act))):
    e = exp[k] if k < len(exp) else '<EOF>'
    a = act[k] if k < len(act) else '<EOF>'
    if e != a:
        print('@%d 全文: %s' % (k + 1, e[:70]))
        print('     文件: %s' % a[:70])
        bad += 1
        if bad >= 8:
            break
print('✅ 底本序列完全一致（无丢失/重复/错位）' if bad == 0 else '⚠️ 底本序列有差异')

# ---------- 2) 另采源一致性 ----------
ref = []
for f in sorted(os.listdir(REF)):
    if not f.endswith('.md') or f == 'README.md':
        continue
    txt = open(os.path.join(REF, f), encoding='utf-8').read()
    m = re.search(r'##\s*原文(.*?)(?:##\s*徐乐吾注|$)', txt, re.S)
    if m:
        ref.append(m.group(1))
refnorm = re.sub(r'\s+', '', '\n'.join(ref))

targets = [(p, body + alts) for p, body, alts in excluded]
excl_paths = set(p for p, _, _ in excluded)
for p in paths:
    if p in excl_paths:
        continue
    header, _, alts = split_file(p)
    if alts:
        targets.append((p, alts))

miss = 0
for p, lines in targets:
    local = 0
    for l in lines:
        if re.sub(r'\s+', '', l) not in refnorm:
            print('⚠️ 另采源比对失败 %s: %s' % (os.path.relpath(p, BOOK), l[:70]))
            local += 1
            miss += 1
            if local >= 5:
                break
print('✅ 另采源行均在对照本原文层中命中（%d 文件 / %d 行）'
      % (len(targets), sum(len(l) for _, l in targets))
      if miss == 0 else '⚠️ 另采源比对有 %d 行未命中' % miss)
