# Clean the BiRefNet cutouts taken from the client's flyer: drop specks, shave the dark fringe, trim to content.
# usage: python3 clean_cutouts.py <cut dir> <out dir>
import sys, glob, os
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
for f in sorted(glob.glob(src + '/*.png')):
    im = Image.open(f).convert('RGBA'); a = np.array(im.getchannel('A')).astype(float)
    lab, n = ndimage.label(a > 40)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(a), lab, range(1, n + 1)); keep = sizes >= sizes.max() * 0.04
        mask = np.isin(lab, np.nonzero(keep)[0] + 1); a = a * ndimage.binary_dilation(mask, iterations=3)
    A = Image.fromarray(a.clip(0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(A)
    bb = A.point(lambda v: 255 if v > 20 else 0).getbbox(); im = im.crop(bb)
    if max(im.size) > 1400: im.thumbnail((1400, 1400), Image.LANCZOS)
    im.save(os.path.join(out, os.path.basename(f)), optimize=True); print(os.path.basename(f), im.size)
