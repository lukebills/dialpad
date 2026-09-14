"""Build a portable app using an isolated environment with PyInstaller."""
from pathlib import Path
import ctypes
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).parent.resolve()
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--name', 'Dialpad',
        '--onedir', '--windowed', '--add-data', f'{ROOT / "ui"}:ui',
        '--add-data', f'{ROOT / "core" / "THIRD_PARTY_LICENSE.txt"}:licenses',
        '--hidden-import', 'core.protocol', '--hidden-import', 'core.transport']
if sys.platform == 'darwin':
    paths = ['/opt/homebrew/lib/libusb-1.0.dylib', '/usr/local/lib/libusb-1.0.dylib']
    lib = next((Path(p) for p in paths if Path(p).exists()), None)
    if lib is None:
        raise SystemExit('Build requires libusb (brew install libusb). End users get a bundled copy.')
    class USBVersion(ctypes.Structure):
        _fields_ = [('major', ctypes.c_uint16), ('minor', ctypes.c_uint16), ('micro', ctypes.c_uint16)]
    usb = ctypes.CDLL(str(lib))
    usb.libusb_get_version.restype = ctypes.POINTER(USBVersion)
    version = usb.libusb_get_version().contents
    if (version.major, version.minor, version.micro) != (1, 0, 30):
        raise SystemExit('This build includes source for libusb 1.0.30. Update the matching source archive and licence before bundling another version.')
    args += ['--add-binary', f'{lib.resolve()}:.', '--osx-bundle-identifier', 'local.dialpad.app']
    license_file = ROOT / 'core' / 'LIBUSB-LICENSE.txt'
    if license_file.exists():
        args += ['--add-data', f'{license_file}:licenses']
elif sys.platform != 'win32':
    raise SystemExit('Build on macOS or Windows to create a portable app for that OS.')
args.append(str(ROOT / 'app.py'))
subprocess.run(args, cwd=ROOT, check=True)
if sys.platform == 'darwin':
    shutil.copy2(ROOT / 'vendor' / 'libusb-1.0.30-source.tar.gz', ROOT / 'dist')
print(f'Built Dialpad for {platform.system()} {platform.machine()} in {ROOT / "dist"}')
