# Prépare les calques de l'avatar (1080×1920) et la courbe de voix qui allume le M.
#   bg.jpg        : studio sans le personnage (trou rebouché, légèrement flou) pour la parallaxe
#   subject.png   : personnage détouré, M du masque éteint (tube sombre)
#   mlit.png      : le M allumé seul (même cadrage), son opacité suit la voix
#   mbloom.jpg    : halo du M (fond noir, fusion « screen »)
#   ../.src/env.json : enveloppe de la voix, une valeur par image à 60 i/s, entre 0 et 1
import os, json
import numpy as np, cv2, soundfile as sf
from PIL import Image, ImageFilter
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = f'{P}/assets/images'
W, H, FPS = 1080, 1920, 60

src = Image.open(f'{I}/avatar.png').convert('RGB').resize((W, H), Image.LANCZOS)
cut = Image.open(f'{I}/subject-raw.png').convert('RGBA').resize((W, H), Image.LANCZOS)
rgb = np.asarray(src).astype(np.float32)
alpha = np.asarray(cut)[..., 3].astype(np.float32) / 255

# fond : on rebouche le personnage (inpainting sur une version réduite, puis flou de profondeur)
hole = cv2.dilate((alpha > 0.05).astype(np.uint8) * 255, np.ones((31, 31), np.uint8))
small = cv2.resize(rgb.astype(np.uint8), (W // 3, H // 3), interpolation=cv2.INTER_AREA)
hs = cv2.resize(hole, (W // 3, H // 3), interpolation=cv2.INTER_NEAREST)
fill = cv2.inpaint(small[..., ::-1], hs, 9, cv2.INPAINT_TELEA)[..., ::-1]
fill = cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
hm = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 12)[..., None]
bg = rgb * (1 - hm) + fill * hm
bg = cv2.GaussianBlur(bg, (0, 0), 3.2)
Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).save(f'{I}/bg.jpg', quality=92)

# le M : pixels orange lumineux dans la zone du masque (tube = 1, reflet sur le masque = partiel)
R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
m = np.clip((R - 110) / 110, 0, 1) * np.clip((R - B - 50) / 90, 0, 1)
zone = np.zeros_like(m); zone[450:720, 370:660] = 1
zone = cv2.GaussianBlur(zone, (0, 0), 6)
m = cv2.GaussianBlur(m * zone, (0, 0), 0.8)
ys, xs = np.nonzero(m > 0.5)
print('M box', xs.min(), ys.min(), xs.max(), ys.max())

dim = rgb * (1 - 0.82 * m[..., None])
sub = np.dstack([np.clip(dim, 0, 255), alpha * 255]).astype(np.uint8)
Image.fromarray(sub, 'RGBA').save(f'{I}/subject.png')
lit = np.dstack([rgb, np.clip(m, 0, 1) * 255]).astype(np.uint8)
Image.fromarray(lit, 'RGBA').save(f'{I}/mlit.png')
glow = cv2.GaussianBlur(rgb * m[..., None], (0, 0), 22) * 2.2 + cv2.GaussianBlur(rgb * m[..., None], (0, 0), 6) * 0.8
Image.fromarray(np.clip(glow, 0, 255).astype(np.uint8)).save(f'{I}/mbloom.jpg', quality=92)

# enveloppe de la voix : RMS par image, en dB, normalisée, attaque rapide et relâche douce
v, sr = sf.read(f'{P}/assets/voice/voice.wav')
v = v if v.ndim == 1 else v.mean(1)
n = int(len(v) / sr * FPS) + 1
rms = np.array([np.sqrt(np.mean(v[int(i * sr / FPS):int(i * sr / FPS) + int(0.04 * sr)] ** 2) + 1e-12) for i in range(n)])
db = 20 * np.log10(rms)
e = np.clip((db + 44) / 28, 0, 1) ** 0.8
out, cur = [], 0.0
for x in e:
    cur += (x - cur) * (0.65 if x > cur else 0.12)
    out.append(round(float(cur), 3))
json.dump(out, open(f'{P}/.src/env.json', 'w'))
print('env', len(out), 'max', max(out))
