# 殆知阁 daizhigev20 GitHub 镜像古籍全文抓取脚本（纯 markdown，带标点）
# 用法（需联网，运行时需提权；Invoke-WebRequest 前缀已授权）：
#   powershell -ExecutionPolicy Bypass -File 古籍/tools/fetch_mirror.ps1 `
#     -RepoPath "易藏/术数/渊海子平.md" `
#     -OutFile "古籍/子平/渊海子平/渊海子平-全文.md" `
#     -BookName "渊海子平" -Author "徐大升" -Dynasty "宋" `
#     -LayerNote "原文=全书正文" -Completeness "全文"
# 说明：自动剥离 YAML front matter；正文原样落盘（不改写内容）；UTF-8 无 BOM。
param(
  [Parameter(Mandatory = $true)][string]$RepoPath,
  [Parameter(Mandatory = $true)][string]$OutFile,
  [string]$BookName,
  [string]$Author = '',
  [string]$Dynasty = '',
  [string]$VersionNote = '殆知阁 daizhigev20 镜像 md 版（frankslin/daizhigev20，data 分支，2025-09-16 由 txt 转换，正文带标点与分段）',
  [string]$LayerNote = '原文=全书正文',
  [string]$Completeness = '全文'
)
$ErrorActionPreference = 'Stop'
$base = 'https://raw.githubusercontent.com/frankslin/daizhigev20/data/'
$url = $base + [uri]::EscapeDataString($RepoPath)
$resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 180
$text = $resp.Content
# 剥离 YAML front matter：首行是 --- 时，跳到下一个 --- 行，之后全是正文
$lines = $text -split "`n"
if ($lines.Count -gt 0 -and $lines[0].Trim() -eq '---') {
  $i = 1
  while ($i -lt $lines.Count -and $lines[$i].Trim() -ne '---') { $i++ }
  if ($i -lt $lines.Count) { $lines = $lines[($i + 1)..($lines.Count - 1)] }
}
$text = (($lines -join "`n") -replace "`r", '')
$text = (($text -split "`n" | ForEach-Object { $_.TrimEnd() }) -join "`n").Trim()
$srcUrl = 'https://github.com/frankslin/daizhigev20/blob/data/' + $RepoPath
$header = @"
> 书名：$BookName｜作者：$Author｜朝代：$Dynasty
> 版本说明：$VersionNote
> 来源：$srcUrl
> 抓取日期：2026-08-12
> 完整性：$Completeness
> 分层：$LayerNote
"@
$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$out = $header + "`n`n" + $text
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $OutFile), $out, (New-Object System.Text.UTF8Encoding($false)))
$first = (($text.Substring(0, [Math]::Min(60, $text.Length))) -replace "`n", ' ')
Write-Output ("OK chars=" + $text.Length + "  ->  " + $OutFile + "  |  " + $first)
