# Détourage des photos produit sur fond blanc pur (catalogue Farmasi) : le fond = les pixels presque blancs reliés au bord
# de l'image (remplissage depuis les bords), le reste = le produit. Plus fiable que le modèle de détourage, qui efface
# les flacons blancs et les boîtes pâles. Bord resserré d'un pixel puis adouci.
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
def cut(src, dst, tol=236, spread=14):
    a = np.asarray(Image.open(src).convert('RGB')).astype(np.int16)
    white = (a.min(2) >= tol) & ((a.max(2) - a.min(2)) <= spread)
    lab, n = ndimage.label(white)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    fg = ndimage.binary_fill_holes(~bg)
    lab2, n2 = ndimage.label(fg)
    if n2 > 1: fg = lab2 == (np.argmax(np.bincount(lab2.ravel())[1:]) + 1)
    al = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    im = Image.open(src).convert('RGB'); im.putalpha(al); im = im.crop(im.getbbox()); im.save(dst)
    return im.size
if __name__ == '__main__':
    for s in sys.argv[1:]:
        n = s.rsplit('/', 1)[-1].replace('.png', '')
        print(n, cut(s, f'assets/cut/{n}.png'))
