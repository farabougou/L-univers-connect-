# Photos d'installations réelles (Wikimedia Commons, domaine public / CC0 / CC BY) → plans verticaux étalonnés.
# Recadrage 9:16 autour d'un point d'intérêt, marge de 10 % pour les mouvements de caméra (1188×2112),
# étalonnage commun « Enoryx » : ombres bleu nuit, couleurs un peu éteintes, contraste doux, piqué léger.
import os
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OW, OH = 1188, 2112
# nom : (centre x en fraction, haut, bas en fraction de la hauteur utile, exposition)
CROPS = {
    'hk':      (0.62, 0.00, 0.85, 0.95),   # bas coupé : filigrane de l'appareil photo et enseignes de rue
    'fns':     (0.58, 0.00, 1.00, 0.92),
    'chiller': (0.42, 0.00, 1.00, 0.95),
    'dctower': (0.50, 0.00, 1.00, 0.95),
    'rooftop': (0.55, 0.00, 1.00, 1.00),
    'genset':  (0.36, 0.00, 1.00, 0.95),
    'valve':   (0.50, 0.00, 1.00, 1.00),
    'duct':    (0.50, 0.00, 1.00, 1.00),
}
NAVY = np.array([5, 11, 26], np.float32)
for k, (cx, top, bot, expo) in CROPS.items():
    im = Image.open(f'{P}/assets/photos-src/{k}.jpg').convert('RGB')
    w, h = im.size
    y0, y1 = int(h * top), int(h * bot)
    ch = y1 - y0; cw = ch * 9 / 16
    if cw > w: cw = w; ch = cw * 16 / 9; y1 = y0 + int(ch)
    x0 = min(max(0, cx * w - cw / 2), w - cw)
    im = im.crop((int(x0), y0, int(x0 + cw), y1)).resize((OW, OH), Image.LANCZOS)
    if cw < OW: im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))   # photo agrandie : piqué
    a = np.asarray(im).astype(np.float32) / 255
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    a = lum + (a - lum) * 0.82                       # couleurs un peu éteintes
    a = np.clip((a - 0.5) * 1.08 + 0.5, 0, 1) * expo  # contraste doux, exposition
    sh = (1 - lum) ** 2.2                             # les ombres glissent vers le bleu nuit d'Enoryx
    a = a * (1 - 0.35 * sh) + (NAVY / 255) * 0.35 * sh + np.array([-0.01, 0.0, 0.025]) * sh
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(f'{P}/assets/photos/{k}.jpg', quality=90)
    print(k, im.size, 'source', (w, h), 'crop', int(cw), int(ch))
