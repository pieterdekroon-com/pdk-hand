"""Draw the specimen images in specimen/ from the built font. Run after build.py."""
from PIL import Image, ImageDraw, ImageFont

FONT = 'fonts/otf/PDKHand-Edding141F.otf'
INK, PAPER, RULE, MUTED = (25, 25, 30), (250, 247, 240), (222, 228, 236), (130, 130, 130)
LABEL = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Medium.otf', 22) if __import__('os').path.exists('/usr/share/fonts/opentype/inter/Inter-Medium.otf') else ImageFont.load_default()


def sheet(path, lines, size=52, width=1600, lead=84):
    h = 60 + lead * len(lines)
    im = Image.new('RGB', (width, h), PAPER); d = ImageDraw.Draw(im)
    y = 30
    for kind, text in lines:
        if kind == 'label':
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
sheet('specimen/feedback.png', [
    ('text', 'Hé Sam,'),
    ('text', 'De opbouw is duidelijk, maar de knop valt weg.'),
    ('text', '✓ De kop staat goed, mooi rustig'),
    ('text', '✗ Knop mag 8px groter → beter klikbaar'),
    ('text', '• Check ook even de tekst op mobiel'),
    ('text', 'Groetjes, Pieter ◡̈'),
], size=56, lead=92)
print('specimen: characters.png, feedback.png')
