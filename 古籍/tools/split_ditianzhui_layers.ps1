# 滴天髓阐微 混排全文 -> 分层双文件 拆分脚本（机械处理，不改写正文）
#
# ⚠️ 已废弃（2026-09-10）：项目决策整体剥离任铁樵批注层，本脚本产出的
#    任注文件已删除、混排底本亦删除，不再使用。保留备查。
#    现行干净原文见：古籍/子平/滴天髓-原文与刘基原注-全本.md 与 古籍/子平/滴天髓/（64章）
#    另：本脚本"每章仅原文+原注"的产物并不干净——它只移除【任氏曰】标记块，
#    案例命造与任氏议论会残留在正文（实测残留 66 处案例命造）。如需再处理，
#    参照 2026-09-10 的清洗做法（先进剔除态、遇【原注】/【原文】/标题才退出）。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File 古籍/tools/split_ditianzhui_layers.ps1
# 输入：古籍/子平/滴天髓阐微-国学3000混排.md（fetch_guoxue3000.ps1 产出，含【原注】【任氏曰】标记）
# 输出：
#   古籍/子平/滴天髓-原文与刘基原注-全本.md（每章仅原文+原注，移除全部任氏曰块）
#   古籍/子平/滴天髓阐微-任铁樵批注-全本.md（原文+原注+任氏曰，任氏例命完整保留）
param(
  [string]$Mixed = '古籍/子平/滴天髓阐微-国学3000混排.md',
  [string]$OutYuan = '古籍/子平/滴天髓-原文与刘基原注-全本.md',
  [string]$OutRen = '古籍/子平/滴天髓阐微-任铁樵批注-全本.md'
)
$ErrorActionPreference = 'Stop'

$src = Get-Content -Raw -Path $Mixed -Encoding UTF8
$parts = [regex]::Split($src, '(?m)^(?=## )')
$sections = $parts | Select-Object -Skip 1

$y1 = New-Object System.Text.StringBuilder
$y2 = New-Object System.Text.StringBuilder
$stats = @()
foreach ($sec in $sections) {
  $lines = $sec -split "`n"
  $title = $lines[0].Trim()
  $inRen = $false
  $kept = New-Object System.Collections.Generic.List[string]
  foreach ($ln in $lines) {
    $t = $ln.Trim()
    # 识别两种来源标记变体：'【任氏曰】：' 与无括号的 '任氏曰；'
    if ($t -match '^【?任氏曰[】：:；;]?') { $inRen = $true; continue }
    if ($inRen) {
      # 任氏曰块结束条件：下一首诗（无空格、无【、长度<=60、非"一曰..八曰"小标题）
      $isPoem = ($t.Length -gt 0) -and ($t -notmatch '\s') -and ($t -notmatch '【') -and ($t.Length -le 60) -and ($t -notmatch '^[一二三四五六七八]曰')
      if ($isPoem) { $inRen = $false } else { continue }
    }
    [void]$kept.Add($ln)
  }
  $body1 = (($kept -join "`n").TrimEnd()) + "`n"
  [void]$y1.Append($body1); [void]$y1.AppendLine()
  [void]$y2.Append($sec.Trim()); [void]$y2.AppendLine(); [void]$y2.AppendLine()
  $stats += [pscustomobject]@{
    Title = $title
    RenBefore = ([regex]::Matches($sec, '【任氏曰】')).Count
    YuanAfter = ([regex]::Matches($body1, '【原注】')).Count
    RenAfter  = ([regex]::Matches($body1, '【任氏曰】')).Count
  }
}

$h1 = @"
> 书名：滴天髓（原文与刘基原注）｜作者：宋·京图撰、明·刘基原注｜朝代：宋/明
> 版本说明：国学3000 网页整理本（后出整理本；任注道光年间仅手抄稿流传，刊刻名目不一，内容有详略差异）
> 来源：https://guoxue3000.com/books/378（逐章 /chapters/N，N=2,4-37,39-67）
> 抓取日期：2026-08-12
> 完整性：全文（序+上篇34章+下篇29章=64章；站内无 ch38）
> 分层：原文=京图诗句；原注=刘基（本文件不含任铁樵批注；源页个别诗句原注无【原注】标记，已按原样保留）
> 拆分规则：自【任氏曰】起至下一首诗（无空格、≤60字、非"一曰…八曰"小标题）为止的段落已机械移除；生成后校验【任氏曰】残留=0

> **版本与引用警示：** 本文件所录为《滴天髓阐微》后出整理本。任注道光年间成书时仅手抄稿流传，刊刻名目不一（阐微/征义/增注玄彻通旨滴天髓命学指南），内容有详略差异；任氏"间有批驳增改"，不完全依循原意。引用必须分层标注：【原文】=京图诗句、【原注】=刘基、【任氏曰】=任铁樵。任氏立场与项目口径存在已知冲突（阴阳同生同死 vs 十干长生/火土同宫、废神煞 vs 天医、批"财为父" vs 《三命通会》女命口径），详见《skill/references/存伪去真-原典考证版.md》。
"@
$h2 = @"
> 书名：滴天髓阐微（任铁樵批注全本）｜作者：宋·京图撰、明·刘基原注、清·任铁樵阐微｜朝代：宋/明/清
> 版本说明：国学3000 网页整理本（后出整理本；任注道光年间仅手抄稿流传，刊刻名目不一，内容有详略差异；任氏例命完整保留）
> 来源：https://guoxue3000.com/books/378（逐章 /chapters/N，N=2,4-37,39-67）
> 抓取日期：2026-08-12
> 完整性：全文（序+上篇34章+下篇29章=64章；站内无 ch38）
> 分层：原文=京图诗句；原注=刘基；注家=任铁樵【任氏曰】（任氏例命完整保留）

> **版本与引用警示：** 本文件所录为《滴天髓阐微》后出整理本。任注道光年间成书时仅手抄稿流传，刊刻名目不一（阐微/征义/增注玄彻通旨滴天髓命学指南），内容有详略差异；任氏"间有批驳增改"，不完全依循原意。引用必须分层标注：【原文】=京图诗句、【原注】=刘基、【任氏曰】=任铁樵。任氏立场与项目口径存在已知冲突（阴阳同生同死 vs 十干长生/火土同宫、废神煞 vs 天医、批"财为父" vs 《三命通会》女命口径），详见《skill/references/存伪去真-原典考证版.md》。
"@

$out1 = $h1 + "`n`n" + $y1.ToString()
$out2 = $h2 + "`n`n" + $y2.ToString()
Set-Content -Path $OutYuan -Value $out1 -Encoding utf8
Set-Content -Path $OutRen -Value $out2 -Encoding utf8

$stats | Format-Table -AutoSize
Write-Output ("文件1(原文+原注)=" + $OutYuan + " 字符数=" + $out1.Length)
Write-Output ("文件2(任批注全本)=" + $OutRen + " 字符数=" + $out2.Length)
