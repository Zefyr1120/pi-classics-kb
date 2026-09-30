# -*- coding: utf-8 -*-
"""素问王冰注补遗（篇75-81）构建：维基文库四库本卷23/24 提取文本 -> 简体 -> 落盘。
输入：$env:TEMP/suwen_buyi/juan23.txt、juan24.txt（由抓取脚本生成）
输出：古籍/内经/素问-王冰注补遗-篇75-81.md
"""
import os
import re
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from opencc import OpenCC

TMP = os.path.join(os.environ['TEMP'], 'suwen_buyi')
OUT = r'古籍\info\..\内经\素问-王冰注补遗-篇75-81.md'

PROTECT_QIAN = re.compile(r'乾(?=[下上宫为位方象金阳元道卦坤造隆乾健龙清])')
PROTECT_ZHENG = re.compile(r'徵(?=于?宫商角|姓音)')
SENT_A = '\ue000'
SENT_B = '\ue001'

# 四库本用字异体 -> 标准繁体（再经 OpenCC t2s 转简）
VARIANT_MAP = {
    '隂': '陰', '逺': '遠', '𠉀': '候', '㝠': '冥', '𡨋': '冥', '髙': '高', '㫖': '旨',
    '緜': '綿', '榖': '穀', '乗': '乘', '㝡': '最', '蔵': '藏', '巻': '卷', '専': '專',
    '騐': '驗', '亷': '廉', '㢘': '廉', '䧏': '降', '㣲': '微', '胷': '胸', '輙': '輒',
    '㨿': '據', '𬾨': '備', '𤣥': '玄', '㵦': '隨', '䝉': '蒙', '㦯': '或', '㕓': '廛',
}


def protect(text):
    holder = {}

    def rep_qian(m):
        idx = len(holder)
        holder[idx] = m.group(0)
        return SENT_A + str(idx) + SENT_B

    def rep_zheng(m):
        idx = len(holder)
        holder[idx] = m.group(0)
        return SENT_A + str(idx) + SENT_B

    text = PROTECT_QIAN.sub(rep_qian, text)
    text = PROTECT_ZHENG.sub(rep_zheng, text)
    return text, holder


def restore(text, holder):
    def rep(m):
        return holder[int(m.group(1))]

    return re.sub(SENT_A + r'(\d+)' + SENT_B, rep, text)


def cut_section(text):
    start = text.find('欽定四庫全書')
    if start < 0:
        for probe in ('黃帝内經素問卷二十三', '黃帝内經素問卷二十四', '黄帝内經素問卷二十三', '黄帝内經素問卷二十四'):
            start = text.find(probe)
            if start >= 0:
                break
        else:
            start = 0
    end = text.find('此作品在全世界都属于公有领域')
    if end < 0:
        end = text.find('检索自')
    if end < 0:
        end = len(text)
    return text[start:end]


def main():
    parts = []
    for juan in ('juan23', 'juan24'):
        p = os.path.join(TMP, juan + '.txt')
        with open(p, encoding='utf-8') as f:
            parts.append(cut_section(f.read()))
    raw = '\n\n'.join(parts)
    # 异体字归一（先于繁转简）
    for src, dst in VARIANT_MAP.items():
        raw = raw.replace(src, dst)
    # 注文括号统一：〈〉 -> 【】
    raw = re.sub(r'[〈〉]', lambda m: '【' if m.group(0) == '〈' else '】', raw)
    protected, holder = protect(raw)
    cc = OpenCC('t2s')
    converted = cc.convert(protected)
    converted = restore(converted, holder)
    header = (
        '> 书名：黄帝内经·素问（王冰注补遗：篇75-81）｜作者：唐·王冰次注、宋·林亿等校正｜朝代：唐/宋\n'
        '> 版本说明：维基文库《黄帝内经素问（四库全书本）》卷23/24 网页整理本；繁体转简体（OpenCC t2s，乾/徵按语境保护）；注文〈〉转【】\n'
        '> 来源：https://zh.wikisource.org/wiki/黄帝内經素問_(四庫全書本)/卷23 与 /卷24\n'
        '> 抓取日期：2026-08-13\n'
        '> 完整性：篇75-81 七篇正文+王冰注+新校正+卷23/24释文\n'
        '> 分层：正文=素问篇文；【】=王冰注/新校正\n'
    )
    body = header + '\n\n' + converted.strip() + '\n'
    out = os.path.normpath(OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    print('OK chars=', len(converted), ' -> ', out)
    # 校验：7 篇标题
    for t in ('著至教論篇七十五', '示從容論篇七十六', '疏五過論篇七十七', '徴四失論篇七十八',
              '陰陽類論篇七十九', '方盛衰論篇八十', '解精微論篇八十一'):
        print(('  ' + t) if raw.find(t) >= 0 else ('  MISSING ' + t))


if __name__ == '__main__':
    main()
