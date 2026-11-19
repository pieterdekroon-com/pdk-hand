import os, json, numpy as np, cv2, potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

lab = np.load('segments/p1/lab.npy')
rows = json.load(open('segments/p1/rows.json'))
comps = {c['id']: c for c in json.load(open('segments/p1/comps.json'))}

def ids(*keys):
    out = []
    for k in keys:
        r, g = map(int, k.split('.'))
        out += rows[r]['groups'][g]
    return out

# char -> (group keys, class, line)
M = {}
def put(chars, keys, cls, line):
    for ch, k in zip(chars, keys):
        M[ch] = (k if isinstance(k, list) else [k], cls, line)

put('abcdefghijklmno', ['1.%d' % i for i in range(15)], None, 'L1')
put('prstuvwxz', ['2.%d' % i for i in range(9)], None, 'L2')
put('y', ['3.0'], None, 'L2')
put('ABCDEFGHIJKL', ['4.%d' % i for i in range(12)], 'cap', 'L3')
put('MOPRSTUV', ['5.1', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.9'], 'cap', 'L4')
put('XY', ['6.1', '6.2'], 'cap', 'L5')
put('ZWN', ['6.4', '6.5', '6.6'], 'cap', 'L5')
put('0123456789', ['7.0', '7.2', '7.3', '7.4', '7.5', '7.6', '7.7', '7.8', '7.9', '7.10'], 'cap', 'L6')
put('.,:;!?\'', ['8.2', '8.3', '8.4', '8.5', '8.6', '8.9', '8.10'], 'punct', 'L7')
M['"'] = (['8.11', '8.12'], 'punct', 'L7')
put('-()&@/', ['8.13', '8.14', '8.15', '8.16', '8.17', '8.18'], 'punct', 'L7')
put('ëéöüè', ['10.0', '10.1', '10.4', '10.5', '10.6'], 'acc', 'L8')
M['ï'] = (['10.2', '10.3'], 'acc', 'L8')
M['ê'] = (['10.7', '9.0'], 'acc', 'L8')
M['ij'] = (['11.0'], 'desc', 'L9')
M['IJ'] = (['11.2'], 'capdesc', 'L9')
put(['et', 'er', 'ch'], ['12.0', '12.2', '12.5'], 'lig', 'L10')
put(['oo', 'aa', 'sch'], ['13.0', '13.1', '13.3'], 'lig', 'L11')

XH = set('acemnorsuvwxz'); ASC = set('bdfhklti'); DESC = set('gjpqy')
for ch in M:
    if M[ch][1] is None:
        M[ch] = (M[ch][0], 'x' if ch in XH else 'asc' if ch in ASC else 'desc', M[ch][2])

def mask_of(keys):
    g = ids(*keys)
    y0 = min(comps[i]['y'] for i in g); y1 = max(comps[i]['y'] + comps[i]['h'] for i in g)
    x0 = min(comps[i]['x'] for i in g); x1 = max(comps[i]['x'] + comps[i]['w'] for i in g)
    m = np.isin(lab[y0:y1, x0:x1], g)
    return m, x0, y0, x1, y1

def body_h(keys):
    # height of the largest component (accent bodies, i/j stems)
    g = ids(*keys); big = max(g, key=lambda i: comps[i]['a'])
    return comps[big]['h']

# ---- baselines per written line: linear fit through bottoms of sitting glyphs
pts = {}
for ch, (keys, cls, line) in M.items():
    if cls in ('x', 'asc', 'cap', 'acc') or ch in ('.', '!', '?', ':', '&', 'er', 'oo', 'aa', 'et', 'ch', 'sch'):
        m, x0, y0, x1, y1 = mask_of(keys)
        pts.setdefault(line, []).append(((x0 + x1) / 2, y1))
pts['L9'] = pts['L8']  # ij row has no sitting glyphs: borrow nearby fit, corrected below
def base_at(line, x):
    p = np.array(pts[line])
    if len(p) >= 3:
        a, b = np.polyfit(p[:, 0], p[:, 1], 1)
        return a * x + b
    return np.median(p[:, 1])

# ---- target sizes (font units)
CAP, XHT, ASCT = 700, 430, 720
def med(cls, f=lambda k: mask_of(k)[0].shape[0]):
    return np.median([f(k) for ch, (k, c, l) in M.items() if c == cls])
line_of = {ch: v[2] for ch, v in M.items()}
cap_px = med('cap'); x_px = med('x'); asc_px = med('asc')
F = CAP / cap_px
DESC_T = 0.92 * np.median([mask_of(M[c][0])[0].shape[0] for c in 'gjpy']) * F
print('cap_px', cap_px, 'x_px', x_px, 'asc_px', asc_px, 'F', round(F, 2))
BLEND = 0.9
WEIGHT = 68      # target stroke width in font units (an Edding has one stroke width)
WEIGHT_MIX = 1.0  # how far each glyph is pulled toward the class target (1 = fully uniform)

def scale_for(ch, keys, cls):
    m = mask_of(keys)[0]; h = m.shape[0]
    if cls == 'cap': t = CAP / F; hh = h
    elif cls == 'x': t = XHT / F; hh = h
    elif cls == 'asc': t = ASCT / F; hh = h
    elif cls == 'acc': t = XHT / F; hh = body_h(keys)
    elif cls == 'lig':
        if ch in ('oo', 'aa', 'er'): hh = h; t = XHT / F
        else:  # use the x-height scale of the partner ligatures on the same written line
            ref = ['er'] if line_of[ch] == 'L10' else ['oo', 'aa']
            return float(np.mean([scale_for(r, M[r][0], 'lig') for r in ref])) * (1.12 if ch == 'sch' else 1)
    elif cls == 'desc':
        if ch == 'ij': return scale_for('y', M['y'][0], 'desc') * 0.95
        return F * (DESC_T / F / h) ** 0.4
    elif cls == 'capdesc': return F * 0.8
    else: return F
    return F * (t / hh) ** BLEND

SIT = {'x', 'asc', 'cap', 'acc', 'lig'}

def stroke_px(m):
    b = np.pad(m, 2).astype(np.uint8); dt = cv2.distanceTransform(b, cv2.DIST_L2, 5)
    mx = cv2.dilate(dt, np.ones((3, 3))); r = (dt >= mx) & (dt > 1.5)
    return 2 * float(np.median(dt[r])) if r.any() else None

def trace(m, delta=0.0):
    up = cv2.resize(np.pad(m, 6).astype(np.float32), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    up = cv2.GaussianBlur(up, (0, 0), 1.6)
    b2 = up > 0.5
    if abs(delta) > 0.1:  # grow/shrink the stroke by delta (original px) on each side
        din = cv2.distanceTransform(b2.astype(np.uint8), cv2.DIST_L2, 5)
        dout = cv2.distanceTransform((~b2).astype(np.uint8), cv2.DIST_L2, 5)
        b2 = (din - dout) > -2 * delta
    mm = np.pad(b2, 4)
    return potrace.Bitmap(~mm).trace(turdsize=30, alphamax=1.0, opticurve=True, opttolerance=0.3), 4

glyphs = {}
def make(name, m, s, bottom_y_img, lsb=45, rsb=45, weight=True):
    """m: bool mask; s: units per px; bottom_y_img: image row (within mask) that maps to y=0."""
    delta = 0.0
    if weight:
        cur = stroke_px(m)
        if cur:
            cur_u = cur * s; want = cur_u + WEIGHT_MIX * (WEIGHT - cur_u)
            delta = float(np.clip((want - cur_u) / s / 2, -3, 3))
    paths, pad = trace(m, delta)
    pad = pad + 12
    h, w = m.shape
    pen = RecordingPen()
    def T(p):
        x = (p.x / 2 - pad / 2) * s + lsb
        y = (bottom_y_img - (p.y / 2 - pad / 2)) * s
        return (round(x), round(y))
    for c in paths:
        pen.moveTo(T(c.start_point))
        for seg in c.segments:
            if seg.is_corner:
                pen.lineTo(T(seg.c)); pen.lineTo(T(seg.end_point))
            else:
                pen.curveTo(T(seg.c1), T(seg.c2), T(seg.end_point))
        pen.closePath()
    adv = int(round(w * s + lsb + rsb))
    if name: glyphs[name] = (pen, adv)
    return pen, adv

def optical(m, s, bot, band_top, C=52, alpha=0.6, cap_u=150, lo=-40):
    h, w = m.shape
    r0 = int(max(0, bot - band_top / s)); r1 = int(min(h, bot))
    capd = cap_u / s; L = []; R = []
    for r in range(r0, r1):
        xs = np.flatnonzero(m[r])
        if len(xs): L.append(min(xs[0], capd)); R.append(min(w - 1 - xs[-1], capd))
        else: L.append(capd); R.append(capd)
    if not L: return 32, 32
    lsb = C - alpha * float(np.mean(L)) * s; rsb = C - alpha * float(np.mean(R)) * s
    return int(max(lo, lsb)), int(max(lo, rsb))

def gname(ch):
    if len(ch) > 1: return {'ij': 'ij', 'IJ': 'IJ'}.get(ch, '_'.join(ch))
    return 'uni%04X' % ord(ch)

SB_ADJ = {'t': (-35, -45), 'r': (0, -15), 'f': (-10, -25)}
SQUEEZE = {'u': 0.72, 't': 0.85, 'G': 0.82, 'Z': 0.85, '2': 0.88, 'E': 0.92}
for ch, (keys, cls, line) in M.items():
    m, x0, y0, x1, y1 = mask_of(keys)
    s = scale_for(ch, keys, cls)
    if ch == 'er': s *= 1.1   # the e inside er was written smaller than the loose e
    if ch in SQUEEZE:
        m = cv2.resize(m.astype(np.float32), (int(m.shape[1] * SQUEEZE[ch]), m.shape[0]), interpolation=cv2.INTER_AREA) > 0.5
    if cls in SIT and ch not in ('et', 'ch', 'sch') and ch not in DESC:
        bot = m.shape[0]
    else:
        bot = base_at(line, (x0 + x1) / 2) - y0
        if line == 'L9':  # ij row: align its curl bottoms like lowercase y does on L2
            yk = M['y'][0]; ym, yx0, yy0, yx1, yy1 = mask_of(yk)
            ydesc = yy1 - base_at('L2', (yx0 + yx1) / 2)
            ratio = 0.85 if ch == 'ij' else 0.9
            bot = m.shape[0] - ydesc * ratio
    if cls == 'punct':
        make(gname(ch), m, s, bot, 25, 25, weight=ch not in '.:;,!?\'"')
    else:
        band = CAP if cls in ('cap', 'capdesc') else XHT
        lsb, rsb = optical(m, s, bot, band)
        a, b = SB_ADJ.get(ch, (0, 0)); lsb += a; rsb += b
        make(gname(ch), m, s, bot, lsb, rsb)

# ---- q and Q from the second photo (same page, q and Q added)
lab2 = np.load('segments/p2/lab.npy'); rows2 = json.load(open('segments/p2/rows.json'))
comps2 = {c['id']: c for c in json.load(open('segments/p2/comps.json'))}
def box2(k):
    r, g = map(int, k.split('.')); gi = rows2[r]['groups'][g]
    x0 = min(comps2[i]['x'] for i in gi); x1 = max(comps2[i]['x'] + comps2[i]['w'] for i in gi)
    y0 = min(comps2[i]['y'] for i in gi); y1 = max(comps2[i]['y'] + comps2[i]['h'] for i in gi)
    return np.isin(lab2[y0:y1, x0:x1], gi), x0, y0, x1, y1
pairs = [('4.0', '4.0'), ('4.1', '4.1'), ('5.3', '5.2'), ('6.6', '6.5'), ('2.0', '2.0'), ('1.0', '1.0')]
k = float(np.median([mask_of([a])[0].shape[0] / box2(b)[0].shape[0] for a, b in pairs]))
print('photo scale k', round(k, 3))
def base2(keys, x):
    p = np.array([((box2(q)[1] + box2(q)[3]) / 2, box2(q)[4]) for q in keys])
    a_, b_ = np.polyfit(p[:, 0], p[:, 1], 1); return a_ * x + b_
def rescale(m):
    r = cv2.resize(m.astype(np.float32), (int(round(m.shape[1] * k)), int(round(m.shape[0] * k))), interpolation=cv2.INTER_LINEAR)
    return r > 0.5
for ch, key, line_keys, cls in (('q', '3.1', ['2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8'], 'desc'),
                                ('Q', '6.6', ['6.0', '6.1', '6.3', '6.4', '6.5'], 'cap')):
    m, x0, y0, x1, y1 = box2(key)
    bot = (base2(line_keys, (x0 + x1) / 2) - y0) * k
    m = rescale(m); h = m.shape[0]
    if cls == 'desc': s_ = F * (DESC_T / F / h) ** 0.4
    else:  # normalise on the part above the baseline, so the tail does not shrink the letter
        s_ = F * ((CAP / F) / bot) ** BLEND
    lsb, rsb = optical(m, s_, bot, XHT if ch == 'q' else CAP)
    make(gname(ch), m, s_, bot, lsb, rsb)

# ---- space, notdef

# ---- photo 5: natural er, et and t written in words (more upright, short t crossbar)
lab5 = np.load('segments/p5/lab.npy'); rows5 = json.load(open('segments/p5/rows.json'))
comps5 = {c['id']: c for c in json.load(open('segments/p5/comps.json'))}
def box5(k):
    r, g = map(int, k.split('.')); gi = rows5[r]['groups'][g]
    x0 = min(comps5[i]['x'] for i in gi); x1 = max(comps5[i]['x'] + comps5[i]['w'] for i in gi)
    y0 = min(comps5[i]['y'] for i in gi); y1 = max(comps5[i]['y'] + comps5[i]['h'] for i in gi)
    return np.isin(lab5[y0:y1, x0:x1], gi)
def e_part_h(m, frac=0.4):
    rr = np.flatnonzero(m[:, :int(m.shape[1] * frac)].any(1)); return rr[-1] - rr[0] + 1
for name, key, kind in (('e_r', '1.8', 'e'), ('e_r.alt1', '1.3', 'e'),
                        ('e_t', '2.1', 'e'), ('e_t.alt1', '1.2', 'e'),
                        ('uni0074', '2.5', 't'), ('uni0074.alt1', '2.3', 't')):
    m = box5(key)
    s_ = XHT / e_part_h(m) if kind == 'e' else 690 / m.shape[0]
    bot = m.shape[0]
    lsb, rsb = optical(m, s_, bot, XHT)
    if kind == 't': rsb -= 15
    make(name, m, s_, bot, lsb, rsb)

# ---- photo 6: sentences. Only letters that beat the current ones, plus variants
lab6 = np.load('segments/p6/lab.npy'); rows6 = json.load(open('segments/p6/rows.json'))
comps6 = {c['id']: c for c in json.load(open('segments/p6/comps.json'))}
def box6(k):
    r, g = map(int, k.split('.')); gi = rows6[r]['groups'][g]
    x0 = min(comps6[i]['x'] for i in gi); x1 = max(comps6[i]['x'] + comps6[i]['w'] for i in gi)
    y0 = min(comps6[i]['y'] for i in gi); y1 = max(comps6[i]['y'] + comps6[i]['h'] for i in gi)
    return np.isin(lab6[y0:y1, x0:x1], gi), y0, y1
def base6(k):
    r = int(k.split('.')[0]); bs = []
    for gi in rows6[r]['groups']:
        hh = max(comps6[i]['y'] + comps6[i]['h'] for i in gi) - min(comps6[i]['y'] for i in gi)
        if hh > 25: bs.append(max(comps6[i]['y'] + comps6[i]['h'] for i in gi))
    return float(np.median(bs))
P6 = [('uni0059', '0.8', 'capdesc', 0),
      ('uni0047', '7.11', 'cap', 0), ('uni0047.alt1', '2.10', 'cap', 0), ('uni0047.alt2', '0.0', 'cap', 0),
      ('uni005A', '9.14', 'cap', 1), ('uni005A.alt1', '1.0', 'cap', 1)]
for name, key, kind, cut in P6:
    m, y0, y1 = box6(key)
    if cut:
        w = m.shape[1]; col = m.sum(0); lo, hi = int(w * 0.35), int(w * 0.75)
        m = m[:, :lo + int(np.argmin(col[lo:hi]))]
        rr = np.flatnonzero(m.any(1)); m = m[rr[0]:rr[-1] + 1]; y0 += rr[0]
        cc = np.flatnonzero(m.any(0)); m = m[:, cc[0]:cc[-1] + 1]
    h = m.shape[0]
    if kind in ('desc', 'capdesc'):
        above = base6(key) - y0
        s_ = (XHT if kind == 'desc' else CAP) / above; bot = above
    else:
        s_ = {'cap': CAP, 'x': XHT, 'asc': ASCT}[kind] / h; bot = h
    band = CAP if kind in ('cap', 'capdesc') else XHT
    lsb, rsb = optical(m, s_, bot, band)
    make(name, m, s_, bot, lsb, rsb)

exec(open('scripts/extra.py').read())
for nm, adv in (('space', 250), ('.notdef', 400)):
    glyphs[nm] = (RecordingPen(), adv)

# ---- build font
order = ['.notdef', 'space'] + sorted(n for n in glyphs if n not in ('.notdef', 'space'))
cmap = {0x20: 'space', 0xA0: 'space'}
for n in order:
    if n.startswith('uni') and len(n) == 7: cmap[int(n[3:], 16)] = n
cmap[0x0133] = 'ij'; cmap[0x0132] = 'IJ'
cmap[0x2019] = 'uni0027'; cmap[0x2018] = 'uni0027'; cmap[0x201C] = 'uni0022'; cmap[0x201D] = 'uni0022'
cmap[0x2010] = 'uni002D'
cmap.update(EXTRA_CMAP)

FAM = 'PDK Hand'
PEN = 'Edding 141F'
PS = 'PDKHand-Edding141F'
VERSION = '1.700'
NAMES = {'familyName': FAM + ' ' + PEN, 'styleName': 'Regular', 'uniqueFontIdentifier': PS + '-' + VERSION,
         'typographicFamily': FAM, 'typographicSubfamily': PEN,
         'fullName': FAM + ' ' + PEN, 'psName': PS, 'version': 'Version ' + VERSION,
         'copyright': 'Copyright 2026 Pieter de Kroon. All rights reserved.',
         'manufacturer': 'Pieter de Kroon', 'designer': 'Pieter de Kroon',
         'vendorURL': 'https://pieterdekroon.com', 'designerURL': 'https://pieterdekroon.com',
         'description': "Pieter de Kroon's handwriting, written with an Edding 141F.",
         'licenseDescription': 'All rights reserved. Not for use or distribution without written permission from Pieter de Kroon.'}

def bounds_of(n):
    bp = BoundsPen(None); glyphs[n][0].replay(bp); return bp.bounds

def setup(fb, ttf):
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    if ttf:
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        from fontTools.pens.cu2quPen import Cu2QuPen
        g = {}
        for n in order:
            p = TTGlyphPen(None); glyphs[n][0].replay(Cu2QuPen(p, max_err=1.0, reverse_direction=True)); g[n] = p.glyph()
        fb.setupGlyf(g)
    else:
        def to_cs(n):
            rec, adv = glyphs[n]; p = T2CharStringPen(adv, None); rec.replay(p); return p.getCharString()
        fb.setupCFF(PS, {'FullName': FAM + ' ' + PEN, 'FamilyName': FAM}, {n: to_cs(n) for n in order}, {})
    # left side bearing in hmtx must equal the left edge of the outline (Windows positions glyphs with it)
    fb.setupHorizontalMetrics({n: (glyphs[n][1], int(round((bounds_of(n) or (0,))[0]))) for n in order})
    fb.setupHorizontalHeader(ascent=900, descent=-400)
    fb.setupNameTable(NAMES)
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-350, sTypoLineGap=150, usWinAscent=1050, usWinDescent=600,
                sxHeight=XHT, sCapHeight=CAP, achVendID='PDK ', fsType=0)
    fb.setupPost()
    if ttf: fb.setupMaxp() if hasattr(fb, 'setupMaxp') else None

fea = '''
languagesystem DFLT dflt;
languagesystem latn dflt;
feature liga {
  sub uni0065 uni0074 by e_t;
  sub uni0065 uni0072 by e_r;
  sub uni0063 uni0068 by c_h;
  sub uni0061 uni0061 by a_a;
  sub uni0069 uni006A by ij;
  sub uni25E1 uni0308 by smiley;
} liga;
@LC = [uni0061 uni0063 uni0064 uni0065 uni0067 uni006D uni006E uni006F uni0070 uni0071 uni0072 uni0073 uni0075 uni0076 uni0077 uni0078 uni0079 uni007A a_a e_r c_h ij uni00E9 uni00E8 uni00EB uni00F6 uni00FC];
feature kern {
  pos uni0054 @LC -110;  pos uni0056 @LC -50;  pos uni0057 @LC -40;  pos uni0059 @LC -60;
  pos uni0046 @LC -60;   pos uni0050 @LC -40;  pos uni0074 @LC -25;
  pos uni0054 uni002E -80; pos uni0054 uni002C -80; pos uni0050 uni002E -80; pos uni0050 uni002C -80;
} kern;
@CYA = [uni0061 uni0062 uni0063 uni0064 uni0065 uni0066 uni0067 uni0068 uni0069 uni006A uni006B uni006C uni006D a_a c_h];
@CYB = [uni006E uni006F uni0070 uni0071 uni0072 uni0073 uni0074 uni0075 uni0076 uni0077 uni0078 uni0079 uni007A e_r e_t ij uni0074.alt1 e_r.alt1 e_t.alt1];
@CY1 = [uni0061 uni0062 uni0063 uni0064 uni0065 uni0066 uni0067 uni0068 a_a c_h];
@CY2 = [uni0069 uni006A uni006B uni006C uni006D uni006E uni006F uni0070 uni0071 ij];
feature calt {
  sub uni0047' @CY1 by uni0047.alt1;
  sub uni0047' @CY2 by uni0047.alt2;
  sub uni005A' @CY1 by uni005A.alt1;
  sub uni005A' @CY2 by uni005A.alt1;
  sub uni0074 uni0074' by uni0074.alt1;
  sub @CYA uni0074' by uni0074.alt1;
  sub @CYB e_r' by e_r.alt1;
  sub @CYA e_t' by e_t.alt1;
} calt;
feature dlig {
  sub uni0073 uni0063 uni0068 by s_c_h;
  sub uni006F uni006F by o_o;
  sub uni0049 uni004A by IJ;
} dlig;
'''
for ttf in (False, True):
    fb = FontBuilder(1000, isTTF=ttf)
    setup(fb, ttf)
    addOpenTypeFeaturesFromString(fb.font, fea)
    if ttf:
        fb.save(f'fonts/ttf/{PS}.ttf')
    else:
        fb.save(f'fonts/otf/{PS}.otf')
        fb.font.flavor = 'woff2'; fb.font.save(f'fonts/webfonts/{PS}.woff2')
print('glyphs', len(order), 'version', VERSION)
