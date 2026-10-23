# Farmasi « un rituel pour chaque instant » : pub de 36 s, en 9:16 (index.html) et 16:9 (paysage/index.html).
# Idée : la journée en trois rituels. 07:00 le soin Dr. C. Tuna Age Reversist, 12:00 l'équilibre Nutriplus,
# 00:00 la magie Midnight Ritual, puis la marque : « Beauté. Bien-être. Opportunité. » (la devise du site).
# Signature visuelle : un cadran d'horloge. On change de moment par un balayage d'aiguille qui fait le tour de l'écran ;
# à la fin, le cadran revient autour du logo et ses trois arcs prennent les couleurs des trois moments.
# Rien d'inventé : les textes viennent de fr.farmasi.com (devise, « Pour un quotidien plus équilibré »,
# « Nouveau ! Édition limitée », « La magie commence, à minuit », « Devenez Farmasi Influenceur »).
# Images : photos du catalogue et bannière Midnight Ritual du site (prep.py). Musique : score.py ; temps : timing.py.
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import TOTAL, CUT, WIPE
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 60
NAVY, NAVY2, CORAL, BLUSH, CREAM = '#2D354E', '#1B2033', '#FF5A68', '#F6C1C4', '#FBF6F1'
ROSE, PLUM, MAUVE, GOLD, LAV = '#8A4F3C', '#3E2F4D', '#8E6F98', '#E2C17E', '#CDB7DB'
AR = {'serum': 128 / 583, 'contour': 204 / 645, 'tonique': 156 / 609, 'masque': 553 / 405, 'serenity': 634 / 585, 'restore': 457 / 488, 'aloe': 285 / 614, 'delish': 408 / 612}
WORDMARK = re.findall(r'<path d="([^"]+)"', open(f'{P}/assets/src/logo-text.svg').read())   # FARMASİ, 198 × 32
M_PATH = 'M 6 88 L 22 41 C 25 32, 33 30, 38 38 L 46 52 C 50 59, 56 59, 61 53 L 91 15 C 96 9, 102 11, 102 18 L 104 89'

# ── mises en page. Produits : (nom, centre x, bas, hauteur, rotation, profondeur) ──
FMT = {
    'v': dict(W=1080, H=1920, file='index.html',
              dial0=(540, 860, 360), dial4=(540, 780, 340), wipe=(540, 900),
              p1=[('tonique', 330, 1560, 600, 0, 1), ('contour', 752, 1560, 560, 0, 1), ('serum', 540, 1592, 700, 0, 1), ('masque', 560, 1745, 300, 0, 1)],
              floor=1560,
              p2=[('restore', 290, 1060, 360, 7, 0.9), ('aloe', 805, 1215, 540, 8, 0.95), ('delish', 255, 1525, 440, -9, 0.92), ('serenity', 600, 1575, 450, -5, 1)],
              glints=[(867, 890), (970, 726), (615, 1750), (96, 1342), (600, 964)],
              css='''
      #wm0 { left: 390px; top: 214px; width: 300px; }
      #h0 { left: 60px; right: 60px; top: 1270px; text-align: center; }
      .tblk { left: 60px; right: 60px; text-align: center; }
      #t1 { top: 196px; } #t2 { top: 196px; } #t3 { top: 176px; }
      .time { justify-content: center; }
      #k3 { margin-top: 6px; }
      #shade3 { background: linear-gradient(rgba(2,16,12,0.9) 0%, rgba(2,16,12,0.72) 26%, rgba(2,16,12,0) 44%), radial-gradient(ellipse 90% 60% at 50% 70%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.45) 100%); }
      #sun1 { left: 140px; top: 650px; width: 800px; height: 800px; }
      #sun2 { left: 560px; top: 260px; width: 560px; height: 560px; }
      #fin { left: 60px; right: 60px; top: 1186px; text-align: center; }
      #sym4 { left: 425px; top: 636px; width: 230px; }
      #wm4 { left: 330px; top: 816px; width: 420px; }
      #url { margin: 34px auto 0; }
      #sig { left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1556px; }'''),
    'h': dict(W=1920, H=1080, file='paysage/index.html',
              dial0=(620, 540, 330), dial4=(620, 540, 330), wipe=(620, 540),
              p1=[('tonique', 1095, 905, 520, 0, 1), ('contour', 1495, 905, 480, 0, 1), ('serum', 1290, 930, 610, 0, 1), ('masque', 1300, 1062, 250, 0, 1)],
              floor=905,
              p2=[('restore', 1040, 470, 300, 7, 0.9), ('aloe', 1640, 600, 470, 8, 0.95), ('delish', 1050, 980, 380, -9, 0.92), ('serenity', 1380, 990, 420, -5, 1)],
              glints=[(1278, 500), (1336, 409), (1136, 984), (844, 755), (1127, 542)],
              css='''
      #wm0 { left: 1270px; top: 330px; width: 300px; }
      #h0 { left: 1040px; width: 760px; top: 420px; text-align: center; }
      .tblk { left: 120px; width: 780px; text-align: left; }
      #t1 { top: 250px; } #t2 { top: 250px; } #t3 { top: 230px; }
      .time { justify-content: flex-start; }
      #k3 { margin-top: 6px; }
      #shade3 { background: linear-gradient(90deg, rgba(2,16,12,0.88) 0%, rgba(2,16,12,0.6) 34%, rgba(2,16,12,0) 52%), radial-gradient(ellipse 80% 80% at 65% 55%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.45) 100%); }
      #sun1 { left: 900px; top: 180px; width: 760px; height: 760px; }
      #sun2 { left: 1380px; top: 60px; width: 480px; height: 480px; }
      #fin { left: 1040px; width: 760px; top: 380px; text-align: center; }
      #sym4 { left: 515px; top: 404px; width: 210px; }
      #wm4 { left: 440px; top: 580px; width: 360px; }
      #url { margin: 34px auto 0; }
      #sig { right: 56px; top: 1004px; }
      .trio { font-size: 56px; gap: 24px; }
      #fin { top: 440px; }
      #br3 { font-size: 104px; }'''),
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
def wordmark(id_, color):
    return f'<svg class="wm" id="{id_}" viewBox="0 0 198 32">' + ''.join(f'<path d="{d}" fill="{color}"/>' for d in WORDMARK) + '</svg>'
def dial(id_, r, ticks=True, hands=False, arcs=False):
    s = f'<svg class="dial" id="{id_}" viewBox="{-r - 20} {-r - 20} {2 * r + 40} {2 * r + 40}" width="{2 * r + 40}" height="{2 * r + 40}">'
    s += f'<circle class="ring" r="{r}" pathLength="100"/>'
    if ticks:
        for k in range(60):
            big = k % 5 == 0; a = k * 6
            s += f'<line class="tk{" big" if big else ""}" x1="0" y1="{-r + 10}" x2="0" y2="{-r + (34 if big else 20)}" transform="rotate({a})"/>'
    if arcs:
        for k, c in enumerate((BLUSH, LAV, GOLD)):
            s += f'<circle class="arc" id="{id_}a{k}" r="{r}" pathLength="360" stroke="{c}" transform="rotate({-90 + 120 * k + 2})"/>'
    if hands:
        s += f'<line class="hand hh" id="{id_}h" x1="0" y1="12" x2="0" y2="{-r * 0.5:.0f}"/><line class="hand mh" id="{id_}m" x1="0" y1="18" x2="0" y2="{-r * 0.8:.0f}"/><circle class="pivot" r="9"/>'
    return s + '</svg>'
def mini(id_, hour):
    a = (hour % 12) * 30
    return (f'<svg class="mini" viewBox="-50 -50 100 100"><circle r="44"/><line x1="0" y1="6" x2="0" y2="-24" transform="rotate({a})"/>'
            f'<line x1="0" y1="8" x2="0" y2="-36"/><circle class="pv" r="4"/></svg>')
def prod(name, cx, bottom, h, rot, depth, scene, reflect=False):
    w = h * AR[name]; st = f'left:{cx - w / 2:.0f}px; top:{bottom - h:.0f}px; width:{w:.0f}px; height:{h:.0f}px'
    mk = f'-webkit-mask-image:url(assets/img/{name}.png); mask-image:url(assets/img/{name}.png)'
    r = f'<img class="refl" src="assets/img/{name}.png" alt="" />' if reflect else ''
    return (f'<div class="prod" id="{scene}-{name}" style="{st}" data-rot="{rot}" data-depth="{depth}"><div class="pin">{r}<img src="assets/img/{name}.png" alt="" />'
            f'<div class="shost" style="{mk}"><i class="st-sheen"></i></div></div></div>')

def build(k):
    f = FMT[k]; W, H = f['W'], f['H']
    x0, y0, r0 = f['dial0']; x4, y4, r4 = f['dial4']; xw, yw = f['wipe']
    S0 = f'''
          <div class="bg" id="bg0"></div>
          <div class="dialw" id="dw0" style="left:{x0 - r0 - 20}px; top:{y0 - r0 - 20}px">{dial("d0", r0, ticks=True, hands=True)}</div>
          {wordmark("wm0", CREAM)}
          <div class="txt" id="h0"><div class="hd">{words("Et si chaque instant")}</div><div class="hd">{words("devenait un <em>rituel</em> ?")}</div></div>'''
    S1 = f'''
          <div class="st-stage">
            <div class="st-layer" id="l1bg"><div class="bg" id="bg1"></div><div class="rays" id="rays1"></div><div class="sun" id="sun1"></div>
              <div class="floor" style="top:{f["floor"]}px"></div></div>
            <div class="st-layer" id="l1p">{"".join(prod(*p, "p1", reflect=True) for p in f["p1"])}</div>
            <div class="st-layer" id="l1t"><div class="txt tblk" id="t1"><div class="time" id="tm1">{mini("mn1", 7)}<span>{chars("07:00")}</span></div>
              <div class="lab" id="lb1">LE MATIN · LE SOIN</div><div class="brand" id="br1">{chars("Dr. C. Tuna")}</div><div class="lab sm" id="pn1">AGE REVERSIST</div></div></div>
          </div>'''
    S2 = f'''
          <div class="st-stage">
            <div class="st-layer" id="l2bg"><div class="bg" id="bg2"></div><div class="sun" id="sun2"></div></div>
            <div class="st-layer" id="l2p">{"".join(prod(*p, "p2") for p in f["p2"])}</div>
            <div class="st-layer" id="l2t"><div class="txt tblk" id="t2"><div class="time" id="tm2">{mini("mn2", 12)}<span>{chars("12:00")}</span></div>
              <div class="lab" id="lb2">À MIDI · L’ÉQUILIBRE</div><div class="brand" id="br2">{chars("Nutriplus")}</div>
              <div class="tag" id="tg2">{words("Pour un quotidien plus équilibré.")}</div><div class="level" id="lv2"><i></i></div></div></div>
          </div>'''
    S3 = f'''
          <div class="cam" id="cam3"><img class="plate" src="assets/img/minuit-{"9x16" if k == "v" else "16x9"}.jpg" alt="" /></div>
          <div class="shade" id="shade3"></div>
          <div class="txt tblk" id="t3"><div class="time gold" id="tm3">{mini("mn3", 0)}<span>{chars("00:00")}</span></div>
            <div class="lab" id="lb3">À MINUIT · LA MAGIE</div><div class="lab sm gold" id="k3">NOUVEAU ! ÉDITION LIMITÉE</div>
            <div class="brand it" id="br3">{chars("Midnight Ritual")}</div><div class="tag" id="tg3">{words("La magie commence, à minuit.")}</div></div>'''
    S4 = f'''
          <div class="bg" id="bg4"></div><div class="glow" id="glow4" style="left:{x4 - 520}px; top:{y4 - 520}px"></div>
          <div class="dialw" id="dw4" style="left:{x4 - r4 - 20}px; top:{y4 - r4 - 20}px">{dial("d4", r4, ticks=True, arcs=True)}</div>
          <img class="logo" id="sym4" src="assets/img/symbole.png" alt="" />{wordmark("wm4", CREAM)}
          <div class="txt" id="fin"><div class="trio">{"".join(f'<span class="tw" id="tw{i}"><i style="background:{c}"></i>{w}</span>' for i, (w, c) in enumerate((("Beauté.", BLUSH), ("Bien-être.", LAV), ("Opportunité.", GOLD))))}</div>
            <div class="lab" id="inf">DEVENEZ FARMASI INFLUENCEUR</div><div id="url">fr.farmasi.com</div></div>
          <div id="sig"><svg viewBox="-14 -14 140 120"><path d="{M_PATH}" pathLength="100"/></svg><span>MOTION DESIGN · <b>@kofamali</b></span></div>'''
    css = f'''
      @font-face {{ font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 700; src: url("assets/fonts/inter-latin-700-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: normal; src: url("assets/fonts/instrument-serif-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/instrument-serif-latin-400-italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {NAVY2}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {NAVY2}; color: {NAVY}; font-family: "Inter", sans-serif; }}
      .sc {{ position: absolute; inset: 0; visibility: hidden; overflow: hidden; }}
      .bg, .shade {{ position: absolute; inset: 0; }}
      .cam {{ position: absolute; inset: 0; transform-origin: 50% 55%; }}
      .txt {{ position: absolute; }}
      .wm {{ position: absolute; height: auto; overflow: visible; }}
      .logo {{ position: absolute; height: auto; }}
      /* typographie : Inter (celle du site) pour l'heure et les étiquettes, Instrument Serif pour les noms */
      .hd {{ font: 400 116px/1.04 "Instrument Serif"; color: {CREAM}; white-space: nowrap; letter-spacing: -0.01em; }}
      .hd em {{ font-style: italic; color: {CORAL}; }}
      .time {{ display: flex; align-items: center; gap: 22px; font: 400 128px/1 "Inter"; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; white-space: nowrap; }}
      .mini {{ width: 84px; height: 84px; flex: none; }}
      .mini circle {{ fill: none; stroke: currentColor; stroke-width: 4; }} .mini line {{ stroke: currentColor; stroke-width: 5; stroke-linecap: round; }} .mini .pv {{ fill: currentColor; }}
      .lab {{ font: 600 25px "Inter"; letter-spacing: 0.3em; white-space: nowrap; margin-top: 26px; }}
      .lab.sm {{ font-size: 22px; margin-top: 18px; }}
      .brand {{ font: 400 156px/1.02 "Instrument Serif"; white-space: nowrap; margin-top: 8px; letter-spacing: -0.01em; }}
      .brand.it {{ font-style: italic; }}
      .tag {{ font: 400 42px/1.3 "Inter"; white-space: nowrap; margin-top: 18px; letter-spacing: -0.01em; }}
      /* 07:00 */
      #bg1 {{ background: linear-gradient(180deg, #FBE6DC 0%, #F7D3CB 45%, #F1DCD4 74%, #EADBD5 100%); }}
      #t1 {{ color: {NAVY}; }} #lb1, #pn1 {{ color: {ROSE}; }}
      .sun {{ position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(255,250,240,0.95) 0%, rgba(255,240,226,0.55) 30%, rgba(255,232,214,0) 68%); }}
      .rays {{ position: absolute; left: 50%; top: 52%; width: 3000px; height: 3000px; margin: -1500px 0 0 -1500px; opacity: 0.22;
               background: repeating-conic-gradient(from 0deg, rgba(255,255,255,0.9) 0deg 3deg, rgba(255,255,255,0) 3deg 15deg); -webkit-mask-image: radial-gradient(circle, #000 0%, rgba(0,0,0,0) 60%); mask-image: radial-gradient(circle, #000 0%, rgba(0,0,0,0) 60%); }}
      .floor {{ position: absolute; left: 0; right: 0; bottom: 0; background: linear-gradient(180deg, rgba(222,186,176,0.55), rgba(240,222,214,0.2) 40%, rgba(240,222,214,0)); border-top: 1px solid rgba(255,255,255,0.7); }}
      .prod {{ position: absolute; }}
      .pin {{ position: absolute; inset: 0; }}
      .pin img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; }}
      .pin img:not(.refl) {{ filter: drop-shadow(0 18px 24px rgba(60,40,50,0.22)) drop-shadow(0 4px 6px rgba(60,40,50,0.18)); }}
      .pin .refl {{ top: 100%; transform: scaleY(-1); opacity: 0.2; -webkit-mask-image: linear-gradient(to top, #000 0%, rgba(0,0,0,0) 38%); mask-image: linear-gradient(to top, #000 0%, rgba(0,0,0,0) 38%); }}
      .shost {{ position: absolute; inset: 0; overflow: hidden; -webkit-mask-size: 100% 100%; mask-size: 100% 100%; }}
      .st-sheen {{ background: linear-gradient(105deg, rgba(255,255,255,0) 20%, rgba(255,246,236,0.75) 50%, rgba(255,255,255,0) 80%); }}
      /* 12:00 */
      #bg2 {{ background: linear-gradient(180deg, #F4EDF7 0%, #E6D9EE 42%, #D5C2E2 78%, #CAB3DA 100%); }}
      #t2 {{ color: {PLUM}; }} #lb2 {{ color: {MAUVE}; }}
      .level {{ position: relative; width: 420px; height: 3px; margin: 30px {"auto" if k == "v" else "0"} 0; background: {MAUVE}; border-radius: 2px; transform-origin: 50% 50%; }}
      .level i {{ position: absolute; left: 50%; top: -9px; width: 20px; height: 20px; margin-left: -10px; border-radius: 50%; background: {PLUM}; }}
      /* 00:00 */
      .plate {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #t3 {{ color: {CREAM}; }} .gold, #br3 {{ color: {GOLD}; }} #lb3 {{ color: rgba(251,246,241,0.85); }}
      #tm3 span, #br3 {{ text-shadow: 0 0 2px rgba(255,240,200,0.4), 0 0 30px rgba(226,193,126,0.45), 0 0 90px rgba(226,193,126,0.25); }}
      #tg3 {{ color: rgba(251,246,241,0.92); }}
      /* fin */
      #bg4 {{ background: radial-gradient(ellipse 80% 65% at {x4 / W * 100:.0f}% {y4 / H * 100:.0f}%, #3A4466 0%, {NAVY} 45%, {NAVY2} 100%); }}
      .glow {{ position: absolute; width: 1040px; height: 1040px; border-radius: 50%; background: radial-gradient(circle, rgba(255,90,104,0.22), rgba(255,90,104,0.06) 45%, rgba(255,90,104,0) 70%); }}
      #fin {{ color: {CREAM}; }}
      .trio {{ display: flex; justify-content: center; gap: 30px; font: 400 62px/1.1 "Instrument Serif"; white-space: nowrap; }}
      .tw {{ display: inline-flex; align-items: center; gap: 14px; }} .tw i {{ width: 14px; height: 14px; border-radius: 50%; display: inline-block; }}
      #inf {{ color: {BLUSH}; font-size: 22px; margin-top: 34px; }}
      #url {{ width: fit-content; padding: 20px 46px; border-radius: 60px; background: {CORAL}; color: #fff; font: 600 42px "Inter"; letter-spacing: -0.01em; white-space: nowrap;
              box-shadow: 0 10px 30px rgba(255,90,104,0.35), 0 2px 4px rgba(0,0,0,0.2); }}
      /* cadrans et aiguille */
      .dialw {{ position: absolute; }}
      .dial {{ overflow: visible; display: block; }}
      .dial .ring {{ fill: none; stroke: rgba(251,246,241,0.55); stroke-width: 2.5; stroke-dasharray: 100 100; stroke-dashoffset: 100; }}
      .dial .tk {{ stroke: rgba(251,246,241,0.45); stroke-width: 2; opacity: 0; }} .dial .tk.big {{ stroke: rgba(251,246,241,0.9); stroke-width: 3.5; }}
      .dial .hand {{ stroke: {CREAM}; stroke-linecap: round; }} .dial .hh {{ stroke-width: 9; }} .dial .mh {{ stroke-width: 5; stroke: {CORAL}; }}
      .dial .pivot {{ fill: {CORAL}; }}
      .dial .arc {{ fill: none; stroke-width: 7; stroke-dasharray: 116 360; stroke-dashoffset: 116; }}
      #hand {{ position: absolute; left: {xw - 3}px; top: {yw - 2400}px; width: 6px; height: 2400px; transform-origin: 50% 100%; opacity: 0; pointer-events: none;
               background: linear-gradient(to top, rgba(255,255,255,0.95), rgba(255,240,230,0.85) 40%, rgba(255,255,255,0)); box-shadow: 0 0 18px rgba(255,220,200,0.9), 0 0 50px rgba(255,90,104,0.6); }}
      #fx {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0.5; mix-blend-mode: screen; pointer-events: none; }}
      /* signature de Mams */
      #sig {{ position: absolute; display: flex; align-items: center; gap: 12px; font: 500 19px "Plex Mono"; letter-spacing: 0.14em; white-space: nowrap; }}
      #sig svg {{ width: 33px; height: 28px; overflow: visible; opacity: 0; }}
      #sig path {{ fill: none; stroke: #FF4F1F; stroke-width: 15; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 100 100; stroke-dashoffset: 100; }}
      #sig span {{ color: rgba(251,246,241,0.7); }} #sig b {{ font-weight: 500; letter-spacing: 0.04em; color: {CREAM}; }}
      #bg0 {{ background: radial-gradient(ellipse 85% 60% at {x0 / W * 100:.0f}% {y0 / H * 100:.0f}%, #262C44 0%, {NAVY2} 60%, #0F1220 100%); }}
{f["css"]}'''
    cfg = dict(W=W, H=H, cut=CUT, wipe=WIPE, center=[xw, yw], glints=f['glints'], logo=[f['dial4'][0], f['dial4'][1] - 70])
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
        <div class="sc" id="s0">{S0}
        </div>
        <div class="sc" id="s1">{S1}
        </div>
        <div class="sc" id="s2">{S2}
        </div>
        <div class="sc" id="s3">{S3}
        </div>
        <div class="sc" id="s4">{S4}
        </div>
        <div id="hand" data-layout-allow-overflow></div>
        <canvas id="fx" width="{W // 2}" height="{H // 2}"></canvas>
        <div class="st-vignette"></div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.06"></canvas>
      </div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }}), cl = (x) => Math.min(1, Math.max(0, x)), once = {{ immediateRender: false }};
        const TOTAL = {TOTAL}, F = {json.dumps(cfg)}, C = F.cut, HW = F.wipe / 2;
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
        // ── plans : chaque scène est visible pendant le balayage qui l'ouvre et celui qui la ferme ──
        const ids = ["s0", "s1", "s2", "s3", "s4"];
        ids.forEach((id, i) => {
          const a = i ? C[id] - HW : 0, b = i < 4 ? C[ids[i + 1]] + HW : TOTAL;
          tl.set("#" + id, { visibility: "visible" }, a); if (b < TOTAL) tl.set("#" + id, { visibility: "hidden" }, b);
        });
        const line = (sel, at, o = {}) => S.maskUp(tl, $$(sel + " .st-word"), at, Object.assign({ duration: 0.7 }, o));
        const time = (n, at) => { S.rise(tl, $$("#tm" + n + " .st-char"), at, { y: 40, blur: 10, duration: 0.7, stagger: 0.05 }); S.pop(tl, "#tm" + n + " .mini", at - 0.05, { from: 0.4, damping: 0.7 }); };

        // ── 0. l'intro : le cadran se dessine, la journée défile jusqu'à 7 h ──
        tl.fromTo("#s0", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: S.ease.silk }, 0);
        S.rise(tl, "#wm0", 0.15, { y: 16, blur: 8, duration: 0.8 });
        tl.fromTo("#d0 .ring", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 1.2, ease: S.ease.glide }, 0.25);
        tl.fromTo($$("#d0 .tk"), { opacity: 0 }, { opacity: 1, duration: 0.4, ease: S.ease.swift, stagger: 0.012 }, 0.5);
        tl.fromTo("#dw0", { scale: 0.92, rotation: -8 }, { scale: 1.0, rotation: 0, duration: 3.9, ease: S.ease.glide }, 0);
        line("#h0 .hd:nth-child(1)", 0.4);
        line("#h0 .hd:nth-child(2)", 1.8);
        tl.fromTo("#h0 em", { textShadow: "0 0 0px rgba(255,90,104,0)" }, { textShadow: "0 0 34px rgba(255,90,104,0.7)", duration: 0.5, ease: S.ease.silk }, 3.2);
        S.leave(tl, ["#h0", "#wm0"], C.s1 - 0.7, { y: -20, blur: 8, duration: 0.35, stagger: 0.05 });
        const d0h = $("#d0h"), d0m = $("#d0m");
        const hands0 = (t) => { if (t > C.s1 + 0.5) return; const p = S.ease.glide(cl((t - 0.8) / 2.9)), m = 360 * 7 * p;
          d0m.setAttribute("transform", `rotate(${m.toFixed(2)})`); d0h.setAttribute("transform", `rotate(${(m / 12).toFixed(2)})`); };

        // ── balayage d'horloge : la scène suivante s'ouvre derrière une aiguille qui fait le tour de l'écran ──
        const [cx, cy] = F.center, hand = $("#hand");
        const wipes = ["s1", "s2", "s3", "s4"].map((id) => [$("#" + id), C[id]]);
        const wipe = (t) => {
          let shown = 0, ang = 0;
          wipes.forEach(([el, tc]) => {
            const p = (t - (tc - HW)) / (2 * HW);
            if (p <= 0) { el.style.webkitMaskImage = el.style.maskImage = "linear-gradient(transparent, transparent)"; return; }
            if (p >= 1) { el.style.webkitMaskImage = el.style.maskImage = "none"; return; }
            const a = 360 * S.ease.glide(p); ang = a; shown = Math.sin(Math.PI * p);
            const m = `conic-gradient(from 0deg at ${cx}px ${cy}px, #000 0deg, #000 ${Math.max(0, a - 1.2).toFixed(2)}deg, transparent ${a.toFixed(2)}deg)`;
            el.style.webkitMaskImage = el.style.maskImage = m;
          });
          hand.style.opacity = Math.min(1, shown * 1.6).toFixed(3); hand.style.transform = `rotate(${ang.toFixed(2)}deg)`;
        };

        // ── 1. 07:00 le soin : lever de soleil, les flacons montent sur leur reflet ──
        S.camera(tl, [{ el: $("#l1bg"), depth: 0.4 }, { el: $("#l1p"), depth: 1 }, { el: $("#l1t"), depth: 1.12, blur: false }],
          { start: C.s1 - HW, end: C.s2 + HW, keys: [{ t: C.s1 - HW, s: 1.0, y: 10 }, { t: 8.6, s: 1.04, y: 0 }, { t: C.s2 + HW, s: 1.09, y: -20 }], drift: { x: 4, y: 3, r: 0.08, period: 9 } });
        tl.fromTo("#sun1", { y: 260, scale: 0.8, opacity: 0.4 }, { y: 0, scale: 1, opacity: 1, duration: 4.5, ease: S.ease.silk }, C.s1 - 0.3);
        tl.fromTo("#rays1", { rotation: -8 }, { rotation: 10, duration: 8.4, ease: "none" }, C.s1 - HW);
        const ps = S.spring({ response: 0.6, damping: 0.8 });
        $$("#l1p .prod").forEach((el, i) => {
          const t = C.s1 + 0.3 + i * 0.3;
          tl.fromTo(el, { y: 700, opacity: 0 }, { y: 0, opacity: 1, duration: ps.duration, ease: ps.ease }, t);
        });
        S.life(tl, $$("#l1p .pin"), C.s1 + 1.8, C.s2 + HW, { y: 3, x: 1, rotate: 0.15, period: 5, seed: 7 });
        [6.1, 9.7].forEach((t) => $$("#l1p .st-sheen").forEach((s, i) => S.sweep(tl, s, t + i * 0.08, { duration: 1.3 })));
        time(1, C.s1 + 0.35);
        S.rise(tl, "#lb1", 4.75, { y: 14, blur: 6, duration: 0.6 });
        S.rise(tl, "#pn1", 5.85, { y: 14, blur: 6, duration: 0.6 });
        S.converge(tl, $$("#br1 .st-char"), 6.75, { spread: 26, duration: 0.9, stagger: 0.03 });
        S.leave(tl, ["#t1"], C.s2 - 0.75, { y: -24, blur: 8, duration: 0.35 });

        // ── 2. 12:00 l'équilibre : les produits Nutriplus flottent, la ligne d'équilibre se pose ──
        S.camera(tl, [{ el: $("#l2bg"), depth: 0.4 }, { el: $("#l2p"), depth: 1 }, { el: $("#l2t"), depth: 1.12, blur: false }],
          { start: C.s2 - HW, end: C.s3 + HW, keys: [{ t: C.s2 - HW, s: 1.0, x: 0 }, { t: C.s3 + HW, s: 1.07, x: -14 }], drift: { x: 5, y: 4, r: 0.1, period: 8 } });
        tl.fromTo("#sun2", { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, duration: 2.5, ease: S.ease.silk }, C.s2 - 0.2);
        const fs = S.spring({ response: 0.7, damping: 0.72 });
        $$("#l2p .prod").forEach((el, i) => {
          const t = C.s2 + 0.25 + i * 0.3, rot = +el.dataset.rot;
          tl.fromTo(el, { y: -900, rotation: rot * 3, opacity: 0 }, { y: 0, rotation: rot, opacity: 1, duration: fs.duration, ease: fs.ease }, t);
        });
        S.life(tl, $$("#l2p .pin"), C.s2 + 1.6, C.s3 + HW, { y: 16, x: 6, rotate: 1.6, period: 4.2, seed: 12 });
        S.sweep(tl, $("#p2-serenity .st-sheen"), 15.6, { duration: 1.3 });
        S.sweep(tl, $("#p2-aloe .st-sheen"), 15.75, { duration: 1.3 });
        time(2, C.s2 + 0.35);
        S.rise(tl, "#lb2", 12.45, { y: 14, blur: 6, duration: 0.6 });
        S.converge(tl, $$("#br2 .st-char"), 12.95, { spread: 30, duration: 0.9, stagger: 0.035 });
        line("#tg2", 13.7, { duration: 0.6 });
        const lv = S.spring({ response: 0.9, damping: 0.45 });
        tl.fromTo("#lv2", { scaleX: 0, rotation: 9 }, { scaleX: 1, rotation: 0, duration: lv.duration, ease: lv.ease }, 14.9);
        S.leave(tl, ["#t2"], C.s3 - 0.75, { y: -24, blur: 8, duration: 0.35 });

        // ── 3. 00:00 la magie : cloche, poussière d'or, éclats sur les produits ──
        tl.fromTo("#cam3", { scale: 1.0, y: 0 }, { scale: 1.08, y: -20, duration: C.s4 - C.s3 + 0.7, ease: S.ease.glide }, C.s3 - HW);
        time(3, C.s3 + 0.15);
        tl.fromTo("#tm3", { filter: "brightness(1.8)" }, { filter: "brightness(1)", duration: 1.2, ease: S.ease.silk }, C.s3 + 0.2);
        S.rise(tl, "#lb3", 20.3, { y: 14, blur: 6, duration: 0.6 });
        line("#tg3", 21.35, { duration: 0.7 });
        S.converge(tl, $$("#br3 .st-char"), 22.8, { spread: 34, duration: 1.0, stagger: 0.035 });
        S.rise(tl, "#k3", 23.95, { y: 12, blur: 6, duration: 0.6 });
        S.leave(tl, ["#t3"], C.s4 - 0.75, { y: -24, blur: 8, duration: 0.35 });

        // ── 4. la marque : le cadran revient, ses trois arcs prennent les couleurs des trois moments ──
        tl.fromTo("#glow4", { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 1.6, ease: S.ease.silk }, C.s4);
        tl.fromTo("#d4 .ring", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 1.0, ease: S.ease.glide }, C.s4 + 0.05);
        tl.fromTo($$("#d4 .tk"), { opacity: 0 }, { opacity: 1, duration: 0.3, ease: S.ease.swift, stagger: 0.008 }, C.s4 + 0.2);
        tl.fromTo("#dw4", { rotation: -30, scale: 0.9 }, { rotation: 0, scale: 1, duration: 2.0, ease: S.ease.silk }, C.s4 - 0.2);
        tl.fromTo("#dw4", { rotation: 0 }, { rotation: 6, duration: TOTAL - C.s4 - 1.8, ease: "none", immediateRender: false }, C.s4 + 1.8);
        const ls = S.spring({ response: 0.6, damping: 0.7 });
        tl.fromTo("#sym4", { scale: 0.2, opacity: 0, rotation: -20 }, { scale: 1, opacity: 1, rotation: 0, duration: ls.duration, ease: ls.ease }, 27.85);
        tl.fromTo("#wm4", { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.8, ease: S.ease.silk }, 28.15);
        [29.0, 29.6, 30.3].forEach((t, i) => {
          S.rise(tl, "#tw" + i, t, { y: 26, blur: 8, duration: 0.6 });
          tl.fromTo("#d4a" + i, { strokeDashoffset: 116 }, { strokeDashoffset: 0, duration: 0.7, ease: S.ease.glide }, t - 0.05);
        });
        S.rise(tl, "#url", 31.45, { y: 24, blur: 8, duration: 0.6 });
        S.rise(tl, "#inf", 32.3, { y: 12, blur: 6, duration: 0.6 });
        S.life(tl, $$("#sym4, #url"), 31.0, TOTAL, { y: 3, x: 1, rotate: 0.2, period: 5, seed: 4 });
        tl.set("#sig svg", { opacity: 1 }, 33.4);
        tl.fromTo("#sig path", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.7, ease: S.ease.glide }, 33.4);
        S.rise(tl, "#sig span", 33.7, { y: 10, blur: 6, duration: 0.6 });

        // ── particules : poussière dorée au matin, bulles à midi, or et scintillements à minuit et à la fin ──
        const fx = $("#fx"), g = fx.getContext("2d"), FW = fx.width, FH = fx.height, r = S.rng(17), k2 = FW / 540;
        const DUST = [...Array(60)].map(() => ({ x: r(), y: r(), s: 0.6 + 1.8 * r(), v: 0.012 + 0.03 * r(), ph: r() * 6.28, f: 0.4 + r() }));
        const BUB = [...Array(26)].map(() => ({ x: 0.05 + 0.9 * r(), s: 5 + 18 * r(), v: 0.05 + 0.07 * r(), ph: r(), sw: 10 + 20 * r(), f: 0.6 + r() }));
        const STAR = [...Array(70)].map(() => ({ x: r(), y: r() * 0.95, s: 0.5 + 1.6 * r(), ph: r() * 6.28, f: 1 + 3 * r() }));
        const win = (t, a, b, e = 0.5) => cl((t - a) / e) * cl((b - t) / e);
        const glint = (x, y, s, a) => {   // éclat à quatre branches
          g.save(); g.translate(x, y); g.globalAlpha = a;
          [[s, s * 0.08], [s * 0.08, s]].forEach(([w, h]) => { const gr = g.createRadialGradient(0, 0, 0, 0, 0, Math.max(w, h));
            gr.addColorStop(0, "rgba(255,248,225,1)"); gr.addColorStop(1, "rgba(255,230,170,0)"); g.fillStyle = gr; g.beginPath(); g.ellipse(0, 0, w, h, 0, 0, 6.283); g.fill(); });
          const gr = g.createRadialGradient(0, 0, 0, 0, 0, s * 0.35); gr.addColorStop(0, "rgba(255,240,200,0.9)"); gr.addColorStop(1, "rgba(255,220,150,0)");
          g.fillStyle = gr; g.beginPath(); g.arc(0, 0, s * 0.35, 0, 6.283); g.fill(); g.restore();
        };
        const GL = F.glints.map(([x, y], i) => [22.9 + i * 0.32, x / 2, y / 2]);
        const fxd = (t) => {
          g.clearRect(0, 0, FW, FH); g.globalCompositeOperation = "lighter";
          const a1 = win(t, C.s1 - 0.3, C.s2 + 0.3), a2 = win(t, C.s2 - 0.3, C.s3 + 0.3), a3 = win(t, C.s3 - 0.3, C.s4 + 0.3), a4 = win(t, C.s4, TOTAL + 1);
          if (a1 > 0.01) DUST.forEach((p) => { const y = ((p.y - t * p.v) % 1 + 1) % 1, x = p.x + 0.01 * Math.sin(t * p.f + p.ph);
            g.fillStyle = `rgba(255,236,210,${(0.7 * a1 * (0.5 + 0.5 * Math.sin(t * 2 + p.ph))).toFixed(3)})`; g.beginPath(); g.arc(x * FW, y * FH, p.s * k2, 0, 6.283); g.fill(); });
          if (a2 > 0.01) BUB.forEach((p) => { const u = ((t * p.v + p.ph) % 1), y = FH * (1.05 - 1.15 * u), x = p.x * FW + p.sw * Math.sin(t * p.f + p.ph * 6) * k2, s = p.s * k2 * 0.6;
            const al = a2 * Math.sin(Math.PI * u);
            g.strokeStyle = `rgba(255,255,255,${(0.9 * al).toFixed(3)})`; g.lineWidth = 1.2; g.beginPath(); g.arc(x, y, s, 0, 6.283); g.stroke();
            g.fillStyle = `rgba(255,255,255,${(0.25 * al).toFixed(3)})`; g.beginPath(); g.arc(x - s * 0.35, y - s * 0.35, s * 0.28, 0, 6.283); g.fill(); });
          const a34 = Math.max(a3, 0.6 * a4);
          if (a34 > 0.01) {
            STAR.forEach((p) => { const tw = 0.5 + 0.5 * Math.sin(t * p.f + p.ph); g.fillStyle = `rgba(255,232,180,${(a34 * tw * 0.8).toFixed(3)})`;
              g.beginPath(); g.arc(p.x * FW, p.y * FH, p.s * k2 * (0.6 + 0.6 * tw), 0, 6.283); g.fill(); });
            DUST.forEach((p) => { const y = ((p.y - t * p.v * 1.4) % 1 + 1) % 1; g.fillStyle = `rgba(255,205,120,${(0.8 * a34).toFixed(3)})`;
              g.beginPath(); g.arc((p.x + 0.015 * Math.sin(t * p.f + p.ph)) * FW, y * FH, p.s * k2 * 0.8, 0, 6.283); g.fill(); });
          }
          GL.forEach(([t0, x, y]) => { const u = (t - t0) / 0.9; if (u > 0 && u < 1) glint(x, y, 46 * k2 * Math.sin(Math.PI * u), Math.sin(Math.PI * u)); });
          if (t > 27.7 && t < 29.2) { const u = (t - 27.85) / 1.1; if (u > 0 && u < 1) glint(F.logo[0] / 2, F.logo[1] / 2, 70 * k2 * Math.sin(Math.PI * u), Math.sin(Math.PI * u)); }
          g.globalCompositeOperation = "source-over";
        };

        S.drive(tl, 0, TOTAL, [hands0, wipe, fxd, S.grain($("#grain"), { fps: 60, seed: 8 })]);
'''
for k, f in FMT.items():
    html = build(k)
    if '/' in f['file']:   # second format: its own project folder (one root composition per project), assets = link to ../assets
        d = f'{P}/{os.path.dirname(f["file"])}'; os.makedirs(d, exist_ok=True)
        if not os.path.lexists(f'{d}/assets'): os.symlink('../assets', f'{d}/assets')
    open(f'{P}/{f["file"]}', 'w').write(html)
    print('ok', f['file'], TOTAL)
