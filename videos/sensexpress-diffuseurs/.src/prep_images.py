# Product photos from the client's sensexpress.com screenshots: EDSR x4 output when present (else bicubic), JPEG ≤1600 px, sizes.json.
import json, os, sys
from PIL import Image
SRC = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/sx2'
OUT = 'assets/images'; sizes = {}
for k in ['prince', 'duchesse', 'senspro', 'monarque', 'nomade', 'duosens']:
    p = f'{SRC}/{k}_x4.png'
    im = Image.open(p).convert('RGB') if os.path.exists(p) else Image.open(f'{SRC}/{k}_src.png').convert('RGB').resize((1888, None or 1), Image.BICUBIC)
    if not os.path.exists(p):
        s = Image.open(f'{SRC}/{k}_src.png').convert('RGB'); im = s.resize((s.width * 4, s.height * 4), Image.BICUBIC)
    im.thumbnail((1600, 1600), Image.LANCZOS); im.save(f'{OUT}/{k}.jpg', quality=90); sizes[k] = list(im.size)
    print(k, im.size, 'EDSR' if os.path.exists(p) else 'bicubic')
json.dump(sizes, open(f'{OUT}/sizes.json', 'w'))
