# Install/update the portable app for this Windows user. No administrator rights requested.
[CmdletBinding()]
param([switch]$NoLaunch, [switch]$DesktopShortcut)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo = 'lukebills/dialpad'
$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\Dialpad'
$work = Join-Path ([IO.Path]::GetTempPath()) ('Dialpad-update-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work -Force | Out-Null
try {
    Write-Host 'Checking the latest Dialpad release...'
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers @{ 'User-Agent' = 'Dialpad-Updater' }
    if ($release.tag_name -notmatch '^v\d+\.\d+\.\d+$' -or $release.draft -or $release.prerelease) { throw 'Unexpected release metadata.' }
    $version = $release.tag_name.Substring(1)
    $name = "Dialpad-$version-windows-x64"
    $zipAsset = @($release.assets | Where-Object { $_.name -eq "$name.zip" })
    $hashAsset = @($release.assets | Where-Object { $_.name -eq "$name.sha256" })
    if ($zipAsset.Count -ne 1 -or $hashAsset.Count -ne 1) { throw 'The release has no complete Windows download.' }
    $prefix = "https://github.com/$repo/releases/download/$($release.tag_name)/"
    foreach ($asset in @($zipAsset[0], $hashAsset[0])) {
        if ($asset.browser_download_url -ne ($prefix + $asset.name)) { throw 'Unexpected download address.' }
        Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile (Join-Path $work $asset.name)
    }
    $zip = Join-Path $work "$name.zip"
    $checksum = (Get-Content -Raw (Join-Path $work "$name.sha256")).Trim()
    if ($checksum -notmatch '^([a-fA-F0-9]{64})\s+(.+)$' -or $Matches[2] -ne "$name.zip") { throw 'Invalid checksum file.' }
    $expected = $Matches[1]
    if ((Get-FileHash -Algorithm SHA256 $zip).Hash -ne $expected) { throw 'Download checksum did not match. Nothing was changed.' }

    # Verify paths before extracting; never merge files into a running app folder.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($zip)
    try {
        foreach ($entry in $archive.Entries) {
            $entryPath = $entry.FullName.Replace('\', '/')
            if (-not $entryPath.StartsWith('Dialpad/') -or $entryPath -match '(^|/)\.\.(/|$)|:' ) { throw 'Unexpected path in release archive.' }
        }
    } finally { $archive.Dispose() }
    $stage = Join-Path $work 'extracted'
    Expand-Archive -LiteralPath $zip -DestinationPath $stage
    $appFolder = Join-Path $stage 'Dialpad'
    if (-not (Test-Path (Join-Path $appFolder 'Dialpad.exe')) -or
        -not (Test-Path (Join-Path $appFolder '_internal\windows\DialpadWindow.exe'))) {
        throw 'The native Windows app is missing from this release.'
    }

    # Ask the existing companion to quit normally; never kill another Python process.
    $sessionFile = Join-Path $env:APPDATA 'Dialpad\session.json'
    if (Test-Path $sessionFile) {
        $session = Get-Content -Raw -Encoding UTF8 $sessionFile | ConvertFrom-Json
        $base = [Uri]$session.base
        if ($base.Scheme -ne 'http' -or $base.Host -ne '127.0.0.1' -or $base.AbsolutePath -ne '/' -or $base.UserInfo) { throw 'Invalid local Dialpad session. Quit Dialpad and retry.' }
        $request = [Net.HttpWebRequest]::Create($session.base + 'api/quit')
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        $request.Timeout = 5000
        $request.Method = 'POST'
        $request.Headers['Authorization'] = 'Bearer ' + $session.token
        $request.ContentType = 'application/json'
        $bytes = [Text.Encoding]::UTF8.GetBytes('{}')
        $request.ContentLength = $bytes.Length
        $closedRunningApp = $false
        try {
            $stream = $request.GetRequestStream()
            try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
            $response = $request.GetResponse()
            $response.Dispose()
            $closedRunningApp = $true
        } catch [Net.WebException] {
            if ($_.Exception.Status -ne [Net.WebExceptionStatus]::ConnectFailure) {
                throw 'Could not close the running Dialpad. Quit it from its tray/companion, then retry.'
            }
            # A crashed app can leave a stale session file. A fresh launch replaces it.
        }
        if ($closedRunningApp) {
            $deadline = (Get-Date).AddSeconds(20)
            while (Test-Path $sessionFile) {
                if ((Get-Date) -gt $deadline) { throw 'Dialpad is still closing. Wait a moment, then retry.' }
                Start-Sleep -Milliseconds 200
            }
        }
    }

    $target = Join-Path $installRoot ('versions\' + $release.tag_name + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Move-Item -LiteralPath $appFolder -Destination (Join-Path $target 'Dialpad')
    $exe = Join-Path $target 'Dialpad\Dialpad.exe'
    $updater = Join-Path $installRoot 'Update-Dialpad.ps1'
    if ([IO.Path]::GetFullPath($PSCommandPath) -ne [IO.Path]::GetFullPath($updater)) {
        Copy-Item -LiteralPath $PSCommandPath -Destination $updater -Force
    }
    $shell = New-Object -ComObject WScript.Shell
    $programs = [Environment]::GetFolderPath('Programs')
    $link = $shell.CreateShortcut((Join-Path $programs 'Dialpad.lnk'))
    $link.TargetPath = $exe
    $link.WorkingDirectory = Split-Path $exe
    $link.IconLocation = $exe
    $link.Save()
    $updateLink = $shell.CreateShortcut((Join-Path $programs 'Update Dialpad.lnk'))
    $updateLink.TargetPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $updateLink.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $updater + '"'
    $updateLink.IconLocation = $exe
    $updateLink.Save()
    if ($DesktopShortcut) {
        Copy-Item -LiteralPath (Join-Path $programs 'Dialpad.lnk') -Destination (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Dialpad.lnk') -Force
    }
    Write-Host "Dialpad $version is ready. Open Dialpad from the Start menu; use Update Dialpad for future updates."
    Write-Host 'Your setups remain in %APPDATA%\Dialpad. Older app folders are retained for rollback.'
    if (-not $NoLaunch) { Start-Process -FilePath $exe }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
