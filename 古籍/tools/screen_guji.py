# -*- coding: utf-8 -*-
"""古籍库粗筛脚本（guwen-cleaning 配套工具）。

用法：
  python screen_guji.py                 # 全库扫描，输出问题清单
  python screen_guji.py --min-han 2000  # 只统计正文超过 N 汉字的文件
  python screen_guji.py --punct 0.05    # 标点密度告警阈值（默认 0.05）
  python screen_guji.py --path 子平      # 只扫子平领域

检查项：
  1) 标点不足（无标点/半标点）候选
  2) 装饰符残留（★☆◆●■□、标题行书名号、标题行全角空格）
  3) 编码问题（UTF-8 BOM）
  4) 繁体残留（简繁统一遗漏的常见繁体字）
  5) 未拆分全文（*-全文.md / 单书全文无同名拆分目录）
"""
import argparse
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = r'古籍'
PUNCT = set('，。；：？！、”“‘’《》【】（）')
DECOR = '★☆◆●■▲△◎※'
HEAD_PUNCT = re.compile(r'^#{1,6}\s*\S*[《》]')
HEAD_FWS = re.compile(r'^#{1,6}[^　]*　')
# 常见简体转换遗漏的繁体字（信号，不替代 OpenCC）
FAN = '書寫讀說聽見風雲氣無萬與為車東來學問體陽陰陽乾徵於後發門開間關隨際靈歸農驚動靜喪聲實寶龍龜鳳鳥樂園國畫飛鳴隱顯榮華麗麗豐餘'


def punct_ratio(text):
    han = len(re.findall(r'[\u4e00-\u9fff]', text))
    pn = sum(1 for c in text if c in PUNCT)
    return han, pn, (pn / han if han else 1.0)


def scan(path, min_han, punct_threshold):
    issues = {
        'punct': [],
        'decor': [],
        'head_book': [],
        'head_fws': [],
        'bom': [],
        'fan': [],
        'unsplit': [],
    }
    fulltext_files = []
    for dirpath, dirs, files in os.walk(path):
        rel = os.path.relpath(dirpath, ROOT)
        if rel.startswith(('guwen-cleaning', 'tools')) or dirpath == ROOT:
            pass
        names = [f for f in files if f.endswith('.md')]
        for fn in names:
            p = os.path.join(dirpath, fn)
            with open(p, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xef\xbb\xbf'):
                issues['bom'].append(p)
            text = raw.decode('utf-8', errors='replace')
            han, pn, ratio = punct_ratio(text)
            if han > min_han and ratio < punct_threshold:
                issues['punct'].append((p, han, pn, ratio))
            # 底本判定：*-全文.md / *-全本.md 且有同名拆分目录（如 渊海子平-全文.md -> 渊海子平/）
            # 底本保留源文 ★/《》/全角空格等原始标记，清洗成果在拆分目录；不再对底本报装饰/标题残留。
            is_source = False
            if re.search(r'(全文|全书|全本)\.md$', fn):
                base = re.sub(r'[-–—]?(全文|全书|全本)\.md$', '', fn)
                if os.path.isdir(os.path.join(dirpath, base)):
                    is_source = True
            if not is_source:
                if any(c in text for c in DECOR):
                    issues['decor'].append(p)
                # 标题行书名号/全角空格残留（正文引用书名不算）
                for ln in text.splitlines():
                    if HEAD_PUNCT.match(ln):
                        issues['head_book'].append((p, ln.strip()[:40]))
                        break
                for ln in text.splitlines():
                    if HEAD_FWS.match(ln):
                        issues['head_fws'].append((p, ln.strip()[:40]))
                        break
            fan = sorted({c for c in text if c in FAN})
            if fan:
                issues['fan'].append((p, ''.join(fan[:12])))
            if re.search(r'全文|全书|全本', fn):
                fulltext_files.append((p, fn, rel))
    # 未拆分全文：有 *-全文.md 且无同名拆分目录
    for p, fn, rel in fulltext_files:
        base = re.sub(r'[-–—]?(全文|全书|全本)\.md$', '', fn)
        book_dir = os.path.join(ROOT, rel, base)
        if not os.path.isdir(book_dir):
            issues['unsplit'].append((p, base))
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-han', type=int, default=2000)
    ap.add_argument('--punct', type=float, default=0.05)
    ap.add_argument('--path', default='.')
    args = ap.parse_args()
    target = os.path.join(ROOT, args.path) if args.path != '.' else ROOT
    issues = scan(target, args.min_han, args.punct)
    print('=' * 70)
    print('古籍库粗筛报告（guwen-cleaning / screen_guji.py）')
    print('扫描范围：%s | 标点阈值：%.3f | 汉字下限：%d' % (target, args.punct, args.min_han))
    print('=' * 70)
    if issues['punct']:
        print('\n[1] 标点不足候选（无标点/半标点，需补标点）')
        for p, han, pn, r in sorted(issues['punct'], key=lambda x: x[3]):
            print('  %.3f | 汉字 %d | 标点 %d | %s' % (r, han, pn, p))
    if issues['decor']:
        print('\n[2] 装饰符残留（★☆◆●等）')
        for p in issues['decor']:
            print('  ' + p)
    if issues['head_book']:
        print('\n[3] 标题行残留书名号')
        for p, ln in issues['head_book']:
            print('  %s :: %s' % (p, ln))
    if issues['head_fws']:
        print('\n[4] 标题行残留全角空格')
        for p, ln in issues['head_fws']:
            print('  %s :: %s' % (p, ln))
    if issues['bom']:
        print('\n[5] UTF-8 BOM 残留')
        for p in issues['bom']:
            print('  ' + p)
    if issues['fan']:
        print('\n[6] 繁体残留（需 OpenCC 复核）')
        for p, fan in issues['fan']:
            print('  %s :: %s' % (p, fan))
    if issues['unsplit']:
        print('\n[7] 未拆分全文（无同名拆分目录）')
        for p, base in issues['unsplit']:
            print('  %s（%s）' % (p, base))
    print('\n完成。')


if __name__ == '__main__':
    main()
