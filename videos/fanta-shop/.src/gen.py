# Fanta shop (@fantafofana61) : pub de 31,2 s avec voix off, en deux formats (index.html 9:16 et paysage/index.html 16:9).
# 100 BPM (1 temps = 0,6 s), coupes sur les temps ; chaque plan s'ouvre sur sa phrase de voix off (carte des temps : timing.py).
# Histoire : une maison qui sent bon → le woussoulan « Chez Mme Traoré » se pose sur son plateau tressé → rouge ou doré
# → aussi en flacon spray → savons et foulards → 12 700 abonnés sur TikTok → le numéro de la boutique.
# Rien d'inventé : seuls les mots des étiquettes (Woussoulan Soumadouman, Chez Mme Traoré), de la page TikTok
# (Fanta shop, 77 22 42 50, Fanta savon, 12,7 k abonnés, 68,1 k j'aime) et ce qui se voit sur les photos.
# Signature visuelle : le plateau tressé bleu et paille des vidéos de la boutique. Ses anneaux tournent et se calent,
# et chaque transition est un cercle qui s'ouvre. Les chiffres du numéro défilent sur des bandes masquées
# (chiffres cachés marqués allow-occlusion / allow-overflow). Signature discrète de Mams sur les 2 dernières secondes. Musique : score.py ; voix et mixage : mix.py ; photos : prep.py.
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import TOTAL, CUT, WORD, PAIRS
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 60
INK, WINE, RED, GOLD, CREAM, SAND, BLUE = '#1A0806', '#4A0D08', '#C8261A', '#E8B04B', '#F6EAD7', '#F1E2C6', '#2F6BD0'
NUM, FOLLOWERS, LIKES = '77 22 42 50', 12700, 68100
M_PATH = 'M 6 88 L 22 41 C 25 32, 33 30, 38 38 L 46 52 C 50 59, 56 59, 61 53 L 91 15 C 96 9, 102 11, 102 18 L 104 89'   # logo de Mams (videos/_studio/avatar)

# ── mises en page : vertical (TikTok, statut WhatsApp) et paysage (Facebook, YouTube) ──
FMT = {
    'v': dict(W=1080, H=1920, file='index.html', smoke=(540, 960),
              col=(70, 70), h1=600, hd=150, hdsm=124, bon=300,
              trayA=(50, 1050, 980), glow2=(-60, 620, 1200), jar2=(340, 645, 400, 909), h2=196, title=176, sub=104,
              trayB=(-210, 260, 1500), h3=196, hex=(440, 508), hexes=[(70, 446), (570, 446), (320, 839)], k3=1390,
              fl=(280, 560, 520, 839, 260), h4=196, noz=(440, 600),
              h5=196, pol=(440, 412, 564), pA=(70, 560), pB=(560, 640),
              s6=dict(k=500, n=550, l=800, likes=975, chip=1100), hearts=(130, 950, 560),
              trayC=(-310, 70, 1700), glow6=(90, 380, 900), right=(0, 0), k6=214, brand=262, jar6=(420, 500, 240, 545),
              k7=1124, num=1170, handle=1352, tag=1462, sig='left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1556px;',
              iris=dict(s2=(540, 1100, 1240), s3=(540, 1540, 1650), s6=(540, 960, 1110), s7=(540, 960, 1110))),
    'h': dict(W=1920, H=1080, file='paysage/index.html', smoke=(960, 540),
              col=(100, 1020), h1=200, hd=150, hdsm=104, bon=300,
              trayA=(890, 450, 900), glow2=(840, 100, 1000), jar2=(1186, 205, 308, 700), h2=330, title=160, sub=96,
              trayB=(700, -90, 1300), h3=330, hex=(380, 439), hexes=[(870, 120), (1260, 120), (1065, 459)], k3=650,
              fl=(1150, 180, 420, 677, 210), h4=380, noz=(1282, 228),
              h5=380, pol=(380, 352, 482), pA=(960, 200), pB=(1390, 250),
              s6=dict(k=190, n=240, l=490, likes=655, chip=770), hearts=(140, 1780, 200),
              trayC=(210, -210, 1500), glow6=(120, 140, 800), right=(760, 80), k6=200, brand=245, jar6=(388, 230, 264, 600),
              k7=520, num=566, handle=745, tag=860, sig='right: 56px; top: 1004px;',
              iris=dict(s2=(960, 600, 1150), s3=(1340, 900, 1630), s6=(960, 540, 1110), s7=(960, 540, 1110))),
}

def words(line):
    # un mot = un masque ; un passage <em> garde sa couleur mot par mot
    out = []
    for tok in re.findall(r'<em[^>]*>.*?</em>|[^<\s]+', line):
        m = re.match(r'(<em[^>]*>)(.*?)</em>', tok)
        out += [f'{m.group(1)}{w}</em>' for w in m.group(2).split()] if m else [tok]
    return ' '.join(f'<span class=st-mask><span class=st-word>{w}</span></span>' for w in out)

def chars(text, cls=''):
    return ''.join(' ' if c == ' ' else f'<span class="st-char {cls}">{c}</span>' for c in text)

def tray(uid, size, flat=1.0, n=13, R=480, r0=70, straw='#E8D6B0', stitch='#9C7A48', blue=BLUE, gap='#6E4E2A', rim=2):
    # plateau tressé : anneaux de paille cousus, secteurs bleus en triangles, bord bleu ; chaque anneau tourne seul
    sp = (R - r0) / n; sw = sp * 0.94; rings = ''
    for k in range(n):
        rk = r0 + sp * (k + 0.5)
        g = f'<circle r="{rk:.1f}" fill="none" stroke="{straw}" stroke-width="{sw:.1f}"/>'
        if k >= n - rim: g += f'<circle r="{rk:.1f}" fill="none" stroke="{blue}" stroke-width="{sw:.1f}"/>'
        elif k >= 2:
            wk = 4 + 44 * (1 - (k - 2) / (n - rim - 3))
            if wk > 4.5: g += f'<circle r="{rk:.1f}" fill="none" stroke="{blue}" stroke-width="{sw:.1f}" pathLength="360" stroke-dasharray="{wk:.1f} {60 - wk:.1f}" stroke-dashoffset="{wk / 2:.1f}"/>'
        g += f'<circle r="{rk:.1f}" fill="none" stroke="{stitch}" stroke-width="{sw:.1f}" stroke-dasharray="1.6 6.4" opacity="0.55"/>'
        g += f'<circle r="{rk + sp / 2:.1f}" fill="none" stroke="{gap}" stroke-width="1.6" opacity="0.5"/>'
        rings += f'<g class="rg" id="{uid}r{k}">{g}</g>'
    core = f'<circle r="{r0:.0f}" fill="{straw}"/><circle r="{r0 * 0.6:.0f}" fill="none" stroke="{stitch}" stroke-width="{r0 * 0.8:.0f}" stroke-dasharray="1.6 6" opacity="0.5"/>'
    return (f'<svg class="tray" id="{uid}" viewBox="-500 -500 1000 1000" width="{size}" height="{size}">'
            f'<g transform="scale(1 {flat})"><g id="{uid}s">{core}{rings}</g></g></svg>')

HEART = '<svg viewBox="0 0 24 24"><path d="M12 21s-7.5-4.6-10-9.3C.6 8.6 2.4 4.5 6.2 4.1c2.2-.2 4 1 5.8 3 1.8-2 3.6-3.2 5.8-3 3.8.4 5.6 4.5 4.2 7.6C19.5 16.4 12 21 12 21z"/></svg>'
fmt_n = lambda n: f'{n:,}'.replace(',', ' ')

def build(k):
    f = FMT[k]; W, H = f['W'], f['H']; cl, cr = f['col']
    HEXES = list(zip(['t-rouge', 't-plateau', 't-dore'], f['hexes']))
    digits = ''.join('<span class="gap"></span>' if c == ' ' else
                     f'<span class="dg"><span class="strip" data-layout-allow-overflow data-d="{c}"><b></b>{"".join(f"<b data-layout-allow-occlusion data-layout-allow-overflow>{d % 10}</b>" for d in range(20))}</span></span>' for c in NUM)
    hearts = ''.join(f'<i class="ht" id="ht{i}">{HEART}</i>' for i in range(22))
    rings = ''.join(f'<div class="ring" id="ring-{s}" data-layout-allow-overflow style="left:{x - R}px; top:{y - R}px; width:{2 * R}px; height:{2 * R}px{"; border-color:" + RED if s == "s3" else ""}"></div>'
                    for s, (x, y, R) in f['iris'].items())
    S1 = f'''
          <div class="cam" id="cam1"><img class="bgimg" src="assets/photos/bg-rouge.jpg" alt="" /></div>
          <div class="shade"></div>
          <div class="txt" id="h1"><div class="kick" id="k1">FANTA SHOP</div>
            <div class="hd">{words("Ta maison")}</div><div class="hd">{words("va sentir")}</div>
            <div class="hd" id="bon">{chars("bon.", "gold")}</div></div>'''
    S2 = f'''
          <div class="st-stage">
            <div class="st-layer" id="l2bg"><img class="bgimg" src="assets/photos/bg-dore.jpg" alt="" /><div class="shade warm"></div><div class="glow" id="glow2"></div></div>
            <div class="st-layer" id="l2tray"><div id="wA">{tray("tA", f["trayA"][2], flat=0.34)}</div></div>
            <div class="st-layer" id="l2jar"><div id="jar2" class="jarw"><div class="jsh"></div><img src="assets/photos/pots.png" alt="" />
              <div class="jsheen st-sheen-host"><i class="st-sheen" id="sh2"></i></div></div></div>
            <div class="st-layer" id="l2txt"><div class="txt col" id="h2"><div class="title" id="wou">{chars("Woussoulan")}</div>
              <div class="sub" id="sou">{chars("Soumadouman")}</div><div class="kick" id="k2">CHEZ MME TRAORÉ</div></div></div>
          </div>'''
    S3 = f'''
          <div class="cam" id="cam3">
            <div id="wB">{tray("tB", f["trayB"][2], straw="#EAD9B9", stitch="#C9A878", blue="#D9583F", gap="#C9A878", rim=1)}</div>
            <div class="txt dark col" id="h3"><div class="hd sm">{words("Rouge ou doré,")}</div><div class="hd sm">{words("à toi de <em>choisir.</em>")}</div>
              <div class="kick dark" id="k3">WOUSSOULAN · SOUMADOUMAN</div></div>
            {"".join(f'<div class="hexw" id="hx{i}" style="left:{x}px; top:{y}px"><div class="hex"><div class="hexin"><img src="assets/photos/{p}.jpg" alt="" /></div></div></div>' for i, (p, (x, y)) in enumerate(HEXES))}
          </div>'''
    S4 = f'''
          <div class="cam" id="cam4"><img class="bgimg" src="assets/photos/bg-rouge.jpg" alt="" /></div>
          <div class="shade red"></div>
          <div id="fl"><div id="flin"><img src="assets/photos/flacon.jpg" alt="" /></div></div>
          <canvas id="mist" width="{W}" height="{H}"></canvas>
          <div class="txt col" id="h4"><div class="hd sm">{words("Aussi en")}</div><div class="hd sm">{words("<em>flacon spray.</em>")}</div></div>'''
    S5 = f'''
          <div class="cam" id="cam5">
            <div class="txt dark col" id="h5"><div class="hd sm">{words("Et ce n’est")}</div><div class="hd sm">{words("pas <em>tout.</em>")}</div></div>
            <div class="pol" id="pA"><div class="pimg"><img src="assets/photos/savon.jpg" alt="" /></div><div class="pcap" id="cA">Savons</div></div>
            <div class="pol" id="pB"><div class="pimg"><img src="assets/photos/foulards.jpg" alt="" /></div><div class="pcap" id="cB">Foulards</div></div>
          </div>'''
    S6 = f'''
          <div class="cam" id="cam6"><img class="bgimg" src="assets/photos/bg-dore.jpg" alt="" /></div>
          <div class="shade"></div><div class="glow" id="glow6b"></div>
          <div id="hearts">{hearts}</div>
          <div class="kick ctr" id="k6b">SUR TIKTOK</div>
          <div id="cnt" class="ctr">{fmt_n(FOLLOWERS)}</div>
          <div id="cntl" class="ctr">{chars("abonnés", "gold")}</div>
          <div id="likes" class="ctr"><i class="hi">{HEART}</i>{fmt_n(LIKES)} j’aime</div>
          <div id="chip6" class="ctr">@fantafofana61</div>'''
    S7 = f'''
          <div class="cam" id="cam7"><div id="wC">{tray("tC", f["trayC"][2], straw="#F3C76E", stitch="#7A1A0E", blue="#F6EAD7", gap="#7A1A0E", rim=1)}</div><div class="glow" id="glow6"></div></div>
          <div id="jar6" class="jarw"><div class="jsh"></div><img src="assets/photos/pots.png" alt="" /></div>
          <div class="rc kick" id="k6">WOUSSOULAN · SAVONS · FOULARDS</div>
          <div class="rc st-sheen-host" id="brand">{chars("Fanta")} {chars("shop", "gold")}<i class="st-sheen" id="sh7"></i></div>
          <div class="rc kick" id="k7">COMMANDE AU +223</div>
          <div id="num" class="st-sheen-host">{digits}<i class="st-sheen" id="sh6"></i></div>
          <div id="handle">@fantafofana61</div>
          <div class="rc" id="tag7">{words("Ça sent bon <em>chez toi !</em>")}</div>
          <div id="sig"><svg viewBox="-14 -14 140 120"><path d="{M_PATH}" pathLength="100"/></svg><span>MOTION DESIGN · <b>@kofamali</b></span></div>'''
    x2, y2, w2, h2 = f['jar2']; xf, yf, wf, hf, rf = f['fl']; pw, piw, pih = f['pol']; hw, hh = f['hex']
    x6, y6, w6, h6 = f['jar6']; rl, rr = f['right']; s6 = f['s6']
    css = f'''
      @font-face {{ font-family: "Instrument Serif"; font-style: normal; src: url("assets/fonts/instrument-serif-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/instrument-serif-latin-400-italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; color: {CREAM}; font-family: "Montserrat", sans-serif; }}
      .sc {{ position: absolute; inset: 0; visibility: hidden; overflow: hidden; }}
      .cam {{ position: absolute; inset: 0; transform-origin: {W // 2}px {H * 0.47:.0f}px; }}
      .bgimg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
      .shade {{ position: absolute; inset: 0; background: radial-gradient(ellipse 80% 60% at 50% 45%, rgba(26,8,6,0.35), rgba(26,8,6,0.88) 100%); }}
      .shade.warm {{ background: radial-gradient(ellipse 70% 50% at {(x2 + w2 / 2) / W * 100:.0f}% 62%, rgba(74,13,8,0.25), rgba(26,8,6,0.9) 100%); }}
      .shade.red {{ background: radial-gradient(ellipse 80% 60% at 50% 50%, rgba(140,24,14,0.55), rgba(26,8,6,0.92) 100%); }}
      .glow {{ position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(232,176,75,0.42), rgba(232,176,75,0.12) 45%, rgba(232,176,75,0) 70%); }}
      /* textes */
      .txt {{ position: absolute; left: 0; right: 0; text-align: center; }}
      .txt.col {{ left: {cl}px; right: {cr}px; }}
      .ctr {{ position: absolute; left: 0; right: 0; text-align: center; white-space: nowrap; }}
      .rc {{ position: absolute; left: {rl}px; right: {rr}px; text-align: center; white-space: nowrap; }}
      .kick {{ font: 600 26px "Montserrat"; letter-spacing: 0.32em; color: {GOLD}; white-space: nowrap; }}
      .kick.dark {{ color: {RED}; }}
      .hd {{ font: 400 {f["hd"]}px/1.02 "Instrument Serif"; letter-spacing: -0.015em; color: {CREAM}; white-space: nowrap; text-shadow: 0 6px 40px rgba(0,0,0,0.45); }}
      .hd.sm {{ font-size: {f["hdsm"]}px; }}
      .hd em, .gold {{ font-style: italic; color: {GOLD}; }}
      .dark .hd {{ color: {INK}; text-shadow: none; }} .dark .hd em {{ color: {RED}; }}
      #h1 {{ top: {f["h1"]}px; }} #k1 {{ margin-bottom: 30px; }}
      #bon {{ font-size: {f["bon"]}px; line-height: 0.95; }}
      #bon .st-char {{ text-shadow: 0 0 2px rgba(255,255,255,0.3), 0 0 26px rgba(232,176,75,0.55), 0 0 80px rgba(232,176,75,0.35); }}
      /* le pot sur son plateau */
      #glow2 {{ left: {f["glow2"][0]}px; top: {f["glow2"][1]}px; width: {f["glow2"][2]}px; height: {f["glow2"][2]}px; }}
      #wA {{ position: absolute; left: {f["trayA"][0]}px; top: {f["trayA"][1]}px; }}
      .jarw {{ position: absolute; }}
      .jarw img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; filter: drop-shadow(0 0 1px rgba(255,220,170,0.5)); }}
      .jsh {{ position: absolute; left: -20%; right: -20%; bottom: -5%; height: 14%; border-radius: 50%; background: radial-gradient(ellipse, rgba(20,6,4,0.7), rgba(20,6,4,0) 70%); }}
      #jar2 {{ left: {x2}px; top: {y2}px; width: {w2}px; height: {h2}px; }}
      .jsheen {{ position: absolute; inset: 0; -webkit-mask-image: url("assets/photos/pots.png"); mask-image: url("assets/photos/pots.png"); -webkit-mask-size: 100% 100%; mask-size: 100% 100%; }}
      #h2 {{ top: {f["h2"]}px; }}
      .title {{ font: 400 {f["title"]}px/1 "Instrument Serif"; color: {CREAM}; white-space: nowrap; text-shadow: 0 6px 40px rgba(0,0,0,0.5); }}
      .sub {{ font: italic 400 {f["sub"]}px/1.05 "Instrument Serif"; color: {GOLD}; white-space: nowrap; margin-top: 2px; }}
      #k2 {{ margin-top: 18px; color: {CREAM}; opacity: 0.85; }}
      /* la gamme */
      #s3, #s5 {{ background: radial-gradient(ellipse 90% 70% at 50% 45%, #FBF3E4, {SAND} 70%, #E6D2AE 100%); }}
      #wB {{ position: absolute; left: {f["trayB"][0]}px; top: {f["trayB"][1]}px; opacity: 0.3; }}
      #h3 {{ top: {f["h3"]}px; }}
      #k3 {{ {"position: absolute; left: 0; right: 0; top: " + str(f["k3"] - f["h3"]) + "px;" if k == "v" else "margin-top: 34px;"} }}
      .hexw {{ position: absolute; width: {hw}px; height: {hh}px; filter: drop-shadow(0 4px 6px rgba(74,13,8,0.25)) drop-shadow(0 22px 34px rgba(74,13,8,0.3)); }}
      .hex {{ position: absolute; inset: 0; clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); background: linear-gradient(160deg, #F6D58A, {GOLD} 45%, #A8742A); }}
      .hexin {{ position: absolute; inset: 10px; clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); overflow: hidden; }}
      .hexin img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      /* le flacon */
      #fl {{ position: absolute; left: {xf}px; top: {yf}px; width: {wf}px; height: {hf}px; padding: 10px; border-radius: {rf}px {rf}px 36px 36px;
             background: linear-gradient(160deg, #F6D58A, {GOLD} 45%, #A8742A); box-shadow: 0 3px 6px rgba(0,0,0,0.3), 0 24px 50px rgba(0,0,0,0.45), 0 70px 140px rgba(0,0,0,0.5); }}
      #flin {{ position: relative; width: 100%; height: 100%; border-radius: {rf - 10}px {rf - 10}px 28px 28px; overflow: hidden; }}
      #flin img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      #mist {{ position: absolute; left: 0; top: 0; opacity: 0.5; mix-blend-mode: screen; }}
      #h4 {{ top: {f["h4"]}px; }}
      /* la boutique */
      #h5 {{ top: {f["h5"]}px; }}
      .pol {{ position: absolute; width: {pw}px; padding: 14px 14px 0; background: #FCF7EE; box-shadow: 0 2px 4px rgba(74,13,8,0.2), 0 18px 36px rgba(74,13,8,0.25), 0 50px 90px rgba(74,13,8,0.25); }}
      .pimg {{ position: relative; width: {piw}px; height: {pih}px; overflow: hidden; }}
      .pimg img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      .pcap {{ height: {96 if k == "v" else 86}px; display: flex; align-items: center; justify-content: center; font: italic 400 {66 if k == "v" else 60}px "Instrument Serif"; color: {RED}; }}
      #pA {{ left: {f["pA"][0]}px; top: {f["pA"][1]}px; }} #pB {{ left: {f["pB"][0]}px; top: {f["pB"][1]}px; }}
      /* les abonnés */
      #s6 {{ background: {INK}; }}
      #s6 .bgimg {{ opacity: 0.6; }}
      #glow6b {{ left: {W / 2 - 600:.0f}px; top: {s6["n"] - 380}px; width: 1200px; height: 1200px; opacity: 0.8; }}
      #k6b {{ top: {s6["k"]}px; color: {CREAM}; opacity: 0.9; }}
      #cnt {{ top: {s6["n"]}px; font: 600 230px/1 "Montserrat"; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; color: {CREAM}; text-shadow: 0 8px 50px rgba(0,0,0,0.45); }}
      #cntl {{ top: {s6["l"]}px; font: 400 128px/1 "Instrument Serif"; }}
      #likes {{ top: {s6["likes"]}px; font: 600 56px/1 "Montserrat"; color: {CREAM}; display: flex; align-items: center; justify-content: center; gap: 18px; }}
      .hi svg {{ width: 54px; height: 54px; fill: #FF3B5C; display: block; filter: drop-shadow(0 0 12px rgba(255,59,92,0.6)); }}
      #chip6 {{ top: {s6["chip"]}px; left: 0; right: 0; margin: 0 auto; width: fit-content; padding: 16px 40px; border-radius: 50px; border: 2.5px solid {GOLD}; font: 600 40px "Montserrat"; color: {GOLD}; background: rgba(26,8,6,0.3); }}
      #hearts {{ position: absolute; inset: 0; }}
      .ht {{ position: absolute; left: 0; top: 0; width: 64px; height: 64px; opacity: 0; }}
      .ht svg {{ width: 100%; height: 100%; display: block; }}
      .ht:nth-child(3n) svg {{ fill: #FF3B5C; }} .ht:nth-child(3n+1) svg {{ fill: {GOLD}; }} .ht:nth-child(3n+2) svg {{ fill: #FF8FA3; }}
      /* l'appel */
      #s7 {{ background: radial-gradient(ellipse 85% 65% at 50% 45%, #B3211A, #6A0F0A 62%, #2A0806 100%); }}
      #wC {{ position: absolute; left: {f["trayC"][0]}px; top: {f["trayC"][1]}px; opacity: 0.07; }}
      #glow6 {{ left: {f["glow6"][0]}px; top: {f["glow6"][1]}px; width: {f["glow6"][2]}px; height: {f["glow6"][2]}px; }}
      #k6 {{ top: {f["k6"]}px; font-size: 22px; color: {CREAM}; opacity: 0.9; }}
      #brand {{ top: {f["brand"]}px; padding: 0.04em 0 0.22em; font: 400 178px/1.05 "Instrument Serif"; color: {CREAM}; text-shadow: 0 6px 40px rgba(0,0,0,0.4); }}
      #jar6 {{ left: {x6}px; top: {y6}px; width: {w6}px; height: {h6}px; }}
      #k7 {{ top: {f["k7"]}px; }}
      #num {{ position: absolute; left: {rl}px; right: {rr}px; margin: 0 auto; width: fit-content; top: {f["num"]}px; display: flex; font: 600 128px/1 "Montserrat"; color: {CREAM}; white-space: nowrap; padding: 6px 10px; }}
      .dg {{ display: inline-block; width: 0.66em; height: 1em; overflow: hidden; }}
      .strip {{ display: block; }} .strip b {{ display: block; height: 1em; text-align: center; font-weight: 600; }}
      .gap {{ display: inline-block; width: 0.3em; }}
      #handle {{ position: absolute; left: {rl}px; right: {rr}px; margin: 0 auto; width: fit-content; top: {f["handle"]}px; padding: 20px 46px; border-radius: 60px; border: 2.5px solid {GOLD};
                 font: 600 44px "Montserrat"; color: {GOLD}; white-space: nowrap; background: rgba(26,8,6,0.25); }}
      #tag7 {{ top: {f["tag"]}px; font: 400 64px/1.1 "Instrument Serif"; color: {CREAM}; }}
      #tag7 em {{ font-style: italic; color: {GOLD}; }}
      /* signature de Mams : le M d'un seul trait se dessine, puis « Motion design · @kofamali » */
      #sig {{ position: absolute; {f["sig"]} display: flex; align-items: center; gap: 12px; font: 500 19px "Plex Mono"; letter-spacing: 0.14em; color: {CREAM}; white-space: nowrap; }}
      #sig svg {{ width: 33px; height: 28px; overflow: visible; opacity: 0; }}
      #sig path {{ fill: none; stroke: #FF4F1F; stroke-width: 15; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 100 100; stroke-dashoffset: 100; }}
      #sig span {{ color: rgba(246,234,215,0.75); }} #sig b {{ font-weight: 500; letter-spacing: 0.04em; color: {CREAM}; }}
      /* transitions et finitions */
      .ring {{ position: absolute; opacity: 0; border-radius: 50%; border: 8px solid {GOLD}; pointer-events: none; }}
      #smoke {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0.5; mix-blend-mode: screen; pointer-events: none; }}'''
    cfg = dict(W=W, H=H, SW=f['smoke'][0], SH=f['smoke'][1], iris=f['iris'], noz=f['noz'], hearts=f['hearts'], cut=CUT, word={w.replace('-', '_'): t for w, t in WORD.items()}, pairs=PAIRS,
               followers=FOLLOWERS)
    html = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>{css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div class="sc" id="s1">{S1}
        </div>
        <div class="sc" id="s2">{S2}
        </div>
        <div class="sc" id="s3">{S3}
        </div>
        <div class="sc" id="s4">{S4}
        </div>
        <div class="sc" id="s5">{S5}
        </div>
        <div class="sc" id="s6">{S6}
        </div>
        <div class="sc" id="s7">{S7}
        </div>
        {rings}
        <canvas id="smoke" width="{f["smoke"][0]}" height="{f["smoke"][1]}"></canvas>
        <div class="st-vignette"></div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.07"></canvas>
      </div>
      <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }}), cl = (x) => Math.min(1, Math.max(0, x)), once = {{ immediateRender: false }};
        const TOTAL = {TOTAL}, F = {json.dumps(cfg)}, C = F.cut, Wd = F.word;
%%JS%%
        tl.to({{}}, {{ duration: TOTAL }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
  </body>
</html>
'''
    return html.replace('%%JS%%', JS)

JS = r'''
        // ── plans : chaque scène est visible pendant sa transition d'entrée et de sortie ──
        [["#s1", 0, C.s2 + 0.4], ["#s2", C.s2 - 0.25, C.s3 + 0.05], ["#s3", C.s3 - 0.5, C.s4 + 0.35], ["#s4", C.s4 - 0.3, C.s5 + 0.05],
         ["#s5", C.s5 - 0.45, C.s6 + 0.05], ["#s6", C.s6 - 0.5, C.s7 + 0.05], ["#s7", C.s7 - 0.5, TOTAL]].forEach(([id, a, b]) => {
          tl.set(id, { visibility: "visible" }, a); if (b < TOTAL) tl.set(id, { visibility: "hidden" }, b);
        });
        // transition « plateau » : un cercle s'ouvre depuis un centre, un anneau de couleur court sur son bord
        const iris = (sid, at, d) => {
          const [x, y, R] = F.iris[sid], scene = "#" + sid, ring = "#ring-" + sid;
          tl.fromTo(scene, { clipPath: `circle(0px at ${x}px ${y}px)` }, { clipPath: `circle(${R}px at ${x}px ${y}px)`, duration: d, ease: S.ease.swift }, at);
          tl.set(ring, { opacity: 1 }, at);
          tl.fromTo(ring, { scale: 0 }, { scale: 1, duration: d, ease: S.ease.swift }, at);
          tl.fromTo(ring, { opacity: 1 }, { opacity: 0, duration: d * 0.5, ease: S.ease.accel, ...once }, at + d * 0.5);
          tl.set(scene, { clipPath: "none" }, at + d);
        };
        const line = (sel, at, o = {}) => S.maskUp(tl, $$(sel + " .st-word"), at, Object.assign({ duration: 0.7 }, o));

        // ── 1. l'accroche : « Tu veux que ta maison sente bon ? » ──
        tl.fromTo("#s1", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: S.ease.silk }, 0);
        tl.fromTo("#cam1", { scale: 1.14 }, { scale: 1.0, duration: C.s2 + 0.4, ease: S.ease.glide }, 0);
        S.rise(tl, "#k1", 0.15, { y: 14, blur: 6, duration: 0.6 });
        line("#h1 .hd:nth-child(2)", 0.45);
        line("#h1 .hd:nth-child(3)", 0.9);
        S.converge(tl, $$("#bon .st-char"), Wd.bon - 0.2, { spread: 70, duration: 0.9, stagger: 0.05 });
        S.leave(tl, ["#k1", ...$$("#h1 .hd")], C.s2 - 0.5, { y: -40, blur: 10, duration: 0.4, stagger: 0.04 });

        // ── 2. le pot sur son plateau : « Découvre le woussoulan Soumadouman, de chez Madame Traoré. » ──
        iris("s2", C.s2 - 0.25, 0.5);
        S.camera(tl, [{ el: $("#l2bg"), depth: 0.35 }, { el: $("#l2tray"), depth: 0.8 }, { el: $("#l2jar"), depth: 1 }, { el: $("#l2txt"), depth: 1.15, blur: false }],
          { start: C.s2 - 0.25, end: C.s3, keys: [{ t: C.s2 - 0.25, s: 1.0, y: 0 }, { t: C.s3, s: 1.07, y: -24 }], drift: { x: 4, y: 3, r: 0.1, period: 8 } });
        const js = S.spring({ response: 0.55, damping: 0.78 });
        tl.fromTo("#jar2", { y: -1250, rotation: -6 }, { y: 0, rotation: 0, duration: js.duration, ease: js.ease }, C.s2 - 0.1);
        tl.fromTo("#jar2 .jsh", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.5, ease: S.ease.silk }, C.s2);
        tl.fromTo("#glow2", { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 1.2, ease: S.ease.silk }, C.s2);
        S.converge(tl, $$("#wou .st-char"), Wd.woussoulan - 0.2, { spread: 34, duration: 0.9, stagger: 0.035 });
        S.rise(tl, $$("#sou .st-char"), Wd.soumadouman - 0.1, { y: 30, blur: 8, duration: 0.8, stagger: 0.03 });
        S.rise(tl, "#k2", Wd.traore - 0.6, { y: 12, blur: 6, duration: 0.6 });
        S.life(tl, $("#jar2 img"), C.s2 + 1.2, C.s3 + 0.1, { y: 5, x: 2, rotate: 0.4, period: 4, seed: 5 });
        S.sweep(tl, "#sh2", Wd.traore + 0.3, { duration: 1.3 });
        S.leave(tl, ["#wou", "#sou", "#k2"], C.s3 - 0.75, { y: -30, blur: 8, duration: 0.3, stagger: 0.04 });

        // ── 3. « Rouge ou doré ? À toi de choisir ! » : le crème s'ouvre depuis le plateau, une tuile par mot ──
        iris("s3", C.s3 - 0.5, 0.5);
        tl.fromTo("#cam3", { scale: 1.0 }, { scale: 1.05, duration: C.s4 - C.s3 + 0.2, ease: S.ease.glide }, C.s3 - 0.3);
        line("#h3 .hd:nth-child(1)", Wd.rouge - 0.1);
        line("#h3 .hd:nth-child(2)", Wd.choisir - 0.45);
        const hs = S.spring({ response: 0.5, damping: 0.74 });
        [[0, Wd.rouge - 0.1], [2, Wd.dore - 0.08], [1, Wd.dore + 0.52]].forEach(([i, t]) => {
          tl.fromTo("#hx" + i, { opacity: 0, scale: 0.55, rotation: i === 1 ? 10 : -10, y: 60 }, { opacity: 1, scale: 1, rotation: 0, y: 0, duration: hs.duration, ease: hs.ease }, t);
          tl.fromTo("#hx" + i + " img", { scale: 1.2 }, { scale: 1.0, duration: C.s4 + 0.35 - t, ease: S.ease.glide }, t);
        });
        S.life(tl, $$(".hexw"), Wd.choisir, C.s4 + 0.4, { y: 7, x: 3, rotate: 0.5, period: 4.5, seed: 11 });
        S.rise(tl, "#k3", Wd.choisir + 0.4, { y: 12, blur: 6, duration: 0.6 });

        // ── 4. « Il existe aussi en flacon spray. » : traversée, puis un nuage de spray sur le mot ──
        S.pushThrough(tl, "#s3", "#s4", C.s4 - 0.3, { duration: 0.6, outScale: 1.3, inScale: 0.88 });
        tl.fromTo("#cam4", { scale: 1.1 }, { scale: 1.0, duration: C.s5 - C.s4 + 0.3, ease: S.ease.glide }, C.s4 - 0.3);
        const fs = S.spring({ response: 0.6, damping: 0.8 });
        tl.fromTo("#fl", { y: 160, rotation: 3 }, { y: 0, rotation: 0, duration: fs.duration, ease: fs.ease }, C.s4 - 0.15);
        tl.fromTo("#flin img", { scale: 1.12 }, { scale: 1.0, duration: C.s5 - C.s4 + 0.2, ease: S.ease.glide }, C.s4 - 0.2);
        line("#h4 .hd:nth-child(1)", C.s4 + 0.15);
        line("#h4 .hd:nth-child(2)", Wd.flacon - 0.15);
        tl.fromTo("#fl", { scale: 1 }, { scale: 1.025, duration: 0.08, ease: S.ease.swift, immediateRender: false }, Wd.spray);
        tl.fromTo("#fl", { scale: 1.025 }, { scale: 1, duration: 0.5, ease: S.ease.silk, immediateRender: false }, Wd.spray + 0.08);
        S.life(tl, $("#flin"), Wd.spray + 0.2, C.s5 + 0.1, { y: 4, x: 2, rotate: 0.3, period: 4, seed: 4 });

        // ── 5. « Et ce n'est pas tout ! Des savons et des foulards ! » : le crème monte, deux tirages sur les mots ──
        S.wipe(tl, "#s5", C.s5 - 0.45, { dir: "up", duration: 0.45, ease: S.ease.swift });
        tl.set("#s5", { clipPath: "none" }, C.s5);
        tl.fromTo("#cam5", { scale: 1.0, x: 0 }, { scale: 1.05, x: -12, duration: C.s6 - C.s5 + 0.2, ease: S.ease.glide }, C.s5 - 0.1);
        line("#h5 .hd:nth-child(1)", C.s5);
        line("#h5 .hd:nth-child(2)", Wd.tout - 0.3);
        const ps = S.spring({ response: 0.6, damping: 0.78 });
        tl.fromTo("#pA", { y: 1500, rotation: -20 }, { y: 0, rotation: -5, duration: ps.duration, ease: ps.ease }, Wd.savons - 0.2);
        tl.fromTo("#pB", { y: 1500, rotation: 18 }, { y: 0, rotation: 4, duration: ps.duration, ease: ps.ease }, Wd.foulards - 0.2);
        tl.fromTo("#pA img", { scale: 1.15 }, { scale: 1.0, duration: C.s6 - Wd.savons + 0.3, ease: S.ease.glide }, Wd.savons - 0.2);
        tl.fromTo("#pB img", { scale: 1.15 }, { scale: 1.0, duration: C.s6 - Wd.foulards + 0.3, ease: S.ease.glide }, Wd.foulards - 0.2);
        S.rise(tl, "#cA", Wd.savons + 0.15, { y: 14, blur: 6, duration: 0.6 });
        S.rise(tl, "#cB", Wd.foulards + 0.15, { y: 14, blur: 6, duration: 0.6 });
        S.life(tl, $$(".pol .pimg"), Wd.foulards + 0.6, C.s6 + 0.1, { y: 3, x: 2, rotate: 0.25, period: 4, seed: 6 });

        // ── 6. « Déjà plus de 12 000 abonnés nous suivent sur TikTok. » : compteur, cœurs qui montent ──
        iris("s6", C.s6 - 0.5, 0.5);
        tl.fromTo("#cam6", { scale: 1.12 }, { scale: 1.0, duration: C.s7 - C.s6 + 0.5, ease: S.ease.glide }, C.s6 - 0.5);
        tl.fromTo("#glow6b", { opacity: 0, scale: 0.6 }, { opacity: 0.8, scale: 1, duration: 1.2, ease: S.ease.silk }, C.s6);
        S.rise(tl, "#k6b", C.s6 + 0.05, { y: 12, blur: 6, duration: 0.6 });
        S.rise(tl, "#cnt", C.s6 + 0.2, { y: 40, blur: 12, duration: 0.7 });
        S.converge(tl, $$("#cntl .st-char"), Wd.abonnes - 0.25, { spread: 30, duration: 0.8, stagger: 0.04 });
        S.rise(tl, "#likes", Wd.abonnes + 0.5, { y: 20, blur: 8, duration: 0.6 });
        S.pop(tl, "#chip6", Wd.tiktok - 0.15, { from: 0.7, damping: 0.75 });
        S.life(tl, $$("#cnt, #likes"), Wd.abonnes + 1.1, C.s7, { y: 3, x: 1, rotate: 0.1, period: 5, seed: 3 });
        const cnt = $("#cnt"), fmtn = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        const counter = (t) => { if (t < C.s6 - 0.6 || t > C.s7 + 0.1) return; cnt.textContent = fmtn(Math.round(F.followers * S.ease.silk(cl((t - C.s6 - 0.2) / (Wd.douze_mille + 0.5 - C.s6))) / 10) * 10); };
        const HT = $$(".ht"), [hx0, hx1, hy1] = F.hearts, rh = S.rng(44);
        const HP = HT.map((_, i) => ({ b: C.s6 + 0.5 + i * 0.17, x: hx0 + (hx1 - hx0) * rh(), sw: 20 + 40 * rh(), f: 1.5 + 2 * rh(), s: 0.6 + 0.8 * rh(), life: 2.0 + 0.8 * rh(), r: (rh() - 0.5) * 30 }));
        const hearts = (t) => {
          if (t < C.s6 - 0.6 || t > C.s7 + 0.1) return;
          HT.forEach((el, i) => {
            const p = HP[i], u = (t - p.b) / p.life;
            if (u < 0 || u > 1) { el.style.opacity = "0"; return; }
            const y = F.H + 40 - (F.H + 40 - hy1) * S.ease.glide(u), x = p.x + p.sw * Math.sin(p.f * (t - p.b) + i);
            const sc = p.s * Math.min(1, u * 8) * (1 + 0.15 * Math.sin(u * 12));
            el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${(p.r * (1 - u)).toFixed(1)}deg) scale(${sc.toFixed(3)})`;
            el.style.opacity = (Math.min(1, u * 6) * Math.min(1, (1 - u) * 3)).toFixed(3);
          });
        };

        // ── 7. l'appel : « Commande maintenant au 77 22 42 50. Fanta shop, ça sent bon chez toi ! » ──
        iris("s7", C.s7 - 0.5, 0.5);
        tl.fromTo("#cam7", { scale: 1.12 }, { scale: 1.0, duration: TOTAL - C.s7 + 0.5, ease: S.ease.glide }, C.s7 - 0.5);
        tl.fromTo("#glow6", { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 1.4, ease: S.ease.silk }, C.s7);
        const j6 = S.spring({ response: 0.55, damping: 0.8 });
        tl.fromTo("#jar6", { y: -900, rotation: 5 }, { y: 0, rotation: 0, duration: j6.duration, ease: j6.ease }, C.s7 - 0.15);
        tl.fromTo("#jar6 .jsh", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.5, ease: S.ease.silk }, C.s7);
        S.converge(tl, $$("#brand .st-char"), C.s7 + 0.15, { spread: 40, duration: 0.9, stagger: 0.04 });
        S.rise(tl, "#k6", C.s7 + 0.5, { y: 12, blur: 6, duration: 0.6 });
        S.rise(tl, "#k7", Wd.numero - 0.9, { y: 12, blur: 6, duration: 0.6 });
        tl.fromTo("#num", { opacity: 0 }, { opacity: 1, duration: 0.25, ease: S.ease.silk }, Wd.numero - 0.4);
        $$("#num .strip").forEach((s, k) => {
          const d = +s.dataset.d, land = F.pairs[k >> 1] + (k % 2) * 0.1;
          tl.fromTo(s, { y: 0, filter: "blur(4px)" }, { y: -(11 + d) * 128, filter: "blur(0px)", duration: 0.55, ease: S.ease.silk }, land - 0.35);   // part d'une case vide
        });
        tl.fromTo("#brand", { scale: 1 }, { scale: 1.05, duration: 0.18, ease: S.ease.swift, immediateRender: false }, Wd.fanta_shop - 0.05);
        tl.fromTo("#brand", { scale: 1.05 }, { scale: 1, duration: 0.6, ease: S.ease.silk, immediateRender: false }, Wd.fanta_shop + 0.13);
        S.sweep(tl, "#sh7", Wd.fanta_shop - 0.05, { duration: 1.1 });
        S.pop(tl, "#handle", Wd.fanta_shop + 0.25, { from: 0.7, damping: 0.75 });
        line("#tag7", Wd.sent_bon - 0.2, { duration: 0.7 });
        S.sweep(tl, "#sh6", 29.9, { duration: 1.1 });
        // signature : le M se dessine quand la voix se tait, le texte suit
        tl.set("#sig svg", { opacity: 1 }, 29.0);
        tl.fromTo("#sig path", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.7, ease: S.ease.glide }, 29.0);
        S.rise(tl, "#sig span", 29.3, { y: 10, blur: 6, duration: 0.6 });
        S.life(tl, $("#jar6 img"), C.s7 + 1.0, TOTAL, { y: 6, x: 2, rotate: 0.5, period: 4, seed: 9 });
        S.life(tl, $$("#brand, #tag7"), Wd.sent_bon + 0.6, TOTAL, { y: 3, x: 1, rotate: 0.1, period: 6, seed: 2 });

        // ── plateaux : chaque anneau part décalé et se cale, puis tout le plateau tourne lentement ──
        const trays = [["tA", C.s2 - 0.1, 1.3], ["tB", C.s3 - 0.4, 1.4], ["tC", C.s7 - 0.4, 1.5]].map(([id, t0, d]) => {
          const rg = [...Array(13)].map((_, k) => $("#" + id + "r" + k)), spin = $("#" + id + "s");
          const off = rg.map((_, k) => (k % 2 ? 1 : -1) * (70 + 23 * k));
          return (t) => {
            const p = S.ease.silk(cl((t - t0) / d));
            rg.forEach((g, k) => g.setAttribute("transform", `rotate(${(off[k] * (1 - p)).toFixed(2)})`));
            spin.setAttribute("transform", `rotate(${((t - t0) * 6).toFixed(2)})`);
          };
        });

        // ── fumée de woussoulan : bouffées douces et rubans d'encens, en demi-résolution (adoucie par l'agrandissement) ──
        const sm = $("#smoke"), sx = sm.getContext("2d"), SW = F.SW, SH = F.SH, r = S.rng(21), k2 = SW / 540;
        const PUFF = [...Array(44)].map(() => ({ x: 0.18 + 0.64 * r(), life: 3.6 + 2.6 * r(), ph: r(), amp: 18 + 40 * r(), f: 0.5 + 0.8 * r(), size: 34 + 52 * r(), a: 0.05 + 0.06 * r(), s: r() * 6.28 }));
        const EMB = [...Array(26)].map(() => ({ x: 0.1 + 0.8 * r(), life: 2.2 + 2.2 * r(), ph: r(), sway: 6 + 14 * r(), f: 1 + 2 * r(), s: r() * 6.28 }));
        const WISP = [{ x: 0.40, ph: 0.0, w: 1.0 }, { x: 0.56, ph: 2.1, w: 0.8 }, { x: 0.48, ph: 4.2, w: 0.65 }];
        const AK = [[0, 0], [0.4, 1], [C.s2 - 0.4, 1], [C.s2 + 0.1, 0.55], [C.s3 - 0.9, 0.55], [C.s3 - 0.5, 0], [C.s6 - 0.3, 0], [C.s6 + 0.4, 0.3], [C.s7 - 0.4, 0.3], [C.s7 + 0.4, 0.45], [TOTAL, 0.45]];
        const alphaAt = (t) => { for (let i = 0; i < AK.length - 1; i++) { const [a, va] = AK[i], [b, vb] = AK[i + 1]; if (t <= b) return va + (vb - va) * S.ease.breath(cl((t - a) / (b - a))); } return 0; };
        const smoke = (t) => {
          const A = 2 * alphaAt(t); sx.clearRect(0, 0, SW, SH); if (A < 0.004) return;
          sx.globalCompositeOperation = "lighter";
          PUFF.forEach((p) => {
            const age = ((t / p.life + p.ph) % 1), y = SH * 1.06 - age * SH * 1.0;
            const x = p.x * SW + (Math.sin(t * p.f + p.s) * p.amp * age + 30 * age * age * Math.sin(p.s * 3)) * k2;
            const rad = p.size * (0.5 + 1.8 * age) * Math.sqrt(k2), al = A * p.a * Math.pow(Math.sin(Math.PI * age), 1.4);
            const g = sx.createRadialGradient(x, y, 0, x, y, rad);
            g.addColorStop(0, `rgba(255,232,208,${al.toFixed(4)})`); g.addColorStop(1, "rgba(255,232,208,0)");
            sx.fillStyle = g; sx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
          });
          WISP.forEach((w) => {
            let px = 0, py = 0;
            for (let j = 0; j <= 56; j++) {
              const u = j / 56, y = SH * (1.0 - u * 0.86), amp = 3 + 70 * u * u;
              const x = w.x * SW + amp * Math.sin(u * 8.5 - t * 1.5 + w.ph) + 26 * u * Math.sin(u * 3.1 + t * 0.45 + w.ph);
              if (j > 0) {
                const fade = Math.sin(Math.PI * Math.min(1, u * 1.15)) * A * w.w;
                [[9 + 16 * u, 0.035], [3.5 + 6 * u, 0.06], [1.2 + 1.5 * u, 0.1]].forEach(([lw, al]) => {
                  sx.beginPath(); sx.moveTo(px, py); sx.lineTo(x, y); sx.lineWidth = lw; sx.lineCap = "round";
                  sx.strokeStyle = `rgba(255,238,220,${(al * fade).toFixed(4)})`; sx.stroke();
                });
              }
              px = x; py = y;
            }
          });
          EMB.forEach((e) => {
            const age = ((t / e.life + e.ph) % 1), y = SH * (1.02 - age * 0.9), x = e.x * SW + Math.sin(t * e.f + e.s) * e.sway;
            const al = A * Math.sin(Math.PI * age) * (0.55 + 0.45 * Math.sin(t * 9 + e.s * 5));
            sx.fillStyle = `rgba(255,190,90,${(0.8 * al).toFixed(3)})`; sx.beginPath(); sx.arc(x, y, 1.3, 0, 6.283); sx.fill();
            sx.fillStyle = `rgba(255,150,60,${(0.18 * al).toFixed(3)})`; sx.beginPath(); sx.arc(x, y, 4.5, 0, 6.283); sx.fill();
          });
          sx.globalCompositeOperation = "source-over";
        };

        // ── spray du flacon : fines gouttelettes qui jaillissent de la buse, plus un voile de brume qui s'étale ──
        const mi = $("#mist"), mx = mi.getContext("2d"), r2 = S.rng(33), NOZ = F.noz, T0 = Wd.spray;
        const part = (n, o) => [...Array(n)].map(() => ({ a: (-60 + o.spread * (r2() - 0.5)) * Math.PI / 180, v: o.v[0] + o.v[1] * r2(), s: o.s[0] + o.s[1] * r2(),
          life: o.life[0] + o.life[1] * r2(), d: r2() * 0.1, al: o.al, g: o.g }));
        const DROP = [...part(220, { spread: 26, v: [380, 720], s: [1.2, 3.2], life: [0.5, 1.1], al: 0.9, g: 2.0 }),
                      ...part(14, { spread: 36, v: [240, 320], s: [22, 34], life: [1.2, 1.2], al: 0.05, g: 3.0 })];
        const mist = (t) => {
          mx.clearRect(0, 0, F.W, F.H); const age0 = t - T0; if (age0 < 0 || age0 > 2.6) return;
          mx.globalCompositeOperation = "lighter";
          DROP.forEach((p) => {
            const age = age0 - p.d; if (age < 0 || age > p.life) return;
            const k = 1 - Math.exp(-age * 3.2), dist = p.v * k / 3.2;
            const x = NOZ[0] + Math.cos(p.a) * dist + 30 * age * age, y = NOZ[1] + Math.sin(p.a) * dist - 30 * age + 60 * age * age * (p.s < 5 ? 1 : 0);
            const rad = p.s * (0.35 + p.g * k), al = p.al * Math.pow(1 - age / p.life, 1.5);
            const g = mx.createRadialGradient(x, y, 0, x, y, rad);
            g.addColorStop(0, `rgba(255,242,226,${al.toFixed(4)})`); g.addColorStop(1, "rgba(255,242,226,0)");
            mx.fillStyle = g; mx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
          });
          mx.globalCompositeOperation = "source-over";
        };

        S.drive(tl, 0, TOTAL, [...trays, smoke, mist, counter, hearts, S.grain($("#grain"), { fps: 60, seed: 8 })]);
'''
for k in FMT:
    html = build(k)
    if '/' in FMT[k]['file']:   # second format in its own project folder (one root composition per project); assets = link to ../assets
        d = f'{P}/{os.path.dirname(FMT[k]["file"])}'; os.makedirs(d, exist_ok=True)
        if not os.path.lexists(f'{d}/assets'): os.symlink('../assets', f'{d}/assets')
    open(f'{P}/{FMT[k]["file"]}', 'w').write(html)
    print('ok', FMT[k]['file'], TOTAL)
