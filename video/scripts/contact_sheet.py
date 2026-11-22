"""Contact sheet of a video: frames every STEP seconds (or listed times), tiled with labels.

Usage: python3 scripts/contact_sheet.py VIDEO OUT.jpg [--step 1.0] [--from 0] [--to END] [--cols 4] [--w 480]
Remotion's bundled ffmpeg lacks the fps/tile filters, so this seeks per frame and tiles with PIL.
"""
import argparse, json, subprocess, tempfile, os
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument('video'); ap.add_argument('out')
ap.add_argument('--step', type=float, default=1.0); ap.add_argument('--from', dest='start', type=float, default=0)
ap.add_argument('--to', type=float, default=None); ap.add_argument('--cols', type=int, default=4); ap.add_argument('--w', type=int, default=480)
a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__)) + '/..'
ff = ['pnpm', 'exec', 'remotion', 'ffmpeg']
probe = subprocess.run(['pnpm', 'exec', 'remotion', 'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', a.video], cwd=here, capture_output=True, text=True)
dur = float(json.loads(probe.stdout)['format']['duration'])
end = a.to if a.to is not None else dur - 0.05
ts = []; t = a.start
while t <= end + 1e-6: ts.append(round(t, 3)); t += a.step
tiles = []
with tempfile.TemporaryDirectory() as d:
    for i, t in enumerate(ts):
        f = f'{d}/{i}.jpg'
        subprocess.run(ff + ['-y', '-loglevel', 'error', '-ss', str(t), '-i', a.video, '-frames:v', '1', '-q:v', '3', f], cwd=here)
        if os.path.exists(f):
            im = Image.open(f); h = int(im.height * a.w / im.width); im = im.resize((a.w, h))
            ImageDraw.Draw(im).rectangle([0, 0, 64, 18], fill='black'); ImageDraw.Draw(im).text((4, 3), f'{t:.2f}s', fill='white')
            tiles.append(im)
rows = (len(tiles) + a.cols - 1) // a.cols
h = tiles[0].height
sheet = Image.new('RGB', (a.cols * a.w, rows * h), 'white')
for i, im in enumerate(tiles): sheet.paste(im, ((i % a.cols) * a.w, (i // a.cols) * h))
sheet.save(a.out, quality=82)
print(a.out, len(tiles), 'frames', f'{dur:.2f}s')
