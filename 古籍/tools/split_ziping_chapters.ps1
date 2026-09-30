# -*- powershell -*-
# 拆分滴天髓（64章，三层标注）与子平真诠（44章，原文/徐注/林注分层），并生成章索引与子平总README。
$ErrorActionPreference = 'Stop'
$root = '\古籍\子平'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Split-ByHeading {
  param([string]$Path, [string]$Pattern, [int]$TitleGroup = 1, [int]$SeqGroup = 0)
  $lines = Get-Content -Encoding UTF8 $Path
  $chunks = @()
  $curTitle = $null
  $cur = New-Object System.Collections.Generic.List[string]
  $rx = [regex]$Pattern
  foreach ($ln in $lines) {
    $m = $rx.Match($ln)
    if ($m.Success) {
      if ($null -ne $curTitle) { $chunks += [pscustomobject]@{Title=$curTitle; Seq=$curSeq; Body=($cur -join "`n")} }
      $curTitle = $m.Groups[$TitleGroup].Value.Trim()
      $curSeq = if ($SeqGroup -gt 0) { $m.Groups[$SeqGroup].Value.Trim() } else { '' }
      $cur = New-Object System.Collections.Generic.List[string]
    } else {
      [void]$cur.Add($ln)
    }
  }
  if ($null -ne $curTitle) { $chunks += [pscustomobject]@{Title=$curTitle; Seq=$curSeq; Body=($cur -join "`n")} }
  return ,$chunks
}

function SafeName([string]$t) { return ($t -replace '[\\/:*?"<>|]', '_') }

# ---------- 滴天髓 ----------
$dSrc = Join-Path $root '滴天髓阐微-国学3000混排.md'
# ⚠️ 已废弃（2026-09-10）：$dSrc 混排底本已删除，本脚本产出的 64 章本含【任氏曰】层，
#    现行 64 章本已剥离任注（见 古籍/子平/滴天髓/）。保留备查。
$dOut = Join-Path $root '滴天髓'
if (-not (Test-Path $dOut)) { New-Item -ItemType Directory -Path $dOut | Out-Null }
$dChunks = Split-ByHeading -Path $dSrc -Pattern '^## (.+)$'
Write-Host ("滴天髓章数: " + $dChunks.Count)
$dRows = @()
for ($i = 0; $i -lt $dChunks.Count; $i++) {
  $nn = '{0:D2}' -f $i
  $safe = SafeName $dChunks[$i].Title
  $fn = Join-Path $dOut ($nn + '-' + $safe + '.md')
  $content = "# $($dChunks[$i].Title)`n`n> 书名：滴天髓阐微（64章分层本）｜分层底本：古籍/子平/滴天髓阐微-国学3000混排.md`n> 章序：$($i+1)/64｜分层：【原文】京图诗句、【原注】刘基、【任氏曰】任铁樵`n> 抓取日期：2026-08-12`n`n$($dChunks[$i].Body.Trim())`n"
  [System.IO.File]::WriteAllText($fn, $content, $utf8)
  $dRows += [pscustomobject]@{Seq=$nn; Name=$dChunks[$i].Title; File="古籍/子平/滴天髓/$nn-$safe.md"}
}
$dIdx = "# 滴天髓（64章）章索引`n`n> 项目路径：古籍/子平/滴天髓/`n> 分层底本：古籍/子平/滴天髓阐微-国学3000混排.md；另存全本：滴天髓-原文与刘基原注-全本.md（【原文】+【原注】）、滴天髓阐微-任铁樵批注-全本.md（含【任氏曰】及例命）`n> 分层：【原文】京图诗句、【原注】刘基、【任氏曰】任铁樵`n`n| 章序 | 章名 | 文件 |`n| --- | --- | --- |`n"
foreach ($r in $dRows) { $dIdx += "| $($r.Seq) | $($r.Name) | $($r.File) |`n" }
[System.IO.File]::WriteAllText((Join-Path $dOut 'AGENTS.md'), $dIdx, $utf8)

# ---------- 子平真诠 ----------
$zSrc = Join-Path $root '子平真诠评注-全文.md'
$zOut = Join-Path $root '子平真诠'
if (-not (Test-Path $zOut)) { New-Item -ItemType Directory -Path $zOut | Out-Null }
$zChunks = Split-ByHeading -Path $zSrc -Pattern '^## 《子平真诠评注》第 (\d+) 章 (.+)$' -TitleGroup 2 -SeqGroup 1
Write-Host ("子平真诠章数: " + $zChunks.Count)
$zRows = @()
foreach ($c in $zChunks) {
  $nn = '{0:D2}' -f [int]$c.Seq
  $safe = SafeName $c.Title
  $fn = Join-Path $zOut ($nn + '-' + $safe + '.md')
  $content = "# $($c.Title)`n`n> 书名：子平真诠评注｜分层底本：古籍/子平/子平真诠评注-全文.md`n> 章序：$nn/44｜分层：【原文】沈孝瞻（原文：起）、【徐注】徐乐吾（徐注：起）、【林注】林君毅（（林注：…））`n> 抓取日期：2026-08-12`n`n$($c.Body.Trim())`n"
  [System.IO.File]::WriteAllText($fn, $content, $utf8)
  $zRows += [pscustomobject]@{Seq=$nn; Name=$c.Title; File="古籍/子平/子平真诠/$nn-$safe.md"}
}
$zIdx = "# 子平真诠（44章）章索引`n`n> 项目路径：古籍/子平/子平真诠/`n> 分层底本：古籍/子平/子平真诠评注-全文.md`n> 分层：【原文】沈氏（原文：起）、【徐注】徐乐吾（徐注：起）、【林注】林君毅（（林注：…））`n`n| 章序 | 章名 | 文件 |`n| --- | --- | --- |`n"
foreach ($r in $zRows) { $zIdx += "| $($r.Seq) | $($r.Name) | $($r.File) |`n" }
[System.IO.File]::WriteAllText((Join-Path $zOut 'AGENTS.md'), $zIdx, $utf8)

Write-Host "滴天髓/子平真诠拆分完成"
