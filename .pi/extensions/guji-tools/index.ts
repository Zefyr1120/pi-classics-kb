/**
 * guji-tools — 古籍库「按节取用」工具（项目自撰，2026-09-15）
 *
 * 为什么需要它（实测依据）
 * - 条目级文件的次序是：原文（＋命例表）→ ## 章旨 → ## 疏解。【疏解】在文件末尾，
 *   而命例表把它顶到第 28–50 行；`read` 只能按 offset/limit 切片，于是「读前 40 行」
 *   会整段丢掉疏解（实测：148 个文件中 7 个的疏解内容越过第 40 行；最坏 10 行全丢）。
 * - 「按键取用」是**工具能力**，不是文件格式：JSON 化解决不了它（子代理工具白名单
 *   只有 read/grep/find/ls，没有解析器）。本工具按 `## ` 锚点切节，MD 源零改动。
 * - 2026-09-15 追加：支持 `### ` 子节。《滴天髓》64 章的【疏解】内含固定五个子节
 *   （句解／判定链位置／操作读法／易误读／存疑），逐节取用比整取疏解更省上下文；
 *   子节层继承父节（不单列层名）。
 *
 * 附带收益：按「层」返回，机械隔离——
 *   头部元信息（标题＋`>` 头注；含 `## 原文` 的文件中，此块勿引）
 *   原文层（原文／命例；含底本自带古注如《滴天髓》刘基原注）→ 可引用（另采源须带版本，古注须注明）
 *   概念条目层（《渊海子平》定义／查法／用法／诗诀等）→ 可引用；与底本歧异时以底本为准
 *   项目自撰注解层（章旨／疏解／关联章节／关联条目／索引表）、项目整理层（白话释／规则条目）→ 不得作为原文引用
 *   注家层（徐乐吾注、任铁樵批注等）                                      → 禁止引用、不入主库
 *
 * 子节：`### ` 子节随父节归属（如《滴天髓》的 句解／判定链位置／操作读法／易误读／存疑 在 `## 疏解` 内）；
 * 可直接用子节名取用（只在二级节未命中时才回退到子节）。
 *
 * 用法：get_section({ path: "古籍/子平/穷通宝鉴/06-戊土/12-十一、十二月戊土.md", section: "疏解" })
 *      省略 section → 返回分节索引（含行号与层）
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MAX_BYTES = 2 * 1024 * 1024;
const LAYER_SOURCE = "原文层";
const LAYER_SOURCE_ANCIENT = "原文层·古注（与原文同层，可引用；须注明为原注）";
const LAYER_SOURCE_CONCEPT = "概念条目层（原文条文重组，可引用；与底本歧异时以底本为准）";
const LAYER_PROJECT = "项目自撰注解层（非原文，引用时不得标为本派原文）";
const LAYER_DERIVED = "项目整理层（依原文归纳，非原文；引用须回底本原文）";
const LAYER_COMMENTARY = "注家层（禁止引用，不入主库）";
const LAYER_UNKNOWN = "未分类（勿当原文引用）";

/** 全库实测的节名→层映射（数据源：古籍库 690 种 `## ` 标题的频次清单） */
const SOURCE_NAMES = new Set(["原文", "卦辞", "彖传（彖曰）", "象传·大象", "爻辞与小象"]);
const CONCEPT_NAMES = new Set(["定义", "查法", "用法", "诗诀（对照整理）", "禁忌/注意事项", "诗诀"]);
const PROJECT_NAMES = new Set(["章旨", "疏解", "关联章节", "关联条目", "注解", "月令速查", "检索表", "四季索引（月令 → 分节文件）"]);
const DERIVED_NAMES = new Set(["规则条目", "白话释（主题归纳）", "与前卷关联", "本卷概览", "四时索引表"]);
const COMMENTARY_PATTERN = /徐乐吾|任铁樵|评注|批注|眉批|阐微|原注系/;

interface Sub {
	name: string;
	start: number; // 1-based，含
	end: number; // 1-based，含
}

interface Block {
	name: string;
	start: number; // 1-based，含
	end: number; // 1-based，含
	layer: string;
	subs: Sub[];
}

function layerOf(name: string): string {
	const n = name.trim();
	// 底本层：原文及其所附命例；底本自带古注（如《滴天髓》刘基原注）
	if (SOURCE_NAMES.has(n) || n.includes("命例")) return LAYER_SOURCE;
	if (n === "原注") return LAYER_SOURCE_ANCIENT;
	// 概念条目层（《渊海子平》概念条目：原文条文重组）
	if (CONCEPT_NAMES.has(n)) return LAYER_SOURCE_CONCEPT;
	// 项目自撰注解层（《注解规范》：章旨／疏解／关联章节）
	if (PROJECT_NAMES.has(n) || /^(索引|速查|概览)/.test(n) || n.includes("索引")) return LAYER_PROJECT;
	// 项目整理层（依原文归纳：三命通会各「…解」文件）
	if (DERIVED_NAMES.has(n) || /归纳|对照整理|提要/.test(n)) return LAYER_DERIVED;
	// 注家层：只认具体注家名（**不用**裸「注／批／评」，否则“注意事项”会被误判）
	if (COMMENTARY_PATTERN.test(n)) return LAYER_COMMENTARY;
	return LAYER_UNKNOWN;
}

function parseBlocks(text: string): { lines: string[]; blocks: Block[] } {
	const lines = text.split(/\r?\n/);
	const marks: { name: string; i: number }[] = [];
	for (let i = 0; i < lines.length; i++) {
		const m = /^##\s+(.+?)\s*$/.exec(lines[i]);
		if (m) marks.push({ name: m[1].replace(/[【】「」]/g, "").trim(), i });
	}
	const blocks: Block[] = [];
	const hasYuanwen = marks.some((m) => m.name === "原文");
	const firstMark = marks.length > 0 ? marks[0].i : lines.length;
	if (firstMark > 0) {
		// 首个 ## 之前的块：
		//  - 文件有 `## 原文` → 这块是头部元信息（正文在 `## 原文`）
		//  - 无 `## 原文` 但有真实正文行（旧结构）→ 这块就是原文
		//  - 无 `## 原文` 且只有标题与 `>` 头注（索引类文件）→ 头部元信息
		const preLines = lines.slice(0, firstMark);
		const hasRealBody = preLines.some((l) => {
			const s = l.trim();
			return s !== "" && !s.startsWith(">") && !s.startsWith("#");
		});
		if (hasYuanwen) {
			blocks.push({ name: "头部元信息", start: 1, end: firstMark, layer: "元信息（正文见 `## 原文`，勿引本块）", subs: [] });
		} else if (hasRealBody) {
			blocks.push({ name: "原文层正文", start: 1, end: firstMark, layer: LAYER_SOURCE, subs: [] });
		} else {
			blocks.push({ name: "头部元信息", start: 1, end: firstMark, layer: "元信息（本文件为索引/导航，无原文）", subs: [] });
		}
	}
	for (let k = 0; k < marks.length; k++) {
		const next = k + 1 < marks.length ? marks[k + 1].i : lines.length;
		const name = marks[k].name;
		// 三级子节（仅存档行号供取用；层继承父节）
		const subMarks: { name: string; i: number }[] = [];
		for (let i = marks[k].i + 1; i < next; i++) {
			const sm = /^###\s+(.+?)\s*$/.exec(lines[i]);
			if (sm) subMarks.push({ name: sm[1].replace(/[【】「」]/g, "").trim(), i });
		}
		const subs: Sub[] = subMarks.map((s, idx) => ({
			name: s.name,
			start: s.i + 2,
			end: idx + 1 < subMarks.length ? subMarks[idx + 1].i : next,
		}));
		blocks.push({ name, start: marks[k].i + 2, end: next, layer: layerOf(name), subs });
	}
	return { lines, blocks };
}

function subCandidates(blocks: Block[], norm: string): { parent: string; name: string }[] {
	const exact: { parent: string; name: string }[] = [];
	for (const b of blocks) for (const s of b.subs) if (s.name === norm) exact.push({ parent: b.name, name: s.name });
	if (exact.length > 0) return exact;
	const part: { parent: string; name: string }[] = [];
	for (const b of blocks) for (const s of b.subs) if (s.name.includes(norm)) part.push({ parent: b.name, name: s.name });
	return part;
}

function pick(blocks: Block[], q: string): { names: string[]; sub?: { parent: string; name: string } } | { error: string; hint: string } {
	const norm = q.replace(/[【】「」\s]/g, "");
	if (norm === "注解") return { names: ["章旨", "疏解"].filter((n) => blocks.some((b) => b.name === n)) };
	if (norm === "原文" || norm === "正文" || norm === "source") {
		const real = blocks.find((b) => b.name === "原文");
		return { names: [real ? real.name : "原文层正文"] };
	}
	const exact = blocks.filter((b) => b.name === norm);
	if (exact.length === 1) return { names: [exact[0].name] };
	if (exact.length > 1) return { error: `节名「${norm}」重复出现 ${exact.length} 次`, hint: "请用更完整的节名（见分节索引）" };
	const partial = blocks.filter((b) => b.name.includes(norm));
	if (partial.length === 1) return { names: [partial[0].name] };
	if (partial.length > 1) {
		return { error: `节名「${norm}」命中多个`, hint: `候选：${partial.map((b) => b.name).join("、")}` };
	}
	// 二级节未命中时，回退到三级子节（如 句解／判定链位置／操作读法／易误读／存疑）
	const subs = subCandidates(blocks, norm);
	if (subs.length === 1) return { names: [], sub: subs[0] };
	if (subs.length > 1) {
		return { error: `子节名「${norm}」命中多个`, hint: `候选：${subs.map((s) => `${s.parent} › ${s.name}`).join("、")}` };
	}
	return { error: `未找到节「${norm}」`, hint: "省略 section 参数可列出该文件全部分节与子节" };
}

function indexText(rel: string, blocks: Block[]): string {
	const subTotal = blocks.reduce((n, b) => n + b.subs.length, 0);
	const rows: string[] = [];
	for (const b of blocks) {
		rows.push(`  · ${b.name}　第 ${b.start}–${b.end} 行　[${b.layer}]`);
		b.subs.forEach((s, i) => {
			rows.push(`      ${i === b.subs.length - 1 ? "└" : "├"} ${s.name}　第 ${s.start}–${s.end} 行`);
		});
	}
	const extra = subTotal > 0 ? `；内含 ${subTotal} 个子节，可直接按子节名取用` : "";
	return `【分节索引】${rel}（共 ${blocks.length} 节${extra}）\n${rows.join("\n")}\n\n用法：get_section({ path: "…", section: "疏解" })（section 省略即此索引；子节名如 句解／判定链位置／操作读法／易误读／存疑）`;
}

const getSectionTool = defineTool({
	name: "get_section",
	label: "Get Section",
	description:
		"按 `## 标题`（或 `### 子节`）锚点读取单个文件中的指定节，并标注该节所属层（原文层／项目自撰注解层／注家层）。用于避免 read 按行切片截断文末内容（如条目文件的【疏解】）。section 省略时返回分节索引（含子节）。",
	promptSnippet: "按节读取文件（原文层／注解层／注家层，带行号与层标注；支持 ### 子节）",
	parameters: Type.Object({
		path: Type.String({ description: "文件路径（相对项目目录，或项目内的绝对路径）" }),
		section: Type.Optional(
			Type.String({
				description:
					"节名，如 疏解／章旨／原文／命例；子节名如 句解／判定链位置／操作读法／易误读／存疑（《滴天髓》）；「注解」＝章旨＋疏解；省略＝返回分节索引",
			}),
		),
	}),

	async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
		const root = path.resolve(ctx.cwd);
		const abs = path.isAbsolute(params.path) ? path.resolve(params.path) : path.resolve(root, params.path);
		if (abs !== root && !abs.startsWith(root + path.sep)) {
			return { content: [{ type: "text", text: `拒绝：路径超出项目目录（${root}）` }], isError: true };
		}
		let text: string;
		try {
			const st = fs.statSync(abs);
			if (st.size > MAX_BYTES) {
				return {
					content: [{ type: "text", text: `拒绝：文件 ${(st.size / 1024).toFixed(0)} KB，超过 ${MAX_BYTES / 1024 / 1024} MB 上限` }],
					isError: true,
				};
			}
			text = fs.readFileSync(abs, "utf-8");
		} catch {
			return { content: [{ type: "text", text: `读取失败：${abs}` }], isError: true };
		}

		const rel = path.relative(root, abs).split(path.sep).join("/") || abs;
		const { lines, blocks } = parseBlocks(text);
		const head = lines.slice(0, blocks[0]?.end ?? 0).join("\n");
		const alt = /另采源/.test(head);
		const provenance = alt
			? "\n【来源标注】文件头注含「另采源」——该文件原文层内容引用须带版本（问真版徐乐吾评注本），不得与底本混引"
			: "";

		if (!params.section || !params.section.trim() || params.section.trim() === "list") {
			return { content: [{ type: "text", text: indexText(rel, blocks) + provenance }] };
		}

		const picked = pick(blocks, params.section);
		if ("error" in picked) {
			return {
				content: [{ type: "text", text: `${picked.error}｜${picked.hint}\n\n${indexText(rel, blocks)}` }],
				isError: true,
			};
		}
		const names = picked.names;
		const sub = "sub" in picked ? picked.sub : undefined;
		if (!sub && names.length === 0) {
			return { content: [{ type: "text", text: `该文件无此节\n\n${indexText(rel, blocks)}` }], isError: true };
		}
		let bodies: { b: Block; text: string }[];
		if (sub) {
			const parent = blocks.find((x) => x.name === sub.parent)!;
			const s = parent.subs.find((x) => x.name === sub.name)!;
			bodies = [
				{
					b: { name: `${parent.name} › ${s.name}`, start: s.start, end: s.end, layer: `${parent.layer}·子节（层随父节）`, subs: [] },
					text: lines.slice(s.start - 1, s.end).join("\n").replace(/\s+$/, ""),
				},
			];
		} else {
			bodies = names.map((n) => {
				const b = blocks.find((x) => x.name === n)!;
				return { b, text: lines.slice(b.start - 1, b.end).join("\n").replace(/\s+$/, "") };
			});
		}
		const header = bodies
			.map(({ b }) => `【取节】${rel} · 「${b.name}」第 ${b.start}–${b.end} 行\n【层】${b.layer}`)
			.join("\n");
		const body = bodies.map((x) => x.text).join("\n\n————\n\n");
		return {
			content: [{ type: "text", text: `${header}${provenance}\n────────────────\n${body}` }],
			details: { path: rel, sections: sub ? [`${sub.parent} › ${sub.name}`] : names, lines: bodies.map((x) => [x.b.start, x.b.end]) },
		};
	},
});

export default function (pi: ExtensionAPI) {
	pi.registerTool(getSectionTool);
}
