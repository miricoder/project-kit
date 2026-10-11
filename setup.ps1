<#
.SYNOPSIS
  Project Kit environment setup for Windows PowerShell.

.DESCRIPTION
  Deliberately thin: locates a Python 3 and hands off to scripts/doctor.py, which holds all
  the logic and is unit-tested. setup.sh does the same on macOS and Linux, so both
  platforms run identical checks rather than two implementations that drift apart.

.EXAMPLE
  .\setup.ps1                 Report what is missing
.EXAMPLE
  .\setup.ps1 -Fix            Apply the safe fixes
.EXAMPLE
  .\setup.ps1 -Dev            Development install (symlink the repo into ~/.claude/skills)
.EXAMPLE
  .\setup.ps1 -Live           Also probe each judge seat with a real call

.NOTES
  If PowerShell refuses to run this file, allow it for this session only:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
#>
[CmdletBinding()]
param(
  [switch]$Fix,
  [switch]$Dev,
  [switch]$Live,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

$doctor = Join-Path $PSScriptRoot 'scripts/doctor.py'
if (-not (Test-Path $doctor)) {
  Write-Error "scripts/doctor.py not found at $doctor"
  exit 2
}

# Resolve a Python 3.9+. On Windows the launcher `py -3` is usually the most reliable.
$python = $null
$candidates = @(
  @{ Exe = 'py';      Args = @('-3') },
  @{ Exe = 'python';  Args = @() },
  @{ Exe = 'python3'; Args = @() }
)
foreach ($candidate in $candidates) {
  $exe = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
  if (-not $exe) { continue }
  $probe = @($candidate.Args) + @('-c', 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)')
  & $exe.Source @probe 2>$null
  if ($LASTEXITCODE -eq 0) {
    $python = @{ Exe = $exe.Source; Args = $candidate.Args }
    break
  }
}

if (-not $python) {
  Write-Host 'error: Python 3.9+ is required and was not found.' -ForegroundColor Red
  Write-Host '  tried: py -3, python, python3'
  Write-Host '  install from https://www.python.org/downloads/ (tick "Add python.exe to PATH")'
  exit 1
}

$forward = @()
if ($Fix)  { $forward += '--fix'  }
if ($Dev)  { $forward += '--dev'  }
if ($Live) { $forward += '--live' }
if ($Json) { $forward += '--json' }

$argv = @($python.Args) + @($doctor) + $forward
& $python.Exe @argv
exit $LASTEXITCODE
