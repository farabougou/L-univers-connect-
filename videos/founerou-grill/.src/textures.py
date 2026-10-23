# Procedural textures for Founerou Grill's: grunge mask (distressed stencil type), dry-brush banner, charcoal slate.
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.default_rng(4)
P = 'assets/images/'
# grunge mask: opaque with speckle holes and fine scratches (alpha channel only matters)
W = 1024; a = np.full((W, W), 255, np.uint8)
im = Image.fromarray(a, 'L'); d = ImageDraw.Draw(im)
for _ in range(2600):
    x, y = rng.integers(0, W, 2); r = rng.choice([1, 1, 2, 2, 3, 5])
    d.ellipse([x - r, y - r, x + r, y + r], fill=int(rng.integers(0, 90)))
for _ in range(140):
    x, y = rng.integers(0, W, 2); L = rng.integers(20, 140); ang = rng.uniform(-0.5, 0.5)
    d.line([x, y, x + L * np.cos(ang), y + L * np.sin(ang)], fill=int(rng.integers(30, 120)), width=1)
noise = rng.random((W, W))
arr = np.array(im.filter(ImageFilter.GaussianBlur(0.6))).astype(float) * (0.82 + 0.18 * noise)
Image.merge('RGBA', [Image.new('L', (W, W), 255)] * 3 + [Image.fromarray(arr.clip(0, 255).astype(np.uint8))]).save(P + 'grunge.png')
# dry brush stroke (white, alpha shape)
BW, BH = 1600, 320
y = np.arange(BH)[:, None]; x = np.arange(BW)[None, :]
cy = BH / 2 + 6 * np.sin(x / 300.0) + 3 * np.sin(x / 61.0) - (x / BW - 0.5) * 22
half = 112 + 6 * np.sin(x / 170.0) + 4 * rng.standard_normal((1, BW)).cumsum(1) / np.sqrt(BW)
edge = np.abs(y - cy) / half
alpha = np.clip((1.05 - edge) * 9, 0, 1)
streak = np.repeat((rng.random((BH, 1)) > 0.12).astype(float), BW, 1)
streak = np.array(Image.fromarray((streak * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur((40, 0.6)))) / 255
alpha *= np.where(edge > 0.62, streak, 0.75 + 0.25 * streak)
fade_l = np.clip(x / 120 + rng.random((BH, 1)) * 0.8 - 0.2, 0, 1); fade_r = np.clip((BW - x) / 90 + rng.random((BH, 1)) * 0.8 - 0.3, 0, 1)
alpha *= fade_l * fade_r
alpha = np.where(alpha > 0.35, np.clip(alpha * 1.4, 0, 1), alpha * 0.4)
A = Image.fromarray((alpha * 255).astype(np.uint8))
Image.merge('RGBA', [Image.new('L', (BW, BH), 255)] * 3 + [A]).save(P + 'brush.png')
# charcoal slate (dark, subtle grain + soft blotches)
SW, SH = 1080, 1920
n = rng.standard_normal((SH // 8, SW // 8))
blot = np.array(Image.fromarray(((n - n.min()) / (n.max() - n.min()) * 255).astype(np.uint8)).resize((SW, SH), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30))) / 255
fine = rng.standard_normal((SH, SW)) * 6
base = 18 + blot * 16 + fine
rgb = np.stack([base * 1.05, base * 0.98, base * 0.95], -1).clip(0, 255).astype(np.uint8)
Image.fromarray(rgb).save(P + 'slate.jpg', quality=90)
print('ok')
