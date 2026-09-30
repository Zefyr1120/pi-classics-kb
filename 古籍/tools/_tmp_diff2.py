# -*- coding: utf-8 -*-
"""穷通宝鉴 对照本(问真徐乐吾评注本·原文层) vs 主库(殆知阁底本) 差异清单 v2。
按「干」做句级校勘（两版切分不同，逐条配对无意义）。
输出：古籍/子平/_对照-徐乐吾评注本-问真版/_差异清单.md
"""
import io, os, re, sys, difflib, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MAIN = os.path.join(ROOT, '古籍', '子平', '穷通宝鉴')
CTRL = os.path.join(ROOT, '古籍', '子平', '_对照-徐乐吾评注本-问真版')
OUT = os.path.join(CTRL, '_差异清单.md')
GAN = {'02-甲木': '甲木', '03-乙木': '乙木', '04-丙火': '丙火', '05-丁火': '丁火', '06-戊土': '戊土',
       '07-己土': '己土', '08-庚金': '庚金', '09-辛金': '辛金', '10-壬水': '壬水', '11-癸水': '癸水'}

def section(text, name):
    m = re.search(r'^## %s\s*$(.*?)(?=^## |\Z)' % name, text, re.M | re.S)
    return m.group(1) if m else ''

def norm(s):
    return re.sub(r'[^\u4e00-\u9fff0-9]', '', s)

def sents(s):
    out = []
    for p in re.split(r'(?<=[。！？；])|\n', s):
        n = norm(p)
        if len(n) >= 4:
            out.append(n)
    return out

def pillars(s):
    out = []
    for line in s.split('\n'):
        toks = re.findall(r'[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]', line)
        if len(toks) >= 4:
            out.append(tuple(toks[:4]))
    return out

ctrl_ch = collections.defaultdict(list)
for f in sorted(os.listdir(CTRL)):
    if not f.endswith('.md') or f.startswith('README') or f.startswith('_'):
        continue
    parts = f.split('_')
    gan = parts[2] if len(parts) >= 3 else '卷首'
    ctrl_ch[gan].append((f, section(open(os.path.join(CTRL, f), encoding='utf-8').read(), '原文')))

res = []
for d in sorted(GAN):
    gan = GAN[d]
    entries = sorted(f for f in os.listdir(os.path.join(MAIN, d)) if f.endswith('.md') and f != 'AGENTS.md')
    mtext = [section(open(os.path.join(MAIN, d, f), encoding='utf-8').read(), '原文') for f in entries]
    m_all, c_all = '\n'.join(mtext), '\n'.join(t for _, t in ctrl_ch.get(gan, []))
    ms, cs = sents(m_all), sents(c_all)
    mset, cset = set(ms), set(cs)
    same = mset & cset
    only_m = [s for s in dict.fromkeys(ms) if s not in cset]
    only_c = [s for s in dict.fromkeys(cs) if s not in mset]
    pairs, used_c = [], set()
    for a in only_m:
        best, br = None, 0.0
        for b in only_c:
            if b in used_c:
                continue
            r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            if r > br:
                best, br = b, r
        if best and br >= 0.7:
            pairs.append((br, a, best)); used_c.add(best)
    only_c2 = [s for s in only_c if s not in used_c]
    only_m2 = [s for s in only_m if s not in {p[1] for p in pairs}]
    mcase, ccase = collections.Counter(), collections.Counter()
    for t in mtext:
        mcase.update(pillars(t))
    for _, t in ctrl_ch.get(gan, []):
        ccase.update(pillars(t))
    res.append({'gan': gan, 'dir': d, 'n_entry': len(entries), 'n_ch': len(ctrl_ch.get(gan, [])),
                'mchar': len(norm(m_all)), 'cchar': len(norm(c_all)),
                'same': len(same), 'only_m': only_m2, 'only_c': only_c2, 'pairs': sorted(pairs, reverse=True),
                'mcase': mcase, 'ccase': ccase,
                'case_same': sum((mcase & ccase).values()), 'case_m': sum(mcase.values()), 'case_c': sum(ccase.values())})

S = lambda k: sum(r[k] for r in res)
SL = lambda k: sum(len(r[k]) for r in res)
L = []
A = L.append
A('# 差异清单：对照本（问真徐乐吾评注本·原文层） vs 主库（殆知阁底本）\n')
A('> 生成日期：2026-09-15｜方法：按「干」做句级校勘（脚本自动比对，人工复核待补）')
A('> **用途**：作为统一校订依据；**只作对照，不改动主库原文**（主库底本仍为殆知阁电子本）。')
A('> **纪律**：对照本只取「## 原文」层；其「## 徐乐吾注」属注家层，**禁止引用**、不得与底本混引。\n')
A('## 一、方法（为什么按「干」比对）\n')
A('两版**章节切分不同**：对照本把多段合为一章（如「正月甲木」一章内含主库的 `正月甲木` ＋ `正二月甲木` ＋ `三春甲木总论` 等条），合章方式亦不同（甲木五-六月、丁火八、九月…）。**逐条配对必然失真**，故改为：')
A('1. 同一「干」内，把两侧全部原文按句切分、归一化（去空白与标点，仅留汉字数字）；')
A('2. 分四类：**同句**（完全一致）／**措辞差异**（相似度 ≥ 0.7 但不等）／**仅主库有**／**仅对照本有**；')
A('3. 命例按**四柱多重集合**比对（主库「时日月年」序、对照本「年月日时」序，序不同只比集合）。')
A('> 判读要点：**「仅对照本有」＝主库的潜在缺口候选**（须人工核是否真缺）；**「仅主库有」＝对照本无此句**。\n')
A('## 二、总体统计\n')
A('| 干 | 主库条目 | 对照本章 | 主库字数 | 对照本字数 | 同句 | 措辞差异 | 仅主库有 | 仅对照本有 | 命例（主/对照/共有） |')
A('|---|---|---|---|---|---|---|---|---|---|')
for r in res:
    A('| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d/%d/%d |' % (
        r['gan'], r['n_entry'], r['n_ch'], r['mchar'], r['cchar'], r['same'], len(r['pairs']),
        len(r['only_m']), len(r['only_c']), r['case_m'], r['case_c'], r['case_same']))
A('| **合计** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d/%d/%d** |' % (
    S('n_entry'), S('n_ch'), S('mchar'), S('cchar'), S('same'), SL('pairs'), SL('only_m'), SL('only_c'),
    S('case_m'), S('case_c'), S('case_same')))
A('')
A('## 三、系统差异（版本性，全库层）\n')
A('1. **切分不同**：见上；这解释了为何"逐条相似度"普遍偏低。')
A('2. **总论结构不同**：对照本为干级总论页（甲木总论／庚金总论／壬水总论／戊土论土），主库为跨干共享 `00-总论/`（论木／论土／论金／论水，21 分节）——不可直接对位，本清单**未纳入 00-总论**。')
A('3. **命例序不同**：主库「时日月年」，对照本「年月日时」——引用时**不得混读**。')
A('4. **合章与另采源**：主库 `03-乙木/15-十二月乙木.md`（整条另采源）与 `06-戊土/12-十一、十二月戊土.md` 的 `## 另采源命例` 取自对照本，其差异＝底本缺口，不属校勘差异。')
A('5. **措辞差异为传本特征**：示例（戊土十一二月、乙木十一月/十二月）已在各条【疏解】登记"传本差异"，本清单可作全量依据。\n')
A('## 四、逐干明细\n')
A('> 每干三类：**① 仅对照本有**（主库潜在缺口候选，重要性最高）｜**② 仅主库有**｜**③ 措辞差异**。每类最多列 40 条。\n')
for r in res:
    A('### %s（%s｜主库 %d 条 / 对照本 %d 章）\n' % (r['gan'], r['dir'], r['n_entry'], r['n_ch']))
    A('**① 仅对照本有（%d 条，主库潜在缺口候选）**\n' % len(r['only_c']))
    if r['only_c']:
        for s in r['only_c'][:40]:
            A('- %s' % s)
        if len(r['only_c']) > 40:
            A('- ……（另有 %d 条）' % (len(r['only_c']) - 40))
    else:
        A('- （无）')
    A('')
    A('**② 仅主库有（%d 条）**\n' % len(r['only_m']))
    if r['only_m']:
        for s in r['only_m'][:40]:
            A('- %s' % s)
        if len(r['only_m']) > 40:
            A('- ……（另有 %d 条）' % (len(r['only_m']) - 40))
    else:
        A('- （无）')
    A('')
    A('**③ 措辞差异（%d 组，按相似度降序）**\n' % len(r['pairs']))
    if r['pairs']:
        A('| 相似度 | 主库 | 对照本 |')
        A('|---|---|---|')
        for br, a, b in r['pairs'][:15]:
            A('| %.2f | %s | %s |' % (br, a[:60], b[:60]))
        if len(r['pairs']) > 15:
            A('| … | （另有 %d 组） | |' % (len(r['pairs']) - 15))
    else:
        A('- （无）')
    A('')
    A('**④ 命例**：主库 %d 例／对照本 %d 例／共有 %d 例' % (r['case_m'], r['case_c'], r['case_same']))
    om, oc = (r['mcase'] - r['ccase']), (r['ccase'] - r['mcase'])
    if om:
        A('- 仅主库有：' + '、'.join(' '.join(k) + (('×%d' % v) if v > 1 else '') for k, v in list(om.items())[:12]))
    if oc:
        A('- 仅对照本有：' + '、'.join(' '.join(k) + (('×%d' % v) if v > 1 else '') for k, v in list(oc.items())[:12]))
    A('')
A('## 五、后续建议\n')
A('1. **先核 ①「仅对照本有」**：逐条判断是"主库缺"还是"对照本增（徐乐吾本的节录/改写）"——判为真缺者，走"另采源＋留痕"路径补入（不直接改底本原文）。')
A('2. **命例差异**：优先核对"仅一侧有"的四柱（可能是漏抄或传本不同），登记于该条【疏解】「存疑」。')
A('3. **措辞差异**：批量差异属传本特征，建议统一登记为条目【疏解】的「传本差异」小节（是否规范化见 `TODO.md` P2.2）。')
A('4. **纪律不变**：主库不改原文；对照本徐注不入库、不引用。')
open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
print('已生成 %s（%d 行）' % (OUT, len(L)))
print('同句 %d｜措辞 %d｜仅主库 %d｜仅对照本 %d｜命例 主%d/对%d/共有%d' % (
    S('same'), SL('pairs'), SL('only_m'), SL('only_c'), S('case_m'), S('case_c'), S('case_same')))
