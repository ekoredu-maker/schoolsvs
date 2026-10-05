param(
  [string]$PythonVersion = "3.11.9",
  [string]$PackageVersion = "0.19.0"
)

$ErrorActionPreference = "Stop"
$HybridDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $HybridDir
$DistBase = Join-Path $RepoRoot "dist"
$PackageRoot = Join-Path $DistBase "SchoolSVS_Portable"
$HybridOut = Join-Path $PackageRoot "hybrid"
$RuntimeDir = Join-Path $HybridOut "runtime"
$ZipOut = Join-Path $DistBase ("SchoolSVS_Portable_v{0}.zip" -f $PackageVersion)
$TempDir = Join-Path $env:TEMP ("schoolsvs_build_" + [guid]::NewGuid().ToString("N"))

Write-Host "[1/7] Preparing output folder..."
if (Test-Path $PackageRoot) { Remove-Item $PackageRoot -Recurse -Force }
if (-not (Test-Path $DistBase)) { New-Item -ItemType Directory -Path $DistBase | Out-Null }
New-Item -ItemType Directory -Path $PackageRoot | Out-Null
New-Item -ItemType Directory -Path $HybridOut | Out-Null
New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Path $TempDir | Out-Null

try {
  Write-Host "[2/7] Copying SchoolSVS application files..."
  Copy-Item (Join-Path $RepoRoot "index.html") (Join-Path $PackageRoot "index.html") -Force
  Copy-Item (Join-Path $HybridDir "app") (Join-Path $HybridOut "app") -Recurse -Force
  Copy-Item (Join-Path $HybridDir "web") (Join-Path $HybridOut "web") -Recurse -Force
  if (Test-Path (Join-Path $HybridDir "templates")) {
    Copy-Item (Join-Path $HybridDir "templates") (Join-Path $HybridOut "templates") -Recurse -Force
  } else {
    New-Item -ItemType Directory -Path (Join-Path $HybridOut "templates") | Out-Null
  }

  foreach ($name in @("SchoolSVS.vbs", "SchoolSVS_진단실행.bat", "run_schoolsvs.bat", "PORTABLE_README.txt")) {
    $source = Join-Path $HybridDir $name
    if (Test-Path $source) { Copy-Item $source (Join-Path $HybridOut $name) -Force }
  }

  foreach ($folder in @("data", "output", "mappings")) {
    $path = Join-Path $HybridOut $folder
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
  }

  Write-Host "[3/7] Downloading official Python Embedded Runtime $PythonVersion..."
  $pyCompact = $PythonVersion -replace '\.', ''
  $runtimeZip = Join-Path $TempDir "python-embed.zip"
  $runtimeUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
  Invoke-WebRequest -Uri $runtimeUrl -OutFile $runtimeZip -UseBasicParsing
  Expand-Archive -Path $runtimeZip -DestinationPath $RuntimeDir -Force

  Write-Host "[4/7] Configuring embedded Python search path..."
  $pthName = "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1])._pth"
  $pthPath = Join-Path $RuntimeDir $pthName
  if (-not (Test-Path $pthPath)) {
    $candidate = Get-ChildItem $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
    if ($null -eq $candidate) { throw "Embedded Python ._pth file was not found." }
    $pthPath = $candidate.FullName
  }
  @(
    "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1]).zip",
    ".",
    "..\app"
  ) | Set-Content -Path $pthPath -Encoding ASCII

  Write-Host "[5/7] Creating root launchers..."
  $rootVbs = Join-Path $PackageRoot "SchoolSVS.vbs"
  @'
Option Explicit
Dim shell, fso, baseDir, launcher
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(baseDir, "hybrid\SchoolSVS.vbs")
If Not fso.FileExists(launcher) Then
  MsgBox "SchoolSVS launcher file is missing.", vbCritical, "SchoolSVS"
  WScript.Quit 2
End If
shell.Run "wscript.exe " & Chr(34) & launcher & Chr(34), 0, False
'@ | Set-Content -Path $rootVbs -Encoding Default

  $rootBat = Join-Path $PackageRoot "SchoolSVS_진단실행.bat"
  @'
@echo off
cd /d "%~dp0hybrid"
call SchoolSVS_진단실행.bat
'@ | Set-Content -Path $rootBat -Encoding Default

  Write-Host "[6/7] Cleaning development-only files..."
  Get-ChildItem $PackageRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem $PackageRoot -Recurse -Include "*.pyc","*.pyo" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

  Write-Host "[7/7] Creating portable ZIP..."
  if (Test-Path $ZipOut) { Remove-Item $ZipOut -Force }
  Compress-Archive -Path (Join-Path $PackageRoot "*") -DestinationPath $ZipOut -CompressionLevel Optimal

  Write-Host ""
  Write-Host "Build complete: $ZipOut"
  Write-Host "End users run SchoolSVS.vbs. Python installation is not required."
}
finally {
  if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue }
}
