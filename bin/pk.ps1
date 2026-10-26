<#
.SYNOPSIS
  Project Kit launcher for Windows PowerShell.
.DESCRIPTION
  Resolves the Python interpreter and the plugin root, so SKILL.md can use one command
  shape on every platform.

    pk state next
    pk gate phase design
    pk doctor -Live
    pk check
    pk judge status
    pk qa

  Plugin root resolution, in order: $env:CLAUDE_PLUGIN_ROOT, $env:PROJECT_KIT_ROOT, this
  script's own parent directory.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('state', 'gate', 'doctor', 'check', 'judge', 'qa')]
  [string]$Subcommand,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

$root = $env:CLAUDE_PLUGIN_ROOT
if (-not $root) { $root = $env:PROJECT_KIT_ROOT }
if (-not $root) { $root = Split-Path -Parent $PSScriptRoot }

$target = switch ($Subcommand) {
  'state'  { Join-Path $root 'skills/pipeline/scripts/state.py' }
  'gate'   { Join-Path $root 'skills/pipeline/scripts/gate.py' }
  'doctor' { Join-Path $root 'scripts/doctor.py' }
  'check'  { Join-Path $root 'scripts/check.py' }
  'judge'  { Join-Path $root 'skills/handover/scripts/judge.py' }
  'qa'     { Join-Path $root 'scripts/qa.py' }
}
if (-not (Test-Path $target)) {
  Write-Error "pk: $target not found; set PROJECT_KIT_ROOT"
  exit 2
}

$python = $null
foreach ($candidate in @(@{E='py';A=@('-3')}, @{E='python';A=@()}, @{E='python3';A=@()})) {
  $exe = Get-Command $candidate.E -ErrorAction SilentlyContinue
  if (-not $exe) { continue }
  $probe = @($candidate.A) + @('-c', 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)')
  & $exe.Source @probe 2>$null
  if ($LASTEXITCODE -eq 0) { $python = @{ Exe = $exe.Source; Args = $candidate.A }; break }
}
if (-not $python) {
  Write-Error 'pk: Python 3.9+ not found (tried py -3, python, python3)'
  exit 1
}

$argv = @($python.Args) + @($target) + @($Rest)
& $python.Exe @argv
exit $LASTEXITCODE
