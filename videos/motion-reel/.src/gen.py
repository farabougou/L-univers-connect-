# « MAMS — MOTION REEL 2026 » : pub pour ses services, format « écran dans l'écran » (référence : reel @danyltn), puis
# on en sort. Vertical 1080×1920, 60 i/s. En haut deux pastilles (sujet + créateur, TikTok @kofamali), au centre une carte
# 16:9 qui joue un showreel de 32 s (16 mesures à 120 BPM, une création par mesure, coupes sur la mesure, habillage
# technique : timecode, mesures, réglages), en bas une accroche lisible sans le son qui change trois fois (pub, site,
# contact). Au drop (mesure 9) le mur des pubs sort de la carte et remplit tout l'écran. Système de motion : videos/_studio.
import os, json, math
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 60
R0 = 0.6                    # le showreel démarre quand la carte est posée
BAR = 2.0                   # 120 BPM : 1 mesure = 2 s
NB = 16
TOTAL = round(R0 + NB * BAR + 0.8, 2)
def at(bar, beat=0): return round(R0 + bar * BAR + beat * BAR / 4, 3)
ORANGE, BLUE, LIME, INK, CREAM = '#FF4F1F', '#2340FF', '#D7FF3A', '#141414', '#F3EBDD'
CARD = 'inset(500px 40px 857px 40px round 30px)'   # la carte, vue comme une découpe de l'écran entier

# ── formes du morphing : 72 points sur des rayons communs, pour passer de l'une à l'autre point par point ──
N = 72
def ray_poly(verts, th):
    dx, dy, best = math.cos(th), math.sin(th), None
    for i in range(len(verts)):
        (x1, y1), (x2, y2) = verts[i], verts[(i + 1) % len(verts)]
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-9: continue
        t, u = (x1 * ey - y1 * ex) / den, (x1 * dy - y1 * dx) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best): best = t
    return best
def poly(n, r, a0=-90, inner=None):
    vs = []
    for k in range(n * (2 if inner else 1)):
        rr = (r if k % 2 == 0 else inner) if inner else r
        a = math.radians(a0 + k * 360 / (n * (2 if inner else 1)))
        vs.append((rr * math.cos(a), rr * math.sin(a)))
    return vs
def sample(fn):
    return [[round(fn(-math.pi / 2 + 2 * math.pi * k / N) * math.cos(-math.pi / 2 + 2 * math.pi * k / N), 1),
             round(fn(-math.pi / 2 + 2 * math.pi * k / N) * math.sin(-math.pi / 2 + 2 * math.pi * k / N), 1)] for k in range(N)]
SHAPES = {'circle': sample(lambda th: 190),
          'triangle': sample(lambda th: ray_poly(poly(3, 235), th)),
          'star': sample(lambda th: ray_poly(poly(5, 235, inner=100), th)),
          'square': sample(lambda th: ray_poly(poly(4, 215, a0=-135), th))}

# ── étoile de la marque (fin) : 10 branches de longueurs un peu irrégulières ──
ARMS = ''.join(f'<line x1="0" y1="0" x2="{round(math.cos(math.radians(k * 36 + 8)) * L, 1)}" y2="{round(math.sin(math.radians(k * 36 + 8)) * L, 1)}"/>'
               for k, L in enumerate([92, 78, 96, 84, 90, 80, 95, 76, 88, 86]))
HEART = 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z'
CURSOR = f'<svg width="32" height="42" viewBox="0 0 32 42"><path d="M2 2 L2 34 L11 25 L17 39 L23 36 L17 23 L29 23 Z" fill="{INK}" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/></svg>'

EASE_ROWS = [('LINÉAIRE', 'none', '#9B958C'), ('EASE-IN', 'power2.in', ORANGE), ('EASE-OUT', 'power2.out', ORANGE),
             ('SILK', 'silk', ORANGE), ('OVERSHOOT', 'overshoot', ORANGE), ('RESSORT', 'spring', BLUE)]
ADS = [('nessa', 'Nessa Paris', 'BEAUTÉ'), ('sensexpress', 'SensExpress', "PARFUM D'AMBIANCE"), ('cassia', 'Cassia Dressing', 'MODE'),
       ('founerou', "Founerou Grill's", 'RESTAURANT'), ('gimso', 'GimSo', 'MODE BOGOLAN'), ('skprint', 'SK Print', 'IMPRESSION')]
WALL = [['nessa', 'kofamoto', 'cassia', 'enoryx'], ['ktf', 'gimso', 'fleche', 'sensexpress'], ['founerou', 'kofaapp', 'skprint', 'enoryx3d']]
WALL_Y = [(-480, -380), (-160, -300), (-560, -460)]     # colonnes en parallaxe (4 vidéos de 640 px pour 1920 px d'écran)
WORDS = [('FLUIDE.', ORANGE, INK), ('PRÉCIS.', '#FFFFFF', BLUE), ('JAMAIS', LIME, INK), ('LINÉAIRE', INK, '#FFFFFF')]
FACES = [('SITES', ORANGE, INK), ('APPLIS', BLUE, '#FFFFFF'), ('SAAS', LIME, INK), ('PUBS', CREAM, INK)]
# produits créés (sites, applis, SaaS) : vraie vidéo, ou maquette animée pour le SaaS (pas de capture disponible)
PRODUCTS = [('kofacode', 'KOFA', 'APPLI MOBILE'), (None, 'SaaS tout-en-un', 'PLATEFORME WEB'), ('enoryxapp', 'Enoryx', 'ÉNERGIE & BÂTIMENTS')]
KPI = [(248, 'CLIENTS'), (96, 'COMMANDES'), (31, 'TÂCHES')]
SBARS = [0.32, 0.5, 0.41, 0.66, 0.55, 0.8, 0.95]
# GimSo : ses photos (tenues en Bogolan) à la place de sa vidéo, une par temps
GIMSO = [f'assets/images/gimso-{i}.jpg' for i in range(1, 5)]
def gph(i, imgs): return f'<div class="gph" id="{i}">' + ''.join(f'<img src="{u}" alt="GimSo" />' for u in imgs) + '</div>'
POSTS = [('#4A3F6B', '#2B2540'), ('#2E6F5E', '#173D33'), ('#8A5B3A', '#4A2F1D'), ('#3A5B8A', '#1F3350'), ('#6B6B6B', '#2E2E2E'),
         ('#7A3A4F', '#3E1D29'), ('#B08A3A', '#5A4519')]
SECTIONS = ['01 — EASING', '02 — MORPHING', '03 — PUBS · LUXE', '04 — PUBS · STREET', '05 — MOTIFS', '06 — 3D', '07 — PARTICULES',
            '08 — SITE INTERNET', '09 — LE MUR', '10 — APPLIS & SAAS', '11 — SCROLL-STOP', '12 — CUBE 3D', '13 — LIQUIDE', '14 — TYPO', '15 — FIN', '16 — CONTACT']
# couleur de l'habillage selon le fond (par mesure, et par mot pendant la typo)
WH = '#FFFFFF'
HUD = [(0, INK), (1, WH), (2, WH), (3, INK), (4, WH), (5, WH), (6, WH), (7, INK), (8, WH), (9, INK), (10, INK), (11, WH), (12, WH),
       (13, INK), (13.25, BLUE), (13.5, INK), (13.75, WH), (14, INK), (15, WH)]

rows = ''.join(f'''
          <div class="row" style="top:{250 + i * 96}px"><span class="lab">{lab}</span><i class="trk"></i><b class="dot" id="d{i}" data-hf-motion-blur='{{"samplesPerFrame": 8}}' style="background:{col}"></b></div>''' for i, (lab, e, col) in enumerate(EASE_ROWS))
trio = {}
for s, base in ((2, 0), (3, 3)):
    ads = ''
    for j in range(3):
        k, name, sector = ADS[base + j]
        x = 177 + j * 432
        media = gph(f'gp{base + j}', GIMSO) if k == 'gimso' else f'<video id="v{base + j}" class="clip vid" src="assets/clips/{k}.mp4" data-start="{at(s)}" data-duration="{BAR}" data-track-index="{3 + j}" muted playsinline></video>'
        ads += f'''
        <div class="ad" id="ad{base + j}" style="left:{x}px">{media}</div>
        <div class="adl" id="al{base + j}" style="left:{x}px"><em>{name}</em><span>{sector}</span></div>'''
    trio[s] = ads
words = ''.join(f'''
        <div class="wbg" id="wb{i}" style="background:{bg}"><div class="word" id="w{i}" data-hf-motion-blur='{{"samplesPerFrame": 8}}' style="color:{fg}">{t}{'<i style="color:' + ORANGE + '">.</i>' if t == 'LINÉAIRE' else ''}</div></div>''' for i, (t, bg, fg) in enumerate(WORDS))
name = ''.join(f'<span id="n{i}">{c}</span>' for i, c in enumerate('MAMS'))
secs = ''.join(f'<span id="sl{i}">{t}</span>' for i, t in enumerate(SECTIONS))
barsq = ''.join('<i></i>' for _ in range(NB))
# mur des pubs : 3 colonnes de 4 vidéos verticales
wall = ''
for c, col in enumerate(WALL):
    tiles = ''.join('<div class="tile"><div class="tin">' + (gph(f'gpw{c}{r}', GIMSO) if k == 'gimso' else f'<video id="wv{c}{r}" class="clip vid" src="assets/clips/{k}.mp4" data-start="{at(8)}" data-duration="{BAR}" data-track-index="{20 + c * 4 + r}" muted playsinline></video>') + '</div></div>' for r, k in enumerate(col))
    wall += f'<div class="col" id="col{c}" style="left:{c * 360}px">{tiles}</div>'
# produits : deux vidéos d'applis et une maquette de tableau de bord SaaS
SC = round(2 * math.pi * 52, 1)
saas = ('<div class="sx-top"><i></i><i></i><i></i></div><div class="sx-side">' + ''.join(f'<i style="top:{20 + i * 50}px{"; background:" + ORANGE if i == 0 else ""}"></i>' for i in range(5)) + '</div>'
        '<div class="sx-h">Tableau de bord</div>'
        + ''.join(f'<div class="sx-kpi" style="left:{80 + i * 99}px"><b id="kv{i}">0</b><span>{lab}</span></div>' for i, (v, lab) in enumerate(KPI))
        + '<div class="sx-panel" style="top:196px; height:236px">' + ''.join(f'<i class="sb" style="left:{18 + i * 37}px; height:{round(h * 180)}px; background:{ORANGE if i == len(SBARS) - 1 else "#4A4A58"}"></i>' for i, h in enumerate(SBARS)) + '</div>'
        + f'<div class="sx-panel" style="top:448px; height:212px"><svg class="sx-don" width="140" height="140"><circle cx="70" cy="70" r="52" fill="none" stroke="#34343E" stroke-width="16"/><circle id="sring" cx="70" cy="70" r="52" fill="none" stroke="{ORANGE}" stroke-width="16" stroke-linecap="round" stroke-dasharray="{SC}" stroke-dashoffset="{SC}" transform="rotate(-90 70 70)"/></svg>'
        + '<div class="sx-dn"><span id="sdn">0</span><small>%</small></div><span class="sx-pl">OBJECTIF DU MOIS</span></div>')
prods = ''
for j, (k, pname, kind) in enumerate(PRODUCTS):
    x = 177 + j * 432
    inner = saas if k is None else f'<video id="v{6 + j}" class="clip vid" src="assets/clips/{k}.mp4" data-start="{at(9)}" data-duration="{BAR}" data-track-index="{3 + j}" muted playsinline></video>'
    prods += f'''
        <div class="ad{' sx' if k is None else ''}" id="ad{6 + j}" style="left:{x}px">{inner}</div>
        <div class="adl" id="al{6 + j}" style="left:{x}px"><em>{pname}</em><span>{kind}</span></div>'''
# fil de réseau social : 7 publications avant la pub
posts = ''.join(f'<div class="post" style="background:linear-gradient(160deg,{a},{b})"><i class="psh"></i><i class="pav"></i><i class="pb" style="left:80px; top:574px; width:150px"></i><i class="pb" style="left:24px; top:622px; width:230px"></i><i class="pb" style="left:24px; top:646px; width:150px"></i><i class="pic" style="top:380px"></i><i class="pic" style="top:450px"></i><i class="pic" style="top:520px"></i></div>' for a, b in POSTS)
faces = ''.join(f'<div class="face" style="background:{bg}; color:{fg}; transform:rotateX({-90 * i}deg) translateZ(150px)">{t}</div>' for i, (t, bg, fg) in enumerate(FACES))
hearts = lambda cls: ''.join(f'<svg class="{cls}" width="34" height="34" viewBox="0 0 24 24"><path d="{HEART}" fill="{ORANGE}"/></svg>' for _ in range(6))
def act(i, l1, l2, l3, top=1196):
    return f'''<div class="act" id="act{i}">
          <div class="hl" style="top:{top}px">{l1}</div>
          <div class="hl" style="top:{top + 106}px">{l2}</div>
          <div class="hl l3" style="top:{top + 222}px"><span class="bx">{l3}</span></div>
        </div>'''
m = lambda w, em=False: f'<span class="st-mask"><{"em" if em else "span"} class="st-word">{w}</{"em" if em else "span"}></span>'

HTML = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      @font-face {{ font-family: "Archivo Black"; src: url("assets/fonts/archivo-black-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/instrument-serif-latin-400-italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: normal; src: url("assets/fonts/instrument-serif-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #0A090B; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #0A090B; font-family: "Inter", sans-serif; }}
      #glow {{ position: absolute; left: -260px; top: 900px; width: 1600px; height: 1300px; border-radius: 50%; background: radial-gradient(closest-side, rgba(255,79,31,0.30), rgba(255,79,31,0.08) 55%, rgba(255,79,31,0)); }}
      .pill {{ position: absolute; left: 56px; top: 318px; height: 82px; padding: 0 34px; border-radius: 41px; background: {CREAM}; display: flex; align-items: center; gap: 16px; font: 800 34px "Inter"; color: #111; }}
      .pill i {{ width: 18px; height: 18px; border-radius: 9px; background: {ORANGE}; }}
      .me {{ position: absolute; right: 56px; top: 308px; width: 420px; height: 102px; border-radius: 24px; background: {CREAM}; display: flex; align-items: center; gap: 18px; padding: 0 20px; }}
      .me b {{ width: 66px; height: 66px; border-radius: 33px; background: {ORANGE}; color: #fff; font: 400 34px "Archivo Black"; display: flex; align-items: center; justify-content: center; }}
      .me div {{ display: flex; flex-direction: column; gap: 2px; }}
      .me strong {{ font: 800 32px "Inter"; color: #111; }}
      .me span {{ font: 600 23px "Inter"; color: #5F5A54; }}
      #card {{ position: absolute; left: 40px; top: 500px; width: 1000px; height: 563px; border-radius: 30px; overflow: hidden; box-shadow: 0 0 0 1px rgba(255,255,255,0.06), 0 0 90px rgba(255,79,31,0.32), 0 40px 90px rgba(0,0,0,0.6); }}
      #stage {{ position: absolute; left: 0; top: 0; width: 1600px; height: 900px; transform: scale(0.625); transform-origin: 0 0; overflow: hidden; background: {INK}; }}
      .kick {{ position: absolute; left: 60px; top: 1150px; font: 500 28px "Plex Mono"; letter-spacing: 0.2em; color: {ORANGE}; white-space: nowrap; }}
      .act {{ position: absolute; left: 0; top: 0; width: 0; height: 0; overflow: visible; }}
      .hl {{ position: absolute; left: 56px; font: 400 104px/1 "Archivo Black"; color: {CREAM}; letter-spacing: -0.02em; white-space: nowrap; }}
      .hl em {{ font: italic 400 118px/1 "Instrument Serif"; color: {ORANGE}; letter-spacing: 0; }}
      #hl3 {{ color: {INK}; }}
      #box {{ position: absolute; left: 44px; top: 1418px; width: 772px; height: 118px; background: {ORANGE}; border-radius: 8px; transform-origin: 0 50%; }}
      .l3 {{ left: 44px; color: {INK}; }}
      .bx {{ display: inline-block; padding: 7px 22px 7px 28px; background: {ORANGE}; border-radius: 8px; }}
      #actB, #actC {{ visibility: hidden; }}
      .sub {{ position: absolute; left: 60px; top: 1580px; font: 500 24px "Plex Mono"; letter-spacing: 0.14em; color: #8E877E; white-space: nowrap; }}
      /* — mur des pubs : sort de la carte et prend tout l'écran — */
      #wall {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; visibility: hidden; overflow: hidden; background: #0A090B; clip-path: {CARD}; }}
      #grid {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; transform-origin: 540px 960px; }}
      .col {{ position: absolute; top: 0; width: 360px; height: 2560px; }}
      .tile {{ position: relative; width: 360px; height: 640px; }}
      .tin {{ position: absolute; inset: 5px; border-radius: 16px; overflow: hidden; background: #000; }}
      #wpill {{ position: absolute; left: 0; right: 0; top: 910px; margin: 0 auto; width: fit-content; height: 100px; padding: 0 44px; border-radius: 50px; background: {CREAM}; color: #111; font: 800 40px "Inter"; display: flex; align-items: center; gap: 16px; box-shadow: 0 24px 70px rgba(0,0,0,0.55); }}
      #wpill i {{ width: 18px; height: 18px; border-radius: 9px; background: {ORANGE}; }}
      /* — showreel (repère 1600×900) — */
      .sec {{ position: absolute; inset: 0; visibility: hidden; opacity: 0; overflow: hidden; }}
      .mono {{ font: 500 18px "Plex Mono"; letter-spacing: 0.14em; white-space: nowrap; }}
      #s0 {{ background: #EFEAE0; color: {INK}; }}
      #s0 h2 {{ position: absolute; left: 92px; top: 92px; font: italic 400 76px/1 "Instrument Serif"; }}
      #s0 .note {{ position: absolute; right: 92px; top: 128px; }}
      .row {{ position: absolute; left: 92px; right: 92px; height: 40px; }}
      .row .lab {{ position: absolute; left: 0; top: 10px; font: 500 18px "Plex Mono"; letter-spacing: 0.14em; color: #3A3732; }}
      .row .trk {{ position: absolute; left: 330px; right: 0; top: 19px; height: 2px; background: repeating-linear-gradient(90deg, rgba(20,20,20,0.35) 0 2px, transparent 2px 40px); }}
      .dot {{ position: absolute; left: 316px; top: 6px; width: 28px; height: 28px; border-radius: 14px; }}
      .ab {{ position: absolute; top: 212px; font: 500 18px "Plex Mono"; color: #3A3732; }}
      #s1 {{ background: {BLUE}; color: #fff; }}
      #s1 svg {{ position: absolute; left: 0; top: 0; }}
      .cross {{ position: absolute; background: rgba(255,255,255,0.22); }}
      #s2 {{ background: #101012; color: #fff; }}
      #s3 {{ background: {ORANGE}; color: {INK}; }}
      .ad {{ position: absolute; top: 96px; width: 382px; height: 680px; border-radius: 18px; overflow: hidden; background: #000; box-shadow: 0 30px 60px rgba(0,0,0,0.45); }}
      .vid {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; }}
      .gph {{ position: absolute; inset: 0; overflow: hidden; background: #000; }}
      .gph img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; visibility: hidden; }}
      .adl {{ position: absolute; top: 792px; width: 382px; display: flex; justify-content: space-between; align-items: baseline; }}
      .adl em {{ font: italic 400 36px "Instrument Serif"; }}
      .adl span {{ font: 500 14px "Plex Mono"; letter-spacing: 0.14em; opacity: 0.75; }}
      #s4, #s5 {{ background: #0B0B0D; }}
      #s4 canvas, #s5 canvas, #s6 canvas {{ position: absolute; left: 0; top: 0; }}
      .lbl {{ position: absolute; left: 200px; top: 780px; }}
      /* 07 · particules */
      #s6 {{ background: {BLUE}; color: #fff; }}
      #crea {{ position: absolute; left: 300px; top: 252px; font: italic 400 76px/1 "Instrument Serif"; color: {CREAM}; }}
      /* 08 · site web */
      #s7 {{ background: {LIME}; color: {INK}; }}
      #win {{ position: absolute; left: 230px; top: 105px; width: 1140px; height: 660px; border-radius: 22px; background: #FBFAF7; overflow: hidden; box-shadow: 0 40px 80px rgba(20,20,20,0.25), 0 0 0 2px rgba(20,20,20,0.08); }}
      #wbar {{ position: absolute; left: 0; top: 0; right: 0; height: 54px; background: #ECE8E0; display: flex; align-items: center; padding-left: 24px; gap: 10px; }}
      #wbar i {{ width: 14px; height: 14px; border-radius: 7px; }}
      #url {{ position: absolute; left: 360px; top: 12px; width: 420px; height: 30px; border-radius: 15px; background: #FBFAF7; font: 500 15px "Plex Mono"; letter-spacing: 0.06em; color: #5F5A54; display: flex; align-items: center; justify-content: center; }}
      #view {{ position: absolute; left: 0; top: 54px; right: 0; bottom: 0; overflow: hidden; }}
      #page {{ position: absolute; left: 0; top: 0; width: 1140px; height: 1000px; }}
      #nav {{ position: absolute; left: 48px; right: 48px; top: 22px; height: 46px; display: flex; align-items: center; justify-content: space-between; }}
      .logo {{ font: 800 24px "Inter"; color: {INK}; display: flex; gap: 12px; align-items: center; }}
      .logo i {{ width: 22px; height: 22px; background: {ORANGE}; border-radius: 6px; transform: rotate(45deg); }}
      .links {{ display: flex; gap: 34px; align-items: center; font: 600 18px "Inter"; color: #5F5A54; }}
      .links b {{ font: 800 17px "Inter"; color: #fff; background: {INK}; padding: 12px 22px; border-radius: 24px; }}
      #wt {{ position: absolute; left: 48px; top: 112px; font: 400 72px/1.02 "Archivo Black"; color: {INK}; letter-spacing: -0.02em; }}
      #wt em {{ font: italic 400 84px/1 "Instrument Serif"; color: {ORANGE}; letter-spacing: 0; }}
      #wsub {{ position: absolute; left: 48px; top: 362px; font: 600 22px "Inter"; color: #5F5A54; }}
      #wbtn {{ position: absolute; left: 48px; top: 412px; height: 62px; padding: 0 32px; border-radius: 31px; background: {BLUE}; color: #fff; font: 800 22px "Inter"; display: flex; align-items: center; }}
      #hv {{ position: absolute; left: 640px; top: 96px; width: 452px; height: 420px; border-radius: 24px; background: {ORANGE}; overflow: hidden; clip-path: inset(100% 0 0 0 round 24px); }}
      .hs {{ position: absolute; }}
      .wc {{ position: absolute; top: 560px; width: 330px; height: 250px; border-radius: 18px; background: #fff; box-shadow: 0 12px 30px rgba(20,20,20,0.08); overflow: hidden; }}
      .wc i {{ position: absolute; left: 0; top: 0; right: 0; height: 150px; }}
      .wc b {{ position: absolute; left: 22px; height: 12px; border-radius: 6px; background: #DDD6CA; }}
      #cur {{ position: absolute; left: 0; top: 0; }}
      /* 10 · applis & SaaS */
      #s9 {{ background: {CREAM}; color: {INK}; }}
      .sx {{ background: #17171C; }}
      .sx-top {{ position: absolute; left: 18px; top: 16px; display: flex; gap: 7px; }}
      .sx-top i {{ width: 10px; height: 10px; border-radius: 5px; background: #3A3A46; }}
      .sx-side {{ position: absolute; left: 0; top: 44px; bottom: 0; width: 62px; background: #1E1E25; }}
      .sx-side i {{ position: absolute; left: 17px; width: 28px; height: 28px; border-radius: 8px; background: #33333D; }}
      .sx-h {{ position: absolute; left: 80px; top: 50px; font: 800 22px "Inter"; color: #fff; }}
      .sx-kpi {{ position: absolute; top: 94px; width: 88px; height: 86px; border-radius: 12px; background: #23232B; }}
      .sx-kpi b {{ position: absolute; left: 12px; top: 14px; font: 400 26px "Archivo Black"; color: #fff; }}
      .sx-kpi span {{ position: absolute; left: 12px; top: 58px; font: 500 10px "Plex Mono"; letter-spacing: 0.08em; color: #9B958C; }}
      .sx-panel {{ position: absolute; left: 80px; width: 286px; border-radius: 14px; background: #23232B; overflow: hidden; }}
      .sb {{ position: absolute; bottom: 24px; width: 22px; border-radius: 6px 6px 0 0; transform-origin: 50% 100%; }}
      .sx-don {{ position: absolute; left: 18px; top: 36px; }}
      .sx-dn {{ position: absolute; left: 176px; top: 66px; font: 400 40px/1 "Archivo Black"; color: #fff; }}
      .sx-dn small {{ font-size: 20px; }}
      .sx-pl {{ position: absolute; left: 178px; top: 120px; font: 500 10px "Plex Mono"; letter-spacing: 0.08em; color: #9B958C; }}
      /* 11 · scroll-stop */
      #s10 {{ background: {ORANGE}; color: {INK}; }}
      .ssl {{ position: absolute; left: 150px; font: 400 128px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      .ssl em {{ font: italic 400 176px/1 "Instrument Serif"; letter-spacing: 0; }}
      #ph {{ position: absolute; left: 1030px; top: 80px; width: 340px; height: 720px; border-radius: 54px; background: #111; box-shadow: 0 40px 80px rgba(0,0,0,0.35); }}
      #scr {{ position: absolute; left: 12px; top: 12px; width: 316px; height: 696px; border-radius: 42px; overflow: hidden; background: #000; }}
      #strip {{ position: absolute; left: 0; top: 0; width: 316px; }}
      .post {{ position: relative; width: 316px; height: 696px; }}
      .psh {{ position: absolute; left: 60px; top: 150px; width: 196px; height: 196px; border-radius: 30%; background: rgba(255,255,255,0.16); }}
      .pav {{ position: absolute; left: 24px; top: 560px; width: 44px; height: 44px; border-radius: 22px; background: rgba(255,255,255,0.55); }}
      .pb {{ position: absolute; height: 12px; border-radius: 6px; background: rgba(255,255,255,0.45); }}
      .pic {{ position: absolute; left: 258px; width: 40px; height: 40px; border-radius: 20px; background: rgba(255,255,255,0.45); }}
      #ssv {{ position: absolute; left: 0; top: 0; width: 316px; height: 696px; }}
      #shade {{ position: absolute; left: 0; right: 0; bottom: 0; height: 240px; background: linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.75)); }}
      #ssn {{ position: absolute; left: 22px; top: 590px; font: 800 24px "Inter"; color: #fff; }}
      #sst {{ position: absolute; left: 22px; top: 626px; font: 600 18px "Inter"; color: #fff; }}
      #hrt {{ position: absolute; left: 252px; top: 372px; }}
      .sic {{ position: absolute; left: 258px; width: 40px; height: 40px; border-radius: 20px; background: rgba(255,255,255,0.75); }}
      .h1, .h2 {{ position: absolute; left: 0; top: 0; opacity: 0; }}
      /* 12 · cube 3D */
      #s11 {{ background: #111114; perspective: 1700px; perspective-origin: 50% 50%; }}
      #s11 h3 {{ position: absolute; left: 0; right: 0; top: 116px; text-align: center; font: italic 400 76px/1 "Instrument Serif"; color: {CREAM}; }}
      #cube {{ position: absolute; left: 350px; top: 320px; width: 900px; height: 300px; transform-style: preserve-3d; }}
      .face {{ position: absolute; left: 0; top: 0; width: 900px; height: 300px; display: flex; align-items: center; justify-content: center; font: 400 170px/1 "Archivo Black"; letter-spacing: -0.03em; backface-visibility: hidden; border-radius: 8px; }}
      /* 13 · liquide */
      #s12 {{ background: {BLUE}; color: #fff; }}
      #liq {{ position: absolute; left: 0; top: 0; width: 1600px; height: 900px; }}
      /* 14 · typo */
      .wbg {{ position: absolute; inset: 0; visibility: hidden; display: flex; align-items: center; justify-content: center; }}
      .word {{ font: 400 232px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      /* 15 · fin */
      #s14 {{ background: {ORANGE}; color: {INK}; }}
      #mark {{ position: absolute; left: 218px; top: 290px; overflow: visible; }}
      #mark line {{ stroke: {INK}; stroke-width: 30; stroke-linecap: round; }}
      #nm {{ position: absolute; left: 438px; top: 252px; font: 400 290px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      #nm span {{ display: inline-block; }}
      #md {{ position: absolute; left: 450px; top: 548px; font: italic 400 96px/1 "Instrument Serif"; white-space: nowrap; }}
      #rule {{ position: absolute; left: 200px; right: 200px; top: 676px; height: 2px; background: {INK}; transform-origin: 0 50%; }}
      #fine {{ position: absolute; left: 200px; right: 200px; top: 700px; display: flex; justify-content: space-between; font: 500 15px "Plex Mono"; letter-spacing: 0.14em; }}
      /* 16 · contact */
      #s15 {{ background: #111114; color: {CREAM}; }}
      #cav {{ position: absolute; left: 740px; top: 150px; width: 120px; height: 120px; border-radius: 60px; background: {ORANGE}; color: #fff; font: 400 60px "Archivo Black"; display: flex; align-items: center; justify-content: center; }}
      #hdl {{ position: absolute; left: 0; right: 0; top: 304px; text-align: center; font: 400 150px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      #ctal {{ position: absolute; left: 0; right: 0; top: 486px; text-align: center; color: #A8A197; }}
      #fol {{ position: absolute; left: 630px; top: 560px; width: 340px; height: 100px; border-radius: 50px; background: {ORANGE}; }}
      #fol span {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font: 800 42px "Inter"; color: {INK}; }}
      #fon {{ opacity: 0; }}
      #cur2 {{ position: absolute; left: 0; top: 0; }}
      /* habillage technique */
      #hud {{ position: absolute; inset: 0; color: {INK}; pointer-events: none; }}
      .cor {{ position: absolute; width: 30px; height: 30px; border-color: currentColor; border-style: solid; }}
      #hud .tl {{ position: absolute; left: 70px; top: 40px; }}
      #hud .tr {{ position: absolute; right: 70px; top: 40px; }}
      #hud .tr span {{ position: absolute; right: 0; top: 0; opacity: 0; }}
      #hud .bl {{ position: absolute; left: 70px; bottom: 40px; }}
      #hud .br {{ position: absolute; right: 70px; bottom: 40px; display: flex; gap: 14px; align-items: center; }}
      #bars {{ display: flex; gap: 4px; }}
      #bars i {{ width: 12px; height: 12px; border: 2px solid currentColor; }}
      #beat {{ width: 12px; height: 12px; border-radius: 6px; background: currentColor; }}
      #prog {{ position: absolute; left: 0; bottom: 0; width: 1600px; height: 4px; background: currentColor; transform-origin: 0 50%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="glow"></div>
        <div class="pill" id="pill"><i></i>Showreel · Motion design</div>
        <div class="me" id="me"><b>M</b><div><strong>Mams</strong><span>TikTok · @kofamali</span></div></div>
        <div id="card"><div id="stage">
          <div class="sec" id="s0"><h2>Six façons d'aller de A à B.</h2><div class="mono note">MÊME DISTANCE · MÊME DURÉE (1,2 S)</div>
            <div class="ab" style="left:420px">A</div><div class="ab" style="right:92px">B</div>{rows}
          </div>
          <div class="sec" id="s1"><div class="cross" style="left:800px; top:120px; width:1px; height:660px"></div><div class="cross" style="left:200px; top:450px; width:1200px; height:1px"></div>
            <svg width="1600" height="900"><g transform="translate(800 450)"><path id="echo" fill="none" stroke="{ORANGE}" stroke-width="3" opacity="0.8"/><path id="shape" fill="#F4F1EA"/></g><g id="ring"></g></svg>
            <div class="mono" style="position:absolute; left:200px; top:480px">MORPH <span id="mlab">CERCLE</span></div>
            <div class="mono" style="position:absolute; right:200px; top:480px">ROT <span id="mrot">0.0</span>° · RESSORT ζ=0.42</div>
          </div>
          <div class="sec" id="s2">{trio[2]}
          </div>
          <div class="sec" id="s3">{trio[3]}
          </div>
          <div class="sec" id="s4"><canvas id="tru" width="1600" height="900"></canvas></div>
          <div class="sec" id="s5"><canvas id="pts" width="1600" height="900"></canvas><div class="mono lbl" style="color:#fff">POINTS 900 · <span id="plab">SPHÈRE</span></div></div>
          <div class="sec" id="s6"><canvas id="par" width="1600" height="900"></canvas><div id="crea">chaque pixel est</div><div class="mono lbl">PARTICULES <span id="pcount">0</span> · TEXTE → POINTS</div></div>
          <div class="sec" id="s7">
            <div id="win"><div id="wbar"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i><div id="url">votremarque.ml</div></div>
              <div id="view"><div id="page">
                <div id="nav"><div class="logo"><i></i>Votre marque</div><div class="links"><span>Accueil</span><span>Produits</span><span>Contact</span><b>Commander</b></div></div>
                <div id="wt"><div>{m("Votre")}</div><div>{m("boutique")}</div><div>{m("en ligne.", True)}</div></div>
                <div id="wsub">Commandez, on livre partout à Bamako.</div>
                <div id="wbtn">Découvrir&nbsp;&nbsp;→</div>
                <div id="hv"><div class="hs" style="left:46px; top:70px; width:250px; height:250px; border-radius:125px; background:{CREAM}"></div><div class="hs" style="left:230px; top:170px; width:170px; height:170px; border-radius:36px; background:{BLUE}; rotate:14deg"></div><div class="hs" style="left:330px; top:50px; width:84px; height:84px; border-radius:42px; background:{LIME}"></div></div>
                <div class="wc" style="left:48px"><i style="background:{BLUE}"></i><b style="top:174px; width:200px"></b><b style="top:200px; width:130px"></b></div>
                <div class="wc" style="left:405px"><i style="background:{ORANGE}"></i><b style="top:174px; width:220px"></b><b style="top:200px; width:110px"></b></div>
                <div class="wc" style="left:762px"><i style="background:{INK}"></i><b style="top:174px; width:180px"></b><b style="top:200px; width:140px"></b></div>
              </div></div>
              <div id="cur">{CURSOR}</div>
            </div>
            <div class="mono" style="position:absolute; left:230px; top:796px">SITE INTERNET · DESIGN + CODE</div>
          </div>
          <div class="sec" id="s8" style="background:#0A090B"></div>
          <div class="sec" id="s9">{prods}
          </div>
          <div class="sec" id="s10"><div class="mono" style="position:absolute; left:154px; top:196px">SCROLL-STOP · L'ACCROCHE</div>
            <div class="ssl" id="ss1" style="top:262px">{m("Le pouce")}</div><div class="ssl" id="ss2" style="top:392px">{m("s'arrête")}</div><div class="ssl" id="ss3" style="top:500px">{m("ici.", True)}</div>
            <div id="ph"><div id="scr">
              <div id="strip" data-hf-motion-blur='{{"samplesPerFrame": 8}}'>{posts}</div>
              <div id="ssv">{gph('gps', GIMSO[1:2])}
                <div id="shade"></div><div id="ssn">@kofamali</div><div id="sst">Pub vidéo · motion design</div>
                <svg id="hrt" width="52" height="52" viewBox="0 0 24 24"><path id="hrtp" d="{HEART}" fill="#FFFFFF"/></svg><i class="sic" style="top:450px"></i><i class="sic" style="top:520px"></i>
                {hearts("h1")}
              </div>
            </div></div>
          </div>
          <div class="sec" id="s11"><h3>Ce que je crée :</h3><div id="cube" data-layout-allow-overlap>{faces}</div>
            <div class="mono" style="position:absolute; left:200px; top:780px; color:#fff">3D · CSS · ROTATION X 90° · RESSORT</div>
          </div>
          <div class="sec" id="s12"><canvas id="liq" width="800" height="450"></canvas><div class="mono lbl">LIQUIDE · 7 MÉTABALLES</div></div>
          <div class="sec" id="s13">{words}
          </div>
          <div class="sec" id="s14"><svg id="mark" width="200" height="200" viewBox="0 0 200 200"><g id="mk" transform="translate(100 100)">{ARMS}</g></svg>
            <div id="nm">{name}</div><div id="md">motion designer</div><div id="rule"></div>
            <div id="fine"><span>SHOWREEL 2026</span><span>32 SECONDES</span><span>CHAQUE IMAGE CRÉÉE EN CODE</span><span>DISPONIBLE POUR VOS PROJETS</span></div>
          </div>
          <div class="sec" id="s15"><div id="cav">M</div><div id="hdl">@kofamali</div><div class="mono" id="ctal">TIKTOK · SITES · APPLIS · PUBS VIDÉO</div>
            <div id="fol"><span id="foff">Suivre</span><span id="fon">Abonné ✓</span></div>{hearts("h2")}
            <div id="cur2">{CURSOR}</div>
          </div>
          <div id="hud">
            <div class="cor" style="left:24px; top:24px; border-width:3px 0 0 3px"></div><div class="cor" style="right:24px; top:24px; border-width:3px 3px 0 0"></div>
            <div class="cor" style="left:24px; bottom:24px; border-width:0 0 3px 3px"></div><div class="cor" style="right:24px; bottom:24px; border-width:0 3px 3px 0"></div>
            <div class="mono tl"><b>MAMS</b>&nbsp;&nbsp;&nbsp;MOTION REEL — 2026</div>
            <div class="mono tr">{secs}</div>
            <div class="mono bl"><span id="tc">00:00:00:00</span>&nbsp;&nbsp;&nbsp;60 FPS</div>
            <div class="mono br">120 BPM <span id="bars">{barsq}</span> <span id="barn">BAR 1/{NB}</span> <span id="beat"></span></div>
            <div id="prog"></div>
          </div>
        </div></div>
        <div class="kick" id="kick">× 100 % CRÉÉ EN CODE · SANS AFTER EFFECTS ×</div>
        <div class="act" id="actA">
          <div class="hl" id="hl1" style="top:1196px">Votre marque</div>
          <div class="hl" id="hl2" style="top:1302px">{m("mérite")} {m("une vraie", True)}</div>
          <div id="box"></div>
          <div class="hl" id="hl3" style="top:1426px">&nbsp;pub vidéo.</div>
        </div>
        {act("B", "Sites internet", m("et") + " " + m("applis mobiles", True), "sur mesure.")}
        {act("C", "Écrivez-moi", m("sur") + " " + m("TikTok", True), "@kofamali")}
        <div class="sub" id="sub">SITES INTERNET · APPLIS MOBILES · PUBS VIDÉO</div>
        <div id="wall"><div id="grid">{wall}</div><div id="wpill"><i></i>Mes dernières créations</div></div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.05"></canvas>
      </div>
      <audio id="music" src="assets/music.wav" data-start="{R0}" data-duration="{round(TOTAL - R0, 2)}" data-track-index="10" data-volume="0.9"></audio>
      <audio id="sfx0" src="assets/whoosh.wav" data-start="0.05" data-duration="0.55" data-track-index="11" data-volume="0.45"></audio>
      <audio id="sfx1" src="assets/impact.wav" data-start="{at(8)}" data-duration="1.2" data-track-index="12" data-volume="0.55"></audio>
      <audio id="sfx2" src="assets/whoosh.wav" data-start="{round(at(9) - 0.45, 2)}" data-duration="0.55" data-track-index="13" data-volume="0.4"></audio>
      <audio id="sfx3" src="assets/whoosh.wav" data-start="{at(10)}" data-duration="0.55" data-track-index="14" data-volume="0.35"></audio>
      <audio id="sfx4" src="assets/impact.wav" data-start="{at(14)}" data-duration="1.2" data-track-index="15" data-volume="0.5"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }});
        const R0 = {R0}, BAR = {BAR}, NB = {NB}, BEAT = BAR / 4, at = (bar, beat = 0) => R0 + bar * BAR + beat * BEAT;
        const cl = (x) => Math.min(1, Math.max(0, x)), smooth = (a, b, x) => {{ const t = cl((x - a) / (b - a)); return t * t * (3 - 2 * t); }};
%%JS%%
        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
%%MB%%
  </body>
</html>
'''
JS = r'''
        // ── cadre : la carte se pose, les pastilles et l'accroche arrivent, puis tout respire ──
        tl.fromTo("#glow", { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 1.4, ease: S.ease.silk }, 0);
        S.pop(tl, ["#pill", "#me"], 0.08, { from: 0.7, y: -20, damping: 0.75, response: 0.45, stagger: 0.1 });
        tl.fromTo("#card", { scale: 0.88, opacity: 0, filter: "blur(18px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.8, ease: S.ease.silk }, 0);
        S.rise(tl, S.split($("#kick")), 0.3, { y: 14, blur: 6, stagger: 0.012, duration: 0.6, max: 0.4 });
        S.maskUp(tl, S.split($("#hl1"), { by: "words", mask: true }), 0.42, { duration: 0.8 });
        S.maskUp(tl, $$("#hl2 .st-word"), 0.55, { duration: 0.8 });
        tl.fromTo("#box", { scaleX: 0 }, { scaleX: 1, duration: 0.55, ease: S.ease.swift }, 0.72);
        S.maskUp(tl, S.split($("#hl3"), { by: "words", mask: true }), 0.82, { duration: 0.7 });
        tl.fromTo("#sub", { opacity: 0 }, { opacity: 1, duration: 0.6, ease: S.ease.breath }, 1.1);
        S.life(tl, [$("#card")], 1.0, TOTAL, { x: 0, y: 4, rotate: 0.15, scale: 0.003, period: 6, seed: 3 });
        S.life(tl, [$("#pill"), $("#me")], 1.0, TOTAL, { x: 2, y: 3, rotate: 0.3, scale: 0.004, period: 5, seed: 7 });
        tl.fromTo("#glow", { scale: 1 }, { scale: 1.06, duration: 2.0, ease: S.ease.breath, yoyo: true, repeat: 15, immediateRender: false }, 1.4);

        // ── l'accroche change avec le propos : la pub (A), le site (B), le contact (C) ──
        const actIn = (id, t) => {
          tl.set(id, { visibility: "visible" }, t);
          S.maskUp(tl, $$(id + " .st-word"), t, { duration: 0.8 });
          S.maskUp(tl, S.split($(id + " .hl"), { by: "words", mask: true }), t, { duration: 0.8 });
          tl.fromTo(id + " .bx", { clipPath: "inset(0% 100% 0% 0% round 8px)" }, { clipPath: "inset(0% 0% 0% 0% round 8px)", duration: 0.55, ease: S.ease.swift }, t + 0.25);
          S.maskUp(tl, S.split($(id + " .bx"), { by: "words", mask: true }), t + 0.35, { duration: 0.7 });
        };
        actIn("#actB", at(9)); actIn("#actC", at(14));
        S.leave(tl, $$("#actB .hl"), at(14) - 0.35, { y: -30, duration: 0.3, stagger: 0.04 });
        tl.set("#actB", { visibility: "hidden" }, at(14));

        // ── sections : coupe franche sur chaque mesure ──
        for (let i = 0; i < NB; i++) {
          tl.set("#s" + i, { autoAlpha: 1 }, at(i));
          if (i < NB - 1) tl.set("#s" + i, { autoAlpha: 0 }, at(i + 1));
          tl.set("#sl" + i, { opacity: 1 }, at(i)); if (i < NB - 1) tl.set("#sl" + i, { opacity: 0 }, at(i + 1));
        }
        HUDC.forEach(([b, c]) => tl.set("#hud", { color: c }, at(Math.floor(b), (b % 1) * 4)));

        // habillage : timecode, mesures, temps, barre de progression (fonction pure du temps)
        const tc = $("#tc"), sq = $$("#bars i"), barn = $("#barn"), beat = $("#beat"), prog = $("#prog");
        const hud = (t) => {
          const lt = Math.max(0, t - R0), f = Math.floor(lt * 60 + 1e-6), b = Math.min(NB - 1, Math.floor(lt / BAR));
          tc.textContent = "00:00:" + String(Math.floor(f / 60)).padStart(2, "0") + ":" + String(f % 60).padStart(2, "0");
          sq.forEach((e, i) => { e.style.background = i <= b ? "currentColor" : "transparent"; });
          barn.textContent = "BAR " + (b + 1) + "/" + NB;
          beat.style.opacity = (lt % BEAT) < 0.12 ? 1 : 0.25;
          prog.style.transform = "scaleX(" + Math.min(1, lt / (NB * BAR)).toFixed(4) + ")";
        };

        // ── 01 · easing : six courbes, même distance, même durée ──
        const spr = S.spring({ response: 0.5, damping: 0.42 }).ease;
        EASES.forEach((e, i) => tl.fromTo("#d" + i, { x: 0 }, { x: 1044, duration: 1.2, ease: e === "spring" ? spr : (S.ease[e] || e) }, at(0, 0.6)));
        S.rise(tl, $("#s0 h2"), at(0), { y: 20, blur: 8, duration: 0.6 });

        // ── 02 · morphing : cercle → triangle → étoile → carré sur les temps, ressort et écho ──
        const SH = SHAPES, SEQ = [["circle", "CERCLE"], ["triangle", "CERCLE → TRIANGLE"], ["star", "TRIANGLE → ÉTOILE"], ["square", "ÉTOILE → CARRÉ"]];
        const mE = S.spring({ response: 0.42, damping: 0.42 }).ease, MD = 0.45, shapePath = $("#shape"), echo = $("#echo");
        const ring = $("#ring"), NS = "http://www.w3.org/2000/svg", tris = [];
        for (let k = 0; k < 10; k++) { const p = document.createElementNS(NS, "polygon"); p.setAttribute("points", "0,-15 13,10 -13,10"); p.setAttribute("fill", "#F4F1EA"); ring.appendChild(p); tris.push(p); }
        const morphAt = (lt) => {
          let i = 0; while (i < 3 && lt >= (i + 1) * BEAT) i++;
          if (i === 0) return { pts: SH.circle, rot: 0, lab: SEQ[0][1] };
          const a = SH[SEQ[i - 1][0]], b = SH[SEQ[i][0]], p = mE(Math.min(1, Math.max(0, (lt - i * BEAT) / MD)));
          return { pts: a.map((q, k) => [q[0] + (b[k][0] - q[0]) * p, q[1] + (b[k][1] - q[1]) * p]), rot: 72 * (i - 1) + 72 * p, lab: SEQ[i][1] };
        };
        const d = (m, s) => "M" + m.pts.map((q) => { const r = m.rot * Math.PI / 180, c = Math.cos(r), n = Math.sin(r); return ((q[0] * c - q[1] * n) * s).toFixed(1) + " " + ((q[0] * n + q[1] * c) * s).toFixed(1); }).join("L") + "Z";
        const morph = (t) => {
          const lt = t - at(1); if (lt < -0.01 || lt > BAR + 0.01) return;
          const pop = S.ease.overshoot(Math.min(1, Math.max(0, lt / 0.35)));
          const m = morphAt(lt), e = morphAt(Math.max(0, lt - 0.08));
          shapePath.setAttribute("d", d(m, pop)); echo.setAttribute("d", d(e, pop * 1.04));
          $("#mlab").textContent = m.lab; $("#mrot").textContent = m.rot.toFixed(1);
          tris.forEach((p, k) => { const a = lt * 0.9 + k * Math.PI / 5, x = 800 + Math.cos(a) * 340 * pop, y = 450 + Math.sin(a) * 300 * pop; p.setAttribute("transform", "translate(" + x.toFixed(1) + " " + y.toFixed(1) + ") rotate(" + (a * 57.3 + 90).toFixed(1) + ")"); });
        };

        // ── 03 / 04 · vos pubs : trois vidéos qui montent sur ressort ──
        [[2, [0, 1, 2]], [3, [3, 4, 5]]].forEach(([bar, ids]) => {
          S.pop(tl, ids.map((i) => "#ad" + i), at(bar), { from: 0.9, y: 140, damping: 0.72, response: 0.5, stagger: 0.07 });
          S.rise(tl, ids.map((i) => "#al" + i), at(bar, 0.6), { y: 16, blur: 6, stagger: 0.07, duration: 0.6 });
        });

        // GimSo : diaporama de ses photos, une coupe par temps et un zoom qui se pose (une seule photo dans le téléphone)
        const slides = (sel, bar) => {
          const im = $$(sel + " img"), n = im.length, d = BAR / n;
          im.forEach((el, i) => {
            const t0 = at(bar) + i * d;
            tl.set(el, { autoAlpha: 1 }, t0); if (i < n - 1) tl.set(el, { autoAlpha: 0 }, t0 + d);
            tl.fromTo(el, { scale: 1.15 }, { scale: 1.03, duration: d, ease: S.ease.silk }, t0);
          });
        };
        slides("#gp4", 3); slides("#gpw11", 8); slides("#gps", 10);

        // ── 05 · motifs : tuiles de Truchet qui pivotent en vagues depuis le centre ──
        const tru = $("#tru").getContext("2d"), hash = (a, b, c) => { let h = (a * 73856093) ^ (b * 19349663) ^ (c * 83492791); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
        const truchet = (t) => {
          const lt = t - at(4); if (lt < -0.01 || lt > BAR + 0.01) return;
          tru.fillStyle = "#0B0B0D"; tru.fillRect(0, 0, 1600, 900); tru.lineWidth = 18; tru.lineCap = "butt";
          for (let gy = 1; gy < 8; gy++) for (let gx = 0; gx < 16; gx++) {  // rangées du haut et du bas laissées noires : l'habillage reste lisible
            const dist = Math.hypot(gx - 7.5, gy - 4) * 0.045; let rot = (hash(gx, gy, 1) < 0.5 ? 0 : 1) * Math.PI / 2;
            for (let w = 0; w < 4; w++) rot += S.ease.silk(Math.min(1, Math.max(0, (lt - w * BEAT - dist) / 0.32))) * Math.PI / 2;
            tru.save(); tru.translate(gx * 100 + 50, gy * 100 + 50); tru.rotate(rot);
            tru.strokeStyle = lt > 2 * BEAT && hash(gx, gy, 2) < 0.3 ? "#FF4F1F" : "#F4F1EA";
            tru.beginPath(); tru.arc(-50, -50, 50, 0, Math.PI / 2); tru.stroke();
            tru.beginPath(); tru.arc(50, 50, 50, Math.PI, Math.PI * 1.5); tru.stroke(); tru.restore();
          }
        };

        // ── 06 · 3D : 900 points, sphère qui devient un tore, en rotation ──
        const pts = $("#pts").getContext("2d"), NP = 900, SPH = [], TOR = [];
        for (let k = 0; k < NP; k++) {
          const y = 1 - 2 * (k + 0.5) / NP, r = Math.sqrt(1 - y * y), ph = k * 2.399963; SPH.push([r * Math.cos(ph), y, r * Math.sin(ph)]);
          const u = 2 * Math.PI * ((k * 0.618034) % 1), v = 2 * Math.PI * k / NP * 23; TOR.push([(0.78 + 0.3 * Math.cos(v)) * Math.cos(u), 0.3 * Math.sin(v), (0.78 + 0.3 * Math.cos(v)) * Math.sin(u)]);
        }
        const cloud = (t) => {
          const lt = t - at(5); if (lt < -0.01 || lt > BAR + 0.01) return;
          pts.fillStyle = "#0B0B0D"; pts.fillRect(0, 0, 1600, 900);
          const m = S.ease.glide(Math.min(1, Math.max(0, (lt - 0.8) / 0.7))), grow = S.ease.silk(Math.min(1, lt / 0.6));
          const ry = lt * 1.2, rx = 0.45 + 0.25 * m, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
          $("#plab").textContent = m < 0.5 ? "SPHÈRE" : "SPHÈRE → TORE";
          for (let k = 0; k < NP; k++) {
            const a = SPH[k], b = TOR[k]; let x = (a[0] + (b[0] - a[0]) * m) * grow, y = (a[1] + (b[1] - a[1]) * m) * grow, z = (a[2] + (b[2] - a[2]) * m) * grow;
            const x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y1 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
            const f = 620 / (z2 + 2.8), px = 800 + x1 * f * 1.3, py = 430 + y1 * f * 1.3, s = Math.max(1.2, 4.2 * f / 300);
            pts.globalAlpha = 0.35 + 0.65 * (1 - (z2 + 1) / 2); pts.fillStyle = k % 9 === 0 ? "#FF4F1F" : "#F4F1EA";
            pts.beginPath(); pts.arc(px, py, s, 0, 6.2832); pts.fill();
          }
          pts.globalAlpha = 1;
        };

        // ── 07 · particules : des points dispersés forment CODÉ. (vague de gauche à droite, ressort), puis explosent ──
        const par = $("#par").getContext("2d"), psp = S.spring({ response: 0.45, damping: 0.6 }); let PT = null;
        const buildPT = () => {
          const c = document.createElement("canvas"); c.width = 1600; c.height = 900; const g = c.getContext("2d");
          g.font = '400 300px "Archivo Black"'; g.textAlign = "center"; g.fillStyle = "#000"; g.fillText("CODÉ.", 800, 570);
          const D = g.getImageData(0, 0, 1600, 900).data, L = [];
          for (let y = 0; y < 900; y += 8) for (let x = 0; x < 1600; x += 8) if (D[(y * 1600 + x) * 4 + 3] > 128) L.push([x, y]);
          $("#pcount").textContent = String(L.length);
          return { ok: document.fonts.check('300px "Archivo Black"'), P: L.map(([x, y], i) => ({ x, y, sx: 800 + (hash(i, 1, 3) - 0.5) * 2600, sy: 450 + (hash(i, 2, 3) - 0.5) * 1500,
            dl: (x - 300) / 1000 * 0.3 + hash(i, 3, 3) * 0.08, v: 500 + 900 * hash(i, 4, 3), lime: hash(i, 5, 3) < 0.12 })) };
        };
        const particles = (t) => {
          const lt = t - at(6); if (lt < -0.01 || lt > BAR + 0.01) return;
          if (!PT || !PT.ok) PT = buildPT();
          par.fillStyle = "#2340FF"; par.fillRect(0, 0, 1600, 900);
          const ex = cl((lt - 1.6) / 0.4), shimmer = lt > 1.0 && lt < 1.6 ? 1 : 0;
          par.globalAlpha = 1 - ex;
          PT.P.forEach((p, i) => {
            const k = psp.ease(cl((lt - 0.05 - p.dl) / psp.duration));
            let x = p.sx + (p.x - p.sx) * k, y = p.sy + (p.y - p.sy) * k;
            if (shimmer) { x += Math.sin(lt * 9 + i) * 0.8; y += Math.cos(lt * 7 + i * 1.3) * 0.8; }
            if (ex > 0) { const dx = p.x - 800, dy = p.y - 460, r = Math.hypot(dx, dy) + 1, s = ex * ex * p.v; x += dx / r * s; y += dy / r * s; }
            par.fillStyle = p.lime ? "#D7FF3A" : "#F4F1EA"; par.fillRect(x - 2.5, y - 2.5, 5, 5);
          });
          par.globalAlpha = 1;
        };
        S.rise(tl, "#crea", at(6, 1.7), { y: 20, blur: 8, duration: 0.6 });
        S.leave(tl, "#crea", at(6, 3.2), { y: -20, duration: 0.3 });

        // ── 08 · site web : la page se construit, le curseur clique, la page défile ──
        const ui = S.spring({ response: 0.5, damping: 0.72 });
        tl.fromTo("#win", { scale: 0.9, y: 40, opacity: 0 }, { scale: 1, y: 0, opacity: 1, duration: ui.duration, ease: ui.ease }, at(7));
        S.rise(tl, $$("#nav .logo, #nav .links > *"), at(7, 0.3), { y: 12, blur: 4, stagger: 0.05, duration: 0.5 });
        S.maskUp(tl, $$("#wt .st-word"), at(7, 0.5), { duration: 0.7, stagger: 0.08 });
        tl.fromTo("#hv", { clipPath: "inset(100% 0% 0% 0% round 24px)" }, { clipPath: "inset(0% 0% 0% 0% round 24px)", duration: 0.6, ease: S.ease.swift }, at(7, 0.6));
        S.pop(tl, $$("#hv .hs"), at(7, 1.0), { from: 0.4, stagger: 0.07, damping: 0.6 });
        S.rise(tl, "#wsub", at(7, 1.2), { y: 12, blur: 4, duration: 0.5 });
        S.pop(tl, "#wbtn", at(7, 1.2), { from: 0.7, damping: 0.7, response: 0.3 });
        tl.fromTo("#cur", { x: 980, y: 620 }, { x: 150, y: 500, duration: 0.55, ease: S.ease.glide }, at(7, 1.2));
        const once = { immediateRender: false };
        tl.fromTo("#wbtn", { scale: 1, backgroundColor: "#2340FF" }, { scale: 1.05, backgroundColor: "#1A30C9", duration: 0.15, ease: S.ease.swift, ...once }, at(7, 2.3));
        tl.fromTo("#wbtn", { scale: 1.05 }, { scale: 0.95, duration: 0.08, ease: "none", ...once }, at(7, 2.6));
        tl.fromTo("#cur", { scale: 1 }, { scale: 0.88, duration: 0.08, ease: "none", ...once }, at(7, 2.6));
        tl.fromTo("#wbtn", { scale: 0.95 }, { scale: 1, duration: 0.25, ease: S.ease.overshoot, ...once }, at(7, 2.76));
        tl.fromTo("#cur", { scale: 0.88 }, { scale: 1, duration: 0.25, ease: S.ease.overshoot, ...once }, at(7, 2.76));
        tl.fromTo("#page", { y: 0 }, { y: -330, duration: 0.7, ease: S.ease.silk }, at(7, 2.9));
        tl.fromTo("#cur", { y: 500 }, { y: 170, duration: 0.7, ease: S.ease.silk, ...once }, at(7, 2.9));
        S.pop(tl, $$("#page .wc"), at(7, 3.0), { from: 0.85, y: 50, stagger: 0.07, damping: 0.7 });

        // ── 09 · le mur : on sort de la carte, toutes les pubs plein écran, colonnes en parallaxe, puis retour ──
        const back = S.spring({ response: 0.45, damping: 0.75 });
        tl.set("#wall", { autoAlpha: 1 }, at(8)); tl.set("#wall", { autoAlpha: 0 }, at(9));
        tl.fromTo("#wall", { clipPath: "CARD" }, { clipPath: "inset(0px 0px 0px 0px round 0px)", duration: 0.55, ease: S.ease.swift }, at(8));
        tl.fromTo("#grid", { scale: 3 }, { scale: 1, duration: 1.0, ease: S.ease.silk }, at(8));
        WALLY.forEach(([a, b], c) => tl.fromTo("#col" + c, { y: a }, { y: b, duration: BAR, ease: "none" }, at(8)));
        S.pop(tl, "#wpill", at(8, 1.2), { from: 0.6, damping: 0.7, response: 0.35 });
        S.leave(tl, "#wpill", at(8, 3.0), { y: -20, duration: 0.25 });
        tl.fromTo("#wall", { clipPath: "inset(0px 0px 0px 0px round 0px)" }, { clipPath: "CARD", duration: 0.32, ease: S.ease.exit, ...once }, at(9) - 0.32);
        tl.fromTo("#grid", { scale: 1 }, { scale: 1.6, duration: 0.32, ease: S.ease.exit, ...once }, at(9) - 0.32);
        const WR = ["#pill", "#me", "#kick", "#actA", "#sub"];  // cachés sous le mur, puis de retour
        tl.fromTo(WR, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.2, ease: "none", ...once }, at(8, 0.4));
        tl.fromTo(["#pill", "#me"], { autoAlpha: 0, scale: 0.7, y: -20 }, { autoAlpha: 1, scale: 1, y: 0, duration: back.duration, ease: back.ease, stagger: 0.08, immediateRender: false }, at(9));
        tl.fromTo(["#kick", "#sub"], { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5, ease: S.ease.breath, immediateRender: false }, at(9, 0.6));

        // ── 10 · applis & SaaS : trois produits sur ressort ; dans le SaaS, compteurs, barres et anneau ──
        S.pop(tl, ["#ad6", "#ad7", "#ad8"], at(9), { from: 0.9, y: 140, damping: 0.72, response: 0.5, stagger: 0.07 });
        S.rise(tl, ["#al6", "#al7", "#al8"], at(9, 0.6), { y: 16, blur: 6, stagger: 0.07, duration: 0.6 });
        const bs = S.spring({ response: 0.5, damping: 0.6 });
        tl.fromTo("#ad7 .sb", { scaleY: 0 }, { scaleY: 1, duration: bs.duration, ease: bs.ease, stagger: 0.05 }, at(9, 1.4));
        const kEl = KPIV.map((v, i) => $("#kv" + i)), sring = $("#sring"), sdn = $("#sdn");
        const saas = (t) => {
          const lt = t - at(9); if (lt < -0.01 || lt > BAR + 0.01) return;
          const k = S.ease.silk(cl((lt - 0.6) / 0.9)), p = S.ease.glide(cl((lt - 0.9) / 0.9));
          KPIV.forEach((v, i) => { kEl[i].textContent = String(Math.round(v * k)); });
          sring.setAttribute("stroke-dashoffset", (SC * (1 - 0.72 * p)).toFixed(1)); sdn.textContent = String(Math.round(72 * p));
        };

        // ── 11 · scroll-stop : le fil défile à toute vitesse (flou de mouvement) et se pose sur la pub ──
        tl.fromTo("#strip", { y: 0 }, { y: -4872, duration: 1.3, ease: S.ease.silk }, at(10, 0.1));
        tl.fromTo("#ssv", { y: 4872 }, { y: 0, duration: 1.3, ease: S.ease.silk }, at(10, 0.1));
        S.maskUp(tl, $$("#s10 .st-word"), at(10, 1.8), { duration: 0.6, stagger: 0.1 });
        const hp = S.spring({ response: 0.35, damping: 0.45 });
        tl.fromTo("#hrt", { scale: 1 }, { scale: 0.7, duration: 0.08, ease: "none", ...once }, at(10, 2.8));
        tl.set("#hrtp", { attr: { fill: "#FF4F1F" } }, at(10, 2.96));
        tl.fromTo("#hrt", { scale: 0.7 }, { scale: 1, duration: hp.duration, ease: hp.ease, ...once }, at(10, 2.96));
        // cœurs qui montent : fonction pure du temps (rejouable dans les deux sens)
        const burst = (els, t0, ox, oy, sx, up) => (t) => els.forEach((h, i) => {
          const lt = t - t0 - i * 0.05;
          if (lt < 0 || lt > 1.1) { h.style.opacity = 0; return; }
          const p = S.ease.silk(lt / 1.1);
          h.style.opacity = (1 - p).toFixed(3);
          h.style.transform = "translate(" + (ox + (i - 2.5) * sx * p).toFixed(1) + "px, " + (oy - (up + i * 26) * p).toFixed(1) + "px) scale(" + (0.5 + 0.8 * p).toFixed(3) + ")";
        });
        const likes = burst($$(".h1"), at(10, 3.0), 262, 382, 22, 120);

        // ── 12 · cube 3D : SITES, APPLIS, PUBS, MOTION, un quart de tour par temps ──
        const cs = S.spring({ response: 0.42, damping: 0.55 }), cubeEl = $("#cube");
        S.rise(tl, "#s11 h3", at(11), { y: 20, blur: 8, duration: 0.6 });
        const cube = (t) => {
          const lt = t - at(11); if (lt < -0.01 || lt > BAR + 0.01) return;
          const intro = S.ease.silk(cl(lt / 0.7)); let rx = 0;
          for (let k = 1; k < 4; k++) rx += 90 * cs.ease(cl((lt - k * BEAT) / cs.duration));
          const ry = -60 + 36 * intro + 14 * cl((lt - 0.7) / (BAR - 0.7));
          cubeEl.style.transform = "scale(" + (0.7 + 0.3 * intro).toFixed(4) + ") rotateY(" + ry.toFixed(2) + "deg) rotateX(" + rx.toFixed(2) + "deg)";
        };

        // ── 13 · liquide : sept métaballes qui tournent puis fusionnent en une seule ──
        const lq = $("#liq").getContext("2d"), LI = lq.createImageData(800, 450), LD = LI.data;
        const LB = [[260, 120, 1.3, 1.7, 0, 1, 70], [220, 140, 1.1, 1.9, 2, 0.5, 62], [300, 100, 1.6, 1.2, 4, 2, 55], [180, 150, 0.9, 1.4, 1, 3, 80], [240, 110, 1.8, 1.1, 3, 4, 50], [200, 130, 1.2, 1.6, 5, 1.5, 66], [280, 90, 1.4, 2.0, 2.5, 5, 58]];
        const liquid = (t) => {
          const lt = t - at(12); if (lt < -0.01 || lt > BAR + 0.01) return;
          const grow = S.ease.silk(cl(lt / 0.7)), mg = S.ease.glide(cl((lt - 0.5) / 1.1));
          const B = LB.map(([ax, ay, w1, w2, p1, p2, r], i) => {
            const ox = 400 + ax * Math.sin(w1 * lt * 1.6 + p1), oy = 225 + ay * 0.9 * Math.sin(w2 * lt * 1.6 + p2);
            const mx = 400 + 34 * Math.cos(i * 0.9 + lt * 3), my = 225 + 24 * Math.sin(i * 1.3 + lt * 2.6);
            const rr = r * grow * (1 - 0.32 * mg); return [ox + (mx - ox) * mg, oy + (my - oy) * mg, rr * rr];
          });
          let o = 0;
          for (let y = 0; y < 450; y++) for (let x = 0; x < 800; x++) {
            let f = 0, fs = 0;
            for (let k = 0; k < 7; k++) {
              const dx = x - B[k][0], dy = y - B[k][1], ex = dx + 16, ey = dy + 18;
              f += B[k][2] / (dx * dx + dy * dy + 1); fs += B[k][2] / (ex * ex + ey * ey + 1);
            }
            const h = smooth(0.45, 1.0, f) * 0.45, c = smooth(0.94, 1.06, f), w = smooth(2.6, 5.0, fs) * smooth(1.2, 1.6, f) * 0.55;
            let r = 35 + (111 - 35) * h, g = 64 + (130 - 64) * h, b = 255;
            r += (255 - r) * c; g += (79 - g) * c; b += (31 - b) * c;
            r += (255 - r) * w; g += (176 - g) * w; b += (143 - b) * w;
            LD[o] = r; LD[o + 1] = g; LD[o + 2] = b; LD[o + 3] = 255; o += 4;
          }
          lq.putImageData(LI, 0, 0);
        };

        // ── 14 · typo : un mot par temps, qui claque (écrasement + flou de mouvement) ──
        for (let i = 0; i < 4; i++) {
          tl.set("#wb" + i, { visibility: "visible" }, at(13, i)); if (i < 3) tl.set("#wb" + i, { visibility: "hidden" }, at(13, i + 1));
          tl.fromTo("#w" + i, { scaleX: 1.35, scaleY: 0.25, y: 80, opacity: 0 }, { scaleX: 1, scaleY: 1, y: 0, opacity: 1, duration: 0.28, ease: S.ease.overshoot }, at(13, i));
        }

        // ── 15 · fin : l'étoile tourne et se pose, MAMS se décode lettre par lettre ──
        const mk = S.spring({ response: 0.5, damping: 0.6 });
        tl.fromTo("#mark", { scale: 0, rotation: -160 }, { scale: 1, rotation: 0, duration: mk.duration, ease: mk.ease }, at(14));
        tl.fromTo("#mark", { rotation: 0 }, { rotation: 40, duration: BAR - 0.6, ease: "none", immediateRender: false }, at(14, 1.2));
        const GL = "ABCDEFGHJKLMNPRSTUVWXYZ#%&*", letters = $$("#nm span"), FINAL = "MAMS";
        const decode = (t) => {
          letters.forEach((el, i) => {
            const s0 = at(14, 0.5) + i * 0.05, f = Math.floor(t * 60);
            if (t < s0) { el.style.opacity = 0; return; }
            el.style.opacity = 1; el.textContent = t < s0 + 0.28 ? GL[Math.floor(hash(f, i, 7) * GL.length)] : FINAL[i];
          });
        };
        S.rise(tl, "#md", at(14, 1.4), { y: 24, blur: 10, duration: 0.8 });
        tl.fromTo("#rule", { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: S.ease.swift }, at(14, 1.8));
        S.rise(tl, $$("#fine span"), at(14, 2.0), { y: 10, blur: 4, stagger: 0.06, duration: 0.5 });

        // ── 16 · contact : @kofamali, le curseur clique sur « Suivre », des cœurs montent ──
        S.pop(tl, "#cav", at(15), { from: 0.4, damping: 0.6 });
        S.converge(tl, S.split($("#hdl")), at(15, 0.15), { spread: 40, duration: 0.9, stagger: 0.04 });
        S.rise(tl, "#ctal", at(15, 0.6), { y: 12, blur: 4, duration: 0.5 });
        S.pop(tl, "#fol", at(15, 0.8), { from: 0.6, damping: 0.7, response: 0.3 });
        tl.fromTo("#cur2", { x: 1320, y: 880 }, { x: 830, y: 612, duration: 0.55, ease: S.ease.glide }, at(15, 1.0));
        tl.fromTo(["#fol", "#cur2"], { scale: 1 }, { scale: 0.92, duration: 0.08, ease: "none", ...once }, at(15, 2.2));
        tl.fromTo("#fol", { backgroundColor: "#FF4F1F" }, { backgroundColor: "#F3EBDD", duration: 0.12, ease: "none", ...once }, at(15, 2.36));
        tl.fromTo("#foff", { opacity: 1 }, { opacity: 0, duration: 0.12, ease: "none", ...once }, at(15, 2.36));
        tl.fromTo("#fon", { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "none", ...once }, at(15, 2.36));
        tl.fromTo(["#fol", "#cur2"], { scale: 0.92 }, { scale: 1, duration: 0.3, ease: S.ease.overshoot, ...once }, at(15, 2.36));
        const follows = burst($$(".h2"), at(15, 2.5), 783, 590, 46, 190);

        // un seul pilote pour tout ce qui se dessine image par image (seek-safe)
        S.drive(tl, 0, TOTAL, [hud, morph, truchet, cloud, particles, saas, likes, cube, liquid, decode, follows, S.grain($("#grain"), { fps: 60, seed: 5 })]);
'''
for k, v in (('HUDC', json.dumps(HUD)), ('EASES', json.dumps([e for _, e, _ in EASE_ROWS])), ('SHAPES', json.dumps(SHAPES)),
             ('WALLY', json.dumps(WALL_Y)), ('"CARD"', json.dumps(CARD)), ('KPIV', json.dumps([v for v, _ in KPI])), ('SC', str(SC)), ('TOTAL', str(TOTAL))):
    JS = JS.replace(k, v)
HTML = HTML.replace('%%JS%%', JS).replace('%%MB%%', open(f'{P}/compositions/components/motion-blur.html').read())
open(f'{P}/index.html', 'w').write(HTML)
print('ok', TOTAL)
