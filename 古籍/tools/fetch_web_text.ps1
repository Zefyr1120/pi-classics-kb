# 通用网页纯文本抓取脚本（HTML -> 纯文本 md，备选古籍源用）
# 用法（需联网，运行时需提权）：
#   powershell -File 古籍/tools/fetch_web_text.ps1 -Urls "https://..." -OutFile "古籍/子平/xxx.md" -BookName "..." -Author "..." -Dynasty "..." -Mode whole
# Mode: whole（整页正文）| content-text（div.content-text 容器）| postmessage（Discuz 帖子 postmessage_N 容器）
param(
  [Parameter(Mandatory = $true)][string[]]$Urls,
  [Parameter(Mandatory = $true)][string]$OutFile,
  [string]$BookName = '',
  [string]$Author = '',
  [string]$Dynasty = '',
  [string]$VersionNote = '网页整理本（HTML 转纯文本）',
  [string]$LayerNote = '原文=全书正文',
  [string]$Completeness = '全文',
  [string]$StartMarker = '',
  [string]$EndMarker = '',
  [switch]$KeepEnd,
  [ValidateSet('whole', 'content-text', 'postmessage')][string]$Mode = 'whole'
)
$ErrorActionPreference = 'Stop'
$urlList = @($Urls -split ',' | Where-Object { $_ -ne '' })
function Get-DecodedText($resp) {
  # 优先按响应头 charset 解码；无 charset 时先试严格 UTF-8，失败回退 GBK(936)
  $bytes = New-Object byte[] $resp.RawContentStream.Length
  $resp.RawContentStream.Position = 0
  [void]$resp.RawContentStream.Read($bytes, 0, $bytes.Length)
  $ct = [string]$resp.Headers['Content-Type']
  if ($ct -match 'charset=([\w-]+)') {
    $cs = $Matches[1].ToLower()
    if ($cs -match 'gbk|gb2312|936|big5') { return [System.Text.Encoding]::GetEncoding(936).GetString($bytes) }
    return [System.Text.Encoding]::GetEncoding($cs).GetString($bytes)
  }
  try {
    $strict = New-Object System.Text.UTF8Encoding($false, $true)
    return $strict.GetString($bytes)
  } catch {
    return [System.Text.Encoding]::GetEncoding(936).GetString($bytes)
  }
}
function Convert-HtmlToText($html) {
  $html = $html -replace '(?is)<script.*?</script>', '' -replace '(?is)<style.*?</style>', ''
  $html = $html -replace '(?i)<br\s*/?>', "`n"
  $html = $html -replace '(?is)</(p|div|h[1-6]|li|tr)>', "`n"
  $html = $html -replace '<[^>]+>', ''
  $html = [System.Net.WebUtility]::HtmlDecode($html)
  if ($StartMarker) {
    $si = $html.IndexOf($StartMarker)
    if ($si -ge 0) { $html = $html.Substring($si) }
  }
  if ($EndMarker) {
    $ei = $html.IndexOf($EndMarker)
    if ($ei -gt 0) { $html = $html.Substring(0, $ei + $(if ($KeepEnd) { $EndMarker.Length } else { 0 })) }
  }
  $lines = $html -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  return ($lines -join "`n")
}
$sb = New-Object System.Text.StringBuilder
foreach ($u in $urlList) {
  $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 120
  $html = Get-DecodedText $resp
  if ($Mode -eq 'content-text') {
    $m = [regex]::Match($html, '(?is)<td id="article_content"[^>]*>(.*?)</td>')
    if (-not $m.Success) { $m = [regex]::Match($html, '(?is)<div class="content-text">(.*?)</div>') }
    if (-not $m.Success) { throw "未找到 content-text 容器: $u" }
    $txt = Convert-HtmlToText $m.Groups[1].Value
  } elseif ($Mode -eq 'postmessage') {
    $ms = [regex]::Matches($html, '(?is)id="postmessage_\d+"[^>]*>(.*?)</td>')
    $parts = @()
    foreach ($mm in $ms) { $t = Convert-HtmlToText $mm.Groups[1].Value; if ($t) { $parts += $t } }
    $txt = ($parts -join "`n`n")
  } else {
    $txt = Convert-HtmlToText $html
  }
  [void]$sb.AppendLine($txt)
  [void]$sb.AppendLine()
  Write-Output ("OK " + $u + "  chars=" + $txt.Length)
}
$body = $sb.ToString().Trim()
$header = @"
> 书名：$BookName｜作者：$Author｜朝代：$Dynasty
> 版本说明：$VersionNote
> 来源：$($Urls -join ' | ')
> 抓取日期：2026-08-12
> 完整性：$Completeness
> 分层：$LayerNote
"@
$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $OutFile), $header + "`n`n" + $body + "`n", (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("DONE " + $OutFile + "  total_chars=" + $body.Length)
