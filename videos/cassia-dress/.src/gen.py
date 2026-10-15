# Cassia Dressing — pub collection Bogolan, 34 s, vertical 1080×1920, 25 i/s. Photos réelles de la marque (Instagram + envois client).
import os
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL, OV = 1080, 1920, 34, 0.5
SC = [('01-intro', 0, 4.6), ('02-heritage', 4.6, 4.8), ('03-chemises', 9.4, 6.2), ('04-vestes', 15.6, 4.8),
      ('05-robe', 20.4, 5.0), ('06-mosaique', 25.4, 3.8), ('07-contact', 29.2, 4.8)]
EARTH, CREAM, OCHRE, INK, RED = '#2A1A10', '#F1E6D2', '#C9923F', '#140D08', '#A3242B'

FONTS = '''
    @font-face { font-family: "Playfair Display"; font-weight: 600; src: url("assets/fonts/playfair-display-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 700; src: url("assets/fonts/playfair-display-latin-700-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Great Vibes"; font-weight: 400; src: url("assets/fonts/greatvibes-400.woff2") format("woff2"); }
'''
CSS = f'''
    .X-a {{ position: absolute; }}
    .X-c {{ left: 0; right: 0; text-align: center; }}
    .X-bg {{ position: absolute; inset: 0; background: radial-gradient(90% 60% at 50% 45%, #3a2416 0%, {EARTH} 55%, {INK} 100%); }}
    .X-kick {{ font-family: "Montserrat"; font-weight: 600; font-size: 26px; letter-spacing: 0.3em; color: {OCHRE}; white-space: nowrap; }}
    .X-t1 {{ font-family: "Playfair Display"; font-weight: 700; font-size: 92px; line-height: 1.05; color: {CREAM}; white-space: nowrap; }}
    .X-t2 {{ font-family: "Playfair Display"; font-weight: 600; font-size: 80px; line-height: 1.05; color: {OCHRE}; white-space: nowrap; }}
    .X-sc {{ font-family: "Great Vibes"; font-weight: 400; color: {CREAM}; white-space: nowrap; line-height: 1; }}
    .X-ph {{ position: absolute; overflow: hidden; }}
    .X-ph img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; display: block; object-fit: cover; }}
    .X-band {{ position: absolute; left: 0; width: 1080px; height: 90px; }}
    .X-band svg {{ display: block; }}
'''

def tile(pid, ink, bg):
    """A 200×200 Bogolan tile: dot grid, bars, cross, zigzag, separated by thick hand-drawn rules."""
    s = f'<pattern id="{pid}" width="200" height="200" patternUnits="userSpaceOnUse"><rect width="200" height="200" fill="{bg}"/>'
    s += f'<g fill="{ink}">' + ''.join(f'<circle cx="{22 + i * 28}" cy="{22 + j * 28}" r="6"/>' for i in range(3) for j in range(3))
    s += ''.join(f'<rect x="{116 + i * 20}" y="12" width="8" height="76" rx="4"/>' for i in range(4))
    s += '<rect x="0" y="94" width="200" height="10" rx="4"/><rect x="94" y="0" width="10" height="200" rx="4"/>'
    s += ''.join(f'<circle cx="{x}" cy="{y}" r="5"/>' for x, y in [(116, 116), (180, 116), (116, 180), (180, 180)])
    s += f'</g><g stroke="{ink}" stroke-width="9" stroke-linecap="round" fill="none"><path d="M 14 130 L 80 190 M 80 130 L 14 190"/>'
    s += '<path d="M 112 140 L 128 124 L 144 140 L 160 124 L 176 140 L 192 124 M 112 168 L 128 152 L 144 168 L 160 152 L 176 168 L 192 152"/></g></pattern>'
    return s

def band(bid, y, ink=CREAM, bg=INK, h=90):
    return (f'    <div class="X-band" id="{bid}" style="top:{y}px; height:{h}px"><svg width="1080" height="{h}"><defs>{tile(bid + "p", ink, bg)}</defs>'
            f'<rect width="1080" height="{h}" fill="url(#{bid}p)" transform="scale(1)"/></svg></div>\n')

def photo(idn, img, x, y, w, h, radius='0', pos='center', extra=''):
    return f'    <div class="X-ph" id="{idn}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{radius}; {extra}"><img id="{idn}i" src="assets/images/{img}" alt="" style="object-position:{pos}"></div>\n'

def up(sel, at, d=0.7, y=34):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, y: {y} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {at});\n'

def mask_up(sel, at, d=0.8):
    return f'      tl.fromTo(R("{sel}"), {{ yPercent: 110 }}, {{ yPercent: 0, duration: {d}, ease: "power3.out" }}, {at});\n'

F = {}
# ── 01 · intro: Bogolan strokes are drawn by hand, then the signature ───────
LINES = ['M -20 300 L 90 220 L 200 300 L 310 220 L 420 300 L 530 220 L 640 300 L 750 220 L 860 300 L 970 220 L 1100 300',
         'M -20 1640 L 90 1720 L 200 1640 L 310 1720 L 420 1640 L 530 1720 L 640 1640 L 750 1720 L 860 1640 L 970 1720 L 1100 1640',
         'M 120 470 L 240 590 M 240 470 L 120 590', 'M 840 470 L 960 590 M 960 470 L 840 590',
         'M 120 1330 L 240 1450 M 240 1330 L 120 1450', 'M 840 1330 L 960 1450 M 960 1330 L 840 1450',
         'M 540 640 m -360 0 a 360 360 0 1 0 720 0 a 360 360 0 1 0 -720 0']
DOTS = [(x, y) for y in (380, 1540) for x in range(80, 1081, 92)]
F['01-intro'] = (f'''
    #X-svg {{ position: absolute; left: 0; top: 0; }}
    #X-name {{ top: 690px; font-size: 230px; }}
    #X-dr {{ top: 880px; font-size: 120px; color: {OCHRE}; }}
    .X-m {{ position: absolute; overflow: hidden; height: 110px; }}
    .X-m span {{ display: inline-block; }}
''', f'''    <div class="X-bg"></div>
    <svg id="X-svg" width="1080" height="1920"><g stroke="{CREAM}" stroke-opacity="0.32" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none">
''' + ''.join(f'      <path class="X-ln" d="{d}"/>\n' for d in LINES[:6]) + f'''      <path class="X-ln" d="M 540 960 m -380 0 a 380 380 0 1 0 760 0 a 380 380 0 1 0 -760 0" stroke-dasharray="4 26"/>
    </g><g fill="{CREAM}" fill-opacity="0.32">''' + ''.join(f'<circle class="X-dt" cx="{x}" cy="{y}" r="9"/>' for x, y in DOTS) + f'''</g></svg>
    <div class="X-a X-kick X-c" id="X-k" style="top:600px">CASSIA DRESSING PRÉSENTE</div>
    <div class="X-a X-c X-sc" id="X-name">Cassia</div>
    <div class="X-a X-c X-sc" id="X-dr">Dressing</div>
    <div class="X-a X-c X-m" id="X-m1" style="top:1130px"><span class="X-t2" style="font-size:66px">La nouvelle collection</span></div>
''', '''      RA(".X-ln").forEach((p, i) => { const L = p.getTotalLength(); tl.fromTo(p, { attr: { "stroke-dasharray": i === 6 ? "4 26" : L + " " + L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.6, ease: "power2.inOut" }, 0.1 + (i % 6) * 0.12); });
      RA(".X-dt").forEach((d, i) => tl.fromTo(d, { attr: { r: 0 } }, { attr: { r: 9 }, duration: 0.3, ease: "back.out(3)" }, 0.6 + (i % 12) * 0.05));
      tl.fromTo(R("#X-k"), { opacity: 0, scale: 1.08 }, { opacity: 1, scale: 1, duration: 1.0, ease: "power2.out" }, 0.3);
      tl.fromTo(R("#X-name"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 1.1, ease: "power2.inOut" }, 0.5);
      tl.fromTo(R("#X-dr"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 0.8, ease: "power2.inOut" }, 1.2);
''' + mask_up('#X-m1 span', 1.9) + '''      tl.to(R("#X-svg"), { scale: 1.06, duration: 4.6, ease: "none", transformOrigin: "50% 50%" }, 0);
      tl.to([R("#X-name"), R("#X-dr"), R("#X-k"), R("#X-m1")], { opacity: 0, y: -30, filter: "blur(6px)", duration: 0.5, ease: "power2.in" }, 4.15);
''')

# ── 02 · héritage: Bogolan cloth unrolls, model in an arch, « réinventé » ───
F['02-heritage'] = (f'''
    #X-cloth {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
    #X-veil {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(20,13,8,0.97) 0%, rgba(20,13,8,0.9) 24%, rgba(20,13,8,0.55) 34%, rgba(20,13,8,0.55) 70%, rgba(20,13,8,0.95) 100%); }}
    #X-rv {{ top: 1545px; font-size: 150px; }}
    #X-ul {{ position: absolute; left: 330px; top: 1715px; width: 420px; height: 4px; background: {OCHRE}; transform-origin: 0 50%; }}
    #X-arc {{ box-shadow: 0 30px 80px rgba(0,0,0,0.6); }}
    #X-arcl {{ position: absolute; left: 175px; top: 545px; width: 730px; height: 960px; border: 3px solid {OCHRE}; border-radius: 365px 365px 20px 20px; }}
''', f'''    <svg id="X-cloth" width="1080" height="1920"><defs>{tile("X-cp", "#E8D9BC", "#1A110A")}</defs><rect width="1080" height="1920" fill="url(#X-cp)"/></svg>
    <div id="X-veil"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:190px">NOTRE HÉRITAGE</div>
    <div class="X-a X-c X-m" style="top:240px; overflow:hidden; height:110px"><span class="X-t1" id="X-s1" style="display:inline-block">Le Bogolan,</span></div>
    <div class="X-a X-c X-m" style="top:350px; overflow:hidden; height:100px"><span class="X-t2" id="X-s2" style="display:inline-block">revisité avec élégance</span></div>
    <div id="X-arcl"></div>
''' + photo('X-arc', 'post2.jpg', 190, 560, 700, 930, '350px 350px 16px 16px', '50% 30%') + '''    <div class="X-a X-c X-sc" id="X-rv">réinventé.</div>
    <div id="X-ul"></div>
''', '''      tl.fromTo(R("#X-cloth"), { clipPath: "inset(0% 0% 100% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 1.0, ease: "power3.inOut" }, 0);
      tl.fromTo(R("#X-cloth"), { y: 0 }, { y: -120, duration: 5.3, ease: "none" }, 0);
      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.6 }, 0.3);
''' + mask_up('#X-s1', 0.35) + mask_up('#X-s2', 0.6) + '''      tl.fromTo(R("#X-arc"), { clipPath: "inset(100% 0% 0% 0% round 350px 350px 16px 16px)" }, { clipPath: "inset(0% 0% 0% 0% round 350px 350px 16px 16px)", duration: 1.1, ease: "power3.inOut" }, 0.5);
      tl.fromTo(R("#X-arci"), { scale: 1.22 }, { scale: 1.02, duration: 4.8, ease: "power1.out" }, 0.5);
      tl.fromTo(R("#X-arcl"), { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.9, ease: "power2.out" }, 1.1);
      tl.fromTo(R("#X-rv"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 0.9, ease: "power2.inOut" }, 2.3);
      tl.fromTo(R("#X-ul"), { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.inOut" }, 2.9);
''')

# ── 03 · chemises: three looks, one word each ────────────────────────────────
LOOKS = [('post3.jpg', 'Élégance', '50% 35%'), ('post4.jpg', 'Caractère', '50% 30%'), ('post5.jpg', 'Tradi-moderne', '50% 35%')]
cards = ''.join(photo(f'X-c{i}', img, 110, 330, 860, 1147, '24px', pos, 'box-shadow: 0 30px 70px rgba(0,0,0,0.55)') for i, (img, w, pos) in enumerate(LOOKS))
words = ''.join(f'    <div class="X-a X-c X-m" data-layout-allow-overlap style="top:1505px; overflow:hidden; height:130px"><span class="X-t2 X-w" data-layout-allow-overlap id="X-w{i}" style="display:inline-block; font-size:88px">{w}</span></div>\n' for i, (img, w, pos) in enumerate(LOOKS))
F['03-chemises'] = (f'''
    #X-num {{ top: 1650px; font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.3em; color: {CREAM}; opacity: 0.7; }}
''', '    <div class="X-bg"></div>\n' + band('X-b1', 120, OCHRE, INK, 70) + band('X-b2', 1760, OCHRE, INK, 70) +
'    <div class="X-a X-kick X-c" id="X-k" style="top:250px">CHEMISES TRADI-MODERNES</div>\n' + cards + words +
'    <div class="X-a X-c" id="X-num">COLLECTION BOGOLAN</div>\n', '''      tl.fromTo(R("#X-k"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.2);
      tl.fromTo([R("#X-b1"), R("#X-b2")], { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 1.0, ease: "power2.inOut" }, 0);
      tl.fromTo(R("#X-b1 svg"), { x: 0 }, { x: -200, duration: 6.7, ease: "none" }, 0);
      tl.fromTo(R("#X-b2 svg"), { x: -200 }, { x: 0, duration: 6.7, ease: "none" }, 0);
      tl.fromTo(R("#X-num"), { opacity: 0 }, { opacity: 0.7, duration: 0.6 }, 0.8);
      const T = [0.15, 2.15, 4.15];
      [0, 1, 2].forEach((i) => {
        const c = R("#X-c" + i), w = R("#X-w" + i), t0 = T[i];
        if (i === 0) tl.fromTo(c, { clipPath: "inset(100% 0% 0% 0% round 24px)" }, { clipPath: "inset(0% 0% 0% 0% round 24px)", duration: 0.9, ease: "power3.inOut" }, t0);
        else tl.fromTo(c, { clipPath: "inset(0% 0% 0% 100% round 24px)" }, { clipPath: "inset(0% 0% 0% 0% round 24px)", duration: 0.75, ease: "power3.inOut" }, t0);
        tl.fromTo(R("#X-c" + i + "i"), { scale: 1.16, xPercent: i === 1 ? -3 : 3 }, { scale: 1.0, xPercent: 0, duration: 2.8, ease: "power1.out" }, t0);
        tl.fromTo(w, { yPercent: 110, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.6, ease: "power3.out" }, t0 + 0.45);
        if (i < 2) tl.to(w, { yPercent: -110, opacity: 0, duration: 0.4, ease: "power2.in" }, T[i + 1] + 0.05);
      });
''')

# ── 04 · vestes: three bombers on cream, signed Cassia ───────────────────────
JK = ['veste1.jpg', 'veste2.jpg', 'veste3.jpg']
jk = ''.join(f'    <div class="X-jk" id="X-j{i}"><i></i><img src="assets/images/{img.replace(".jpg", ".png")}" alt=""></div>\n' for i, img in enumerate(JK))
F['04-vestes'] = (f'''
    .X-jk {{ position: absolute; left: 240px; top: 640px; width: 600px; height: 690px; }}
    .X-jk img {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 18px 30px rgba(60,35,15,0.25)); }}
    .X-jk i {{ position: absolute; left: 90px; right: 90px; bottom: -26px; height: 50px; border-radius: 50%; background: radial-gradient(closest-side, rgba(60,35,15,0.35), rgba(60,35,15,0)); }}
    #X-cream {{ position: absolute; inset: 0; background: radial-gradient(80% 55% at 50% 52%, #FBF5EA 0%, {CREAM} 60%, #E2D2B5 100%); }}
    .X-dk {{ color: {EARTH}; }}
    #X-sig {{ top: 1440px; font-size: 104px; color: {RED}; }}
''', '    <div id="X-cream"></div>\n' + band('X-b1', 0, EARTH, CREAM, 80) + band('X-b2', 1840, EARTH, CREAM, 80) + f'''    <div class="X-a X-kick X-c" id="X-k" style="top:260px; color:{RED}">NOUVEAU · VESTES BOGOLAN</div>
    <div class="X-a X-c" style="top:315px; overflow:hidden; height:110px"><span class="X-t1 X-dk" id="X-s1" style="display:inline-block">Des vestes</span></div>
    <div class="X-a X-c" style="top:420px; overflow:hidden; height:100px"><span class="X-t2" id="X-s2" style="display:inline-block; color:#8A5A22">au style urbain</span></div>
''' + jk + '''    <div class="X-a X-c X-sc" id="X-sig">signées Cassia</div>
''', '''      tl.fromTo([R("#X-b1"), R("#X-b2")], { opacity: 0 }, { opacity: 1, duration: 0.6 }, 0);
      tl.fromTo(R("#X-k"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.15);
''' + mask_up('#X-s1', 0.25) + mask_up('#X-s2', 0.5) + '''      // each jacket lands centre-stage, then steps aside for the next
      const J = [R("#X-j0"), R("#X-j1"), R("#X-j2")];
      gsap.set(J, { zIndex: (i) => i + 1 });
      tl.fromTo(J[0], { y: 900, rotation: -8 }, { y: 0, rotation: 0, duration: 0.7, ease: "power3.out" }, 0.3);
      tl.to(J[0], { x: -300, scale: 0.6, rotation: -6, duration: 0.6, ease: "power3.inOut" }, 1.4);
      tl.fromTo(J[1], { y: 900, rotation: 8 }, { y: 0, rotation: 0, duration: 0.7, ease: "power3.out" }, 1.4);
      tl.to(J[1], { x: 300, scale: 0.6, rotation: 6, duration: 0.6, ease: "power3.inOut" }, 2.5);
      tl.fromTo(J[2], { y: 900, scale: 1 }, { y: 0, duration: 0.7, ease: "power3.out" }, 2.5);
      tl.to(J[2], { scale: 1.05, duration: 2.0, ease: "none" }, 3.2);
      tl.fromTo(R("#X-sig"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 0.9, ease: "power2.inOut" }, 3.0);
''')

# ── 05 · robe Diaz: curtain reveal, script title ─────────────────────────────
F['05-robe'] = (f'''
    #X-shade {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(20,13,8,0.55) 0%, rgba(20,13,8,0) 20%, rgba(20,13,8,0) 48%, rgba(20,13,8,0.8) 63%, rgba(20,13,8,1) 69.5%); }}
    #X-pm {{ top: 1330px; font-size: 140px; }}
    #X-fr {{ border: 3px solid {OCHRE}; position: absolute; left: 40px; top: 40px; right: 40px; bottom: 40px; border-radius: 20px; }}
''', photo('X-dress', 'robe-diaz.jpg', 0, 0, 1080, 1340, '0', '60% 18%') + f'''    <div id="X-shade"></div>
    <div id="X-fr"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:120px; color:{CREAM}">POUR ELLE</div>
    <div class="X-a X-c X-sc" id="X-pm">Pour madame</div>
    <div class="X-a X-c" style="top:1500px; overflow:hidden; height:100px"><span class="X-t1" id="X-s1" style="display:inline-block; font-size:78px">Robes en tissu Diaz</span></div>
    <div class="X-a X-kick X-c" id="X-s2" style="top:1630px">FLUIDES · RAFFINÉES</div>
''', '''      tl.fromTo(R("#X-dress"), { clipPath: "inset(0% 50% 0% 50%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 1.1, ease: "power3.inOut" }, 0);
      tl.fromTo(R("#X-dressi"), { scale: 1.2 }, { scale: 1.04, duration: 5.5, ease: "power1.out" }, 0);
      tl.fromTo(R("#X-fr"), { opacity: 0, scale: 1.04 }, { opacity: 0.85, scale: 1, duration: 0.9, ease: "power2.out" }, 0.8);
      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.6 }, 0.9);
      tl.fromTo(R("#X-pm"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 1.0, ease: "power2.inOut" }, 0.9);
''' + mask_up('#X-s1', 1.6) + up('#X-s2', 2.2, 0.6, 16))

# ── 06 · mosaïque: the whole wardrobe, then the promise ─────────────────────
MOS = [('post6.jpg', '50% 25%'), ('veste2.png', 'center'), ('robe-diaz.jpg', '60% 45%'), ('post4.jpg', '50% 30%'), ('veste1.png', 'center'), ('post2.jpg', '50% 30%')]
tiles = ''.join(photo(f'X-t{i}', img, 30 + (i % 2) * 520, 140 + (i // 2) * 560, 500, 540, '18px', pos, 'background:#F1E6D2' if 'veste' in img else '') for i, (img, pos) in enumerate(MOS))
F['06-mosaique'] = (f'''
    #X-dim {{ position: absolute; inset: 0; background: rgba(20,13,8,0.62); }}
    #X-amp {{ top: 860px; font-size: 150px; color: {OCHRE}; }}
''', '    <div class="X-bg"></div>\n' + tiles + '''    <div id="X-dim"></div>
    <div class="X-a X-c" style="top:740px; overflow:hidden; height:120px"><span class="X-t1" id="X-s1" style="display:inline-block; font-size:100px">Modernité</span></div>
    <div class="X-a X-c X-sc" id="X-amp">&amp;</div>
    <div class="X-a X-c" style="top:1020px; overflow:hidden; height:120px"><span class="X-t1" id="X-s2" style="display:inline-block; font-size:100px">authenticité</span></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:1170px; color:#FFFFFF">POUR TOUTES VOS OCCASIONS</div>
''', '''      [0, 1, 2, 3, 4, 5].forEach((i) => {
        tl.fromTo(R("#X-t" + i), { opacity: 0, scale: 0.86 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.6)" }, 0.05 + i * 0.12);
        tl.fromTo(R("#X-t" + i + "i"), { scale: 1.15 }, { scale: 1.0, duration: 3.8, ease: "power1.out" }, 0.05 + i * 0.12);
      });
      tl.fromTo(R("#X-dim"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, 1.0);
''' + mask_up('#X-s1', 1.15) + '''      tl.fromTo(R("#X-amp"), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(2)" }, 1.4);
''' + mask_up('#X-s2', 1.55) + up('#X-k', 2.0, 0.6, 14))

# ── 07 · contact: signature, call to action, WhatsApp ───────────────────────
WA = '<svg width="54" height="54" viewBox="0 0 32 32"><path fill="#25D366" d="M16 3C9 3 3.3 8.6 3.3 15.6c0 2.4.7 4.7 1.9 6.6L3 29l7-2.2c1.8 1 3.9 1.6 6 1.6 7 0 12.7-5.6 12.7-12.6S23 3 16 3z"/><path fill="#fff" d="M12.2 9.6c-.3-.6-.6-.6-.9-.6h-.8c-.3 0-.7.1-1 .5-.4.4-1.3 1.3-1.3 3.1s1.3 3.6 1.5 3.9c.2.3 2.6 4.1 6.4 5.6 3.1 1.2 3.8 1 4.5.9.7-.1 2.2-.9 2.5-1.8.3-.9.3-1.6.2-1.8-.1-.2-.3-.3-.7-.5l-2.5-1.2c-.3-.1-.6-.2-.8.2-.2.4-.9 1.2-1.1 1.4-.2.2-.4.3-.8.1-.4-.2-1.6-.6-3-1.9-1.1-1-1.9-2.2-2.1-2.6-.2-.4 0-.6.2-.8l.6-.7c.2-.2.3-.4.4-.6.1-.3.1-.5 0-.7l-1.1-2.7z"/></svg>'
F['07-contact'] = (f'''
    #X-name {{ top: 560px; font-size: 230px; }}
    #X-dr {{ top: 750px; font-size: 120px; color: {OCHRE}; }}
    #X-cta {{ top: 1000px; font-family: "Playfair Display"; font-weight: 700; font-size: 74px; color: {CREAM}; }}
    #X-wa {{ top: 1180px; display: flex; justify-content: center; align-items: center; gap: 22px; }}
    #X-wa b {{ font-family: "Montserrat"; font-weight: 600; font-size: 58px; color: #FFFFFF; letter-spacing: 0.02em; }}
    #X-pill {{ position: absolute; left: 150px; top: 1155px; width: 780px; height: 110px; border-radius: 55px; border: 3px solid {OCHRE}; background: rgba(201,146,63,0.12); }}
    #X-ig {{ top: 1320px; font-family: "Montserrat"; font-weight: 500; font-size: 34px; color: {CREAM}; opacity: 0.85; letter-spacing: 0.06em; }}
    #X-city {{ top: 1385px; }}
    #X-fil {{ position: absolute; left: 390px; top: 960px; width: 300px; height: 3px; background: {OCHRE}; }}
''', '    <div class="X-bg"></div>\n' + band('X-b1', 130, OCHRE, INK, 80) + band('X-b2', 1680, OCHRE, INK, 80) + f'''    <div class="X-a X-c X-sc" id="X-name">Cassia</div>
    <div class="X-a X-c X-sc" id="X-dr">Dressing</div>
    <div id="X-fil"></div>
    <div class="X-a X-c" id="X-cta">Affirmez votre classe</div>
    <div id="X-pill"></div>
    <div class="X-a X-c" id="X-wa">{WA}<b>+223 94 55 85 40</b></div>
    <div class="X-a X-c" id="X-ig">@cassia_dress</div>
    <div class="X-a X-kick X-c" id="X-city">BAMAKO · COMMANDEZ MAINTENANT</div>
''', '''      tl.fromTo([R("#X-b1"), R("#X-b2")], { clipPath: "inset(0% 50% 0% 50%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.9, ease: "power2.inOut" }, 0);
      tl.fromTo(R("#X-b1 svg"), { x: 0 }, { x: -200, duration: 5.3, ease: "none" }, 0);
      tl.fromTo(R("#X-b2 svg"), { x: -200 }, { x: 0, duration: 5.3, ease: "none" }, 0);
      tl.fromTo(R("#X-name"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 1.0, ease: "power2.inOut" }, 0.15);
      tl.fromTo(R("#X-dr"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 0.7, ease: "power2.inOut" }, 0.7);
      tl.fromTo(R("#X-fil"), { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.inOut" }, 1.0);
''' + up('#X-cta', 1.1) + '''      tl.fromTo(R("#X-pill"), { opacity: 0, scaleX: 0.6 }, { opacity: 1, scaleX: 1, duration: 0.6, ease: "power3.out" }, 2.0);
''' + up('#X-wa', 2.15, 0.6, 20) + up('#X-ig', 2.6, 0.5, 14) + up('#X-city', 2.8, 0.5, 14) + '''      tl.to(R("#X-pill"), { boxShadow: "0 0 50px rgba(201,146,63,0.55)", duration: 0.6, ease: "sine.inOut", yoyo: true, repeat: 2 }, 3.0);
''')

def frame(fid, dur, css, html, js):
    pre = 'c' + fid[:2]
    sub = lambda s: s.replace('X-', pre + '-')
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; font-family: "Montserrat", sans-serif; color: {CREAM}; background: {INK}; }}
{sub(CSS)}
{sub(css)}
  </style>
  <div id="root" data-composition-id="{fid}" data-start="0" data-duration="{dur}" data-width="{W}" data-height="{H}">
    <div id="{pre}-clip" class="clip" data-start="0" data-duration="{dur}" data-track-index="0" style="position:absolute; inset:0"></div>
{sub(html)}
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      const R = (s) => document.querySelector('[data-composition-id="{fid}"] ' + s);
      const RA = (s) => document.querySelectorAll('[data-composition-id="{fid}"] ' + s);
{sub(js)}
      tl.to({{}}, {{ duration: {dur} }}, 0);
      window.__timelines["{fid}"] = tl;
    }})();
  </script>
</template>
'''

os.makedirs(f'{P}/compositions/frames', exist_ok=True)
scenes, trans = '', ''
for i, (fid, st, ln) in enumerate(SC):
    css, html, js = F[fid]
    dur = round(ln + (OV if i < len(SC) - 1 else 0), 2)
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(frame(fid, dur, css, html, js))
    scenes += f'      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{i % 2}"></div>\n'
    if i > 0:
        trans += f'        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {OV}, ease: "power2.inOut" }}, {st});\n'
VOICE = os.path.exists(f'{P}/assets/voice/01.wav')
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
{scenes}
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="{0.22 if VOICE else 0.75}"></audio>
<!--VO-->
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
{trans}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok')
