"""Draw the specimen images in specimen/ from the built font. Run after build.py."""
from PIL import Image, ImageDraw, ImageFont

FONT = 'fonts/otf/PDKHand-Edding141F.otf'
# Warm paper with a warm rule, like a notebook page. Ink is a warm near-black, like the Edding.
INK, PAPER, RULE, MUTED = (33, 30, 27), (247, 242, 233), (224, 213, 195), (150, 140, 128)
LABEL = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Medium.otf', 22) if __import__('os').path.exists('/usr/share/fonts/opentype/inter/Inter-Medium.otf') else ImageFont.load_default()


def sheet(path, lines, size=52, width=1600, lead=84):
    h = 60 + lead * len(lines)
    im = Image.new('RGB', (width, h), PAPER); d = ImageDraw.Draw(im)
    y = 30
    for kind, text in lines:
        if kind == 'gap':
            d.line([(40, y + int(size * 1.05)), (width - 40, y + int(size * 1.05))], fill=RULE, width=2)
        elif kind == 'label':
            d.text((60, y + lead - 40), text, font=LABEL, fill=MUTED)
        else:
            f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.RAQM)
            d.line([(40, y + int(size * 1.05)), (width - 40, y + int(size * 1.05))], fill=RULE, width=2)
            d.text((60, y), text, font=f, fill=INK)
        y += lead
    im.save(path)


sheet('specimen/characters.png', [
    ('label', 'Letters and figures'),
    ('text', 'abcdefghijklmnopqrstuvwxyz'),
    ('text', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    ('text', "0123456789 .,:;!?'\"-()&@/"),
    ('label', 'Accents'),
    ('text', 'à á â ã ä å ç è é ê ë ì í î ï ñ ò ó ô õ ö ù ú û ü ý ÿ š ž'),
    ('text', 'À Á Â Ã Ä Å Ç È É Ê Ë Ì Í Î Ï Ñ'),
    ('text', 'Ò Ó Ô Õ Ö Ù Ú Û Ü Ý Ÿ Š Ž Ø Œ Æ'),
    ('label', 'Symbols'),
    ('text', '→ ← ↑ ↓ ✓ ✗ + = % × < > • … – ~ # * € $ [ ] _ ◡̈'),
    ('label', 'Joined letters, and shapes that change with the letter next to them'),
    ('text', 'er et ch aa ij   tt totaal letter   Goed Gijs Groet'),
])
def wrap(text, font, width):
    lines, line = [], ''
    for word in text.split(' '):
        test = (line + ' ' + word).strip()
        if font.getlength(test) <= width or not line: line = test
        else: lines.append(line); line = word
    return lines + [line]


NOTE = ['Hi Sam,',
        'Nice start. The page reads calm and the title works well. I would make the button a little '
        'bigger, so a thumb finds it without looking. The text on a phone is worth a second check. '
        'Shall we go over it together on Thursday?',
        'Pieter ◡̈']
f = ImageFont.truetype(FONT, 56, layout_engine=ImageFont.Layout.RAQM)
note = []
for para in NOTE:
    note += [('text', l) for l in wrap(para, f, 1440)] if para else [('gap', '')]
sheet('specimen/feedback.png', note, size=56, lead=92)
print('specimen: characters.png, feedback.png')
