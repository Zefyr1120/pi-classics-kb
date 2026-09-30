# -*- coding: utf-8 -*-
"""素问王冰注本断句内容完整性校验工具。

用法：
    python suwen_verify_punct.py <git_ref> <文件路径>

以 git_ref 版本为原文基准，检查当前文件的内容完整性：
1. 两侧都去掉标点（，。；：？！、、“”《》 与 ASCII 直引号 "），
   因此引号风格差异（直引号/弯引号）不会误报；
2. 去掉标点后，其余字符必须逐字一致（不增删、不改序、不改字）；
3. 全角空格 U+3000 与换行视为格式字符，另行统计，不并入实质差异。

输出：
- [实质差异] 真正增删改字（或头部说明文字有意更新），需人工核对；
- [空格差异] 仅全角空格增删（断句时为“新校正云”等标记前统一加 　 属合规）。
"""
import io
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PUNCT = set("，。；：？！、“”《》\"")


def git_show(ref: str, path: str) -> list:
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        cwd=r"",
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace"))
    text = out.stdout.decode("utf-8-sig")
    return text.splitlines()


def strip_punct(line: str, extra: set) -> str:
    return "".join(ch for ch in line if ch not in PUNCT and ch not in extra)


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    ref, path = sys.argv[1], sys.argv[2]
    old = git_show(ref, path)
    with open(path, encoding="utf-8-sig") as f:
        new = f.read().splitlines()

    real_diff = []
    space_only = []
    changed = 0
    for i, n in enumerate(new):
        o = old[i] if i < len(old) else ""
        if o == n:
            continue
        changed += 1
        stripped_new = strip_punct(n, set())
        stripped_old = strip_punct(o, set())
        if stripped_new == stripped_old:
            continue
        new_no_space = stripped_new.replace("\u3000", "")
        old_no_space = stripped_old.replace("\u3000", "")
        if new_no_space == old_no_space:
            space_only.append(i + 1)
        else:
            real_diff.append((i + 1, stripped_old, stripped_new))

    print(f"旧版行数 {len(old)} / 现行数 {len(new)}")
    print(f"改动行数 {changed}")
    print(f"仅全角空格增删 {len(space_only)} 行: {space_only[:40]}")
    print(f"实质差异 {len(real_diff)} 行")
    for lineno, o, s in real_diff[:12]:
        m = max(len(o), len(s))
        diffs = []
        for j in range(m):
            oc = o[j] if j < len(o) else ""
            nc = s[j] if j < len(s) else ""
            if oc != nc:
                diffs.append(f"{j}:[{oc}]->[{nc}]")
        print(f"  行 {lineno} ({len(diffs)} 处): {diffs[:10]}")


if __name__ == "__main__":
    main()
