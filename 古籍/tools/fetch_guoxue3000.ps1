# 国学3000 古籍逐章抓取脚本（HTML 正文 -> 纯文本 markdown）
# 用法（需联网，运行时需提权）：
#   powershell -File 古籍/tools/fetch_guoxue3000.ps1 -BookId 378 -OutFile "古籍/子平/滴天髓阐微-国学3000.md" -BookName "滴天髓阐微" -Author "京图撰·刘基注·任铁樵阐微" -Dynasty "宋/明/清"
# 说明：从书目页枚举全部章节链接，逐章抓取 <h2> 标题与 <p class="indented"> 正文，
#       自动剔除导航/图片区；分层标记（如【原注】【任氏曰】）保留在正文中。
param(
  [Parameter(Mandatory = $true)][int]$BookId,
  [Parameter(Mandatory = $true)][string]$OutFile,
  [string]$BookName,
  [string]$Author = '',
  [string]$Dynasty = '',
  [string]$VersionNote = '国学3000 网页整理本（章节正文，含原注/注家标记）',
  [string]$LayerNote = ''
)
$ErrorActionPreference = 'Stop'
$bookUrl = "https://guoxue3000.com/books/$BookId"
$resp = Invoke-WebRequest -Uri $bookUrl -UseBasicParsing -TimeoutSec 90
$links = [regex]::Matches($resp.Content, 'href="(/books/' + $BookId + '/chapters/(\d+))"[^>]*>([^<]+)<') | ForEach-Object {
  [pscustomobject]@{ Num = [int]$_.Groups[2].Value; Name = $_.Groups[3].Value.Trim() }
} | Where-Object { $_.Name -and $_.Name -notmatch '上一章|下一章|目录|图片' } | Sort-Object Num -Unique
if ($links.Count -eq 0) { throw "未从书目页解析到章节链接: $bookUrl" }
$sb = New-Object System.Text.StringBuilder
foreach ($l in $links) {
  $u = "https://guoxue3000.com/books/$BookId/chapters/$($l.Num)"
  $cp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 90
  $html = $cp.Content
  $m = [regex]::Match($html, '<h2[^>]*>([^<]+)</h2>')
  $title = if ($m.Success) { $m.Groups[1].Value.Trim() } else { $l.Name }
  [void]$sb.AppendLine("## " + $title)
  $paras = [regex]::Matches($html, '<p class="indented">(.*?)</p>', 'Singleline')
  foreach ($p in $paras) {
    $txt = $p.Groups[1].Value -replace '<br\s*/?>', "`n" -replace '<[^>]+>', ''
    $txt = [System.Net.WebUtility]::HtmlDecode($txt)
    $txt = (($txt -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join "`n")
    if ($txt) { [void]$sb.AppendLine($txt); [void]$sb.AppendLine() }
  }
  Write-Output ("  ch " + $l.Num + " " + $title + " (" + $paras.Count + " 段)")
}
$text = $sb.ToString().Trim()
$srcUrl = $bookUrl
$header = @"
> 书名：$BookName｜作者：$Author｜朝代：$Dynasty
> 版本说明：$VersionNote
> 来源：$srcUrl
> 抓取日期：2026-08-12
> 完整性：全书 $($links.Count) 章全文
> 分层：$LayerNote
"@
$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
Set-Content -Path $OutFile -Value ($header + "`n`n" + $text) -Encoding utf8
Write-Output ("OK 章数=" + $links.Count + " 字符数=" + $text.Length + "  ->  " + $OutFile)
