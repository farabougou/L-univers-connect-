# KTF Shipping — « Un trajet clair, dès le premier clic » — 60 s, 1920×1080.
# Writes compositions/frames/*.html and index.html for the HyperFrames project.
import os, json
P = '/home/user/L-univers-connect-/videos/ktf-shipping-vertical'
W, H = 1080, 1920
# scene id, start, length (brief: 0-7, 7-16, 16-27, 27-38, 38-50, 50-60)
SC = [('01-trajet', 0, 7), ('02-reperes', 7, 9), ('03-offre', 16, 11), ('04-information', 27, 11), ('05-action', 38, 12), ('06-adresse', 50, 10)]
OV = 0.5   # overlap used by transitions
TOTAL = 60

FONTS = '''
    @font-face { font-family: "Oswald"; font-weight: 400; src: url("assets/fonts/oswald-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Oswald"; font-weight: 500; src: url("assets/fonts/oswald-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Oswald"; font-weight: 600; src: url("assets/fonts/oswald-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Oswald"; font-weight: 700; src: url("assets/fonts/oswald-latin-700-normal.woff2") format("woff2"); }
    @font-face { font-family: "Roboto"; font-weight: 400; src: url("assets/fonts/roboto-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Roboto"; font-weight: 500; src: url("assets/fonts/roboto-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Roboto"; font-weight: 700; src: url("assets/fonts/roboto-latin-700-normal.woff2") format("woff2"); }
'''
# ── brand tokens (observed in the site CSS, see brief p.4) ──
CSS = '''
    .X-abs { position: absolute; }
    .X-bgd { position: absolute; inset: 0; background: radial-gradient(90% 80% at 70% 40%, #0b1f36 0%, #06111F 70%); }
    .X-bgl { position: absolute; inset: 0; background: #F4F8FC; }
    .X-bgw { position: absolute; inset: 0; background: #FFFFFF; }
    .X-kick { display: flex; align-items: center; gap: 18px; font-family: "Roboto"; font-weight: 500; font-size: 24px; letter-spacing: 0.24em; color: #1EAAE2; white-space: nowrap; }
    .X-kick i { display: block; width: 56px; height: 3px; background: #1EAAE2; }
    .X-st { font-family: "Oswald"; font-weight: 600; font-size: 88px; line-height: 1.08; text-transform: uppercase; color: #FFFFFF; white-space: nowrap; }
    .X-st em { font-style: normal; color: #1EAAE2; }
    .X-st.dk { color: #152235; }
    .X-fil { display: flex; align-items: center; gap: 14px; }
    .X-fil i { display: block; width: 110px; height: 4px; border-radius: 2px; background: #1EAAE2; }
    .X-fil u { display: block; width: 14px; height: 14px; border-radius: 7px; background: #1EAAE2; }
    .X-fil u.o { background: #F07828; }
    .X-ex { font-family: "Roboto"; font-weight: 400; font-size: 34px; line-height: 1.45; color: #9FB3C8; }
    .X-ex.dk { color: #46586E; }
    /* site components */
    .X-site { position: absolute; left: 0; top: 0; width: 1440px; background: #06111F; overflow: hidden; transform-origin: 0 0; }
    .X-hd { height: 96px; background: #FFFFFF; display: flex; align-items: center; padding: 0 56px; gap: 40px; }
    .X-hd img { display: block; height: 66px; }
    .X-hd nav { display: flex; gap: 34px; margin-left: auto; font-family: "Roboto"; font-weight: 500; font-size: 17px; letter-spacing: 0.08em; color: #152235; }
    .X-btn { display: inline-flex; align-items: center; gap: 12px; padding: 16px 28px; border-radius: 3px; font-family: "Roboto"; font-weight: 700; font-size: 17px; letter-spacing: 0.12em; text-transform: uppercase; color: #FFFFFF; background: #1EAAE2; white-space: nowrap; }
    .X-btn.ol { background: transparent; border: 2px solid #8a96a3; }
    .X-btn svg { display: block; }
    .X-bar { height: 6px; background: linear-gradient(90deg, #1EAAE2 0 33%, #D93A2B 33% 66%, #F07828 66% 100%); }
    .X-hero { position: relative; height: 700px; padding: 150px 80px 0; background:
        radial-gradient(40% 55% at 82% 70%, rgba(240,120,40,0.22), rgba(240,120,40,0) 70%),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.025) 0 2px, rgba(255,255,255,0) 2px 180px),
        linear-gradient(180deg, #0a1a2c 0%, #06111F 100%); }
    .X-hk { display: flex; align-items: center; gap: 22px; font-family: "Roboto"; font-weight: 700; font-size: 20px; letter-spacing: 0.3em; color: #1EAAE2; }
    .X-hk i { display: block; width: 64px; height: 3px; background: #1EAAE2; }
    .X-ht { margin-top: 34px; font-family: "Oswald"; font-weight: 600; font-size: 84px; line-height: 1.08; color: #FFFFFF; white-space: nowrap; }
    .X-ht em { font-style: italic; color: #1EAAE2; }
    .X-hp { margin-top: 26px; font-family: "Roboto"; font-weight: 400; font-size: 24px; line-height: 1.6; color: #C9D3DE; }
    .X-hb { margin-top: 38px; display: flex; gap: 20px; }
    /* browser chrome */
    .X-br { position: absolute; border-radius: 18px; overflow: hidden; background: #FFFFFF; box-shadow: 0 40px 90px rgba(0,0,0,0.45); }
    .X-brt { height: 44px; background: #EEF2F6; display: flex; align-items: center; gap: 10px; padding: 0 18px; }
    .X-brt u { display: block; width: 13px; height: 13px; border-radius: 7px; background: #c7d0da; }
    .X-brt b { display: block; margin-left: 24px; padding: 6px 22px; border-radius: 14px; background: #FFFFFF; font-family: "Roboto"; font-weight: 500; font-size: 17px; color: #46586E; }
    .X-brv { position: relative; overflow: hidden; }
    /* cards */
    .X-card { position: absolute; border-radius: 18px; background: #FFFFFF; box-shadow: 0 24px 60px rgba(21,34,53,0.14); border: 1px solid #E3EAF2; }
    .X-ic { display: flex; width: 96px; height: 96px; border-radius: 18px; align-items: center; justify-content: center; background: #E6F5FC; }
    .X-ct { font-family: "Oswald"; font-weight: 600; font-size: 44px; color: #152235; text-transform: uppercase; white-space: nowrap; }
    .X-cp { font-family: "Roboto"; font-weight: 400; font-size: 26px; line-height: 1.45; color: #46586E; }
    .X-cl { display: flex; align-items: center; gap: 10px; font-family: "Roboto"; font-weight: 700; font-size: 20px; letter-spacing: 0.14em; color: #1EAAE2; }
    .X-cur { position: absolute; left: 0; top: 0; width: 40px; height: 40px; }
'''
ARROW = '<svg width="20" height="20" viewBox="0 0 20 20"><path d="M3 10 H16 M11 5 L16 10 L11 15" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ARROWB = ARROW.replace('#fff', '#1EAAE2')
TARGET = '<svg width="22" height="22" viewBox="0 0 22 22"><circle cx="11" cy="11" r="6.5" stroke="#fff" stroke-width="2.2" fill="none"/><circle cx="11" cy="11" r="2.4" fill="#fff"/><path d="M11 1 V4 M11 18 V21 M1 11 H4 M18 11 H21" stroke="#fff" stroke-width="2.2"/></svg>'
CURSOR = '<svg width="40" height="40" viewBox="0 0 40 40"><path d="M6 3 L6 32 L13 25 L18 36 L23 34 L18 23 L28 23 Z" fill="#FFFFFF" stroke="#152235" stroke-width="2.2" stroke-linejoin="round"/></svg>'
ICON = {
 'air': '<svg width="58" height="58" viewBox="0 0 64 64"><path d="M6 34 L26 30 L38 8 L45 8 L39 30 L56 28 C61 28 61 35 56 35 L39 36 L45 56 L38 56 L26 38 L6 36 Z" fill="#1EAAE2"/></svg>',
 'sea': '<svg width="58" height="58" viewBox="0 0 64 64"><path d="M20 22 H42 V36 H20 Z M30 12 H37 V22 H30 Z" fill="#1EAAE2"/><path d="M6 36 H58 L50 50 H14 Z" fill="#1EAAE2"/><path d="M4 56 Q12 52 20 56 T36 56 T52 56 T60 56" stroke="#1EAAE2" stroke-width="3" fill="none"/></svg>',
 'road': '<svg width="58" height="58" viewBox="0 0 64 64"><path d="M4 18 H38 V46 H4 Z M38 26 H50 L60 36 V46 H38 Z" fill="#1EAAE2"/><circle cx="14" cy="48" r="6" fill="#152235"/><circle cx="48" cy="48" r="6" fill="#152235"/><circle cx="14" cy="48" r="2.5" fill="#fff"/><circle cx="48" cy="48" r="2.5" fill="#fff"/></svg>',
}

def site_html(fid, nav=True):
    navs = '<nav><span>SERVICES</span><span>DÉPARTS</span><span>SUIVI</span><span>À PROPOS</span><span>CONTACT</span></nav><div class="X-btn" id="X-hdbtn">Demander un devis</div>' if nav else ''
    return f'''<div class="X-hd"><img src="assets/images/ktf-logo.png" alt="KTF">{navs}</div>
        <div class="X-bar"></div>
        <div class="X-hero">
          <div class="X-hk" id="X-hk"><i></i>SOLUTIONS LOGISTIQUES — EUROPE &amp; AFRIQUE</div>
          <div class="X-ht" id="X-ht"><em>TRANSPORT</em> AÉRIEN, MARITIME<br>&amp; ROUTIER</div>
          <div class="X-fil" style="margin-top:30px" id="X-hf"><i></i><u></u></div>
          <div class="X-hp" id="X-hp">KTF Shipping, votre partenaire de confiance entre l'Europe<br>et toute l'Afrique de l'Ouest.</div>
          <div class="X-hb" id="X-hb"><div class="X-btn">{ARROW}Nos services</div><div class="X-btn ol">{TARGET}Suivre mon envoi</div></div>
        </div>'''

def statement(kick, l1, l2, x, y, dark=True, em2=True):
    cls = '' if dark else ' dk'
    l2h = f'<em>{l2}</em>' if em2 else l2
    return f'''    <div class="X-abs" id="X-sk" style="left:{x}px; top:{y}px"><div class="X-kick"><i></i>{kick}</div></div>
    <div class="X-abs X-st{cls}" id="X-s1" style="left:{x}px; top:{y+52}px">{l1}</div>
    <div class="X-abs X-st{cls}" id="X-s2" style="left:{x}px; top:{y+52+95}px">{l2h}</div>
'''
def st_in(at):
    return f'''      tl.fromTo(R("#X-sk"), {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.5, ease: "power2.out" }}, {at});
      tl.fromTo(R("#X-s1"), {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, {at + 0.1});
      tl.fromTo(R("#X-s2"), {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, {at + 0.35});
'''

F = {}
# ── 01 · Un trajet clair, dès le premier clic (0–7) ──────────────────────
F['01-trajet'] = ('''
    #X-logo { position: absolute; left: 50%; top: 50%; width: 860px; height: 286px; margin: -143px 0 0 -430px; }
    #X-logo img { display: block; width: 100%; }
    #X-dark { position: absolute; inset: 0; background: radial-gradient(90% 80% at 70% 40%, #0b1f36 0%, #06111F 70%); }
    #X-brw { left: 60px; top: 760px; width: 960px; height: 620px; }
    #X-line { position: absolute; left: 0; top: 0; }
''', '''    <div class="X-bgw"></div>
    <div id="X-dark"></div>
    <div id="X-logo"><img src="assets/images/ktf-logo.png" alt="KTF Shipping"></div>
    <div class="X-br" id="X-brw"><div class="X-brt"><u></u><u></u><u></u><b>ktf-shipping.com</b></div>
      <div class="X-brv" style="height:576px"><div class="X-site" id="X-site" style="transform: scale(0.6667)">''' + site_html('01') + '''</div></div></div>
    <svg id="X-line" width="1080" height="1920" viewBox="0 0 1080 1920"><path id="X-lp" d="M 1100 1640 C 820 1640 700 1520 520 1500 S 230 1470 160 1470" stroke="#1EAAE2" stroke-width="5" fill="none" stroke-linecap="round"/><circle id="X-ld" cx="160" cy="1470" r="11" fill="#1EAAE2"/></svg>
''' + statement('KTF SHIPPING', 'Un trajet clair,', 'dès le premier clic.', 80, 330), '''      const lp = R("#X-lp"), L = lp.getTotalLength();
      tl.fromTo(R("#X-logo"), { opacity: 0, scale: 0.92 }, { opacity: 1, scale: 1, duration: 0.7, ease: "power2.out" }, 0.2);
      tl.to(R("#X-logo"), { opacity: 0, scale: 1.04, duration: 0.5, ease: "power2.in" }, 2.0);
      tl.fromTo(R("#X-dark"), { clipPath: "inset(100% 0% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.7, ease: "power3.inOut" }, 2.3);
      tl.fromTo(R("#X-brw"), { opacity: 0, y: 80, scale: 0.94 }, { opacity: 1, y: 0, scale: 1, duration: 0.7, ease: "power3.out" }, 2.75);
      tl.fromTo(R("#X-hk"), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.45, ease: "power2.out" }, 3.2);
      tl.fromTo(R("#X-ht"), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, 3.3);
      tl.fromTo(R("#X-hf"), { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, transformOrigin: "0 50%", duration: 0.45, ease: "power2.out" }, 3.45);
      tl.fromTo(R("#X-hp"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, 3.55);
      tl.fromTo(R("#X-hb"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, 3.65);
      tl.fromTo(lp, { attr: { "stroke-dasharray": L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.1, ease: "power2.inOut" }, 4.0);
      tl.fromTo(R("#X-ld"), { opacity: 0, scale: 0, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, 5.05);
'''+st_in(4.3)+'''      tl.to(R("#X-site"), { scale: 0.8, x: -40, y: -30, duration: 2.2, ease: "power1.inOut" }, 4.7);
''')
# ── 02 · Des repères visuels (7–16) ──────────────────────────────────────
SW = [('#1EAAE2', 'Bleu'), ('#06111F', 'Fond'), ('#D93A2B', 'Rouge'), ('#F07828', 'Orange'), ('#F5C800', 'Jaune'), ('#FFFFFF', 'Blanc'), ('#F4F8FC', 'Clair'), ('#152235', 'Texte')]
sw_html = ''.join(f'<div class="X-sw" id="X-w{i}"><u style="background:{c}"></u><b>{n}</b><span>{c}</span></div>' for i, (c, n) in enumerate(SW))
ANN = [('Titre', 'Oswald 600, capitales'), ('Accent', 'bleu #1EAAE2'), ('Texte', 'Roboto 400'), ('Boutons', 'capitales, arrondi 3 px')]
ann_html = ''.join(f'<div class="X-an" id="X-a{i}"><i></i><div><b>{a}</b><span>{b}</span></div></div>' for i, (a, b) in enumerate(ANN))
F['02-reperes'] = ('''
    #X-stage { position: absolute; left: 80px; top: 480px; width: 920px; height: 560px; perspective: 2200px; }
    #X-stk { position: absolute; inset: 0; transform-style: preserve-3d; }
    .X-ly { position: absolute; left: 0; }
    #X-ly0 { top: 0; } #X-ly1 { top: 60px; } #X-ly2 { top: 270px; } #X-ly3 { top: 320px; } #X-ly4 { top: 450px; }
    #X-ly1 .X-ht { margin: 0; font-size: 92px; }
    #X-ly3 .X-hp { margin: 0; font-size: 28px; }
    #X-ann { position: absolute; left: 80px; top: 1140px; display: flex; flex-direction: column; gap: 26px; }
    .X-an { display: flex; align-items: center; gap: 20px; }
    .X-an i { display: block; width: 70px; height: 3px; background: #1EAAE2; }
    .X-an b { display: block; font-family: "Oswald"; font-weight: 600; font-size: 40px; color: #FFFFFF; text-transform: uppercase; }
    .X-an span { display: block; font-family: "Roboto"; font-weight: 400; font-size: 30px; color: #9FB3C8; }
    #X-pal { position: absolute; left: 80px; top: 1150px; display: grid; grid-template-columns: repeat(4, 210px); gap: 26px 22px; }
    .X-sw u { display: block; width: 210px; height: 110px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.18); }
    .X-sw b { display: block; margin-top: 12px; font-family: "Oswald"; font-weight: 500; font-size: 30px; color: #FFFFFF; text-transform: uppercase; }
    .X-sw span { display: block; font-family: "Roboto"; font-weight: 500; font-size: 22px; letter-spacing: 0.06em; color: #9FB3C8; }
    #X-kx { left: 80px; top: 1090px; }
''', '''    <div class="X-bgd"></div>
''' + statement('02 — HIÉRARCHIE', 'Des repères', 'visuels.', 80, 150) + '''    <div id="X-stage"><div id="X-stk">
      <div class="X-ly" id="X-ly0"><div class="X-hk"><i></i>SOLUTIONS LOGISTIQUES — EUROPE &amp; AFRIQUE</div></div>
      <div class="X-ly" id="X-ly1"><div class="X-ht"><em>TRANSPORT</em> AÉRIEN,<br>MARITIME &amp; ROUTIER</div></div>
      <div class="X-ly" id="X-ly2"><div class="X-fil"><i></i><u></u></div></div>
      <div class="X-ly" id="X-ly3"><div class="X-hp">KTF Shipping, votre partenaire de confiance<br>entre l'Europe et toute l'Afrique de l'Ouest.</div></div>
      <div class="X-ly" id="X-ly4"><div class="X-hb" style="margin:0"><div class="X-btn">''' + ARROW + '''Nos services</div><div class="X-btn ol">''' + TARGET + '''Suivre mon envoi</div></div></div>
    </div></div>
    <div class="X-abs X-kick" id="X-kx"><i></i>PALETTE OBSERVÉE</div>
    <div id="X-ann">''' + ann_html + '''</div>
    <div id="X-pal">''' + sw_html + '''</div>
''', st_in(0.2) + '''      const LY = [0, 1, 2, 3, 4].map((i) => R("#X-ly" + i));
      LY.forEach((el, i) => tl.fromTo(el, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, 0.4 + i * 0.1));
      tl.fromTo(R("#X-stk"), { rotationY: 0, rotationX: 0 }, { rotationY: 16, rotationX: 6, duration: 1.2, ease: "power2.inOut" }, 1.4);
      LY.forEach((el, i) => tl.fromTo(el, { z: 0, x: 0 }, { z: 160 - i * 80, x: i * 26, duration: 1.2, ease: "power2.inOut", immediateRender: false }, 1.4));
      [0, 1, 2, 3].forEach((i) => tl.fromTo(R("#X-a" + i), { opacity: 0, x: 40 }, { opacity: 1, x: 0, duration: 0.45, ease: "power2.out" }, 2.0 + i * 0.35));
      tl.to(R("#X-ann"), { opacity: 0, y: -20, duration: 0.4, ease: "power2.in" }, 4.9);
      tl.fromTo(R("#X-kx"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 5.3);
      [0, 1, 2, 3, 4, 5, 6, 7].forEach((i) => tl.fromTo(R("#X-w" + i), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, 5.4 + i * 0.1));
      tl.to(R("#X-stk"), { rotationY: 0, rotationX: 0, duration: 1.0, ease: "power2.inOut" }, 7.4);
      LY.forEach((el) => tl.to(el, { z: 0, x: 0, duration: 1.0, ease: "power2.inOut" }, 7.4));
''')
# ── 03 · Une offre organisée (16–27) ─────────────────────────────────────
CARDS = [('air', 'Transport aérien'), ('sea', 'Transport maritime'), ('road', 'Transport routier')]
cards_html = ''.join(f'''    <div class="X-card" id="X-c{i}" style="left:130px; top:{560 + i * 330}px; width:870px; height:280px">
      <div style="padding:44px 44px; display:flex; gap:36px; align-items:flex-start">
        <div class="X-ic" style="flex:none">{ICON[k]}</div>
        <div><div class="X-ct">{t}</div>
        <div class="X-cp" style="margin-top:8px">Europe — Afrique de l'Ouest</div>
        <div class="X-cl" style="margin-top:22px">EN SAVOIR PLUS {ARROWB}</div></div>
      </div>
    </div>
''' for i, (k, t) in enumerate(CARDS))
F['03-offre'] = ('''
    #X-rail { position: absolute; left: 0; top: 0; }
''', '''    <div class="X-bgl"></div>
''' + statement('03 — MODULES', 'Une offre', 'organisée.', 80, 190, dark=False) + cards_html + '''    <svg id="X-rail" width="1080" height="1920" viewBox="0 0 1080 1920"><path id="X-rp" d="M 80 540 V 1480" stroke="#1EAAE2" stroke-width="4" fill="none" stroke-linecap="round"/>
      <circle id="X-r0" cx="80" cy="700" r="11" fill="#1EAAE2"/><circle id="X-r1" cx="80" cy="1030" r="11" fill="#1EAAE2"/><circle id="X-r2" cx="80" cy="1360" r="11" fill="#1EAAE2"/></svg>
''', st_in(0.3) + '''      // each card is isolated in the centre, then placed in the row
      const C = [0, 1, 2].map((i) => R("#X-c" + i)), dy = [330, 0, -330];
      C.forEach((c, i) => {
        const t0 = 1.3 + i * 1.7;
        tl.fromTo(c, { opacity: 0, x: 0, y: dy[i] + 40, scale: 1.08 }, { opacity: 1, y: dy[i], scale: 1.08, duration: 0.55, ease: "power3.out" }, t0);
        tl.to(c, { y: 0, scale: 1, duration: 0.7, ease: "power3.inOut" }, t0 + 1.1);
      });
      const rp = R("#X-rp"), RL = rp.getTotalLength();
      tl.fromTo(rp, { attr: { "stroke-dasharray": RL, "stroke-dashoffset": RL } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.4, ease: "power2.inOut" }, 6.6);
      [0, 1, 2].forEach((i) => tl.fromTo(R("#X-r" + i), { opacity: 0, scale: 0, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, 6.85 + i * 0.4));
      C.forEach((c, i) => tl.to(c, { x: 14, duration: 0.4, ease: "power2.out", yoyo: true, repeat: 1 }, 6.9 + i * 0.4));
''')
# ── 04 · Une information à portée de clic (27–38) ────────────────────────
deps = ''.join(f'''<div class="X-dr"><div class="X-ic" style="width:72px;height:72px;border-radius:12px">{ICON[k].replace('width="58" height="58"', 'width="42" height="42"')}</div><div><b>{t}</b><span>Europe — Afrique de l'Ouest</span></div><div class="X-dv">Consulter</div></div>''' for k, t in CARDS)
F['04-information'] = ('''
    #X-vp { left: 80px; top: 760px; width: 920px; height: 840px; }
    #X-pg { position: absolute; left: 0; top: 0; width: 920px; }
    .X-sec { padding: 54px 56px; }
    .X-sh { font-family: "Oswald"; font-weight: 600; font-size: 52px; color: #152235; text-transform: uppercase; }
    .X-sh em { font-style: normal; color: #1EAAE2; }
    .X-dr { display: flex; align-items: center; gap: 24px; margin-top: 22px; padding: 22px 26px; border-radius: 10px; background: #F4F8FC; border: 1px solid #E3EAF2; }
    .X-dr b { display: block; font-family: "Oswald"; font-weight: 500; font-size: 32px; color: #152235; text-transform: uppercase; }
    .X-dr span { display: block; font-family: "Roboto"; font-size: 22px; color: #46586E; }
    .X-dv { margin-left: auto; padding: 12px 20px; border-radius: 3px; border: 2px solid #1EAAE2; font-family: "Roboto"; font-weight: 700; font-size: 16px; letter-spacing: 0.12em; text-transform: uppercase; color: #1EAAE2; }
    .X-in { display: flex; gap: 16px; margin-top: 30px; }
    .X-in div.f { flex: 1; display: flex; align-items: center; height: 76px; padding: 0 26px; border-radius: 3px; border: 2px solid #c7d0da; background: #FFFFFF; font-family: "Roboto"; font-size: 26px; color: #8a96a3; }
    .X-in div.f i { display: block; width: 3px; height: 34px; margin-right: 6px; background: #152235; }
    #X-steps { position: absolute; left: 80px; top: 480px; }
    .X-sp { display: flex; align-items: center; gap: 22px; height: 70px; font-family: "Roboto"; font-weight: 500; font-size: 32px; color: #5b6f86; }
    .X-sp u { display: block; width: 22px; height: 22px; border-radius: 11px; border: 3px solid #1EAAE2; background: #06111F; }
    .X-sp.on { color: #FFFFFF; } .X-sp.on u { background: #1EAAE2; }
    #X-sline { position: absolute; left: 90px; top: 515px; width: 3px; height: 140px; background: #1EAAE2; transform-origin: 50% 0; }
''', '''    <div class="X-bgd"></div>
''' + statement('04 — PARCOURS', 'Une information', 'à portée de clic.', 80, 150) + '''    <div id="X-sline"></div>
    <div id="X-steps">
      <div class="X-sp on" id="X-p0"><u></u>Services</div>
      <div class="X-sp" id="X-p1"><u></u>Départs</div>
      <div class="X-sp" id="X-p2"><u></u>Suivi</div>
    </div>
    <div class="X-br" id="X-vp"><div class="X-brt"><u></u><u></u><u></u><b>ktf-shipping.com</b></div>
      <div class="X-brv" style="height:796px"><div id="X-pg">
        <div class="X-sec" id="X-dep">
          <div class="X-kick"><i></i>CONSULTER</div>
          <div class="X-sh" style="margin-top:14px">Nos <em>départs</em></div>
          ''' + deps + '''
        </div>
        <div class="X-sec" id="X-trk" style="background:#06111F">
          <div class="X-kick"><i></i>SUIVI</div>
          <div class="X-sh" style="margin-top:14px; color:#fff">Suivre <em>mon envoi</em></div>
          <div class="X-in"><div class="f" id="X-fld"><i id="X-caret"></i>Numéro de suivi</div><div class="X-btn" id="X-tb" style="height:76px">''' + TARGET + '''Suivre</div></div>
          <div style="height:420px"></div>
        </div>
      </div></div></div>
    <div class="X-cur" id="X-cur">''' + CURSOR + '''</div>
''', st_in(0.3) + '''      tl.fromTo(R("#X-vp"), { opacity: 0, x: 60 }, { opacity: 1, x: 0, duration: 0.7, ease: "power3.out" }, 0.6);
      tl.fromTo(R("#X-steps"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 1.2);
      tl.fromTo(R("#X-sline"), { scaleY: 0 }, { scaleY: 0, duration: 0.01 }, 0);
      RA(".X-dr").forEach((el, i) => tl.fromTo(el, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, 1.3 + i * 0.12));
      // cursor → departures
      tl.fromTo(R("#X-cur"), { x: 900, y: 1820, opacity: 0 }, { x: 890, y: 1195, opacity: 1, duration: 1.0, ease: "power2.inOut" }, 2.1);
      tl.to(R("#X-sline"), { scaleY: 0.5, duration: 0.5, ease: "power2.out" }, 2.6);
      tl.set(R("#X-p1"), { className: "X-sp on" }, 2.9);
      tl.to(RA(".X-dv")[0], { backgroundColor: "#1EAAE2", color: "#FFFFFF", duration: 0.2 }, 3.1);
      tl.to(R("#X-cur"), { scale: 0.85, duration: 0.1, yoyo: true, repeat: 1 }, 3.1);
      // scroll to the tracking entry
      tl.to(R("#X-pg"), { y: -470, duration: 1.4, ease: "power2.inOut" }, 4.4);
      tl.to(R("#X-cur"), { x: 460, y: 1400, duration: 1.2, ease: "power2.inOut" }, 5.6);
      tl.to(R("#X-sline"), { scaleY: 1, duration: 0.5, ease: "power2.out" }, 6.2);
      tl.set(R("#X-p2"), { className: "X-sp on" }, 6.5);
      tl.to(R("#X-cur"), { scale: 0.85, duration: 0.1, yoyo: true, repeat: 1 }, 6.9);
      tl.to(R("#X-fld"), { borderColor: "#1EAAE2", duration: 0.2 }, 7.0);
      tl.fromTo(R("#X-caret"), { opacity: 0 }, { opacity: 1, duration: 0.01, repeat: 7, yoyo: true, repeatDelay: 0.45 }, 7.1);
      tl.to(R("#X-cur"), { opacity: 0, duration: 0.4 }, 9.8);
''')
# ── 05 · Un parcours vers l'action (38–50) ───────────────────────────────
PATH5 = 'M 120 540 V 1060'
F['05-action'] = ('''
    #X-r5 { position: absolute; left: 0; top: 0; }
    .X-lb { position: absolute; left: 170px; font-family: "Oswald"; font-weight: 500; font-size: 48px; color: #152235; text-transform: uppercase; white-space: nowrap; }
    #X-cta { position: absolute; left: 170px; top: 1090px; }
    #X-cta .X-btn { font-size: 28px; padding: 26px 44px; }
    #X-dsk { left: 80px; top: 480px; width: 920px; height: 600px; }
    #X-ph { position: absolute; left: 390px; top: 1130px; width: 300px; height: 640px; border-radius: 40px; border: 10px solid #152235; background: #06111F; overflow: hidden; box-shadow: 0 40px 90px rgba(21,34,53,0.35); }
    #X-ph .X-site { width: 280px; }
    #X-ph .X-hd { height: 76px; padding: 0 18px; }
    #X-ph .X-hd img { height: 48px; }
    #X-ph .X-hero { height: 760px; padding: 60px 22px 0; }
    #X-ph .X-hk { font-size: 13px; letter-spacing: 0.2em; gap: 10px; } #X-ph .X-hk i { width: 30px; }
    #X-ph .X-ht { font-size: 36px; margin-top: 18px; white-space: normal; }
    #X-ph .X-hp { font-size: 17px; } #X-ph .X-hb { flex-direction: column; gap: 12px; margin-top: 22px; }
    #X-ph .X-btn { font-size: 14px; padding: 14px 18px; }
    #X-burger { margin-left: auto; width: 44px; height: 44px; border: 2px solid #e3eaf2; border-radius: 4px; display: flex; flex-direction: column; justify-content: center; gap: 6px; padding: 0 9px; }
    #X-burger i { display: block; height: 3px; background: #152235; }
''', '''    <div class="X-bgl"></div>
''' + statement('05 — ACTION', 'Un parcours', "vers l'action.", 80, 150, dark=False) + '''    <svg id="X-r5" width="1080" height="1920" viewBox="0 0 1080 1920">
      <path id="X-p5" d="''' + PATH5 + '''" stroke="#1EAAE2" stroke-width="5" fill="none" stroke-linecap="round"/>
      <circle id="X-d0" cx="120" cy="560" r="14" fill="#1EAAE2"/><circle id="X-d1" cx="120" cy="720" r="14" fill="#1EAAE2"/><circle id="X-d2" cx="120" cy="880" r="14" fill="#1EAAE2"/><circle id="X-d3" cx="120" cy="1140" r="16" fill="#F07828"/></svg>
    <div id="X-steps5">
      <div class="X-lb" id="X-l0" style="top:526px">Services</div>
      <div class="X-lb" id="X-l1" style="top:686px">Départs</div>
      <div class="X-lb" id="X-l2" style="top:846px">Suivi</div>
    </div>
    <div id="X-cta"><div class="X-btn" id="X-cb">Demander un devis ''' + ARROW + '''</div></div>
    <div class="X-cur" id="X-cur">''' + CURSOR + '''</div>
    <div class="X-br" id="X-dsk"><div class="X-brt"><u></u><u></u><u></u><b>ktf-shipping.com</b></div>
      <div class="X-brv" style="height:556px"><div class="X-site" style="transform: scale(0.6389)">''' + site_html('05') + '''</div></div></div>
    <div id="X-ph"><div class="X-site"><div class="X-hd"><img src="assets/images/ktf-logo.png" alt="KTF"><div id="X-burger"><i></i><i></i><i></i></div></div><div class="X-bar"></div>
      <div class="X-hero"><div class="X-hk"><i></i>SOLUTIONS LOGISTIQUES</div><div class="X-ht"><em>TRANSPORT</em> AÉRIEN, MARITIME &amp; ROUTIER</div><div class="X-fil" style="margin-top:18px"><i style="width:60px"></i><u style="width:10px;height:10px"></u></div>
      <div class="X-hp">KTF Shipping, votre partenaire de confiance entre l'Europe et toute l'Afrique de l'Ouest.</div><div class="X-hb"><div class="X-btn">''' + ARROW + '''Nos services</div><div class="X-btn ol">''' + TARGET + '''Suivre mon envoi</div></div></div></div></div>
''', st_in(0.3) + '''      const p5 = R("#X-p5"), L5 = p5.getTotalLength();
      tl.fromTo(p5, { attr: { "stroke-dasharray": L5, "stroke-dashoffset": L5 } }, { attr: { "stroke-dashoffset": 0 }, duration: 2.4, ease: "power1.inOut" }, 0.8);
      [0, 1, 2].forEach((i) => {
        tl.fromTo(R("#X-d" + i), { opacity: 0, scale: 0, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, 0.8 + i * 0.75);
        tl.fromTo(R("#X-l" + i), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.45, ease: "power2.out" }, 0.85 + i * 0.75);
      });
      tl.fromTo(R("#X-d3"), { opacity: 0, scale: 0, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)" }, 3.15);
      tl.fromTo(R("#X-cta"), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.5, ease: "power2.out" }, 3.25);
      tl.fromTo(R("#X-cur"), { x: 900, y: 1820, opacity: 0 }, { x: 470, y: 1140, opacity: 1, duration: 0.9, ease: "power2.inOut" }, 3.7);
      tl.to(R("#X-cur"), { scale: 0.85, duration: 0.1, yoyo: true, repeat: 1 }, 4.65);
      tl.to(R("#X-cb"), { backgroundColor: "#1590C2", boxShadow: "0 0 0 8px rgba(30,170,226,0.25)", duration: 0.2 }, 4.65);
      // wide view, then the vertical composition: same markers on both formats
      tl.to([R("#X-r5"), R("#X-steps5"), R("#X-cta"), R("#X-cur")], { opacity: 0, duration: 0.5, ease: "power2.in" }, 5.6);
      tl.fromTo(R("#X-dsk"), { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }, 6.0);
      tl.fromTo(R("#X-ph"), { opacity: 0, y: 80 }, { opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }, 7.6);
      ''')
# ── 06 · Découvrez ktf-shipping.com (50–60) ──────────────────────────────
F['06-adresse'] = ('''
    #X-big { left: 60px; top: 480px; width: 960px; height: 900px; }
    #X-pg6 { position: absolute; left: 0; top: 0; }
    .X-svc { background: #FFFFFF; padding: 90px 80px 120px; text-align: center; }
    .X-svc .X-st { font-size: 76px; color: #152235; }
    .X-svc .X-cr { display: flex; gap: 34px; margin-top: 60px; }
    .X-svc .X-cr div.k { flex: 1; height: 300px; border-radius: 18px; background: #F4F8FC; border: 1px solid #E3EAF2; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 22px; }
    #X-white { position: absolute; inset: 0; background: #FFFFFF; }
    #X-lg { position: absolute; left: 50%; top: 50%; width: 860px; height: 286px; margin: -143px 0 0 -430px; }
    #X-lg img { display: block; width: 100%; }
    #X-url { position: absolute; left: 0; right: 0; top: 820px; text-align: center; font-family: "Oswald"; font-weight: 600; font-size: 112px; letter-spacing: 0.01em; color: #152235; }
    #X-url em { font-style: normal; color: #1EAAE2; }
    #X-uf { position: absolute; left: 0; right: 0; top: 1000px; display: flex; justify-content: center; }
''', '''    <div class="X-bgd"></div>
    <div class="X-br" id="X-big"><div class="X-brt"><u></u><u></u><u></u><b>ktf-shipping.com</b></div>
      <div class="X-brv" style="height:856px"><div id="X-pg6"><div class="X-site" style="position:relative; transform: scale(0.6667)">''' + site_html('06') + '''
        <div class="X-svc"><div class="X-kick" style="justify-content:center"><i></i>CE QUE NOUS FAISONS</div><div class="X-st" style="margin-top:18px">Nos <em>services</em> logistiques</div>
          <div class="X-cr">''' + ''.join(f'<div class="k"><div class="X-ic">{ICON[k]}</div><div class="X-ct" style="font-size:34px">{t}</div></div>' for k, t in CARDS) + '''</div></div>
      </div></div></div></div>
    <div id="X-white"></div>
    <div id="X-lg"><img src="assets/images/ktf-logo.png" alt="KTF Shipping"></div>
    <div id="X-url">ktf-shipping<em>.com</em></div>
    <div id="X-uf"><div class="X-fil"><i style="width:160px"></i><u class="o"></u></div></div>
''', '''      tl.fromTo(R("#X-big"), { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.6, ease: "power2.out" }, 0.0);
      tl.to(R("#X-pg6"), { y: -110, duration: 2.6, ease: "power1.inOut" }, 0.6);
      tl.fromTo(R("#X-white"), { opacity: 0 }, { opacity: 1, duration: 0.6, ease: "power2.inOut" }, 3.4);
      tl.fromTo(R("#X-lg"), { opacity: 0, scale: 0.92 }, { opacity: 1, scale: 1, duration: 0.7, ease: "power2.out" }, 3.8);
      tl.to(R("#X-lg"), { opacity: 0, duration: 0.45, ease: "power2.in" }, 5.4);
      tl.fromTo(R("#X-url"), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 5.85);
      tl.fromTo(R("#X-uf"), { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, duration: 0.5, ease: "power2.out" }, 6.1);
''')

def frame(fid, dur, css, html, js):
    pre = 'k' + fid[:2]
    sub = lambda s: s.replace('X-', pre + '-')
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; font-family: "Roboto", sans-serif; color: #FFFFFF; }}
{sub(CSS)}
{sub(css)}
  </style>
  <div id="root" data-composition-id="{fid}" data-start="0" data-duration="{dur}" data-width="{W}" data-height="{H}">
    <div id="{pre}-bgclip" class="clip" data-start="0" data-duration="{dur}" data-track-index="0" style="position:absolute; inset:0"></div>
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
    dur = ln + (OV if i < len(SC) - 1 else 0)
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(frame(fid, dur, css, html, js))
    scenes += f'''      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{i % 2}"></div>\n'''
    if i > 0:
        if fid == '03-offre':   # the one marked transition: a light panel wipes in behind a blue filet
            trans += f'''        tl.fromTo("#el-{fid}", {{ clipPath: "inset(0% 100% 0% 0%)" }}, {{ clipPath: "inset(0% 0% 0% 0%)", duration: {OV + 0.2}, ease: "power3.inOut" }}, {st - 0.2});\n'''
        else:
            trans += f'''        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {OV}, ease: "power2.inOut" }}, {st});\n'''
# discreet clicks on the three cursor presses (scene-relative times + scene start)
clicks = [27 + 3.1, 27 + 6.9, 38 + 4.65]
cl = ''.join(f'''      <audio id="el-click{i}" src="assets/click.wav" data-start="{t}" data-duration="0.2" data-track-index="{12 + i}" data-volume="0.5"></audio>\n''' for i, t in enumerate(clicks))
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #06111F; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
{scenes}
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="0.55"></audio>
{cl}    </div>
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
