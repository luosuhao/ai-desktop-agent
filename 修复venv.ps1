param([string]$VenvDir)

# 校验 tablenet-venv 是否可用；不可用时探测本机 Python 3.11 并改写 pyvenv.cfg
# （venv 的 pyvenv.cfg 写死 base Python 路径，跨机器不可移植，需指向本机 3.11）

$ErrorActionPreference = 'SilentlyContinue'
$pyExe = Join-Path $VenvDir 'Scripts\python.exe'

# 1) 已可用则直接成功
& $pyExe -c "import sys" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "venv 已可用"; exit 0 }

# 2) 探测本机 Python 3.11
$py = $null
try { $py = (& py -3.11 -c "import sys;print(sys.executable)" 2>$null | Select-Object -First 1) } catch {}
if (-not $py) {
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python311\python.exe",
        "C:\Program Files\Python311\python.exe",
        "D:\Python\python.exe"
    )
    foreach ($x in $cands) { if (Test-Path $x) { $py = $x; break } }
}
if (-not $py) {
    Write-Host "未找到 Python 3.11，无法自动修复。"
    exit 1
}

# 3) 改写 pyvenv.cfg
$homeDir = Split-Path $py
$cfg = Join-Path $VenvDir 'pyvenv.cfg'
$lines = Get-Content -Path $cfg -Encoding UTF8
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^home\s*=') { $lines[$i] = "home = $homeDir" }
    if ($lines[$i] -match '^executable\s*=') { $lines[$i] = "executable = $py" }
}
Set-Content -Path $cfg -Value $lines -Encoding ASCII
Write-Host "已修复 pyvenv.cfg -> $py"
exit 0
