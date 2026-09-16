"""Package native build output; never pretend to cross-compile an executable."""
from pathlib import Path
import hashlib
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
dist = ROOT / 'dist'
assets = dist / 'release'
assets.mkdir(exist_ok=True)
arch = {'AMD64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine(), platform.machine())
if sys.platform == 'win32':
    shutil.copy2(ROOT / 'scripts' / 'Update-Dialpad.ps1', assets)
    name = f'Dialpad-{version}-windows-{arch}'
    if not (dist / 'Dialpad' / 'Dialpad.exe').is_file():
        raise SystemExit('Build the Windows app first.')
    archive = Path(shutil.make_archive(str(assets / name), 'zip', dist, 'Dialpad'))
elif sys.platform == 'darwin':
    name = f'Dialpad-{version}-macos-{arch}'
    archive = assets / (name + '.zip')
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                    str(dist / 'Dialpad.app'), str(archive)], check=True)
    shutil.copy2(ROOT / 'vendor' / 'libusb-1.0.30-source.tar.gz', assets)
else:
    raise SystemExit('Package on macOS or Windows.')
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(assets / (name + '.sha256')).write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
print(archive.name)
