# Product photos exactly as published on nessaparisbeauty.com (Shopify /products.json): no AI enhancement, no
# sharpening — resized with Lanczos to ≤1600 px. Ingredient orbs are plain crops of the same photos.
# usage: python3 .src/prep_images.py <folder with the downloaded product images>
import json, sys
from PIL import Image
SRC = sys.argv[1]; OUT = 'assets/images'; sizes = {}
PRODUCTS = {'softglow': 'savon-soft-glow-500-ml__0.png', 'intense': 'sans-titre-6sept-_07-42-25__0.png', 'nila': 'savon-nila-visage__0.png',
            'perfectskin': 'perfect-skin-creme-visage-reparatrice__0.png', 'hydra': 'hydra-face-cream__0.png', 'bridal': 'bridal-glow-ritual__0.png'}
CROPS = {'papaye': ('savon-soft-glow-500-ml__1.png', (0.0, 0.29, 0.21, 0.5)), 'carotte': ('sans-titre-6sept-_07-42-25__0.png', (0.0, 0.6, 0.24, 0.84)),
         'curcuma': ('sans-titre-6sept-_07-42-25__0.png', (0.70, 0.68, 1.0, 0.98))}
for k, f in PRODUCTS.items():
    im = Image.open(f'{SRC}/{f}').convert('RGB'); im.thumbnail((1600, 1600), Image.LANCZOS)
    im.save(f'{OUT}/{k}.jpg', quality=92); sizes[k] = list(im.size); print(k, im.size)
for k, (f, (a, b, c, d)) in CROPS.items():
    s = Image.open(f'{SRC}/{f}').convert('RGB'); w, h = s.size
    im = s.crop((round(a * w), round(b * h), round(c * w), round(d * h))).resize((400, 400), Image.LANCZOS)
    im.save(f'{OUT}/{k}.jpg', quality=92); sizes[k] = [400, 400]; print(k, 'crop', im.size)
json.dump(sizes, open(f'{OUT}/sizes.json', 'w'))
