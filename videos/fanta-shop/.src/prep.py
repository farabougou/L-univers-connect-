# (assets/cut/c07.png : sortie de « hyperframes remove-background » sur c07 ; les autres pots en verre ne se détourent pas.)
# Fanta shop : couvertures TikTok de la boutique (720×1280) → tuiles recadrées et étalonnées, pot détouré, fonds flous.
# Étalonnage commun « Fanta » : contraste doux, couleurs un peu plus riches, ombres qui glissent vers le brun-rouge.
import os
from PIL import Image, ImageFilter
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT = f'{P}/assets/photos-src', f'{P}/assets/photos'
EMBER = np.array([26, 8, 6], np.float32) / 255

def grade(im, sat=1.1, con=1.08, expo=1.0, warm=0.02):
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    a = lum + (a - lum) * sat
    a = np.clip((a - 0.5) * con + 0.5, 0, 1) * expo
    sh = (1 - lum) ** 2.4
    a = a * (1 - 0.3 * sh) + EMBER * 0.3 * sh + np.array([warm, warm * 0.3, -warm]) * (1 - sh)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))

def crop(name, cx, cy, fw, aspect, out_w, **g):
    # cx, cy : centre en fraction ; fw : largeur du recadrage en fraction ; aspect : largeur / hauteur de la tuile
    im = Image.open(f'{SRC}/{name}.jpg').convert('RGB'); w, h = im.size
    cw = fw * w; ch = cw / aspect
    x0 = min(max(0, cx * w - cw / 2), w - cw); y0 = min(max(0, cy * h - ch / 2), h - ch)
    out_h = round(out_w / aspect)
    im = im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))).resize((out_w, out_h), Image.LANCZOS)
    if out_w > cw: im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    return grade(im, **g)

HEX = 0.866
TILES = {   # nom : (couverture, centre x, centre y, largeur, aspect, largeur de sortie)
    't-rouge':  ('c05', 0.60, 0.43, 0.80, HEX, 620),
    't-dore':   ('c08', 0.50, 0.31, 0.85, HEX, 620),
    't-plateau': ('c04', 0.55, 0.38, 0.95, HEX, 620),
    'flacon':   ('c00', 0.38, 0.33, 0.62, 0.62, 640),
    'savon':    ('c01', 0.50, 0.385, 1.00, 0.73, 560),
    'foulards': ('c02', 0.50, 0.385, 1.00, 0.73, 560),
}
for k, (n, cx, cy, fw, asp, ow) in TILES.items():
    crop(n, cx, cy, fw, asp, ow).save(f'{OUT}/{k}.jpg', quality=92); print(k)

# fonds : la même matière, très floue et sombre (deuxième plan de profondeur)
for k, (n, cx, cy) in {'bg-rouge': ('c09', 0.4, 0.5), 'bg-dore': ('c08', 0.5, 0.35)}.items():
    im = crop(n, cx, cy, 1.0, 1080 / 1920, 540, sat=1.25, con=1.0, expo=0.55)
    im.filter(ImageFilter.GaussianBlur(18)).resize((1080, 1920), Image.BICUBIC).save(f'{OUT}/{k}.jpg', quality=88); print(k)

# pot détouré (les deux pots empilés de c07). Deux réparations :
#  - le coin gauche du pot hexagonal touche le bord de la vidéo d'origine (lignes 130 à 310, coupé net à x = 0) :
#    la pointe manquante (environ 16 px, d'après l'axe de l'étiquette) est prolongée en V avec la couleur du bord ;
#  - le détourage laisse le verre du pot doré à moitié transparent : la silhouette (plus grande zone, trous bouchés)
#    devient opaque, puis son bord est resserré d'un pixel et adouci.
from scipy import ndimage
PAD, TIP, Y0, Y1, YV = 18, 16, 130, 310, 220
src = Image.open(f'{P}/assets/cut/c07.png').convert('RGBA').crop((0, 238, 324, 996))
w, h = src.size
O = np.zeros((h, w + PAD, 4), np.float32); O[:, PAD:] = np.asarray(src)
for y in range(Y0, Y1):
    e = TIP * (1 - abs(y - YV) / ((YV - Y0) if y < YV else (Y1 - YV)))
    if e <= 0 or O[y, PAD, 3] < 128: continue
    O[y, PAD - int(round(e)):PAD, :3] = O[y, PAD:PAD + 3, :3].mean(0)
    O[y, PAD - int(round(e)):PAD, 3] = 255
im = Image.fromarray(O.astype(np.uint8))
A = np.asarray(im)[..., 3]
lab, n = ndimage.label(A > 60)
big = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
mask = ndimage.binary_fill_holes(ndimage.binary_closing(big, iterations=3))
r, g, b, _ = im.split()
a = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
rgb = grade(Image.merge('RGB', (r, g, b)), sat=1.12, con=1.1, expo=1.04)
im = Image.merge('RGBA', (*rgb.split(), a))
bb = im.getbbox(); im = im.crop(bb).resize((round((bb[2] - bb[0]) * 2), round((bb[3] - bb[1]) * 2)), Image.LANCZOS)
rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.4, percent=80, threshold=2))
Image.merge('RGBA', (*rgb.split(), im.split()[3])).save(f'{OUT}/pots.png'); print('pots', im.size)
