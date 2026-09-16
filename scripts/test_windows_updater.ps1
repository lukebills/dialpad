# Exercise the real updater against local build assets; no network, user settings or real shortcuts.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('Dialpad-updater-test-' + [Guid]::NewGuid().ToString('N'))
$oldAppData = $env:APPDATA
$oldLocalAppData = $env:LOCALAPPDATA
$script:testVersion = (Get-Content -Raw (Join-Path $root 'VERSION')).Trim()
$script:assets = Join-Path $root 'dist\release'
$script:badChecksum = $false
$script:shortcuts = @{}
function Invoke-RestMethod {
    param($Uri, $Headers)
    if ($Uri -ne 'https://api.github.com/repos/lukebills/dialpad/releases/latest') { throw 'Unexpected metadata request' }
    $name = "Dialpad-$script:testVersion-windows-x64"
    return @{ tag_name = "v$script:testVersion"; draft = $false; prerelease = $false; assets = @(
        @{name = "$name.zip"; browser_download_url = "https://github.com/lukebills/dialpad/releases/download/v$script:testVersion/$name.zip"},
        @{name = "$name.sha256"; browser_download_url = "https://github.com/lukebills/dialpad/releases/download/v$script:testVersion/$name.sha256"}
    ) }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $OutFile)
    $name = [IO.Path]::GetFileName(([Uri]$Uri).AbsolutePath)
    Copy-Item -LiteralPath (Join-Path $script:assets $name) -Destination $OutFile
    if ($script:badChecksum -and $name.EndsWith('.sha256')) {
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
        $link | Add-Member ScriptMethod Save { $script:shortcuts[[IO.Path]::GetFileName($this.Path)] = $this.TargetPath }
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
    $first = $script:shortcuts['Dialpad.lnk']
    if (-not (Test-Path $first) -or -not (Test-Path $script:shortcuts['Update Dialpad.lnk'])) { throw 'Missing app or update shortcut targets' }
    & (Join-Path $PSScriptRoot 'Update-Dialpad.ps1') -NoLaunch
    $second = $script:shortcuts['Dialpad.lnk']
    if ($first -eq $second -or -not (Test-Path $first) -or -not (Test-Path $second)) { throw 'Update overwrote an older app folder' }
    $script:badChecksum = $true
    $rejected = $false
    try { & (Join-Path $PSScriptRoot 'Update-Dialpad.ps1') -NoLaunch }
    catch { if ($_.Exception.Message -notlike '*checksum did not match*') { throw }; $rejected = $true }
    if (-not $rejected -or $script:shortcuts['Dialpad.lnk'] -ne $second) { throw 'Invalid checksum changed the installed app' }
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($settings)) -ne [Convert]::ToBase64String($before)) { throw 'Saved setups changed' }
    Write-Host 'Updater checks passed: first install, repeated update, retained settings and previous app, checksum rejection, shortcut targets. No network or real shortcuts.'
} finally {
    $env:APPDATA = $oldAppData
    $env:LOCALAPPDATA = $oldLocalAppData
    Remove-Item -LiteralPath $fixture -Recurse -Force -ErrorAction SilentlyContinue
}
