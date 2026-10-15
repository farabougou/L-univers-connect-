# KOFA — reel « dev à l'écran » : la vraie photo du bureau de Mohamed (HP Pavilion), l'écran remplacé par VS Code +
# aperçu iPhone 15 Pro Max qui affiche les vraies captures de KOFA. Vertical 1080×1920, 25 i/s, 25 s.
# L'écran est un div 1920×1080 projeté sur la dalle de la photo par une homographie (matrix3d).
import os, re, html, json
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL = 1080, 1920, 25
ORANGE, BLUE, GREEN, INK = '#EB6834', '#2A78D6', '#1BAF7A', '#0E0E10'

# ── screen homography: 1920×1080 screen → photo (photo resized 1500×2000 → 1440×1920) ──
S = 0.96
QUAD = [(-40, -5), (1768, -83), (1535, 923), (195, 937)]  # TL TR BR BL, measured on the original photo
Q = [(x * S, y * S) for x, y in QUAD]
def homog(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]; b += [u, v]
    h = np.linalg.solve(np.array(A, float), np.array(b, float)); return np.append(h, 1).reshape(3, 3)
HM = homog([(0, 0), (1920, 0), (1920, 1080), (0, 1080)], Q)
M3D = 'matrix3d(' + ','.join(f'{v:.9g}' for v in [HM[0, 0], HM[1, 0], 0, HM[2, 0], HM[0, 1], HM[1, 1], 0, HM[2, 1], 0, 0, 1, 0, HM[0, 2], HM[1, 2], 0, HM[2, 2]]) + ')'
def to_photo(x, y):
    u = HM @ np.array([x, y, 1.0]); return float(u[0] / u[2]), float(u[1] / u[2])

# ── screen layout (screen px) ──
PANEL = (48, 700)             # device preview panel x-range
PH_W, PH_H = 420, 910         # phone outer size
PH_X, PH_Y = 48 + (652 - PH_W) // 2, 100
CODE_X = 700
phone_c = to_photo(PH_X + PH_W / 2, PH_Y + PH_H * 0.45)
code_c = to_photo(1180, 470)
wide = (600, 960)
def cam(pt, k, oy=960, ox=540):
    return {'x': round(ox - k * pt[0], 1), 'y': round(oy - k * pt[1], 1), 'scale': k}

# ── code (typed live) ──
HOME = '''import { ScrollView, Text, View } from 'react-native';
import { CategoryChip, SearchBar, RestaurantList } from '../components';
import { colors } from '../theme';

const CATEGORIES = ['Repas', 'Courses', 'Colis', 'Grillades'];

export default function HomeScreen({ navigation }) {
  const { user, city } = useSession(); // Bamako, Mali

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.hello}>Bonjour {user.firstName}</Text>
      <Text style={styles.title}>
        Le goût de Bamako,{'\\n'}
        <Text style={{ color: colors.orange }}>livré chez vous.</Text>
      </Text>
      <SearchBar placeholder="Un plat, un restaurant..." />
      <View style={styles.row}>
        {CATEGORIES.map((c) => (
          <CategoryChip key={c} label={c} onPress={() => navigation.navigate(c)} />
        ))}
      </View>
      <RestaurantList city={city} />
    </ScrollView>
  );
}'''
DIAS = '''import { Screen, CountryFlags, Steps, Step } from '../components';
import { DIASPORA_COUNTRIES } from '../data/countries';

// Commander depuis l'étranger pour un proche à Bamako
export default function DiasporaScreen() {
  return (
    <Screen title="Faites plaisir à votre famille à Bamako">
      <CountryFlags origins={DIASPORA_COUNTRIES} destination="Bamako" />
      <Steps title="Comment ça marche">
        <Step n={1}>Vous remplissez le formulaire</Step>
        <Step n={2}>L'équipe KOFA vous recontacte</Step>
        <Step n={3}>Vous envoyez le montant</Step>
      </Steps>
      <Button color={colors.orange} onPress={sendRequest}>
        Envoyer ma demande
      </Button>
    </Screen>
  );
}'''
KW = r'\b(import|from|export|default|function|const|return|=>)\b'
def hl(line):
    out, i = '', 0
    pat = re.compile(r"(//.*$)|('[^']*'|\"[^\"]*\")|(\b(?:import|from|export|default|function|const|return)\b)|(</?[A-Z][A-Za-z]*|/?>)|(\b[A-Z][A-Z_]{2,}\b)|(\b[a-z][A-Za-z]*(?=\())|([{}()\[\]])")
    for m in pat.finditer(line):
        out += html.escape(line[i:m.start()])
        g = m.lastindex; t = html.escape(m.group(0))
        cls = {1: 'cm', 2: 'st', 3: 'kw', 4: 'tg', 5: 'cn', 6: 'fn', 7: 'br'}[g]
        out += f'<span class="{cls}">{t}</span>'; i = m.end()
    return out + html.escape(line[i:])
CH = 12.6   # IBM Plex Mono 21px advance
def code_block(fid, src, t0, cps, pre=0):
    lines = src.split('\n'); h, js, t = '', '', t0
    for n, ln in enumerate(lines):
        ind = len(ln) - len(ln.lstrip())
        h += f'      <div class="ln" id="{fid}{n}"{" style=\"opacity:1\"" if n < pre else ""}><i>{n + 1}</i><b>{hl(ln) or "&nbsp;"}</b></div>\n'
        if n < pre: continue
        typed = max(1, len(ln) - ind); d = round(typed / cps, 2)
        if ln.strip():
            js += f'      tl.fromTo("#{fid}{n} b", {{ clipPath: "inset(0 100% 0 {ind * CH:.0f}px)" }}, {{ clipPath: "inset(0 0% 0 0px)", duration: {d}, ease: "steps({typed})" }}, {t:.2f});\n'
            js += f'      tl.set("#{fid}{n}", {{ opacity: 1 }}, {t:.2f});\n'
            js += f'      tl.fromTo("#cur", {{ x: {ind * CH:.0f}, y: {n * 30} }}, {{ x: {len(ln) * CH:.0f}, y: {n * 30}, duration: {d}, ease: "steps({typed})", immediateRender: false }}, {t:.2f});\n'
        else:
            js += f'      tl.set("#{fid}{n}", {{ opacity: 1 }}, {t:.2f});\n'
        t += d + 0.06
    return h, js, t

home_h, home_js, home_end = code_block('ha', HOME, 1.9, 72, pre=9)
dias_h, dias_js, dias_end = code_block('da', DIAS, 11.6, 72, pre=4)

# ── phone screens: (id, image, push time) ──
SCREENS = [('accueil', 'accueil.jpg', 2.9), ('diaspora', 'diaspora.jpg', 11.4), ('resto', 'restaurant-onboarding.jpg', 15.2), ('compte', 'compte.jpg', 17.6)]
scr = ''.join(f'            <img class="pv" id="pv-{i}" src="assets/images/{img}" alt="">\n' for i, img, t in SCREENS)
scr_js = ''
for k, (i, img, t) in enumerate(SCREENS):
    if k == 0:
        scr_js += f'      tl.fromTo("#pv-{i}", {{ opacity: 0, scale: 1.04 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "power2.out" }}, {t});\n'
    else:
        prev = SCREENS[k - 1][0]
        scr_js += f'      tl.fromTo("#pv-{i}", {{ xPercent: 100 }}, {{ xPercent: 0, duration: 0.45, ease: "power3.inOut" }}, {t});\n'
        scr_js += f'      tl.to("#pv-{prev}", {{ xPercent: -30, filter: "brightness(0.6)", duration: 0.45, ease: "power3.inOut" }}, {t});\n'
# taps (phone-display px, 392×850) just before a push
TAPS = [(196, 600, 11.05), (330, 812, 17.25)]
taps = ''.join(f'            <div class="tap" id="tap{k}" style="left:{x - 22}px; top:{y - 22}px"></div>\n' for k, (x, y, t) in enumerate(TAPS))
taps_js = ''.join(f'      tl.fromTo("#tap{k}", {{ opacity: 0.85, scale: 0.4 }}, {{ opacity: 0, scale: 1.6, duration: 0.45, ease: "power2.out" }}, {t});\n' for k, (x, y, t) in enumerate(TAPS))

# ── camera path on the photo ──
CAM = [(0.0, cam(wide, 1.0)), (3.6, cam(wide, 1.07, 990)), (5.0, cam(phone_c, 2.05, 900)), (8.2, cam(phone_c, 2.2, 880)),
       (9.4, cam(code_c, 1.75, 900)), (11.2, cam(code_c, 1.85, 900)), (12.4, cam(wide, 1.1, 980)), (14.6, cam(wide, 1.12, 980)),
       (15.6, cam(phone_c, 2.1, 900)), (18.6, cam(phone_c, 2.25, 880)), (19.8, cam(wide, 1.0)), (25.0, cam(wide, 1.04))]
cam_js = f'      gsap.set("#cam", {json.dumps(CAM[0][1])});\n'
for (t0, a), (t1, b) in zip(CAM, CAM[1:]):
    ease = 'power2.inOut' if abs(a['scale'] - b['scale']) > 0.3 or abs(a['x'] - b['x']) > 200 else 'none'
    cam_js += f'      tl.fromTo("#cam", {json.dumps(a)}, {{ ...{json.dumps(b)}, duration: {round(t1 - t0, 2)}, ease: "{ease}", immediateRender: false }}, {t0});\n'

TASK_ICONS = ''.join(f'<i style="background:{c}"></i>' for c in ['#3b82f6', '#2b2b2b', '#f59e0b', '#0ea5e9', '#22c55e', ORANGE, '#a855f7', '#2b2b2b'])
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; font-family: "Inter", sans-serif; }}
      #cam {{ position: absolute; left: 0; top: 0; width: 1440px; height: 1920px; transform-origin: 0 0; }}
      #photo {{ position: absolute; left: 0; top: 0; width: 1440px; height: 1920px; filter: brightness(0.5) contrast(1.12) saturate(0.55) sepia(0.15); }}
      #scr {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: 0 0; transform: {M3D}; background: #0b0b0d; overflow: hidden; }}
      #glow {{ position: absolute; left: 0; top: 760px; width: 1440px; height: 1160px; background: radial-gradient(60% 45% at 50% 18%, rgba(110,140,255,0.22), rgba(235,104,52,0.06) 55%, rgba(0,0,0,0) 80%); mix-blend-mode: screen; }}
      #vig {{ position: absolute; inset: 0; background: radial-gradient(75% 60% at 50% 42%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.75) 100%); pointer-events: none; }}
      #grain {{ position: absolute; left: -200px; top: -200px; width: 1480px; height: 2320px; background: url(assets/images/grain.png); opacity: 0.07; mix-blend-mode: overlay; }}
      /* ── the virtual Windows screen ── */
      .tb {{ position: absolute; left: 0; bottom: 0; width: 1920px; height: 48px; background: #1c1c1f; border-top: 1px solid #2c2c30; display: flex; justify-content: center; align-items: center; gap: 14px; }}
      .tb i {{ display: block; width: 26px; height: 26px; border-radius: 6px; opacity: 0.9; }}
      .tray {{ position: absolute; right: 22px; bottom: 9px; font: 500 15px "Inter"; color: #ddd; text-align: right; line-height: 15px; }}
      .title {{ position: absolute; left: 0; top: 0; width: 1920px; height: 34px; background: #1f1f23; color: #b9b9c0; font: 400 15px/34px "Inter"; text-align: center; }}
      .act {{ position: absolute; left: 0; top: 34px; width: 48px; bottom: 48px; background: #18181b; border-right: 1px solid #26262a; }}
      .act i {{ display: block; width: 24px; height: 24px; margin: 18px auto 0; border: 2px solid #6b6b74; border-radius: 6px; }}
      .act i.on {{ border-color: #e8e8ee; }}
      .pane {{ position: absolute; left: 48px; top: 34px; width: 652px; bottom: 48px; background: #101012; border-right: 1px solid #26262a; }}
      .pane h6 {{ height: 40px; padding-left: 18px; font: 500 15px/40px "Plex Mono"; color: #9aa0aa; border-bottom: 1px solid #222226; }}
      .pane h6 b {{ color: #e8e8ee; font-weight: 500; }}
      .pane h6 em {{ font-style: normal; color: {GREEN}; float: right; margin-right: 18px; }}
      #phone {{ position: absolute; left: {PH_X - 48}px; top: {PH_Y - 34}px; width: {PH_W}px; height: {PH_H}px; border-radius: 66px; background: #0a0a0a; border: 4px solid #8c8780; box-shadow: 0 0 0 2px #3a3835, 0 30px 80px rgba(0,0,0,0.6); }}
      #disp {{ position: absolute; left: 10px; top: 10px; width: 392px; height: 882px; border-radius: 54px; overflow: hidden; background: #000; }}
      #isl {{ position: absolute; left: 50%; top: 14px; width: 118px; height: 34px; margin-left: -59px; border-radius: 17px; background: #000; z-index: 5; }}
      .pv {{ position: absolute; left: 0; top: 0; width: 392px; height: 850px; }}
      #splash {{ position: absolute; inset: 0; background: {ORANGE}; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 18px; }}
      .klogo {{ width: 96px; height: 96px; border-radius: 26px; background: {BLUE}; color: #fff; font: 900 64px/96px "Inter"; text-align: center; }}
      #splash b {{ font: 900 44px "Inter"; color: #fff; letter-spacing: -0.02em; }}
      .tap {{ position: absolute; width: 44px; height: 44px; border-radius: 22px; background: rgba(255,255,255,0.75); opacity: 0; z-index: 6; }}
      .tabs {{ position: absolute; left: {CODE_X}px; top: 34px; right: 0; height: 40px; background: #161619; border-bottom: 1px solid #26262a; }}
      .tab {{ position: absolute; top: 0; height: 40px; padding: 0 22px; font: 500 15px/40px "Plex Mono"; color: #8c8c96; border-right: 1px solid #26262a; }}
      .tab.on {{ background: #0d0d10; color: #f0f0f5; border-top: 2px solid {ORANGE}; }}
      .crumb {{ position: absolute; left: {CODE_X + 20}px; top: 80px; font: 500 14px "Plex Mono"; color: #777780; }}
      .code {{ position: absolute; left: {CODE_X}px; top: 108px; right: 0; bottom: 48px; background: #0d0d10; padding-top: 6px; }}
      .ln {{ position: relative; height: 30px; font: 500 21px/30px "Plex Mono"; color: #d4d4d8; white-space: pre; opacity: 0; }}
      .ln i {{ display: inline-block; width: 70px; padding-right: 22px; text-align: right; font-style: normal; color: #4b4b55; }}
      .ln b {{ font-weight: 500; display: inline-block; }}
      .kw {{ color: #c586c0; }} .st {{ color: #ce9178; }} .tg {{ color: #4ec9b0; }} .cn {{ color: #4fc1ff; }} .fn {{ color: #dcdcaa; }} .br {{ color: #ffd700; }} .cm {{ color: #6a9955; }}
      #curw {{ position: absolute; left: {CODE_X + 70}px; top: 114px; }}
      #cur {{ position: absolute; left: 0; top: 3px; width: 3px; height: 24px; background: #f0f0f5; }}
      .status {{ position: absolute; left: 0; right: 0; bottom: 48px; height: 26px; background: {ORANGE}; font: 500 14px/26px "Plex Mono"; color: #1a0d07; padding-left: 60px; }}
      #off {{ position: absolute; inset: 0; background: #000; }}
      /* ── overlays ── */
      #cap {{ position: absolute; left: 0; right: 0; top: 230px; text-align: center; }}
      #cap span {{ display: inline-block; padding: 18px 34px; border-radius: 18px; background: rgba(10,10,12,0.72); font: 800 46px/1.2 "Inter"; color: #fff; letter-spacing: -0.01em; }}
      #cap em {{ font-style: normal; color: {ORANGE}; }}
      #end {{ position: absolute; inset: 0; background: rgba(8,8,10,0.86); opacity: 0; }}
      #endk {{ position: absolute; left: 0; right: 0; top: 700px; display: flex; justify-content: center; align-items: center; gap: 28px; }}
      #endk .klogo {{ width: 150px; height: 150px; border-radius: 40px; font-size: 100px; line-height: 150px; }}
      #endk b {{ font: 900 150px/1 "Inter"; color: #fff; letter-spacing: -0.04em; }}
      #e1 {{ top: 930px; font: 800 58px/1.15 "Inter"; color: #fff; letter-spacing: -0.02em; }}
      #e1 em {{ font-style: normal; color: {ORANGE}; }}
      #e2 {{ position: absolute; left: 140px; top: 1110px; width: 800px; height: 96px; border-radius: 48px; background: {ORANGE}; font: 800 40px/96px "Inter"; color: #fff; text-align: center; }}
      #e3 {{ top: 1250px; font: 500 30px "Plex Mono"; color: #c9c9d2; letter-spacing: 0.06em; }}
      .c {{ position: absolute; left: 0; right: 0; text-align: center; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <div id="film" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="cam">
          <img id="photo" src="assets/images/bureau.jpg" alt="">
          <div id="scr" data-layout-allow-occlusion data-layout-allow-overlap data-layout-allow-overflow>
            <div class="title">HomeScreen.tsx — kofa-app — Visual Studio Code</div>
            <div class="act"><i class="on"></i><i></i><i></i><i></i><i></i></div>
            <div class="pane">
              <h6><b>iPhone 15 Pro Max</b> · iOS 18 · Expo <em>● en direct</em></h6>
              <div id="phone"><div id="disp"><div id="isl"></div>
            <div id="splash"><div class="klogo">K</div><b>KOFA</b></div>
{scr}{taps}              </div></div>
            </div>
            <div class="tabs"><div class="tab on" id="tab1" style="left:0">HomeScreen.tsx</div><div class="tab" id="tab2" style="left:200px">DiasporaScreen.tsx</div></div>
            <div class="crumb" id="crumb">kofa-app › src › screens › <span id="crf">HomeScreen.tsx</span></div>
            <div class="code" id="code1">
{home_h}            </div>
            <div class="code" id="code2" style="opacity:0">
{dias_h}            </div>
            <div id="curw"><div id="cur"></div></div>
            <div class="status">⎇ main   ✓ 0 erreur   Expo : connecté à l'iPhone 15 Pro Max   TypeScript React</div>
            <div class="tb">{TASK_ICONS}<div class="tray">FRA&nbsp;&nbsp;13:20<br><span style="font-size:12px">15/10/2026</span></div></div>
            <div id="off"></div>
          </div>
          <div id="glow"></div>
        </div>
        <div id="vig" data-layout-allow-occlusion></div>
        <div id="grain" data-layout-allow-occlusion data-layout-allow-overflow></div>
        <div id="cap" data-layout-allow-overlap><span>Je code <em>KOFA</em>, l'app de livraison<br>de Bamako</span></div>
        <div id="end" data-layout-allow-occlusion></div>
        <div id="endk"><div class="klogo">K</div><b>KOFA</b></div>
        <div class="c" id="e1">Le goût de Bamako,<br><em>livré chez vous.</em></div>
        <div id="e2">Bientôt disponible à Bamako</div>
        <div class="c" id="e3">kofa.ml</div>
      </div>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="5" data-volume="0.8"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
      // camera
{cam_js}      // dark room fades in, then the screen wakes up
      tl.fromTo("#photo", {{ opacity: 0 }}, {{ opacity: 1, duration: 1.0, ease: "power1.out" }}, 0);
      tl.fromTo("#off", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.35, ease: "power2.out" }}, 1.1);
      tl.fromTo("#glow", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, 1.1);
      tl.fromTo("#grain", {{ x: 0, y: 0 }}, {{ x: -180, y: -140, duration: {TOTAL}, ease: "steps({TOTAL * 25})" }}, 0);
      // caption
      tl.fromTo("#cap span", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, 0.6);
      tl.to("#cap span", {{ opacity: 0, y: -16, duration: 0.4, ease: "power2.in" }}, 4.4);
      // phone: splash then real KOFA screens
      tl.fromTo("#splash .klogo", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "back.out(2)" }}, 1.6);
      tl.fromTo("#splash b", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, 1.9);
{scr_js}{taps_js}      // code typing: HomeScreen, then DiasporaScreen
{home_js}      tl.set("#code1", {{ opacity: 0 }}, 11.3);
      tl.set("#code2", {{ opacity: 1 }}, 11.3);
      tl.set("#tab1", {{ className: "tab" }}, 11.3);
      tl.set("#tab2", {{ className: "tab on" }}, 11.3);
      tl.set("#crf", {{ textContent: "DiasporaScreen.tsx" }}, 11.3);
{dias_js}      tl.fromTo("#cur", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.5, ease: "steps(1)", repeat: 49, yoyo: true }}, 0);
      // end card
      tl.fromTo("#end", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.7, ease: "power2.out" }}, 20.2);
      tl.fromTo("#endk", {{ opacity: 0, scale: 0.85 }}, {{ opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.6)" }}, 20.6);
      tl.fromTo("#e1", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, 21.1);
      tl.fromTo("#e2", {{ opacity: 0, scale: 0.8 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.8)" }}, 21.7);
      tl.fromTo("#e3", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, 22.2);
      tl.set({{}}, {{}}, {TOTAL});
    </script>
  </body>
</html>
'''
# screen text lives inside the photo (dimmed, vignetted, under the caption) on purpose: tell the layout audit
a, b = idx.index('<div id="scr"'), idx.index('<div id="glow">')
mark = ' data-layout-allow-occlusion data-layout-allow-overlap'
inner = re.sub(r'<(div|span|h6|em|b|i)(?=[ >])', lambda m: '<' + m.group(1) + mark, idx[a:b])
idx = idx[:a] + inner + idx[b:]
open(f'{P}/index.html', 'w').write(idx)
print('ok phone', [round(v) for v in phone_c], 'code', [round(v) for v in code_c], 'home typed until', round(home_end, 1), 'dias until', round(dias_end, 1))
