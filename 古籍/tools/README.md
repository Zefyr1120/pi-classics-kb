# 古籍清洗工具速查（tools/）

> 本目录是古籍数据清洗流水线的脚本库。**完整的功能说明、问题与解决思路、可迁移方法论见 [`脚本清单与处理思路沉淀.md`](脚本清单与处理思路沉淀.md)。**
> 方法论总纲见 [`../guwen-cleaning/references/清洗核心规则.md`](../guwen-cleaning/references/清洗核心规则.md)。

## 流水线四层

| 层 | 作用 | 工具 |
|---|---|---|
| ① 采集 | 从网页/镜像站抓原文 | `fetch_mirror.ps1`、`fetch_guoxue3000.ps1`、`fetch_daizhige.ps1`、`fetch_web_text.ps1`、`fetch_clean_sources.py`、`fetch_sanming_vols.py` |
| ② 结构化 | 大文件按卷/篇/章/节拆成可检索单元 | `split_guji.py`（主力）、`split_sanming_vols.py`、`parse_zhouyi.py` |
| ③ 净化 | 繁简、标点、装饰符、BOM | `convert_simplify.py`、`screen_guji.py`（粗筛） |
| ④ 校验 | 改完确认没改错字 | `suwen_verify_punct.py`（★核心）、`scan_variants.py`、`build_suwen_buyi.py` |

## 常用命令

```bash
# 全库质量粗筛（清洗前观察格式 / 清洗后验收）
python tools/screen_guji.py
python tools/screen_guji.py --path 子平 --min-han 2000 --punct 0.05

# 逐字校验（以某次 git 提交为基准，检查当前文件内容未增删改）
python tools/suwen_verify_punct.py <git_ref> <文件路径>
```

## 核心方法论（两条，务必遵守）

1. **增量修改必须可校验**：批量改动写成 `{行号: 新内容}` 声明式脚本 → 执行 → 逐字校验 → git 提交。脚本即 diff，校验即测试。
2. **归一化后比对**：校验时先剥离标点/空格等无意义差异，再逐字比对；差异只允许出现在被剥离的字符集内。

## 注意与局限

- `screen_guji.py` **只是粗筛**：文件级标点密度正常 ≠ 卷内没有无标点段落（三命通会卷七曾漏报）。定位须"全库粗筛 + 章节段落级复核"两层。
- **底本豁免**：`*-全文.md` 且存在同名拆分目录的文件是底本，保留原始标记，不受装饰符检查约束。
- **保护字**：繁简转换不得动"乾坤/乾卦/乾造"之乾、"宫商角徵羽"之徵。

## 已废弃（保留供溯源，勿再使用）

- `split_ziping_chapters.ps1` ⚠️ — 机械拆分无法区分沈氏原文与徐乐吾评注，已改由权威底本重录重建。
- `split_ditianzhui_layers.ps1` ⚠️ — 只删【任氏曰】标记会残留案例命造，已改由状态机逐章剥离。

## 归档

- `_已归档-一次性脚本/` — 78 个素问逐篇断句脚本（内容已固化进古籍文件，**留档不留用**）。
