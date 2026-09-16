"""Build the Windows WebView2 host with the system .NET Framework compiler."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK_VERSION = '1.0.3650.58'
SDK_SHA256 = '911a472128c82ac8baa0c486c23342cc9dd6e7dc50d754e676726642ca065c60'

def build():
    output = ROOT / 'build' / 'windows-window'
    output.mkdir(parents=True, exist_ok=True)
    package = ROOT / 'build' / 'webview2.nupkg'
    if not package.exists() or hashlib.sha256(package.read_bytes()).hexdigest() != SDK_SHA256:
        url = f'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/{SDK_VERSION}/microsoft.web.webview2.{SDK_VERSION}.nupkg'
        with urllib.request.urlopen(url, timeout=60) as response:
            package.write_bytes(response.read())
    if hashlib.sha256(package.read_bytes()).hexdigest() != SDK_SHA256:
        raise RuntimeError('Microsoft WebView2 SDK checksum did not match.')
    with zipfile.ZipFile(package) as archive:
        for name in ('lib/net462/Microsoft.Web.WebView2.Core.dll',
                     'lib/net462/Microsoft.Web.WebView2.WinForms.dll',
                     'runtimes/win-x64/native/WebView2Loader.dll', 'LICENSE.txt'):
            (output / ('WEBVIEW2-LICENSE.txt' if name == 'LICENSE.txt' else Path(name).name)).write_bytes(archive.read(name))
    shutil.copy2(ROOT / 'assets' / 'Dialpad.ico', output)
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
        '/out:' + str(output / 'DialpadWindow.exe'),
        '/win32icon:' + str(ROOT / 'assets/Dialpad.ico'),
        '/win32manifest:' + str(ROOT / 'native/WindowsWindow.manifest'),
        '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Drawing.dll',
        '/reference:System.Windows.Forms.dll', '/reference:System.Net.Http.dll',
        '/reference:System.Web.Extensions.dll',
        '/reference:' + str(output / 'Microsoft.Web.WebView2.Core.dll'),
        '/reference:' + str(output / 'Microsoft.Web.WebView2.WinForms.dll'),
        str(ROOT / 'native/WindowsWindow.cs')], check=True)
    (output / 'DialpadWindow.exe.config').write_text('''<?xml version="1.0"?>
<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.6.2"/></startup></configuration>
''', encoding='utf-8')
    return output

if __name__ == '__main__':
    build()
