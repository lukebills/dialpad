"""Render our editable SVG to Mac/Windows icons. Requires Playwright + Chrome on Mac."""
from pathlib import Path
import struct
import subprocess
import tempfile
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
assets = root / 'assets'
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
    page = browser.new_page(viewport={'width':1024,'height':1024}, device_scale_factor=1)
    page.set_content('<body style="margin:0;background:transparent">' + (root / 'ui/icon.svg').read_text() + '</body>')
    page.screenshot(path=str(assets / 'app-icon.png'), omit_background=True)
    browser.close()
with tempfile.TemporaryDirectory() as directory:
    iconset = Path(directory) / 'Dialpad.iconset'
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = '@2x' if scale == 2 else ''
            target = iconset / f'icon_{size}x{size}{suffix}.png'
            subprocess.run(['sips','-z',str(size*scale),str(size*scale),str(assets / 'app-icon.png'),'--out',str(target)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(assets / 'Dialpad.icns')],check=True)
    png = (iconset / 'icon_256x256.png').read_bytes()
    (assets / 'Dialpad.ico').write_bytes(struct.pack('<HHH',0,1,1) + struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22) + png)
