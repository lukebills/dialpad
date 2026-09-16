"""Build a portable app using an isolated environment with PyInstaller."""
from pathlib import Path
import ctypes
import platform
import os
import shutil
import subprocess
import sys
import tarfile
import plistlib
import re

ROOT = Path(__file__).parent.resolve()
release_version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', release_version):
    raise SystemExit('VERSION must contain major.minor.patch.')
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--name', 'Dialpad',
        '--onedir', '--windowed', '--add-data', f'{ROOT / "ui"}:ui',
        '--add-data', f'{ROOT / "VERSION"}:.',
        '--add-data', f'{ROOT / "assets" / "app-icon.png"}:assets',
        '--add-data', f'{ROOT / "core" / "THIRD_PARTY_LICENSE.txt"}:licenses',
        '--hidden-import', 'core.protocol', '--hidden-import', 'core.transport']
if sys.platform == 'darwin':
    args += ['--icon', str(ROOT / 'assets' / 'Dialpad.icns')]
    # Reuse the same identity for every release so macOS privacy grants survive updates.
    identity_file = ROOT / '.signing-identity'
    identity = os.environ.get('DIALPAD_SIGNING_IDENTITY') or (identity_file.read_text().strip() if identity_file.exists() else None)
    if identity:
        args += ['--codesign-identity', identity]
    else:
        print('Development build: ad-hoc signatures change on rebuild; macOS device-control permission may need renewing.', flush=True)
    args += ['--exclude-module', 'core.windows_desktop', '--exclude-module', 'tkinter']
    native = ROOT / 'build' / 'native' / 'DialpadDesktop'
    native.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['xcrun', 'swiftc', '-O', '-target', f'{platform.machine()}-apple-macosx12.0',
                    str(ROOT / 'native' / 'DialpadDesktop.swift'), '-o', str(native)], check=True)
    args += ['--add-binary', f'{native}:.']
    # Build the vendored source for the same minimum OS as the native host.
    # Homebrew's binary may target the build machine's much newer macOS version.
    source_root = ROOT / 'build' / 'vendor'
    source_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ROOT / 'vendor' / 'libusb-1.0.30-source.tar.gz') as archive:
        archive.extractall(source_root, filter='data')
    source = source_root / 'libusb-1.0.30'
    lib = source_root / 'libusb-1.0.0.dylib'
    units = ['core.c', 'descriptor.c', 'hotplug.c', 'io.c', 'strerror.c', 'sync.c',
             'os/events_posix.c', 'os/threads_posix.c', 'os/darwin_usb.c']
    subprocess.run(['xcrun', 'clang', '-dynamiclib', '-O2', '-fvisibility=hidden',
                    '-arch', platform.machine(), '-mmacosx-version-min=12.0',
                    '-I', str(source / 'Xcode'), '-I', str(source / 'libusb'),
                    *[str(source / 'libusb' / unit) for unit in units],
                    '-framework', 'IOKit', '-framework', 'CoreFoundation', '-framework', 'Security',
                    '-install_name', '@rpath/libusb-1.0.0.dylib', '-o', str(lib)], check=True)
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
else:
    version_file = ROOT / 'build' / 'windows-version.txt'
    version_file.parent.mkdir(parents=True, exist_ok=True)
    numbers = tuple(map(int, release_version.split('.'))) + (0,)
    version_file.write_text(f"""VSVersionInfo(ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription','Dialpad'), StringStruct('FileVersion','{release_version}'), StringStruct('ProductName','Dialpad'), StringStruct('ProductVersion','{release_version}'), StringStruct('OriginalFilename','Dialpad.exe')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])""", encoding='utf-8')
    args += ['--version-file', str(version_file)]
    args += ['--icon', str(ROOT / 'assets' / 'Dialpad.ico'), '--add-data', f'{ROOT / "assets" / "Dialpad.ico"}:assets']
    args += ['--hidden-import', 'core.windows_desktop', '--hidden-import', 'tkinter']
args.append(str(ROOT / 'app.py'))
subprocess.run(args, cwd=ROOT, check=True)
if sys.platform == 'darwin':
    bundle = ROOT / 'dist' / 'Dialpad.app'
    info_file = bundle / 'Contents' / 'Info.plist'
    info = plistlib.loads(info_file.read_bytes())
    info.update(CFBundleShortVersionString=release_version, CFBundleVersion=release_version, LSMinimumSystemVersion='12.0')
    info_file.write_bytes(plistlib.dumps(info))
    subprocess.run(['codesign', '--force', '--sign', identity or '-', *(['--options', 'runtime'] if identity else []), str(bundle)], check=True)
    shutil.copy2(ROOT / 'vendor' / 'libusb-1.0.30-source.tar.gz', ROOT / 'dist')
print(f'Built Dialpad for {platform.system()} {platform.machine()} in {ROOT / "dist"}')
