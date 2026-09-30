# -*- coding: utf-8 -*-
"""古籍库统一结构化拆分（第二批）。
对尚未拆分的书按卷/篇/章/节/局拆分，输出 古籍/<领域>/<书名>/NN-标题.md + AGENTS.md。
通用规则：标题行（正则匹配）开新节；正文按原样保留；文件头用统一模板；
标题清洗（去全角空格/异体字规范化）；文件命名 NN-清洗后标题.md。
"""
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = r'古籍'

CN = '一二三四五六七八九十'
SKIP_LINE = object()

def cn_num(n):
    if n <= 10:
        return CN[n - 1]
    if n < 20:
        return '十' + (CN[n - 11] if n > 10 else '')
    if n % 10 == 0:
        return CN[n // 10 - 1] + '十'
    return CN[n // 10 - 1] + '十' + CN[n % 10 - 1]

def clean_title(t):
    t = t.replace('　', '').replace(' ', '')
    t = t.replace('巻', '卷')
    t = re.sub(r'[\\/:*?"<>|]', '_', t)
    return t.strip()

def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def parse_blocks(lines, pat, group_fn):
    """按标题行切块：返回 [(seq, title, body_lines), ...]。group_fn(标题行)->标题文本或None。"""
    rx = re.compile(pat)
    blocks = []
    cur_title = None
    cur = []
    for ln in lines:
        s = ln.rstrip()
        m = rx.match(s)
        if m:
            title = group_fn(m, s)
            if title is SKIP_LINE:
                continue
            if title is None:
                # 视为正文行：并入当前块（如《诗诀》《甲》等行内子目）
                if cur_title is not None:
                    cur.append(s)
                continue
            if cur_title is not None and title == cur_title:
                # 同标题重复（如同一日内多局、篇题重出）：并入当前块
                cur.append(s)
            else:
                if cur_title is not None:
                    blocks.append((cur_title, cur))
                cur_title = title
                cur = []
        else:
            if cur_title is not None:
                cur.append(s)
    if cur_title is not None:
        blocks.append((cur_title, cur))
    return blocks

def write_book(cfg):
    src = cfg['src']
    out_dir = os.path.join(ROOT, cfg['domain'], cfg['dir'])
    if os.path.isdir(out_dir):
        for n in os.listdir(out_dir):
            p = os.path.join(out_dir, n)
            if os.path.isfile(p):
                os.remove(p)
    os.makedirs(out_dir, exist_ok=True)
    with open(src, encoding='utf-8') as f:
        text = f.read()
    if cfg.get('preprocess'):
        text = cfg['preprocess'](text)
    # 去掉文件头（> 开头行）仅用于解析，正文保留
    lines = text.splitlines()
    if cfg.get('cut_prefix_until'):
        rx = re.compile(cfg['cut_prefix_until'])
        for i, ln in enumerate(lines):
            if rx.match(ln):
                lines = lines[i:]
                break
    if cfg.get('keep_suffix_from'):
        rx = re.compile(cfg['keep_suffix_from'])
        idx = None
        for i, ln in enumerate(lines):
            if rx.match(ln):
                idx = i
                break
        if idx is not None:
            suffix = '\n'.join(lines[idx:])
            with open(os.path.join(out_dir, cfg['suffix_file']), 'w', encoding='utf-8') as f:
                f.write('# %s\n\n> 书名：黄帝内经·素问｜底本：%s\n> 说明：%s\n\n%s\n' % (
                    cfg['suffix_title'], cfg['rel'], cfg['suffix_note'], suffix.strip()))
            lines = lines[:idx]
    blocks = parse_blocks(lines, cfg['pat'], cfg['group'])
    if cfg.get('drop_tail'):
        blocks = [(t, b) for t, b in blocks if not t.rstrip().endswith(cfg['drop_tail'])]
    if cfg.get('pre_title'):
        rx = re.compile(cfg['pat'])
        first = None
        for i, ln in enumerate(lines):
            m = rx.match(ln)
            if m and m.group(1) is not None:
                first = i
                break
        if first is not None and ''.join(lines[:first]).strip():
            blocks.insert(0, (cfg['pre_title'], lines[:first]))
    if cfg.get('skip_empty'):
        blocks = [(t, b) for t, b in blocks if ''.join(b).strip()]
    if cfg.get('merge_same'):
        by_title = {}
        order = []
        for t, b in blocks:
            if t not in by_title:
                by_title[t] = []
                order.append(t)
            by_title[t].extend(b)
        blocks = [(t, by_title[t]) for t in order]
    rows = []
    for i, (title, body) in enumerate(blocks, 1):
        nn = '%02d' % i
        clean = clean_title(title)
        fn = nn + '-' + safe(clean) + '.md'
        path = os.path.join(out_dir, fn)
        header = cfg['header'].format(seq=nn, total=len(blocks), title=title, src=cfg['rel'])
        content = header + '\n\n' + '\n'.join(body).strip() + '\n'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        rel = os.path.join('古籍', cfg['domain'], cfg['dir'], fn).replace('\\', '/')
        rows.append((nn, title, rel))
    # 索引
    idx = ['# %s（%d节）索引' % (cfg['name'], len(blocks)), '',
           '> 项目路径：古籍/%s/%s/' % (cfg['domain'], cfg['dir']),
           '> 底本：%s' % cfg['rel'],
           '> 拆分日期：2026-08-12（split_guji.py）', '',
           '| 节序 | 标题 | 文件 |', '| --- | --- | --- |']
    for nn, title, rel in rows:
        idx.append('| %s | %s | %s |' % (nn, title, rel))
    with open(os.path.join(out_dir, 'AGENTS.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(idx) + '\n')
    print('%s: %d 节 -> %s' % (cfg['name'], len(blocks), out_dir.replace(ROOT + '\\', '')))


def make_yuanhai_group():
    """渊海子平：章节标题 = 《...》；【渊海子平】分域标记只改前缀不建文件。
    配合 pat=r'^\s*(?:《([^》]+)》|【渊海子平】\s*([^】]*))' 使用。"""
    state = {'sec': '基础'}
    SUBS = {'当兴', '崛起', '聚兴', '中兴', '末兴'}
    GANZHI = set('甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥')

    def group(m, s):
        if m.group(2) is not None:
            sec = m.group(2).replace('　', '').strip()
            if sec:
                state['sec'] = sec
            return SKIP_LINE
        title = m.group(1) or ''
        suffix = s[m.end():].strip().replace('　', '')
        # 《诗诀》★、《甲》★…干支体象诗、引文（云/曰/见）、群兴论子目：留在当前章
        if title == '诗诀' or title in SUBS:
            return None
        if len(title) == 1 and title in GANZHI:
            return None
        if any(k in suffix for k in ('云', '曰', '见')):
            return None
        clean = title.replace('　', '').strip()
        if suffix:
            clean += '·' + suffix
        return '%s·%s' % (state['sec'], clean)
    return group


def preprocess_yuanhai(t):
    """渊海子平预处理：合并首部分域标记；把《题》★正文拆成标题行+正文行。"""
    t = re.sub(r'【渊海子平】\s*\n\s*基\s*础', '【渊海子平】基础', t)
    t = re.sub(r'^(\s*《[^》]+》)★', r'\1\n', t, flags=re.M)
    return t

def g1(m, s):
    return m.group(1).strip()

def g_plain(m, s):
    return m.group(0).strip()

def g_qian(m, s):
    return m.group(1).strip()

def g_lingshu(m, s):
    return m.group(1).strip()

def g_nan(m, s):
    return m.group(1).strip() + '难'

def g_ri(m, s):
    return m.group(1).strip() + '日'

CONFIGS = [
    dict(name='五行精纪', domain='子平', dir='五行精纪', rel='古籍/子平/五行精纪-全文.md',
         src=ROOT + r'\子平\五行精纪-全文.md',
         pat=r'^\s*第[一二三四五六七八九十百廿卅]+卷[一-龥]',
         group=lambda m, s: s.strip(),
         header='# {title}\n\n> 书名：五行精纪｜底本：{src}\n> 节序：{seq}/{total}｜卷目标记"第X卷"\n> 拆分日期：2026-08-12'),
    dict(name='素问', domain='内经', dir='素问', rel='古籍/内经/素问-全文.md',
         src=ROOT + r'\内经\素问-全文.md',
         pat=r'^\s*([一-龥]{2,12}篇第[一二三四五六七八九十百]+)$',
         group=lambda m, s: m.group(1).strip().replace('六微防', '六微旨').replace('五营运', '五运行'),
         cut_prefix_until=r'^\s*上古天真论篇第一$',
         keep_suffix_from=r'^\s*上古天真论篇第一【新校正',
         suffix_file='99-王冰注本-存74篇.md',
         suffix_title='王冰注本（存74篇）',
         suffix_note='源文件含白文全本（81篇）与王冰注本（存篇1-74，缺75-81）两版；白文全本按篇拆分，王冰注本整篇另存。',
         header='# {title}\n\n> 书名：黄帝内经·素问（白文全本81篇）｜底本：{src}\n> 节序：{seq}/{total}｜篇目（王冰注本另存 99-王冰注本-存74篇.md）\n> 拆分日期：2026-08-12'),
    dict(name='灵枢', domain='内经', dir='灵枢', rel='古籍/内经/灵枢-全文.md',
         src=ROOT + r'\内经\灵枢-全文.md',
         pat=r'^\s*([一-龥]{2,12}第[一二三四五六七八九十百]+)',
         group=lambda m, s: m.group(1).strip(),
         header='# {title}\n\n> 书名：黄帝内经·灵枢｜底本：{src}\n> 节序：{seq}/{total}｜篇目（源文篇题与正文同行，已按篇题切分）\n> 拆分日期：2026-08-12'),
    dict(name='难经', domain='内经', dir='难经', rel='古籍/内经/难经-全文.md',
         src=ROOT + r'\内经\难经-全文.md',
         pat=r'^\s*([一二三四五六七八九十]+)难$',
         group=lambda m, s: m.group(1).strip() + '难',
         header='# {title}\n\n> 书名：难经｜底本：{src}\n> 节序：{seq}/{total}｜难\n> 拆分日期：2026-08-12'),
    dict(name='五行大义', domain='五行', dir='五行大义', rel='古籍/五行/五行大义-全文.md',
         src=ROOT + r'\五行\五行大义-全文.md',
         pat=r'^\s*五行大义卷[第]?[一二三四五六七八九十]+',
         group=lambda m, s: s.strip(),
         header='# {title}\n\n> 书名：五行大义（隋·萧吉）｜底本：{src}\n> 节序：{seq}/{total}｜卷\n> 拆分日期：2026-08-12'),
    dict(name='六壬说约', domain='六壬', dir='六壬说约', rel='古籍/六壬/六壬说约-全文.md',
         src=ROOT + r'\六壬\六壬说约-全文.md',
         pat=r'^\s*大六壬说约卷[上中下末]',
         group=lambda m, s: s.strip(),
         cut_prefix_until=r'^\s*大六壬说约卷上',
         preprocess=lambda t: t.replace('大六壬说约卷末', '\n大六壬说约卷末'),
         header='# {title}\n\n> 书名：六壬说约（清·张鋐）｜底本：{src}\n> 节序：{seq}/{total}｜卷（卷末杂说标题原嵌行内，已切出）\n> 拆分日期：2026-08-12'),
    dict(name='六壬大全', domain='六壬', dir='六壬大全', rel='古籍/六壬/六壬大全-全文.md',
         src=ROOT + r'\六壬\六壬大全-全文.md',
         pat=r'^\s*六壬大全[巻卷][一二三四五六七八九十]+',
         group=lambda m, s: s.strip().replace('巻', '卷'),
         skip_empty=True,
         drop_tail='终',
         header='# {title}\n\n> 书名：六壬大全（明·郭御青）｜底本：{src}\n> 节序：{seq}/{total}｜卷（源文巻/卷异体已统一）\n> 拆分日期：2026-08-12'),
    dict(name='御定六壬直指', domain='六壬', dir='御定六壬直指', rel='古籍/六壬/御定六壬直指-全文.md',
         src=ROOT + r'\六壬\御定六壬直指-全文.md',
         pat=r'^\s*([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])日第[一二三四五六七八九十]+局',
         group=lambda m, s: m.group(1).strip() + '日',
         header='# {title}\n\n> 书名：御定六壬直指｜底本：{src}\n> 节序：{seq}/{total}｜日课（每日常12局）\n> 拆分日期：2026-08-13（guwen-cleaning：修正拆分正则后重拆，60日720局齐全；戊辰日据外部源补入，源文戊寅日重复段已去重）'),
    dict(name='滴天髓辑要', domain='子平', dir='滴天髓辑要', rel='古籍/子平/滴天髓辑要.md',
         src=ROOT + r'\子平\滴天髓辑要.md',
         pat=r'^\s*[一-龥]{2,5}论(-[真假])?$',
         group=lambda m, s: s.strip(),
         cut_prefix_until=r'^\s*吉凶寿夭论',
         header='# {title}\n\n> 书名：滴天髓辑要（清·陈之遴）｜底本：{src}\n> 节序：{seq}/{total}｜论（已截除卷首目录）\n> 拆分日期：2026-08-12'),
    dict(name='神峰通考', domain='子平', dir='神峰通考', rel='古籍/子平/神峰通考-全文.md',
         src=ROOT + r'\子平\神峰通考-全文.md',
         pat=r'^\s*[一-龥]{2,16}(说类|说|格|论|定诀)$',
         group=lambda m, s: s.strip(),
         header='# {title}\n\n> 书名：神峰通考（明·张楠）｜底本：{src}\n> 节序：{seq}/{total}｜类目\n> 拆分日期：2026-08-12'),
    dict(name='穷通宝鉴', domain='子平', dir='穷通宝鉴', rel='古籍/子平/穷通宝鉴-全文.md',
         src=ROOT + r'\子平\穷通宝鉴-全文.md',
         pat=r'^\s*(论木|三春乙木|论丙火|论丁火|论土|论己土|论金|论辛金|论水|论癸水)$',
         pre_title='卷首（五行总论）',
         group=lambda m, s: {'论木': '甲木', '三春乙木': '乙木', '论丙火': '丙火',
                             '论丁火': '丁火', '论土': '戊土', '论己土': '己土',
                             '论金': '庚金', '论辛金': '辛金', '论水': '壬水',
                             '论癸水': '癸水'}[m.group(1).strip()],
         header='# {title}\n\n> 书名：穷通宝鉴｜底本：{src}\n> 节序：{seq}/{total}｜十干（含总起；卷首=五行总论）\n> 拆分日期：2026-08-12'),
    dict(name='命理约言', domain='子平', dir='命理约言', rel='古籍/子平/命理约言-全文.md',
         src=ROOT + r'\子平\命理约言-全文.md',
         pat=r'^\s*(序|蒋序|韦序|看[一-龥]{2,10}法[一二]?|总纲赋|格局赋|行运赋|流年赋|[一-龥]{1,4}(官|印|财|杀|食|伤)赋|卷[一二三四]杂论)$',
         group=lambda m, s: s.strip(),
         skip_empty=True,
         header='# {title}\n\n> 书名：命理约言（清·陈素庵）｜底本：{src}\n> 节序：{seq}/{total}｜法/赋\n> 拆分日期：2026-08-12'),
    dict(name='脾胃论', domain='内经', dir='脾胃论', rel='古籍/内经/脾胃论-全文.md',
         src=ROOT + r'\内经\脾胃论-全文.md',
         pat=r'^\s*[一-龥]{2,16}(论|汤|法|说|图说)$',
         group=lambda m, s: s.strip(),
         skip_empty=True,
         header='# {title}\n\n> 书名：脾胃论（金·李杲）｜底本：{src}\n> 节序：{seq}/{total}｜节\n> 拆分日期：2026-08-12'),
    dict(name='壬归', domain='六壬', dir='壬归', rel='古籍/六壬/壬归-全文.md',
         src=ROOT + r'\六壬\壬归-全文.md',
         pat=r'^\s*[一-龥]{2,10}第[一二三四五六七八九十]+$',
         group=lambda m, s: s.strip(),
         skip_empty=True,
         cut_prefix_until=r'^\s*观四课之加临第一',
         header='# {title}\n\n> 书名：壬归｜底本：{src}\n> 节序：{seq}/{total}｜节\n> 拆分日期：2026-08-12'),
    dict(name='渊海子平', domain='子平', dir='渊海子平', rel='古籍/子平/渊海子平-全文.md',
         src=ROOT + r'\子平\渊海子平-全文.md',
         pat=r'^\s*(?:《([^》]+)》|【渊海子平】\s*([^】]*))',
         group=make_yuanhai_group(),
         preprocess=preprocess_yuanhai,
         cut_prefix_until=r'^\s*【渊海子平】',
         pre_title='基础·开篇（五干六亲十神）',
         header='# {title}\n\n> 书名：渊海子平（宋·徐大升）｜底本：{src}\n> 节序：{seq}/{total}｜分域：基础/神煞/六亲/女命/赋论\n> 拆分日期：2026-08-12（split_guji.py）'),
]

def main():
    only = None
    if len(sys.argv) > 1 and sys.argv[1] == '--only' and len(sys.argv) > 2:
        only = sys.argv[2]
    for cfg in CONFIGS:
        if only and cfg['name'] != only:
            continue
        try:
            write_book(cfg)
        except Exception as e:
            print('失败:', cfg['name'], e)
    # 大六壬指南：结构索引（正文卷三/卷四无独立标题，不拆文件）
    dlg_dir = os.path.join(ROOT, '六壬', '大六壬指南')
    os.makedirs(dlg_dir, exist_ok=True)
    with open(os.path.join(ROOT, r'六壬\大六壬指南-全文.md'), encoding='utf-8') as f:
        dlg_lines = f.read().splitlines()
    vol_lines = {}
    for i, ln in enumerate(dlg_lines):
        t = ln.strip()
        if t == '卷一':
            vol_lines['卷一'] = i + 1
        elif t == '卷二':
            vol_lines['卷二'] = i + 1
        elif t.startswith('大六壬九天玄女指掌赋'):
            vol_lines.setdefault('卷二正文', i + 1)
        elif '会纂' in t and len(t) < 20:
            vol_lines.setdefault('卷三正文', i + 1)
        elif t.startswith('神煞') or (t.startswith('大六壬神煞') and len(t) < 25):
            vol_lines.setdefault('卷四正文', i + 1)
    idx = ['# 大六壬指南（4卷）结构索引', '',
           '> 项目路径：古籍/六壬/大六壬指南/',
           '> 底本：古籍/六壬/大六壬指南-全文.md（2.7万字，整篇保留未拆）',
           '> 说明：正文仅"卷一/卷二"有独立卷标题，卷三/卷四无独立标题，故不拆分文件，按卷登记行号。', '',
           '| 卷 | 内容 | 底本行号 |',
           '| --- | --- | --- |']
    for vol, desc in [('卷一', '大六壬心印赋（陈公献注）'),
                      ('卷二', '大六壬九天玄女指掌赋（陈公献注）'),
                      ('卷三', '六壬会纂占验指南'),
                      ('卷四', '大六壬神煞指南')]:
        ln = vol_lines.get(vol, vol_lines.get(vol + '正文', '?'))
        idx.append('| %s | %s | 约行 %s |' % (vol, desc, ln))
    idx.append('')
    with open(os.path.join(dlg_dir, 'AGENTS.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(idx) + '\n')
    print('大六壬指南: 结构索引（不拆）')

if __name__ == '__main__':
    main()
