"""Turn the photos in sources/photos into ink segments that build.py can pick letters from.

For every photo: crop the page, even out the light, make it black and white, find every
connected piece of ink, and group the pieces into rows and glyphs. The result goes to
segments/<photo>/ (lab.npy, comps.json, rows.json, plus bin.png and vis.jpg to look at).

A glyph is addressed in build.py as "row.group", for example "1.8" is the ninth glyph in
the second row. vis.jpg shows the numbers. Run from the root of the repository:

    python scripts/segment.py
"""
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

# photo, crop box on the upright photo (x0, x1, y0, y1)
PHOTOS = {
    'p1': ('p1-alphabet.heic', (520, 2600, 300, 3500)),
    'p2': ('p2-alphabet-q.heic', (420, 2600, 250, 3600)),
    'p3': ('p3-symbols.heic', (560, 2560, 300, 3150)),
    'p4': ('p4-symbols-2.heic', (330, 2600, 1530, 2250)),
    'p5': ('p5-words.heic', (400, 2560, 850, 2300)),
    'p6': ('p6-sentences.heic', (400, 2620, 850, 3650)),
}


def segment(name, photo, box):
    out = f'segments/{name}'
    os.makedirs(out, exist_ok=True)
    im = ImageOps.exif_transpose(Image.open(f'sources/photos/{photo}')).convert('RGB')
    im.save(f'{out}/full.jpg', quality=92)  # the letters were cut from this JPEG; keep it identical
    g = cv2.cvtColor(cv2.imread(f'{out}/full.jpg'), cv2.COLOR_BGR2GRAY)
    x0, x1, y0, y1 = box
    p = g[y0:y1, x0:x1].astype(np.float32)
    bg = cv2.GaussianBlur(cv2.morphologyEx(p, cv2.MORPH_CLOSE, np.ones((41, 41), np.uint8)), (0, 0), 15)
    n = np.clip(p / bg * 255, 0, 255).astype(np.uint8)
    _, b = cv2.threshold(n, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cv2.imwrite(f'{out}/bin.png', b)
    nl, lab, st, _ = cv2.connectedComponentsWithStats(b, 8)
    comps = [dict(id=i, x=int(st[i][0]), y=int(st[i][1]), w=int(st[i][2]), h=int(st[i][3]), a=int(st[i][4]))
             for i in range(1, nl) if st[i][4] >= 40]
    json.dump(comps, open(f'{out}/comps.json', 'w'))
    np.save(f'{out}/lab.npy', lab)
    rows = group(comps, lab.shape)
    json.dump(rows, open(f'{out}/rows.json', 'w'))

    # A picture with the row.group numbers, to find a letter
    vis = cv2.cvtColor(255 - b, cv2.COLOR_GRAY2BGR)
    byid = {c['id']: c for c in comps}
    for ri, r in enumerate(rows):
        for gi, gr in enumerate(r['groups']):
            gx0 = min(byid[i]['x'] for i in gr); gy0 = min(byid[i]['y'] for i in gr)
            gx1 = max(byid[i]['x'] + byid[i]['w'] for i in gr); gy1 = max(byid[i]['y'] + byid[i]['h'] for i in gr)
            cv2.rectangle(vis, (gx0, gy0), (gx1, gy1), (0, 0, 255), 2)
            cv2.putText(vis, f'{ri}.{gi}', (gx0, gy0 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
    cv2.imwrite(f'{out}/vis.jpg', vis)
    print(f'{name}: {len(comps)} pieces of ink in {len(rows)} rows')


def group(comps, shape):
    H, W = shape
    comps = [c for c in comps if c['x'] > 2 and c['y'] > 2 and c['x'] + c['w'] < W - 2 and c['y'] + c['h'] < H - 2 and c['w'] < 600]
    rows = []
    for c in sorted([c for c in comps if c['h'] > 40], key=lambda c: c['y'] + c['h'] / 2):
        cy = c['y'] + c['h'] / 2
        if rows and cy - rows[-1]['cy'] < 70:
            rows[-1]['m'].append(c); rows[-1]['cy'] = np.mean([d['y'] + d['h'] / 2 for d in rows[-1]['m']])
        else:
            rows.append(dict(cy=cy, m=[c]))
    # small pieces (dots, accents, punctuation) join the glyph they sit on or under
    for s in [c for c in comps if c['h'] <= 40]:
        sx = s['x'] + s['w'] / 2; sy = s['y'] + s['h'] / 2
        best = None
        for r in rows:
            for c in r['m']:
                if c['x'] - 15 <= sx <= c['x'] + c['w'] + 15 and -140 < c['y'] - sy < c['h'] + 60:
                    d = abs(c['y'] + c['h'] / 2 - sy)
                    if best is None or d < best[0]: best = (d, r)
        (best[1] if best else min(rows, key=lambda r: abs(r['cy'] - sy)))['m'].append(s)
    out = []
    for r in rows:
        groups = []
        for c in sorted(r['m'], key=lambda c: c['x']):
            if groups and c['x'] < groups[-1]['x1'] - 3 and not (c['h'] > 40 and groups[-1]['big'] and c['x'] > groups[-1]['x1'] - 25):
                g = groups[-1]
            else:
                g = dict(ids=[], x1=c['x'] + c['w'], big=False); groups.append(g)
            g['ids'].append(c['id']); g['x1'] = max(g['x1'], c['x'] + c['w']); g['big'] = g['big'] or c['h'] > 40
        out.append(dict(cy=float(r['cy']), groups=[g['ids'] for g in groups]))
    return out


if __name__ == '__main__':
    for name, (photo, box) in PHOTOS.items():
        segment(name, photo, box)
