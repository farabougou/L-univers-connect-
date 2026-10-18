# Pub « services » de Mohamed : sites internet, applications, pubs vidéo. Vertical 1080×1920, 25 i/s, 64 temps à 124 BPM (31 s).
# Proof, not promises: the live sites (ktf-shipping.com, sensexpress.com, captured full-page), the KOFA app screens,
# and real ad renders. Same identity as the showreel (ink, orange, Inter 900, Plex Mono).
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
B = 60 / 124
T = lambda b: round(b * B, 3)
TOTAL = T(64)
ACC, INK, WHITE, MUTE = '#FF5A1F', '#0A0A0C', '#F4F2EE', '#9A98A0'

def phone(pid, x, y, w, h, inner, rot=0, extra=''):
    r = int(w * 0.16)
    return (f'<div class="ph" id="{pid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{r}px; transform: rotate({rot}deg); {extra}">'
            f'<div class="ph-s" style="border-radius:{r - 10}px">{inner}<i class="isl"></i></div></div>')

# section 1 — sites
LAP_X, LAP_Y, LAP_W = 70, 560, 940
SCR_W, SCR_H = 900, 562
desk_h = {n: int(4200 * SCR_W / 1200) for n in ('ktf', 'sensexpress')}
mob_w = 276; mob_h = int(5200 * mob_w / 600)
s1 = f'''
    <section id="sec1" class="sec">
      <div class="num">01</div><div class="ttl">Sites internet</div>
      <div class="sub">Votre vitrine en ligne, belle sur ordinateur et sur mobile.</div>
      <div class="lap" style="left:{LAP_X}px; top:{LAP_Y}px; width:{LAP_W}px">
        <div class="lap-s" style="width:{SCR_W}px; height:{SCR_H}px">
          <img class="site" id="d-ktf" src="assets/images/ktf-desk.jpg" alt="" style="width:{SCR_W}px">
          <img class="site" id="d-sx" src="assets/images/sensexpress-desk.jpg" alt="" style="width:{SCR_W}px; opacity:0">
        </div>
        <div class="lap-b"></div>
      </div>
      {phone('p1', 770, 860, 300, 620, f'<img class="site" id="m-ktf" src="assets/images/ktf-mob.jpg" alt="" style="width:{mob_w}px"><img class="site" id="m-sx" src="assets/images/sensexpress-mob.jpg" alt="" style="width:{mob_w}px; opacity:0">')}
      <div class="url" id="u1"><b>●</b> ktf-shipping.com</div>
      <div class="url" id="u2" style="opacity:0"><b>●</b> sensexpress.com</div>
      <div class="pills" style="top:1560px"><span>Design sur mesure</span><span>Version mobile</span><span>Mise en ligne</span></div>
    </section>'''
# section 2 — app
SCREENS = ['accueil', 'diaspora', 'restaurant-onboarding', 'compte']
app_inner = ''.join(f'<img class="kscr" id="k{i}" src="assets/images/{n}.jpg" alt="">' for i, n in enumerate(SCREENS)) + '<div class="tap" id="tap"></div>'
CARDS = [('c1', 40, 760, 'Suivi du livreur', 'en direct sur la carte'), ('c2', 700, 1060, 'Note vocale', 'pour guider le livreur'), ('c3', 40, 1360, 'Code à 4 chiffres', 'remis à la livraison')]
cards = ''.join(f'<div class="card" id="{i}" style="left:{x}px; top:{y}px"><i></i><b>{t}</b><span>{s}</span></div>' for i, x, y, t, s in CARDS)
s2 = f'''
    <section id="sec2" class="sec">
      <div class="num">02</div><div class="ttl">Applications</div>
      <div class="sub">Comme KOFA, mon app de livraison à Bamako.</div>
      {phone('p2', 300, 520, 480, 1000, app_inner)}
      {cards}
    </section>'''
# section 3 — ads
ADS = [('founerou', "Founerou Grill's"), ('sensexpress-diffuseurs', 'SensExpress'), ('gimso', 'GimSo'),
       ('cassia-dress', 'Cassia Dressing'), ('enoryx-pub', 'Enoryx'), ('sk-print', 'SK Print')]
def ad_video(k, i, st, d):
    return f'<video id="a-{k}" class="clip adv" src="assets/clips/{k}.mp4" data-start="{st}" data-duration="{d}" data-track-index="{2 + i}" muted playsinline></video>'
SLOT = [(60, 640, 300, 620, -7), (360, 560, 360, 740, 0), (720, 640, 300, 620, 7)]
s3_ph = ''
for j, (x, y, w, h, rot) in enumerate(SLOT):
    a, b2 = ADS[j], ADS[j + 3]
    inner = ad_video(a[0], j, T(40), T(6.2)) + ad_video(b2[0], j + 3, T(46), T(6.2))
    s3_ph += phone(f'p3{j}', x, y, w, h, inner, rot, 'z-index:' + ('3' if j == 1 else '1'))
    s3_ph += f'<div class="brand" id="bA{j}" style="left:{x}px; width:{w}px; top:{y + h + 26}px">{a[1]}</div><div class="brand" id="bB{j}" style="left:{x}px; width:{w}px; top:{y + h + 26}px; opacity:0">{b2[1]}</div>'
s3 = f'''
    <section id="sec3" class="sec">
      <div class="num">03</div><div class="ttl">Pubs vidéo</div>
      <div class="sub">Motion design pour vos réseaux : déjà 9 marques.</div>
      {s3_ph}
    </section>'''
s4 = f'''
    <section id="sec4" class="sec">
      <div class="big" id="q1" style="top:470px">Votre projet</div>
      <div class="big" id="q2" style="top:600px">est <em>le prochain.</em></div>
      <div class="pills" id="q3" style="top:820px"><span>Site internet</span><span>Application</span><span>Pub vidéo</span></div>
      <div class="name" id="q4">MOHAMED</div>
      <div class="cap" id="q5">Motion design · Vibe coding · Bamako</div>
      <div class="cta" id="q6">Écrivez-moi en message privé</div>
    </section>'''
hook = '''
    <section id="sec0" class="sec">
      <div class="big" id="h1" style="top:620px"><span class="w">Votre</span> <span class="w">business</span></div>
      <div class="big" id="h2" style="top:750px"><span class="w">mérite</span> <span class="w">d'être</span></div>
      <div class="big" id="h3" style="top:880px; font-size:220px"><em>vu.</em></div>
      <div class="cap" id="h4" style="top:1160px">Site · Application · Pub vidéo</div>
    </section>'''

js = []
J = js.append
# living background
J(f'tl.fromTo("#grid", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "0px -240px", duration: {TOTAL}, ease: "none" }}, 0);')
J(f'tl.fromTo("#glow1", {{ x: -120, y: 0 }}, {{ x: 160, y: 300, duration: {TOTAL}, ease: "sine.inOut" }}, 0);')
J(f'tl.fromTo("#glow2", {{ x: 100, y: 0 }}, {{ x: -140, y: -260, duration: {TOTAL}, ease: "sine.inOut" }}, 0);')
# section visibility windows + exits
WIN = [('sec0', 0, 8), ('sec1', 8, 24), ('sec2', 24, 40), ('sec3', 40, 52), ('sec4', 52, 64)]
for sid, a, b in WIN:
    J(f'tl.set("#{sid}", {{ autoAlpha: 1 }}, {T(a)});')
    if b < 64:
        J(f'tl.to("#{sid}", {{ y: -140, autoAlpha: 0, filter: "blur(14px)", duration: 0.28, ease: "power3.in" }}, {T(b) - 0.28:.3f});')
for sid, a, b in WIN[1:4]:
    J(f'tl.fromTo("#{sid} .num", {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: "expo.out" }}, {T(a)});')
    J(f'tl.fromTo("#{sid} .ttl", {{ opacity: 0, y: 50, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {T(a) + 0.05:.3f});')
    J(f'tl.fromTo("#{sid} .sub", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {T(a + 1)});')
# hook
J(f'gsap.utils.toArray("#h1 .w, #h2 .w").forEach((w, i) => tl.fromTo(w, {{ opacity: 0, y: 50, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.4, ease: "expo.out" }}, {B:.4f} * (0.5 + i)));')
J(f'tl.fromTo("#h3", {{ opacity: 0, scale: 2.2, filter: "blur(24px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, {T(4)});')
J(f'tl.fromTo("#h4", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {T(6)});')
# section 1 — laptop rises, sites scroll, switch on beat 16
J(f'tl.fromTo(".lap", {{ y: 500, rotationX: 28, opacity: 0 }}, {{ y: 0, rotationX: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(8) + 0.1:.3f});')
J(f'tl.fromTo("#p1", {{ x: 400, rotation: 14, opacity: 0 }}, {{ x: 0, rotation: 4, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(9)});')
for n, a, b in [('ktf', 8, 16), ('sx', 16, 24)]:
    dh = desk_h['ktf' if n == 'ktf' else 'sensexpress']
    J(f'tl.fromTo("#d-{n}", {{ y: 0 }}, {{ y: {-(dh - SCR_H) * 0.55:.0f}, duration: {T(b - a) - 0.4:.3f}, ease: "power1.inOut" }}, {T(a) + 0.4:.3f});')
    J(f'tl.fromTo("#m-{n}", {{ y: 0 }}, {{ y: {-(mob_h - 596) * 0.35:.0f}, duration: {T(b - a) - 0.4:.3f}, ease: "power1.inOut" }}, {T(a) + 0.4:.3f});')
J(f'tl.fromTo(["#d-sx", "#m-sx"], {{ opacity: 0, x: 120 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }}, {T(16)});')
J(f'tl.to(["#d-ktf", "#m-ktf"], {{ opacity: 0, x: -120, duration: 0.3, ease: "power3.in" }}, {T(16)});')
J(f'tl.fromTo("#u1", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, {T(10)}); tl.to("#u1", {{ opacity: 0, duration: 0.2 }}, {T(16) - 0.1:.3f});')
J(f'tl.fromTo("#u2", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, {T(16) + 0.1:.3f});')
J(f'gsap.utils.toArray("#sec1 .pills span").forEach((p, i) => tl.fromTo(p, {{ opacity: 0, y: 24, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(2)" }}, {T(12)} + i * {B:.4f}));')
# section 2 — KOFA phone, push transitions on beats, feature cards
J(f'tl.fromTo("#p2", {{ y: 700, rotation: -6, opacity: 0 }}, {{ y: 0, rotation: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(24) + 0.1:.3f});')
J(f'tl.fromTo("#p2", {{ rotationY: 0 }}, {{ rotationY: -10, duration: {T(15)}, ease: "sine.inOut" }}, {T(25)});')
for i in range(1, 4):
    t0 = T(24 + i * 4)
    J(f'tl.fromTo("#tap", {{ opacity: 0.85, scale: 0.4 }}, {{ opacity: 0, scale: 1.7, duration: 0.4, ease: "power2.out", immediateRender: false }}, {t0 - 0.3:.3f});')
    J(f'tl.fromTo("#k{i}", {{ xPercent: 100 }}, {{ xPercent: 0, duration: 0.42, ease: "power3.inOut", immediateRender: false }}, {t0});')
    J(f'tl.set("#k{i}", {{ opacity: 1 }}, {t0});')
    J(f'tl.to("#k{i - 1}", {{ xPercent: -30, filter: "brightness(0.55)", duration: 0.42, ease: "power3.inOut" }}, {t0});')
for j, (cid, x, y, t_, s_) in enumerate(CARDS):
    J(f'tl.fromTo("#{cid}", {{ opacity: 0, x: {-120 if x < 300 else 120}, filter: "blur(10px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {T(27 + j * 4)});')
    J(f'tl.to("#{cid}", {{ y: -14, duration: 1.4, ease: "sine.inOut", yoyo: true, repeat: 3 }}, {T(28 + j * 4)});')
# section 3 — three phones, swap ads on beat 46
for j in range(3):
    J(f'tl.fromTo("#p3{j}", {{ y: 900, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.7, ease: "expo.out" }}, {T(40) + 0.08 * j:.3f});')
    J(f'tl.fromTo("#bA{j}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {T(41)}); tl.to("#bA{j}", {{ opacity: 0, duration: 0.2 }}, {T(46) - 0.1:.3f});')
    J(f'tl.fromTo("#bB{j}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {T(46) + 0.1:.3f});')
    J(f'tl.fromTo("#p3{j}", {{ scale: 1.06 }}, {{ scale: 1, duration: 0.35, ease: "power3.out", immediateRender: false }}, {T(46)});')
# section 4 — CTA
J(f'tl.fromTo("#q1", {{ opacity: 0, y: 60, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {T(52)});')
J(f'tl.fromTo("#q2", {{ opacity: 0, y: 60, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {T(53)});')
J(f'gsap.utils.toArray("#q3 span").forEach((p, i) => tl.fromTo(p, {{ opacity: 0, y: 24, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(2)" }}, {T(54)} + i * {B:.4f}));')
J(f'tl.fromTo("#q4", {{ opacity: 0, scale: 1.3, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out" }}, {T(56)});')
J(f'tl.fromTo("#q5", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {T(57)});')
J(f'tl.fromTo("#q6", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2)" }}, {T(58)});')
J(f'tl.to("#q6", {{ scale: 1.05, duration: {B:.4f}, ease: "sine.inOut", yoyo: true, repeat: 7 }}, {T(59)});')
# flash on the drops
for bt in (8, 24, 40, 52):
    J(f'tl.fromTo("#flash", {{ opacity: 0.6 }}, {{ opacity: 0, duration: 0.25, ease: "power2.out", immediateRender: false }}, {T(bt)});')

SFX = [('riser', T(5), 0.3), ('impact', T(8), 0.5), ('whoosh', T(16) - 0.1, 0.3), ('impact', T(24), 0.45), ('impact', T(40), 0.45), ('impact', T(52), 0.55)]
import soundfile as _sf
LEN = {n: round(_sf.info(f'{P}/assets/{n}.wav').duration, 2) for n in ('impact', 'whoosh', 'riser')}
sfx = ''.join(f'      <audio id="sfx{i}" src="assets/{f}.wav" data-start="{t}" data-duration="{LEN[f]}" data-track-index="{20 + i % 3}" data-volume="{v}"></audio>\n' for i, (f, t, v) in enumerate(SFX))
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
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; font-family: "Inter", sans-serif; perspective: 1600px; }}
      #grid {{ position: absolute; inset: 0; background-image: radial-gradient(rgba(244,242,238,0.10) 1.5px, transparent 1.6px); background-size: 40px 40px; }}
      .glow {{ position: absolute; width: 900px; height: 900px; border-radius: 50%; background: radial-gradient(closest-side, rgba(255,90,31,0.22), rgba(255,90,31,0)); }}
      .sec {{ position: absolute; inset: 0; visibility: hidden; opacity: 0; }}
      .num {{ position: absolute; left: 70px; top: 150px; font: 500 34px "Plex Mono"; color: {ACC}; }}
      .ttl {{ position: absolute; left: 66px; top: 190px; font: 900 112px/1 "Inter"; color: {WHITE}; letter-spacing: -0.045em; white-space: nowrap; }}
      .sub {{ position: absolute; left: 70px; right: 70px; top: 330px; font: 500 38px/1.3 "Inter"; color: {MUTE}; }}
      .big {{ position: absolute; left: 0; right: 0; text-align: center; font: 900 128px/1 "Inter"; color: {WHITE}; letter-spacing: -0.045em; white-space: nowrap; }}
      .big em, .ttl em {{ font-style: normal; color: {ACC}; }}
      .w {{ display: inline-block; }}
      .cap {{ position: absolute; left: 0; right: 0; text-align: center; font: 600 32px "Inter"; letter-spacing: 0.3em; color: {MUTE}; text-transform: uppercase; white-space: nowrap; }}
      .lap {{ position: absolute; transform-origin: 50% 100%; }}
      .lap-s {{ position: relative; margin: 0 auto; overflow: hidden; background: #000; border: 20px solid #1c1c21; border-bottom-width: 26px; border-radius: 26px 26px 6px 6px; box-sizing: content-box; box-shadow: 0 40px 80px rgba(0,0,0,0.6); }}
      .lap-b {{ width: 1000px; height: 28px; margin: 0 0 0 -30px; background: linear-gradient(180deg, #3a3a42, #1d1d22); border-radius: 0 0 26px 26px; }}
      .site {{ position: absolute; left: 0; top: 0; display: block; }}
      .ph {{ position: absolute; background: #0d0d10; padding: 10px; box-shadow: 0 0 0 3px #4a4a52, 0 40px 80px rgba(0,0,0,0.65); }}
      .ph-s {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; }}
      .isl {{ position: absolute; left: 50%; top: 12px; width: 30%; height: 26px; margin-left: -15%; border-radius: 14px; background: #000; z-index: 5; }}
      .kscr {{ position: absolute; left: 0; top: 0; width: 100%; height: auto; opacity: 0; filter: brightness(1); }}
      #k0 {{ opacity: 1; }}
      .tap {{ position: absolute; left: 50%; top: 58%; width: 70px; height: 70px; margin: -35px; border-radius: 50%; background: rgba(255,255,255,0.7); opacity: 0; z-index: 6; }}
      .adv {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; }}
      .url {{ position: absolute; left: 70px; top: 1230px; font: 500 34px "Plex Mono"; color: {WHITE}; padding: 14px 22px; border-radius: 12px; background: rgba(244,242,238,0.06); border: 1px solid rgba(244,242,238,0.16); }}
      .url b {{ color: #3BD16F; font-weight: 500; }}
      .pills {{ position: absolute; left: 0; right: 0; display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; }}
      .pills span {{ font: 700 32px "Inter"; color: {WHITE}; padding: 16px 26px; border-radius: 40px; border: 2px solid {ACC}; background: rgba(255,90,31,0.10); }}
      .card {{ position: absolute; width: 340px; padding: 22px 24px; border-radius: 22px; background: rgba(22,22,26,0.88); border: 1px solid rgba(244,242,238,0.14); box-shadow: 0 20px 50px rgba(0,0,0,0.45); z-index: 4; }}
      .card i {{ display: block; width: 14px; height: 14px; border-radius: 7px; background: {ACC}; margin-bottom: 12px; box-shadow: 0 0 18px {ACC}; }}
      .card b {{ display: block; font: 800 34px/1.1 "Inter"; color: {WHITE}; }}
      .card span {{ display: block; margin-top: 6px; font: 500 26px "Inter"; color: {MUTE}; }}
      .brand {{ position: absolute; text-align: center; font: 800 30px "Inter"; color: {WHITE}; }}
      .name {{ position: absolute; left: 0; right: 0; top: 1090px; text-align: center; font: 900 150px/1 "Inter"; color: {WHITE}; letter-spacing: -0.05em; }}
      #q5 {{ top: 1260px; }}
      .cta {{ position: absolute; left: 140px; right: 140px; top: 1380px; text-align: center; font: 800 42px/104px "Inter"; color: {INK}; background: {ACC}; border-radius: 52px; }}
      #flash {{ position: absolute; inset: 0; background: {WHITE}; opacity: 0; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <div id="stage" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="grid"></div>
        <div class="glow" id="glow1" style="left:-200px; top:200px"></div>
        <div class="glow" id="glow2" style="left:400px; top:1100px"></div>
{hook}{s1}{s2}{s3}{s4}
        <div id="flash"></div>
      </div>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="15" data-volume="0.9"></audio>
{sfx}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
{chr(10).join('      ' + j for j in js)}
      tl.to({{}}, {{ duration: {TOTAL} }}, 0);
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok', TOTAL, 'desk_h', desk_h, 'mob_h', mob_h)
