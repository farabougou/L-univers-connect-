# Farmasi : préparation des images (sources : page d'accueil fr.farmasi.com, catalogue et bannière « Midnight Ritual »).
#  - produits détourés : modèle de détourage pour les pots et flacons colorés, remplissage du fond blanc pour les autres
#    (cutwhite.py) et enveloppe convexe pour le sérum en verre blanc ; ici on les recadre au plus juste ;
#  - symbole Farmasi : extrait du logo officiel (les deux flammes corail), agrandi ×2 ;
#  - plaques « Midnight Ritual » : la bannière sans son texte, recadrée en 9:16 et en 16:9 (côté gauche prolongé par
#    le même vert), étalonnée et piquée.
import os
import numpy as np
from PIL import Image, ImageFilter
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, CUT, OUT = f'{P}/assets/src', f'{P}/assets/cut', f'{P}/assets/img'
os.makedirs(OUT, exist_ok=True)

PRODUCTS = {'serum': '1000272', 'contour': '1000273', 'tonique': '1000270', 'masque': '1000269',
            'serenity': '1000764', 'restore': '1002297', 'aloe': '1002303', 'delish': '1002740'}
TRIM = {'serenity': 28}
for name, ref in PRODUCTS.items():
    im = Image.open(f'{CUT}/{ref}.png').convert('RGBA')
    a = np.asarray(im)[..., 3]; a = np.where(a > 12, a, 0).astype(np.uint8)   # traces de détourage presque invisibles
    # bord : 2 px resserrés (le liseré blanc du fond d'origine se voyait sur les fonds colorés), puis adouci
    a = np.asarray(Image.fromarray(a).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.9)))
    im.putalpha(Image.fromarray(a)); im = im.crop(im.getbbox())
    # bas : l'ombre claire posée sous la boîte Serenity sur la photo du catalogue (≈ 28 px plus clairs que la boîte) est retirée
    if name in TRIM: im = im.crop((0, 0, im.width, im.height - TRIM[name]))
    im.save(f'{OUT}/{name}.png'); print(name, im.size)

# symbole : pixels corail du logo (rouge fort, vert et bleu faibles)
lg = Image.open(f'{SRC}/logo.png').convert('RGBA'); A = np.asarray(lg).astype(np.int16)
coral = (A[..., 0] > 180) & (A[..., 1] < 150) & (A[..., 3] > 0)
ys, xs = np.nonzero(coral); box = (xs.min() - 4, ys.min() - 4, xs.max() + 5, ys.max() + 5)
sym = lg.crop(box); sym = sym.resize((sym.width * 2, sym.height * 2), Image.LANCZOS)
sym.save(f'{OUT}/symbole.png'); print('symbole', sym.size)

# plaques de minuit
ban = Image.open(f'{SRC}/midnight-banner.png').convert('RGB')
def grade(im):
    a = np.asarray(im).astype(np.float32) / 255
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    a = lum + (a - lum) * 1.08; a = np.clip((a - 0.5) * 1.06 + 0.5, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))
v = ban.crop((1235, 0, 1235 + 729, 1295)).resize((1080, 1920), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
grade(v).save(f'{OUT}/minuit-9x16.jpg', quality=92); print('minuit-9x16')
# 16:9 : la bannière fait 2:1 ; on garde x ≥ 900 (le texte d'origine est à gauche) et on prolonge à gauche par le vert du fond
right = ban.crop((900, 0, 2590, 1295)); W16 = round(1295 * 16 / 9); x0 = W16 - right.width
h = ban.crop((900, 0, 960, 1295)).resize((W16, 1295), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30))
ramp = Image.fromarray((np.clip(np.arange(right.width) / 160, 0, 1)[None, :].repeat(1295, 0) * 255).astype(np.uint8))   # raccord doux sur 160 px
h.paste(right, (x0, 0), ramp)
grade(h.resize((1920, 1080), Image.LANCZOS)).save(f'{OUT}/minuit-16x9.jpg', quality=92); print('minuit-16x9')
