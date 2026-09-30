# 殆知阁 GitHub 镜像（daizhigev20）古籍 markdown 全文抓取脚本
# 用法（需联网，运行时需提权）：
#   powershell -File 古籍/tools/fetch_daizhige.ps1 -RepoPath "易藏/术数/五行大义.md" -OutFile "古籍/五行/五行大义-全文.md" -BookName "五行大义" -Author "萧吉" -Dynasty "隋"
# 说明：殆知阁 md 自带 YAML front matter，脚本自动剥离；正文按原样落盘，不改写内容。
param(
  [Parameter(Mandatory = $true)][string]$RepoPath,
  [Parameter(Mandatory = $true)][string]$OutFile,
  [string]$BookName,
  [string]$Author = '',
  [string]$Dynasty = '',
  [string]$VersionNote = '殆知阁 daizhigev20 仓库 md 版（2025-09-16 由 txt 转换，无标点断句，保留整理者分段）',
  [string]$LayerNote = ''
)
$ErrorActionPreference = 'Stop'
$base = 'https://raw.githubusercontent.com/frankslin/daizhigev20/data/'
$url = $base + [uri]::EscapeDataString($RepoPath)
$resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 180
$text = $resp.Content
# 剥离 YAML front matter
$text = [regex]::Replace($text, '(?s)^---\r?\n.*?\r?\n---\r?\n', '')
$text = $text -replace "`r`n", "`n"
$text = (($text -split "`n" | ForEach-Object { $_.TrimEnd() }) -join "`n").Trim()
$srcUrl = 'https://github.com/frankslin/daizhigev20/blob/data/' + $RepoPath
$header = @"
> 书名：$BookName｜作者：$Author｜朝代：$Dynasty
> 版本说明：$VersionNote
> 来源：$srcUrl
> 抓取日期：2026-08-12
> 完整性：全文
> 分层：$LayerNote
"@
$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$out = $header + "`n`n" + $text
Set-Content -Path $OutFile -Value $out -Encoding utf8
$first = ($text.Substring(0, [Math]::Min(70, $text.Length)) -replace "`n", ' ')
Write-Output ("OK 字符数=" + $text.Length + "  |  " + $first)
