"""Render every newly authored PDF page and compose compact QA contact sheets."""
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / 'test/.qa/workbench_demo'
RENDER = QA / 'pdf-pages'
RENDER.mkdir(parents=True, exist_ok=True)
tool = shutil.which('pdftoppm')
if not tool:
    raise SystemExit('pdftoppm is required')
for path in sorted((ROOT / 'test/workbench_demo/assets').glob('*.pdf')):
    # Remove only generated previews of this exact source before rerendering it.
    for stale in RENDER.glob(path.stem + '-*.png'):
        if stale.resolve().is_relative_to(RENDER.resolve()):
            stale.unlink()
    subprocess.run([tool, '-scale-to', '1200', '-png', str(path), str(RENDER / path.stem)], check=True, capture_output=True)


def contact(paths, prefix, w, h, rows=3, cols=4):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    for start in range(0, len(paths), rows * cols):
        board = Image.new('RGB', (w * cols, (h+40) * rows), '#D9E3EB')
        draw = ImageDraw.Draw(board)
        for i, path in enumerate(paths[start:start+rows*cols]):
            with Image.open(path) as source:
                source.thumbnail((w-12, h-8))
                x, y = (i % cols) * w, (i // cols) * (h+40)
                board.paste(source, (x+6, y+5))
                draw.text((x+5, y+h+8), path.name[:45], font=font, fill='#17324D')
        board.save(QA / f'{prefix}-{start//(rows*cols)+1}.jpg', quality=92)


pages = sorted(RENDER.glob('*.png'))
contact(pages, 'pdf-contact', 340, 485)
contact(sorted(QA.glob('*.png')), 'sheet-contact', 630, 240, rows=4, cols=2)
print(f'Rendered {len(pages)} PDF pages and spreadsheet contact sheets.')
