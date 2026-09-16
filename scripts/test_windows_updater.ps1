# Exercise the real updater against local build assets; no network, user settings or real shortcuts.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('Dialpad-updater-test-' + [Guid]::NewGuid().ToString('N'))
$oldAppData = $env:APPDATA
$oldLocalAppData = $env:LOCALAPPDATA
$global:DialpadTest_testVersion = (Get-Content -Raw (Join-Path $root 'VERSION')).Trim()
$global:DialpadTest_assets = Join-Path $root 'dist\release'
$global:DialpadTest_badChecksum = $false
$global:DialpadTest_shortcuts = @{}
function Invoke-RestMethod {
    param($Uri, $Headers)
    if ($Uri -ne 'https://api.github.com/repos/lukebills/dialpad/releases/latest') { throw 'Unexpected metadata request' }
    $name = "Dialpad-$global:DialpadTest_testVersion-windows-x64"
    return @{ tag_name = "v$global:DialpadTest_testVersion"; draft = $false; prerelease = $false; assets = @(
        @{name = "$name.zip"; browser_download_url = "https://github.com/lukebills/dialpad/releases/download/v$global:DialpadTest_testVersion/$name.zip"},
        @{name = "$name.sha256"; browser_download_url = "https://github.com/lukebills/dialpad/releases/download/v$global:DialpadTest_testVersion/$name.sha256"}
    ) }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $OutFile)
    $name = [IO.Path]::GetFileName(([Uri]$Uri).AbsolutePath)
    Copy-Item -LiteralPath (Join-Path $global:DialpadTest_assets $name) -Destination $OutFile
    if ($global:DialpadTest_badChecksum -and $name.EndsWith('.sha256')) {
        Set-Content -LiteralPath $OutFile -Value (('0' * 64) + '  ' + $name.Replace('.sha256', '.zip'))
    }
}
function New-Object {
    param($ComObject)
    if ($ComObject -ne 'WScript.Shell') { throw 'Unexpected COM object' }
    $shell = [pscustomobject]@{}
    $shell | Add-Member ScriptMethod CreateShortcut {
        param($path)
        $link = [pscustomobject]@{ Path = $path; TargetPath = ''; WorkingDirectory = ''; IconLocation = ''; Arguments = '' }
        $link | Add-Member ScriptMethod Save { $global:DialpadTest_shortcuts[[IO.Path]::GetFileName($this.Path)] = $this.TargetPath }
        return $link
    }
    return $shell
}
try {
    $env:APPDATA = Join-Path $fixture 'roaming'
    $env:LOCALAPPDATA = Join-Path $fixture 'local'
    $settings = Join-Path $env:APPDATA 'Dialpad\setups.json'
    New-Item -ItemType Directory -Path (Split-Path $settings) -Force | Out-Null
    [IO.File]::WriteAllText($settings, '[{"name":"Keep my custom setup"}]')
    $before = [IO.File]::ReadAllBytes($settings)
    & (Join-Path $PSScriptRoot 'Update-Dialpad.ps1') -NoLaunch
    $first = $global:DialpadTest_shortcuts['Dialpad.lnk']
    if (-not (Test-Path $first) -or -not (Test-Path $global:DialpadTest_shortcuts['Update Dialpad.lnk'])) { throw 'Missing app or update shortcut targets' }
    & (Join-Path $PSScriptRoot 'Update-Dialpad.ps1') -NoLaunch
    $second = $global:DialpadTest_shortcuts['Dialpad.lnk']
    if ($first -eq $second -or -not (Test-Path $first) -or -not (Test-Path $second)) { throw 'Update overwrote an older app folder' }
    $global:DialpadTest_badChecksum = $true
    $rejected = $false
    try { & (Join-Path $PSScriptRoot 'Update-Dialpad.ps1') -NoLaunch }
    catch { if ($_.Exception.Message -notlike '*checksum did not match*') { throw }; $rejected = $true }
    if (-not $rejected -or $global:DialpadTest_shortcuts['Dialpad.lnk'] -ne $second) { throw 'Invalid checksum changed the installed app' }
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($settings)) -ne [Convert]::ToBase64String($before)) { throw 'Saved setups changed' }
    Write-Host 'Updater checks passed: first install, repeated update, retained settings and previous app, checksum rejection, shortcut targets. No network or real shortcuts.'
} finally {
    Remove-Variable -Name 'DialpadTest_*' -Scope Global -ErrorAction SilentlyContinue
    $env:APPDATA = $oldAppData
    $env:LOCALAPPDATA = $oldLocalAppData
    Remove-Item -LiteralPath $fixture -Recurse -Force -ErrorAction SilentlyContinue
}
