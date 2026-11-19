# Extra glyphs: symbols from photo 3, accents, composed accented letters.
EXTRA_CMAP = {}
lab3 = np.load('segments/p3/lab.npy'); rows3 = json.load(open('segments/p3/rows.json'))
comps3 = {c['id']: c for c in json.load(open('segments/p3/comps.json'))}
S3 = F * 1.0  # same pen stroke width as photo 1 -> same scale

def gids(rows_, keys):
    out = []
    for k in keys:
        r, g = map(int, k.split('.')); out += rows_[r]['groups'][g]
    return out

def mask_ids(lab_, comps_, gi):
    x0 = min(comps_[i]['x'] for i in gi); x1 = max(comps_[i]['x'] + comps_[i]['w'] for i in gi)
    y0 = min(comps_[i]['y'] for i in gi); y1 = max(comps_[i]['y'] + comps_[i]['h'] for i in gi)
    return np.isin(lab_[y0:y1, x0:x1], gi), x0, y0, x1, y1

def box3(*keys):
    return mask_ids(lab3, comps3, gids(rows3, keys))

def bounds(rec):
    bp = BoundsPen(None); rec.replay(bp); return bp.bounds

def xform(rec, sx=1, dx=0, dy=0):
    out = RecordingPen(); rec.replay(TransformPen(out, (sx, 0, 0, sx, dx, dy))); return out

def place(name, m, s, rule='base', target=0, lsb=32, rsb=32, weight=True):
    rec, adv = make(None, m, s, m.shape[0], lsb, rsb, weight)
    b = bounds(rec)
    dy = {'base': -b[1], 'below': target - b[1], 'top': target - b[3],
          'center': target - (b[1] + b[3]) / 2}[rule]
    rec = xform(rec, 1, 0, dy); glyphs[name] = (rec, adv); return rec

hy = bounds(glyphs['uni002D'][0]); MID = (hy[1] + hy[3]) / 2

def u(cp): return 'uni%04X' % cp

# ---- symbols
SYM = [('6.0', [0x2192], 'center', MID), ('6.1', [0x2190], 'center', MID),
       ('6.2', [0x2191], 'base', 0), ('6.3', [0x2193], 'base', 0),
       ('6.4', [0x23], 'base', 0), ('6.5', [0x2A], 'top', CAP),
       ('7.0', [0x2713, 0x2714], 'base', 0), ('7.1', [0x2717, 0x2718], 'base', 0),
       ('7.2', [0x20AC], 'base', 0), ('7.4', [0x24], 'below', -50),
       ('7.5', [0x5B], 'below', -110), ('7.6', [0x5D], 'below', -110), ('7.7', [0x5F], 'top', -60),
       ('8.1', [0x2B], 'center', MID), ('8.3', [0x3D], 'center', MID), ('8.4', [0x25], 'base', 0),
       ('9.1', [0x25A1, 0x2022, 0x25AB], 'center', MID + 40),
       ('11.3', [0x2013, 0x2014], 'center', MID), ('11.6', [0x7E], 'center', MID)]
for key, cps, rule, tgt in SYM:
    m = box3(key)[0]
    place(u(cps[0]), m, S3, rule, tgt)
    for cp in cps[1:]: EXTRA_CMAP[cp] = u(cps[0])
m = box3('11.0', '11.1', '11.2')[0]; place('uni2026', m, S3, 'base', weight=False)

# smiley + its mouth alone, for the ◡ + combining diaeresis ligature
gi = gids(rows3, ['10.2']); m, x0, y0, x1, y1 = mask_ids(lab3, comps3, gi)
sm = place('smiley', m, S3, 'base', lsb=40, rsb=40)
EXTRA_CMAP[0x263A] = 'smiley'
mouth = max(gi, key=lambda i: comps3[i]['a'])
mm_, mx0, my0, mx1, my1 = mask_ids(lab3, comps3, [mouth])
full = np.zeros_like(m); full[my0 - y0:my1 - y0, mx0 - x0:mx1 - x0] = mm_
rec, adv = make(None, full, S3, m.shape[0], 40, 40)
glyphs['uni25E1'] = (xform(rec, 1, 0, -bounds(glyphs['smiley'][0])[1] + 0), adv)

# ---- handwritten capitals/letters from photo 3
row12 = [box3(k) for k in ('12.6', '12.7')]
BASE12 = np.median([r[4] for r in row12])
for key, ch in (('12.3', 'Ç'), ('12.5', 'Ø'), ('12.6', 'Œ'), ('12.7', 'Æ')):
    m, x0, y0, x1, y1 = box3(key)
    above = BASE12 - y0
    s_ = S3 * ((CAP / S3) / above) ** BLEND
    make(gname(ch), m, s_, above, 32, 32)
    if ch == 'Ç':
        ced_mask = m.copy(); ced_mask[:int(above) + 4] = False; CED_S = s_
BASE5 = box3('5.1')[4]  # small ü: only used as baseline reference
m, x0, y0, x1, y1 = box3('5.2')  # ÿ
make(gname('ÿ'), m, S3 * (DESC_T / S3 / m.shape[0]) ** 0.4, BASE5 - y0, 32, 32)

# ---- accent marks (recordings, origin roughly at their bottom-left)
def mark_from(lab_, comps_, gi, s):
    m = mask_ids(lab_, comps_, gi)[0]
    rec, _ = make(None, m, s, m.shape[0], 0, 0)
    b = bounds(rec); return xform(rec, 1, -b[0], -b[1])

def accent_of(ch):
    keys = M[ch][0]; gi = ids(*keys)
    big = max(gi, key=lambda i: comps[i]['a'])
    return mark_from(lab, comps, [i for i in gi if i != big], scale_for(ch, keys, 'acc'))

MARK = {'acute': accent_of('é'), 'grave': accent_of('è'), 'dieresis': accent_of('ë'),
        'circumflex': mark_from(lab, comps, ids('9.0'), scale_for('ê', M['ê'][0], 'acc'))}
def width_norm(key, target_w):
    gi = gids(rows3, [key]); m = mask_ids(lab3, comps3, gi)[0]
    return mark_from(lab3, comps3, gi, target_w / m.shape[1])
MARK['tilde'] = width_norm('12.0', 210)
MARK['ring'] = width_norm('12.1', 130)
MARK['caron'] = width_norm('12.4', 170)
rec, _ = make(None, ced_mask, CED_S, ced_mask.shape[0], 0, 0)
b = bounds(rec); MARK['cedilla'] = xform(rec, 1, -b[0], -b[3])  # origin at top-left

# dotless i
gi = ids(*M['i'][0]); big = max(gi, key=lambda i: comps[i]['a'])
m, x0, y0, x1, y1 = mask_of(M['i'][0])
mi = np.isin(lab[y0:y1, x0:x1], [big])
_s = scale_for('i', M['i'][0], 'asc'); _l, _r = optical(mi, _s, m.shape[0], XHT)
make('uni0131', mi, _s, m.shape[0], _l, _r)

def compose(ch, base, mark, cap):
    brec, adv = glyphs[gname(base) if base != 'ı' else 'uni0131']
    b = bounds(brec); mrec = MARK[mark]; mb = bounds(mrec)
    sc = 0.9 if cap else 1.0
    cx = (b[0] + b[2]) / 2
    out = RecordingPen(); brec.replay(out)
    if mark == 'cedilla':
        sc = 1.0 if cap else 0.85
        dx = cx - (mb[0] + mb[2]) / 2 * sc; dy = 30
    else:
        gap = 30 if mark == 'ring' else (45 if cap else 55)
        dx = cx - (mb[0] + mb[2]) / 2 * sc; dy = b[3] + gap - mb[1] * sc
    mrec.replay(TransformPen(out, (sc, 0, 0, sc, dx, dy)))
    glyphs[gname(ch)] = (out, adv)

ACC = {'grave': 'ÀÈÌÒÙàìòù', 'acute': 'ÁÉÍÓÚÝáíóúý', 'circumflex': 'ÂÊÎÔÛâîôû',
       'tilde': 'ÃÑÕãñõ', 'dieresis': 'ÄËÏÖÜŸä', 'ring': 'Åå', 'caron': 'ŠŽšž', 'cedilla': 'ç'}
import unicodedata
for mark, chars in ACC.items():
    for ch in chars:
        base = unicodedata.normalize('NFD', ch)[0]
        if base == 'i': base = 'ı'
        compose(ch, base, mark, ch.isupper())

# spacing accents and the combining diaeresis
for cp, mark in ((0xB4, 'acute'), (0x60, 'grave'), (0x2C6, 'circumflex'), (0x2DC, 'tilde'),
                 (0xA8, 'dieresis'), (0x2DA, 'ring'), (0x2C7, 'caron')):
    mrec = MARK[mark]; mb = bounds(mrec)
    glyphs[u(cp)] = (xform(mrec, 1, 30, XHT + 70), int(mb[2] + 60))
mb = bounds(MARK['cedilla'])
glyphs[u(0xB8)] = (xform(MARK['cedilla'], 1, 30, 30), int(mb[2] + 60))
# combining diaeresis: zero width, sits over the previous character
mrec = MARK['dieresis']; mb = bounds(mrec)
glyphs['uni0308'] = (xform(mrec, 1, -260 - (mb[2] / 2), XHT + 60), 0)

# ---- < > × from photo 4 (scale matched on Œ and Æ, written in both photos)
lab4 = np.load('segments/p4/lab.npy'); rows4 = json.load(open('segments/p4/rows.json'))
comps4 = {c['id']: c for c in json.load(open('segments/p4/comps.json'))}
def box4(*keys): return mask_ids(lab4, comps4, gids(rows4, keys))
k4 = float(np.median([box3(a)[0].shape[0] / box4(b)[0].shape[0] for a, b in (('12.6', '0.7'), ('12.7', '0.8'), ('12.5', '0.6'))]))
print('photo4 scale', round(k4, 3))
for key, cp in (('1.1', 0x3C), ('1.2', 0x3E), ('1.4', 0xD7)):
    place(u(cp), box4(key)[0], S3 * k4, 'center', MID - (30 if cp == 0xD7 else 0))
