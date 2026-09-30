# 古籍知识库 · 分层检索与检索评测

<p>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green.svg">
  <img alt="corpus" src="https://img.shields.io/badge/corpus-1543%20files%20%C2%B7%2027MB-blue.svg">
  <img alt="eval" src="https://img.shields.io/badge/retrieval%20eval-462%20queries-orange.svg">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB.svg">
</p>

> 把上千个文言古籍文件做成**可追溯、可分层引用、可评测**的知识库。
> 核心不是「让模型读古文」，而是**回答时能说清楚这句话到底出自哪一层**。

---

## 为什么这件事不简单

拿通用 RAG 硬套古籍，会踩三个坑：

1. **底本质量参差、原文与后人评注混排**，正则切不干净，一句话可能同时混着唐宋正文和民国批注。
2. **通用向量检索在专有领域召回不可靠**——问一个精确概念，回来的常常是「看起来很相关」的另一段。
3. **最要命的一条：整理成果会被当成原文引用。** 项目自己写的章旨、疏解、检索词，
   一旦混进检索结果，模型就会把现代人的注解当成古人原话输出。

这个项目针对的就是第 3 条 —— **引用必须可分层归因**。

---

## 核心设计

### 1. 六层引用模型

全库 690 种小节标题被归入六个层级，取用时**逐层标注、逐层约束**：

| 层 | 内容 | 能否作为原文引用 |
| --- | --- | --- |
| 原文层 | 底本正文 | ✅ 可直接引用 |
| 原文层·古注 | 底本自带原注（如刘基原注） | ✅ 引用须注明为原注 |
| 概念条目层 | 由原文条文重组的定义 / 查法 / 用法 | ✅ 与底本歧异时以底本为准 |
| 项目自撰注解层 | 章旨 / 疏解 / 关联章节 / 索引表 | ❌ 不得标为原文 |
| 项目整理层 | 白话释 / 规则条目 | ❌ 引用须回底本原文 |
| 注家层 | 徐乐吾注、任铁樵批注等 | ❌ 不入主库、禁止引用 |

这一层判断写在工具里（`SOURCE_NAMES` / `CONCEPT_NAMES` / `PROJECT_NAMES` / `COMMENTARY_PATTERN`），
不靠提示词叮嘱 —— **模型可以忘，代码不会忘。**

### 2. 按节取用，而不是整文件读

条目级文件的次序是「原文 → 章旨 → 疏解」，疏解在文件末尾，中间还夹着大段表格。
用 `read` 按行切片，读前 40 行会整段丢掉疏解（实测 148 个文件里有 7 个、最坏 10 行全丢）。

所以有了 `get_section`：按 `## ` / `### ` 锚点切节，**Markdown 源零改动**，
可只取「疏解」下的某个子节，上下文占用比整取小一个数量级。

```js
get_section({ path: "古籍/子平/穷通宝鉴/06-戊土/12-十一、十二月戊土.md", section: "疏解" })
// 省略 section → 返回分节索引（含行号与所属层）
```

### 3. 三级导航 + 渐进式披露，不建向量库

不用嵌入管线、不用向量数据库。索引就是 Markdown 本身：
**领域 → 书 → 节**三级导航，模型按需逐级下钻，只把命中的那一节带进上下文。

代价是多一次导航决策，收益是：零嵌入成本、零向量库运维、人类可读、**每次召回都可在文件系统里回溯**。

### 4. 评测的防循环论证红线

检索评测最容易自欺：拿加工产物去检索，数字当然好看。所以定了四条不可违反的隔离纪律：

| # | 纪律 | 检查方式 |
| --- | --- | --- |
| R1 | QAG 臂的索引**只允许来自原文层**，注解层一个字都不进 | 建库时断言 chunk 不含注解层标记 + 交叉扫描 |
| R2 | 结构法臂才允许用注解层（它本身就是被评测的处理方法） | 反向断言 |
| R3 | query 生成器**只见原文**，不得见标题 / 章旨 / 疏解 / 检索词 | prompt 只插 `orig` + `note` |
| R4 | gold 与两臂共用同一来源，不得各标各的 | 单一 `queries.jsonl` |

---

## 检索评测

**语料**：259 个分层重建单元（《子平真诠》47 章 +《滴天髓》64 章 +《穷通宝鉴》148 节）
**测试集**：518 条生成 → 剔除占位节与零可答漂移题 → **462 条有效题**（user 口语 212 + analyst 检索式 250），覆盖全部 252 个可评测节
**gold 校准**：TREC pooling（汇集各臂 top-5 ≈ 均长 19 节）+ LLM 逐题判定「能否直接作为回答依据」，只给原文不给注解

### 单次检索（无重排）

| 臂 | 索引内容 | R@1 | R@3 | R@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| **struct-full** | 标题＋章旨＋检索词＋疏解 | **48.7%** | **70.3%** | 77.5% | 0.597 |
| raw-emb | 原文切块直嵌（对照） | **48.7%** | 68.8% | **78.8%** | 0.598 |
| qag-ema | QAG（问题＋答案） | 43.5% | 64.7% | 71.4% | 0.544 |
| struct-thin | 标题＋章旨＋检索词 | 39.0% | 59.7% | 68.2% | 0.498 |
| qag-emb | QAG（只嵌生成的问题） | 38.3% | 57.6% | 65.2% | 0.485 |

> 结构法 vs 标准 QAG：R@5 相对 **+18.9%**、R@1 相对 **+27.2%**。

### 同款 LLM 重排后（统一 top-20 候选）

| 臂 | 候选池上限 | R@1 | R@3 | R@5 |
| --- | --- | --- | --- | --- |
| **三级导航（无向量库）** | 93.5% | 87.9% | 92.4% | **93.1%** |
| struct-full | 93.3% | 88.1% | 92.2% | **93.1%** |
| raw-emb | 92.9% | **88.3%** | 91.3% | 92.2% |
| qag-ema | 90.7% | 83.5% | 88.3% | 89.0% |
| qag-emb | 84.0% | 76.2% | 81.0% | 82.5% |

**两条结论**：

* QAG 是全场最弱的索引方式，即使配上同款重排仍垫底 —— **"生成问答对"这一步本身有损**（候选池上限只有 84.0%，原文/结构法为 92.9%/93.5%）。
* 三级导航不建向量库，召回与向量方案打平。**结构化知识库的收益不在召回率，而在引用分层、可校验、免向量库。**

完整报告见 [`古籍/eval/RESULTS.md`](古籍/eval/RESULTS.md)，评测协议见 [`古籍/eval/README.md`](古籍/eval/README.md)。

---

## 语料

| 领域 | 文件数 | 代表典籍 |
| --- | --- | --- |
| 子平 | 857 | 三命通会（12 卷）、滴天髓（64 章）、子平真诠（44 章）、渊海子平、神峰通考、穷通宝鉴 |
| 内经 | 317 | 素问（81 篇 + 王冰注本）、灵枢（81 篇）、难经（81 难）、脾胃论 |
| 六壬 | 129 | 六壬大全（12 卷）、御定六壬直指（60 日 720 局）、壬归（42 节）、大六壬指南 |
| 易学 | 74 | 周易（64 卦 + 十翼）、易纬乾凿度 |
| 五行 | 11 | 五行大义、淮南子天文墬形、尚书洪范 |
| 天文地理 | 4 | 史记天官书、汉书律历志 |

采集规范：全文、纯文本、统一简体（乾/徵按语境保留）、**原文 / 原注 / 注家分层**、UTF-8 无 BOM。

质量缺口是**登记在册**的，不是假装没有 —— 见 [`古籍/README.md`](古籍/README.md) 的「已登记的质量缺口」一节，
里面写着哪几篇缺注源、哪些异体字已修正、哪些疑似脱字待善本对校。

---

## 快速开始

```bash
# 语料即文档，无构建步骤。检索工具是 Pi Coding Agent 扩展：
#   .pi/extensions/guji-tools/index.ts   —— 按节取用 + 分层归因
#   .pi/extensions/subagent/index.ts     —— 子代理委派（single / parallel / chain）

# 检索评测（三书，需 Python 3.10+ 与嵌入模型）
cd 古籍/eval
python build_corpus.py        # 从 Markdown 重建分节语料
python gen_queries.py         # 生成 query（只见原文层）
python run_eval.py            # 跑各臂召回
python rerank_compare.py      # 同款重排对比
```

---

## 目录结构

```
.
├── .pi/extensions/
│   ├── guji-tools/        # 按节取用 + 六层归因（核心检索工具）
│   └── subagent/          # 子代理委派：single / parallel / chain
└── 古籍/
    ├── README.md          # 总索引 + 已登记的质量缺口
    ├── AGENTS.md          # 采集与分层规范
    ├── 子平/ 内经/ 六壬/ 易学/ 五行/ 天文地理/
    ├── guwen-cleaning/    # 清洗与校验脚本
    ├── tools/             # 拆分 / 比对 / 取节辅助
    └── eval/              # 检索评测：语料构建、query 生成、四臂对比、重排、结果报告
```

---

## 几个工程细节

* **通用拆分脚本适配 14 本书**：把「按卷/章/节切分」的规则抽象成一套可配置切分器，
  而不是给每本书写一个脚本。
* **改动可溯源**：用「行号 + 新内容」脚本批量替换数万字正文，校验时**剥掉标点逐字比对**，
  确认差异只出现在标点位置后才分批提交。
* **底本混排就换权威底本**：发现某卷原文与评注混排无法机械切分时，不用启发式硬切，
  改用权威底本重建该卷。
* **多代理方案被否**：上下文与知识库隔离成本过高，多出的 token 开销没换来准确率提升；
  单 Agent + 三级导航只把所需内容带进上下文，token 与延迟可控。

---

## 通用性

里层的技术不是古籍专属的：

* **分层归因**适用于任何「原文 + 后人加工」并存的语料 —— 法条与释义、代码与注释、论文与综述。
* **按锚点取节**是一个通用的长文档检索原语，与具体 Agent 框架无关。
* **防循环论证的四条红线**可以直接抄到任何检索评测里。

`.pi/extensions/` 是适配层；上面这些才是主体。

---

## License

[MIT](LICENSE) —— 代码与脚本适用。

古籍原文属公有领域；各底本的整理成果、校勘记与登记信息请在使用时注明来源。

<details>
<summary>English</summary>

**Classics Knowledge Base** — a layered, traceable retrieval system over ~1,500 files of
classical Chinese texts, with a 462-query retrieval benchmark.

The core idea: every retrieved passage carries a **provenance layer** (source text / original
annotation / concept entry / project-authored commentary / derived notes / later commentators),
and only the first three may ever be quoted as source text. Query generation, gold labelling
and indexing are kept isolated by four explicit anti-circularity rules.

Structured knowledge base (R@5 77.5%) beats QAG (65.2%) under identical single-pass retrieval;
a three-level navigation index reaches R@5 93.1% with **no vector database at all**.
</details>
