# -*- coding: utf-8 -*-
"""解析《周易-经传全文.md》为 64 卦文件 + 十翼文件 + 索引。
输出目录：古籍/易学/周易/
规则：
- 卦标题匹配 "01. 乾（卦一）" 或 "03．屯（卦三）"（半角/全角点、转义点均可）；
- 卦画行（罗马数字符号行）单独识别并提取"乾下乾上"式卦象，不并入内容块；
- 段落按前缀分拣（卦辞/彖/象/文言/爻辞），无前缀行为续行并入上一块；
- 《象》曰 段拆为 大象 + 逐爻小象（按 “…” ，…也。 句式）；
- 卦辞块内若混入《彖》曰（源文本折行合并），在《彖》曰 处切开；
- 爻辞与小象配对：先做标点归一化精确匹配，失败则按顺序兜底。
"""
import os
import re
import json

SRC = r"古籍\易学\周易-经传全文.md"
OUT = r"古籍\易学\周易"

GUA_RE = re.compile(r'^\s*(\d{2})(?:\\\.|[\.．])\s*(.+?)（卦[一二三四五六七八九十]+）\s*$')
YAO_RE = re.compile(r'^\s*(初九|九二|九三|九四|九五|上九|初六|六二|六三|六四|六五|上六|用九|用六)[，,：:]')
GUA_CI_RE = re.compile(r'^\s*《[^》]+》[：:]')
XIANG_RE = re.compile(r'^\s*《象》曰[：:]?')
TUAN_RE = re.compile(r'^\s*《彖》曰[：:]?')
WENYAN_RE = re.compile(r'^\s*《文言》曰[：:]?')
HUAXIANG_RE = re.compile(r'^\s*[ⅰⅱⅲⅳⅴⅵⅶⅷ]+（([^）]+)）\s*$')
HUAXIANG_SYM_RE = re.compile(r'^\s*[ⅰⅱⅲⅳⅴⅵⅶⅷ]+\s*$')
SEC_RE = re.compile(r'^\s*(上经|下经|系辞|系辞上|系辞下|说卦|序卦|杂卦)\s*$')

XIAO_XIANG_RE = re.compile(r'“[^”]+”[，。](?:[^“]*?。)+')
DX_HEUR_RE = re.compile(r'君子以|先王以|后以|大人以|上以|君子|先王|大人')

def norm(s):
    return re.sub(r'[《》“”，。！？、\s（）()]', '', s or '')

def load_lines():
    with open(SRC, encoding='utf-8') as f:
        return f.read().splitlines()

def split_blocks(lines, start, end):
    """[start,end) 行分块：前缀行开新块，续行并入上一块；跳过卦画行。返回 (块列表, 卦象或None)。"""
    blocks = []
    cur = []
    huaxiang = None
    for ln in lines[start:end]:
        s = ln.rstrip()
        if not s.strip():
            continue
        if GUA_RE.match(s):
            continue
        m = HUAXIANG_RE.match(s)
        if m:
            huaxiang = m.group(1).strip()
            continue
        if HUAXIANG_SYM_RE.match(s):
            continue
        is_new = bool(YAO_RE.match(s) or GUA_CI_RE.match(s) or XIANG_RE.match(s)
                      or TUAN_RE.match(s) or WENYAN_RE.match(s))
        if is_new:
            if cur:
                blocks.append(''.join(cur))
            cur = [s]
        else:
            cur.append(s)
    if cur:
        blocks.append(''.join(cur))
    return [b for b in blocks if b.strip()], huaxiang

def split_tuan_in_guaci(block):
    m = re.search(r'《彖》曰[：:]', block)
    if m:
        return block[:m.start()].strip(), block[m.start():].strip()
    return block.strip(), None

def parse_xiaoxiang(xiang_text):
    items = []
    for m in XIAO_XIANG_RE.finditer(xiang_text):
        inner = re.match(r'“(.*?)”[，。](.*)', m.group(0), re.S)
        if inner:
            items.append((inner.group(1).strip(), inner.group(2).strip()))
    first_quote = xiang_text.find('“')
    big = xiang_text[:first_quote].strip() if first_quote >= 0 else xiang_text.strip()
    return (big or None), items

def chinese_num(n):
    m = '零一二三四五六七八九十'
    if n <= 10:
        return m[n]
    if n < 20:
        return '十' + m[n - 10]
    if n % 10 == 0:
        return m[n // 10] + '十'
    return m[n // 10] + '十' + m[n % 10]

SHIYI_MAP = [
    ('系辞', '十翼-系辞上传.md', '系辞上传', '系辞上传（《易传》之一，总论易道）'),
    ('系辞下', '十翼-系辞下传.md', '系辞下传', '系辞下传（《易传》之一）'),
    ('说卦', '十翼-说卦传.md', '说卦传', '说卦传（《易传》之一，八卦万物类象之祖）'),
    ('序卦', '十翼-序卦传.md', '序卦传', '序卦传（《易传》之一，六十四卦次序之义）'),
    ('杂卦', '十翼-杂卦传.md', '杂卦传', '杂卦传（《易传》之一，卦名对举）'),
]

def write_shiyi(lines, sec_idx):
    for sec_key, fn, display, desc in SHIYI_MAP:
        start = sec_idx[sec_key]
        end = len(lines)
        for n2, _, _, _ in SHIYI_MAP:
            if sec_idx[n2] > start:
                end = min(end, sec_idx[n2])
        paras = []
        for ln in lines[start + 1:end]:
            s = ln.strip()
            if s and s != sec_key:
                paras.append(s)
        p = []
        p.append('# %s' % display)
        p.append('')
        p.append('> 篇名：%s｜%s' % (display, desc))
        p.append('> 底本：古籍/易学/周易-经传全文.md（原文）')
        p.append('> 来源：https://github.com/frankslin/daizhigev20/blob/data/易藏/易经/周易.md')
        p.append('')
        p.extend(paras)
        p.append('')
        with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write('\n'.join(p).rstrip() + '\n')
        print('已写', fn, '段落数', len(paras))

def write_index(meta):
    p = []
    p.append('# 周易（经+十翼）索引')
    p.append('')
    p.append('> 项目路径：古籍/易学/周易/')
    p.append('> 底本：古籍/易学/周易-经传全文.md（殆知阁镜像原文，保留不改）')
    p.append('> 结构化日期：2026-08-12（parse_zhouyi.py 自动拆分，已全量校验）')
    p.append('> 查找方式：查某卦 → 打开 古籍/易学/周易/NN-卦名.md；查十翼 → 十翼-*.md；查万物类象 → 十翼-说卦传.md')
    p.append('')
    p.append('## 每卦文件结构')
    p.append('')
    p.append('每个卦文件按固定结构组织，便于检索：')
    p.append('')
    p.append('| 字段 | 内容 |')
    p.append('| --- | --- |')
    p.append('| 卦序/卦名 | 01-64，上经/下经 |')
    p.append('| 卦象 | 上下卦（如 乾下乾上） |')
    p.append('| 卦辞 | 《X》：… |')
    p.append('| 彖传（彖曰） | 卦辞之解释 |')
    p.append('| 象传·大象 | 君子以… |')
    p.append('| 爻辞与小象 | 表格：爻位｜爻辞｜小象（象曰） |')
    p.append('| 文言传 | 仅乾、坤两卦 |')
    p.append('')
    p.append('## 卦序表（64卦）')
    p.append('')
    for part in ('上经', '下经'):
        p.append('### %s' % part)
        p.append('')
        p.append('| 卦序 | 卦名 | 文件 |')
        p.append('| --- | --- | --- |')
        for m in meta:
            if m['part'] == part:
                p.append('| %02d | %s | 古籍/易学/周易/%s |' % (m['num'], m['name'], m['file']))
        p.append('')
    p.append('## 十翼（易传）')
    p.append('')
    p.append('| 篇 | 文件 | 说明 |')
    p.append('| --- | --- | --- |')
    for sec_key, fn, display, desc in SHIYI_MAP:
        p.append('| %s | 古籍/易学/周易/%s | %s |' % (display, fn, desc))
    p.append('| 彖传/象传 | （已并入各卦文件） | 彖曰、大象、小象分别落在每卦对应字段 |')
    p.append('| 文言传 | （已并入 01-乾/02-坤） | 仅乾坤有 |')
    p.append('')
    p.append('## 易纬·乾凿度')
    p.append('')
    p.append('独立文件：古籍/易学/易纬乾凿度.md（汉·郑玄注，卷上/卷下两篇，未拆分）')
    p.append('')
    with open(os.path.join(OUT, 'AGENTS.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(p).rstrip() + '\n')
    print('已写 AGENTS.md')

def main():
    lines = load_lines()
    gua_idx = []
    for i, ln in enumerate(lines):
        m = GUA_RE.match(ln)
        if m:
            gua_idx.append((i, int(m.group(1)), m.group(2).strip()))
    print('卦标题数:', len(gua_idx))
    sec_idx = {}
    toc = {10, 11, 12, 13, 14, 15, 16}
    for i, ln in enumerate(lines):
        if i + 1 in toc:
            continue
        m = SEC_RE.match(ln)
        if m:
            sec_idx.setdefault(m.group(1), i)
    print('节位置:', {k: v + 1 for k, v in sec_idx.items()})
    os.makedirs(OUT, exist_ok=True)
    xia_start = sec_idx.get('下经')
    xici_start = min([sec_idx.get(k) for k in ('系辞', '系辞上', '系辞下') if sec_idx.get(k)] or [len(lines)])
    records = []
    for k, (i, num, name) in enumerate(gua_idx):
        part = '下经' if (xia_start is not None and i >= xia_start) else '上经'
        if k + 1 < len(gua_idx):
            end = gua_idx[k + 1][0]
        else:
            end = xici_start
        if xia_start is not None and part == '上经':
            end = min(end, xia_start)
        blocks, huaxiang = split_blocks(lines, i + 1, end)
        gua_ci, tuan, wenyen, big_xiang = None, None, None, None
        yao = []
        pending_xq = []
        yao_xiang = {}
        for b in blocks:
            s = b.strip()
            if GUA_CI_RE.match(s):
                gc, t = split_tuan_in_guaci(s)
                gua_ci = gc
                if t:
                    tuan = t
            elif TUAN_RE.match(s):
                tuan = s
            elif WENYAN_RE.match(s):
                wenyen = s
            elif XIANG_RE.match(s):
                body = re.sub(r'^\s*《象》曰[：:]\s*', '', s)
                big, items = parse_xiaoxiang(body)
                # 带引号卦名的大象（如 风行天上，“小畜”。君子以懿文德。）
                if items and big and not DX_HEUR_RE.search(big) and not big_xiang:
                    q0, e0 = items[0]
                    if norm(q0) == norm(name) and DX_HEUR_RE.search(e0):
                        big_xiang = (big + '“' + q0 + '”。' + e0).strip()
                        items = items[1:]
                    elif DX_HEUR_RE.search(e0):
                        big_xiang = (big + '“' + q0 + '”。' + e0).strip()
                        items = items[1:]
                if big and DX_HEUR_RE.search(big):
                    big_xiang = big
                if items:
                    pending_xq.extend(items)
                elif not (big and DX_HEUR_RE.search(big)):
                    # 无引号、非大象句式的象段 = 该爻小象（紧跟最近爻）
                    if yao:
                        yao_xiang.setdefault(yao[-1][0], body)
            elif YAO_RE.match(s):
                pos = YAO_RE.match(s).group(1)
                text = re.sub(r'^\s*%s[，,：:]\s*' % re.escape(pos), '', s)
                # 爻辞行内嵌《象》曰（源文本折行合并）→ 拆出该爻小象
                emb = re.search(r'《象》曰[：:]?', text)
                if emb:
                    body = text[emb.end():].strip()
                    text = text[:emb.start()].strip()
                    bq, items = parse_xiaoxiang(body)
                    if items:
                        yao_xiang.setdefault(pos, []).extend(e for _, e in items)
                    elif body and not (bq and DX_HEUR_RE.search(bq)):
                        yao_xiang.setdefault(pos, []).append(body)
                yao.append((pos, text))
        # 配对小象（引文式）：先精确、再前缀、最后顺序兜底（允许一爻多条）
        yao_xiang = {k: (v if isinstance(v, list) else [v]) for k, v in yao_xiang.items()}
        used_quotes = set()
        for pos, text in yao:
            if pos in yao_xiang:
                continue
            key = norm(text)
            for q, e in pending_xq:
                if id(q) not in used_quotes and norm(q) == key:
                    yao_xiang.setdefault(pos, []).append(e)
                    used_quotes.add(id(q))
        for pos, text in yao:
            if pos in yao_xiang:
                continue
            hits = [(id(q), e) for q, e in pending_xq
                    if id(q) not in used_quotes and norm(q) and norm(q) in norm(text)]
            for qid, e in hits:
                used_quotes.add(qid)
                yao_xiang.setdefault(pos, []).append(e)
        unmatched_yao = [pos for pos, _ in yao if pos not in yao_xiang]
        remain_pending = [e for q, e in pending_xq if id(q) not in used_quotes]
        for i, expl in enumerate(remain_pending):
            if not unmatched_yao:
                break
            target = unmatched_yao[min(i, len(unmatched_yao) - 1)]
            yao_xiang.setdefault(target, []).append(expl)
        # 合并为分号连接字符串
        yao_xiang = {k: '；'.join(v) for k, v in yao_xiang.items()}
        records.append({
            'num': num, 'name': name, 'part': part, 'huaxiang': huaxiang or '',
            'gua_ci': gua_ci or '', 'tuan': tuan or '', 'wenyen': wenyen or '',
            'big_xiang': big_xiang or '', 'yao': yao, 'yao_xiang': yao_xiang,
        })
    meta = []
    for d in records:
        fn = '%02d-%s.md' % (d['num'], d['name'])
        rows = []
        for pos, text in d['yao']:
            x = d['yao_xiang'].get(pos, '')
            rows.append('| %s | %s | %s |' % (pos, text, x))
        p = []
        p.append('# %s（卦%s）' % (d['name'], chinese_num(d['num'])))
        p.append('')
        p.append('> 卦序：%02d｜%s｜卦象：%s' % (d['num'], d['part'], d['huaxiang']))
        p.append('> 底本：古籍/易学/周易-经传全文.md（原文）')
        p.append('')
        p.append('## 卦辞')
        p.append('')
        p.append(d['gua_ci'])
        p.append('')
        if d['tuan']:
            p.append('## 彖传（彖曰）')
            p.append('')
            p.append(re.sub(r'^\s*《彖》曰[：:]\s*', '', d['tuan']))
            p.append('')
        if d['big_xiang']:
            p.append('## 象传·大象')
            p.append('')
            p.append(d['big_xiang'])
            p.append('')
        p.append('## 爻辞与小象')
        p.append('')
        p.append('| 爻位 | 爻辞 | 小象（象曰） |')
        p.append('| --- | --- | --- |')
        p.extend(rows)
        p.append('')
        if d['wenyen']:
            p.append('## 文言传（文言曰）')
            p.append('')
            p.append(re.sub(r'^\s*《文言》曰[：:]\s*', '', d['wenyen']))
            p.append('')
        with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write('\n'.join(p).rstrip() + '\n')
        meta.append({'num': d['num'], 'name': d['name'], 'part': d['part'], 'file': fn,
                     'yao_count': len(d['yao']), 'has_wenyen': bool(d['wenyen'])})
    with open(os.path.join(OUT, '_parse_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print('已写', len(records), '个卦文件')
    write_shiyi(lines, sec_idx)
    write_index(meta)

if __name__ == '__main__':
    main()
