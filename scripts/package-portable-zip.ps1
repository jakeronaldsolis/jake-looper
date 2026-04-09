# Builds a portable zip: Jake Looper exe + ffmpeg/ffprobe + third_party/ffmpeg license texts.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/package-portable-zip.ps1
# Optional: -Version 1.0.2

param([string]$Version = "1.0.0")

$ErrorActionPreference = "Stop"
# Repo root = parent of scripts/
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "jake_looper_gui.py"))) {
    throw "Run this script from the Jake Looper repository (jake_looper_gui.py not found)."
}
$jakelooper = Join-Path $root "jakelooper"
$tp = Join-Path $root "third_party"
$ffmpeg = Join-Path $jakelooper "ffmpeg.exe"
$ffprobe = Join-Path $jakelooper "ffprobe.exe"
$app = Join-Path $jakelooper "jake_looper_gui.exe"
foreach ($f in @($ffmpeg, $ffprobe, $app)) {
    if (-not (Test-Path $f)) { throw "Missing: $f" }
}
if (-not (Test-Path (Join-Path $tp "ffmpeg\COPYING.LGPLv2.1"))) { throw "Missing third_party/ffmpeg license files." }

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("jake-looper-portable-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Copy-Item -LiteralPath $ffmpeg -Destination (Join-Path $staging "ffmpeg.exe")
    Copy-Item -LiteralPath $ffprobe -Destination (Join-Path $staging "ffprobe.exe")
    Copy-Item -LiteralPath $app -Destination (Join-Path $staging "jake_looper_gui.exe")
    Copy-Item -LiteralPath $tp -Destination $staging -Recurse
    $zipName = "jake-looper-v{0}-windows-portable.zip" -f $Version
    $zipPath = Join-Path $root $zipName
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -CompressionLevel Optimal
    Get-Item -LiteralPath $zipPath | Select-Object FullName, @{N = "SizeMB"; E = { [math]::Round($_.Length / 1MB, 2) } }
}
finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}
