"""Build the single-file, windowed Flightpath executable on Windows."""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw
import PyInstaller.__main__


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / 'build'
DIST_DIR = ROOT / 'dist'
ICON_PATH = BUILD_DIR / 'flightpath.ico'


def make_icon():
    """Create a crisp multi-resolution app icon without a checked-in binary."""
    BUILD_DIR.mkdir(exist_ok=True)
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = Image.new('RGBA', (size, size), '#08131b')
        draw = ImageDraw.Draw(image)
        scale = size / 256
        margin = max(1, round(20 * scale))
        draw.rounded_rectangle((margin, margin, size - margin, size - margin),
                               radius=max(2, round(46 * scale)), fill='#102b38')
        # An ascending flight path and bright vehicle silhouette.
        draw.line([(round(49 * scale), round(196 * scale)),
                   (round(104 * scale), round(142 * scale)),
                   (round(150 * scale), round(151 * scale)),
                   (round(207 * scale), round(67 * scale))],
                  fill='#39d8bc', width=max(1, round(18 * scale)), joint='curve')
        draw.polygon([(round(176 * scale), round(48 * scale)),
                      (round(224 * scale), round(45 * scale)),
                      (round(218 * scale), round(94 * scale))], fill='#f6b44b')
        images.append(image)
    images[-1].save(ICON_PATH, format='ICO', append_images=images[:-1],
                    sizes=[(image.width, image.height) for image in images])


def main():
    if sys.platform != 'win32':
        raise SystemExit('Flightpath.exe must be built on Windows.')
    make_icon()
    for path in (BUILD_DIR / 'Flightpath', DIST_DIR / 'Flightpath.exe'):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    PyInstaller.__main__.run([
        str(ROOT / 'desktop.py'),
        '--name=Flightpath',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        f'--icon={ICON_PATH}',
        f'--add-data={ROOT / "companies.json"}{os_path_separator()}.',
        f'--add-data={ROOT / "static"}{os_path_separator()}static',
        f'--distpath={DIST_DIR}',
        f'--workpath={BUILD_DIR / "Flightpath"}',
        f'--specpath={BUILD_DIR}',
    ])
    print(f'Built {DIST_DIR / "Flightpath.exe"}')


def os_path_separator():
    # PyInstaller accepts the platform path separator in --add-data arguments.
    return ';' if sys.platform == 'win32' else ':'


if __name__ == '__main__':
    main()
