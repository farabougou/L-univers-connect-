# Product photos exactly as supplied by the client (sensexpress.com screenshots): cropped, scaled up with Lanczos only
# (no AI enhancement, no sharpening), JPEG ≤1600 px; writes sizes.json for the cover maths in gen.py.
import json, sys
from PIL import Image
SRC = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/sx2'
OUT = 'assets/images'; sizes = {}
for k in ['prince', 'duchesse', 'senspro', 'monarque', 'nomade', 'duosens']:
    s = Image.open(f'{SRC}/{k}_src.png').convert('RGB')
    im = s.resize((s.width * 3, s.height * 3), Image.LANCZOS)
    im.thumbnail((1600, 1600), Image.LANCZOS); im.save(f'{OUT}/{k}.jpg', quality=92); sizes[k] = list(im.size)
    print(k, s.size, '->', im.size)
json.dump(sizes, open(f'{OUT}/sizes.json', 'w'))
