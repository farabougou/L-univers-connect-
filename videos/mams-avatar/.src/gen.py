# « Mams, le motion designer masqué » : présentation TikTok (19 s, 1080×1920) sur la voix off ElevenLabs.
# Idée maîtresse : le masque n'a pas de bouche, alors le M du masque s'allume au rythme de la voix.
# Profondeur : studio flou (fond) < « MAMS » géant qui défile derrière lui < personnage détouré < M néon et son halo
# < écrans flottants (ses vraies pubs). Tout le texte vit dans une seule zone basse, au-dessus de l'interface TikTok.
# Calques préparés par prep.py, sons par sfx.py, musique par ../motion-reel/.src/beat120.py (couchée sous la voix).
import os, json, html
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 60
V0 = 1.0                    # la voix démarre après l'allumage du néon
VEND = round(V0 + 15.8, 2)  # fin de la voix : carte finale
TOTAL = 19.0
ORANGE, BLUE, INK, CREAM = '#FF4F1F', '#2340FF', '#141414', '#F3EBDD'
ENV = json.load(open(f'{P}/.src/env.json'))
FLICK = json.load(open(f'{P}/.src/flick.json'))
M_PATH = 'M 6 88 L 22 41 C 25 32, 33 30, 38 38 L 46 52 C 50 59, 56 59, 61 53 L 91 15 C 96 9, 102 11, 102 18 L 104 89'

# sous-titres : (mot, temps dans la vidéo, mot clé) ; les temps viennent de la transcription (+ V0)
CAPS = [
    [('et', 3.24), ('vous', 3.41), ("n'avez", 3.64), ('jamais', 4.02)],
    [('vu', 4.42), ('mon', 4.55), ('visage.', 4.75, 1)],
    [('Et', 5.32), ('ça', 5.37), ('ne', 5.50), ('va', 5.62), ('pas', 5.77), ('changer.', 5.96, 1)],
    [('Je', 8.12), ('crée', 8.17), ('des', 8.42), ('pubs', 8.62, 1), ('vidéo,', 8.87, 1)],
    [('des', 9.36), ('sites', 9.51, 1), ('internet', 9.79, 1)],
    [('et', 10.02), ('des', 10.45), ('applis', 10.50, 1), ('mobiles,', 10.81, 1)],
    [('100 %', 11.20, 1), ('en', 11.98), ('code.', 12.05)],
    [('Votre', 12.78), ('prochaine', 13.02), ('pub ?', 13.56, 1)],
    [("C'est", 13.88), ('peut-être', 14.14), ('moi', 14.61, 1), ('qui', 14.71), ('la', 14.78), ('ferai.', 15.13)],
    [('Écrivez-moi', 15.57), ('en', 16.07), ('message.', 16.21, 1)],
]
CAP_END = [c[0][1] for c in CAPS[1:]] + [VEND]
CAP_END[2] = 6.70           # « changer » s'efface avant la carte de nom
CAP_END[6] = 12.70
# écrans flottants : vraie vidéo, marque, côté, entrée, sortie
CARDS = [('pubs', 'Nessa Paris', 'L', 8.62, 10.40), ('site', 'KTF Shipping', 'R', 9.51, 12.55), ('appli', 'KOFA', 'L', 10.50, 12.60)]

def cap_html(i, words):
    out, j = [], 0
    while j < len(words):
        if len(words[j]) > 2:  # mots clés consécutifs dans une seule boîte
            k = j
            while k < len(words) and len(words[k]) > 2: k += 1
            out.append('<span class="kw">' + ' '.join(f'<span class="w" data-t="{w[1]}">{html.escape(w[0])}</span>' for w in words[j:k]) + '</span>')
            j = k
        else:
            out.append(f'<span class="w" data-t="{words[j][1]}">{html.escape(words[j][0])}</span>'); j += 1
    return f'<div class="cap" id="cp{i}">' + ' '.join(out) + '</div>'
caps = '\n        '.join(cap_html(i, c) for i, c in enumerate(CAPS))
cards = ''.join(f'''
          <div class="card {side}" id="cd{i}"><video id="cv{i}" class="clip cvid" src="assets/clips/{k}.mp4" data-start="{t0}" data-duration="{round(t1 - t0 + 0.1, 2)}" data-track-index="{4 + i}" muted playsinline></video><span class="tag">{name}</span></div>'''
                for i, (k, name, side, t0, t1) in enumerate(CARDS))
logo = f'<svg viewBox="-12 -12 140 120" width="{{w}}" height="{{h}}"><defs><filter id="lg{{i}}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter></defs><path class="mdraw" d="{M_PATH}" fill="none" stroke="{ORANGE}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round" opacity="0.7" filter="url(#lg{{i}})" pathLength="100"/><path class="mdraw" d="{M_PATH}" fill="none" stroke="#FF6A3A" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" pathLength="100"/><path class="mdraw" d="{M_PATH}" fill="none" stroke="#FFD3B5" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" pathLength="100"/></svg>'
slots = ''.join(f'<span class="dg{" sp" if c == " " else ""}" id="dg{i}"></span>' for i, c in enumerate('55 000'))

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
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      .L {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      .L img {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #Lbg, #Lsub {{ filter: brightness(1); }}
      #Lbloom, #Lspill {{ mix-blend-mode: screen; }}
      #spill {{ position: absolute; left: 140px; top: 260px; width: 760px; height: 760px; border-radius: 50%; background: radial-gradient(closest-side, rgba(255,110,50,0.55), rgba(255,79,31,0.18) 55%, rgba(255,79,31,0)); }}
      #mq {{ position: absolute; left: 0; top: 300px; font: 400 520px/1 "Archivo Black"; color: {ORANGE}; letter-spacing: -0.03em; white-space: nowrap; opacity: 0; }}
      .card {{ position: absolute; top: 410px; width: 290px; height: 516px; border-radius: 24px; overflow: visible; opacity: 0; }}
      .card.L {{ left: 36px; }} .card.R {{ left: 754px; }}
      .cvid {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; border-radius: 24px; box-shadow: 0 0 0 3px rgba(243,235,221,0.9), 0 2px 4px rgba(0,0,0,0.4), 0 18px 40px rgba(0,0,0,0.45), 0 50px 90px rgba(0,0,0,0.35); }}
      .tag {{ position: absolute; left: 50%; bottom: -24px; transform: translateX(-50%); padding: 10px 22px; border-radius: 30px; background: {CREAM}; color: #111; font: 800 26px "Inter"; white-space: nowrap; box-shadow: 0 8px 20px rgba(0,0,0,0.4); }}
      #vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse 80% 60% at 50% 38%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%), linear-gradient(rgba(0,0,0,0) 48%, rgba(0,0,0,0.62) 72%, rgba(0,0,0,0.7) 100%); }}
      /* zone de texte unique, au-dessus de l'interface TikTok */
      .cap {{ position: absolute; left: 70px; right: 70px; top: 1190px; text-align: center; font: 400 84px/1.1 "Archivo Black"; color: {CREAM}; letter-spacing: -0.01em; text-shadow: 0 4px 22px rgba(0,0,0,0.65); }}
      .cap .w {{ display: inline-block; }}
      .kw {{ display: inline-block; padding: 2px 16px 6px; margin: 0 -2px; border-radius: 10px; background: {ORANGE}; color: {INK}; text-shadow: none; }}
      .serif {{ font: italic 400 72px/1 "Instrument Serif"; }}
      #h1a {{ position: absolute; left: 0; right: 0; top: 1060px; text-align: center; color: {CREAM}; text-shadow: 0 4px 18px rgba(0,0,0,0.6); }}
      #cnt {{ position: absolute; left: 0; right: 0; top: 1140px; text-align: center; font: 400 230px/1 "Archivo Black"; color: {CREAM}; text-shadow: 0 6px 30px rgba(0,0,0,0.6); white-space: nowrap; }}
      .dg {{ display: inline-block; width: 0.7em; text-align: center; }} .dg.sp {{ width: 0.26em; }}
      #h1b {{ position: absolute; left: 0; right: 0; top: 1385px; text-align: center; color: {ORANGE}; text-shadow: 0 4px 18px rgba(0,0,0,0.6); }}
      #n1 {{ position: absolute; left: 0; right: 0; top: 1060px; text-align: center; color: {CREAM}; text-shadow: 0 4px 18px rgba(0,0,0,0.6); }}
      #n2 {{ position: absolute; left: 0; right: 0; top: 1140px; display: flex; justify-content: center; align-items: center; gap: 26px; }}
      #n2 b {{ font: 400 210px/1 "Archivo Black"; color: {CREAM}; letter-spacing: -0.03em; text-shadow: 0 6px 30px rgba(0,0,0,0.6); }}
      #n3 {{ position: absolute; left: 0; right: 0; top: 1375px; text-align: center; color: {ORANGE}; text-shadow: 0 4px 18px rgba(0,0,0,0.6); }}
      #e1 {{ position: absolute; left: 0; right: 0; top: 990px; display: flex; justify-content: center; }}
      #e2 {{ position: absolute; left: 0; right: 0; top: 1190px; text-align: center; font: 400 140px/1 "Archivo Black"; color: {CREAM}; letter-spacing: -0.02em; text-shadow: 0 6px 30px rgba(0,0,0,0.6); white-space: nowrap; }}
      #e3 {{ position: absolute; left: 0; right: 0; top: 1370px; text-align: center; font: 500 26px "Plex Mono"; letter-spacing: 0.2em; color: {CREAM}; opacity: 0.85; }}
      .mdraw {{ stroke-dasharray: 100 100; stroke-dashoffset: 100; }}
      #n2 svg, #e1 svg {{ visibility: hidden; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div class="L" id="Lbg"><img src="assets/images/bg.jpg" alt="" /></div>
        <div class="L" id="Lmq"><div id="mq" data-layout-allow-overflow>MAMS — MAMS — MAMS — MAMS — MAMS —</div></div>
        <div class="L" id="Lsub"><img src="assets/images/subject.png" alt="" /></div>
        <div class="L" id="Lm"><img id="mlit" src="assets/images/mlit.png" alt="" style="opacity:0" /></div>
        <div class="L" id="Lbloom"><img id="mbloom" src="assets/images/mbloom.jpg" alt="" style="opacity:0" /></div>
        <div class="L" id="Lspill"><div id="spill" style="opacity:0"></div></div>
        <div id="vig"></div>
        <div class="L" id="Lcards">{cards}
        </div>
        <div id="h1a" class="serif">Vous êtes</div>
        <div id="cnt">{slots}</div>
        <div id="h1b" class="serif">à me suivre…</div>
        {caps}
        <div id="n1" class="serif">Moi, c'est</div>
        <div id="n2">{logo.format(w=190, h=163, i=1)}<b id="nm">MAMS</b></div>
        <div id="n3" class="serif">motion designer</div>
        <div id="e1">{logo.format(w=220, h=189, i=2)}</div>
        <div id="e2">@kofamali</div>
        <div id="e3">TIKTOK · SITES · APPLIS · PUBS VIDÉO</div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.06"></canvas>
      </div>
      <audio id="voice" src="assets/voice/voice.wav" data-start="{V0}" data-duration="15.8" data-track-index="10" data-volume="1"></audio>
      <audio id="music" src="assets/music.wav" data-start="0.9" data-duration="{round(TOTAL - 0.9, 2)}" data-track-index="11" data-volume="0.6"></audio>
      <audio id="sfxon" src="assets/sfx/neon-on.wav" data-start="0.12" data-duration="1.0" data-track-index="12" data-volume="0.5"></audio>
      <audio id="sfxgl" src="assets/sfx/neon-glitch.wav" data-start="5.96" data-duration="0.7" data-track-index="13" data-volume="0.4"></audio>
      <audio id="sfxw0" src="assets/sfx/whoosh.wav" data-start="8.55" data-duration="0.55" data-track-index="14" data-volume="0.3"></audio>
      <audio id="sfxw1" src="assets/sfx/whoosh.wav" data-start="9.44" data-duration="0.55" data-track-index="15" data-volume="0.3"></audio>
      <audio id="sfxw2" src="assets/sfx/whoosh.wav" data-start="10.43" data-duration="0.55" data-track-index="16" data-volume="0.3"></audio>
      <audio id="sfxim" src="assets/sfx/impact.wav" data-start="{VEND}" data-duration="1.2" data-track-index="17" data-volume="0.45"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }}), cl = (x) => Math.min(1, Math.max(0, x)), once = {{ immediateRender: false }};
        const V0 = {V0}, VEND = {VEND}, TOTAL = {TOTAL}, ENV = {json.dumps(ENV)}, FLICK = {json.dumps(FLICK)};
%%JS%%
        tl.to({{}}, {{ duration: TOTAL }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
  </body>
</html>
'''
JS = r'''
        // ── la voix allume le M : enveloppe de la voix + allumage du néon + accents (« changer », « moi ») ──
        const env = (t) => { const i = (t - V0) * 60; if (i < 0 || i >= ENV.length - 1) return 0; const k = Math.floor(i), f = i - k; return ENV[k] * (1 - f) + ENV[k + 1] * f; };
        const inSteps = (steps, x) => steps.some(([a, b]) => x >= a && x < b);
        const mlit = $("#mlit"), mbloom = $("#mbloom"), spill = $("#spill");
        const neon = (t) => {
          let lit;
          if (t < 1.12) lit = inSteps(FLICK.on, t - 0.12) ? 1 : 0.04;                       // allumage du tube
          else if (t >= VEND) lit = 0.88 + 0.12 * Math.sin((t - VEND) * 3.2);                  // carte finale : il respire
          else lit = 0.32 + 0.68 * env(t);
          if (t >= 5.96 && t < 6.66) lit *= inSteps(FLICK.glitch, t - 5.96) ? 1.15 : 0.15;    // « changer » : il grésille
          lit += 0.5 * Math.exp(-Math.max(0, t - 14.61) * 5) * (t >= 14.61 ? 1 : 0);           // « moi » : éclat
          lit = Math.min(1.25, lit);
          mlit.style.opacity = Math.min(1, lit).toFixed(3);
          mbloom.style.opacity = Math.min(1.2, Math.pow(lit, 1.4) * 1.05).toFixed(3);
          mbloom.style.transform = "scale(" + (1 + 0.035 * lit).toFixed(4) + ")";
          spill.style.opacity = (t < 1.12 ? 0.25 * lit : 0.18 + 0.42 * env(t)).toFixed(3);
        };

        // ── lumière de la pièce : noir au départ, le studio s'allume après le néon ; pénombre sur la carte finale ──
        tl.set(["#Lbg", "#Lsub"], { filter: "brightness(0.05)" }, 0);
        tl.fromTo(["#Lbg", "#Lsub"], { filter: "brightness(0.05)" }, { filter: "brightness(1)", duration: 1.0, ease: S.ease.silk }, 0.62);
        tl.fromTo(["#Lbg", "#Lsub"], { filter: "brightness(1)" }, { filter: "brightness(0.42)", duration: 0.7, ease: S.ease.glide, ...once }, VEND);

        // ── caméra : rapprochée à l'allumage, recule, pousse sur « visage », claque sur « changer », recule pour
        //    le nom et les écrans, pousse sur la question, recule pour la fin. Point fixe : le masque. ──
        const F = (s) => ({ s, x: 35 * (s - 1), y: 360 * (s - 1) });
        const k = (t, s, ease) => Object.assign({ t, ease }, F(s));
        S.camera(tl, [{ el: $("#Lbg"), depth: 0.55 }, { el: $("#Lmq"), depth: 0.75 }, { el: $("#Lsub"), depth: 1 }, { el: $("#Lm"), depth: 1 },
                      { el: $("#Lbloom"), depth: 1 }, { el: $("#Lspill"), depth: 1 }, { el: $("#Lcards"), depth: 1.2 }], {
          keys: [k(0, 1.1), k(1.0, 1.1), k(2.7, 1.0), k(4.2, 1.0), k(5.3, 1.09), k(5.96, 1.09), k(6.25, 1.17, S.ease.swift), k(6.6, 1.17),
                 k(7.5, 1.0), k(12.7, 1.02), k(15.5, 1.12), k(16.8, 1.12), k(17.6, 1.03), k(TOTAL, 1.045)],
          drift: { x: 4, y: 3, r: 0.1, period: 8 }, start: 0, end: TOTAL });

        // ── « Vous êtes 55 000 à me suivre… » : compteur à chiffres fixes (pas de tremblement de largeur) ──
        S.rise(tl, "#h1a", 1.08, { y: 18, blur: 8, duration: 0.6 });
        S.rise(tl, "#cnt", 1.5, { y: 30, blur: 10, duration: 0.6 });
        const dg = $$("#cnt .dg");
        const counter = (t) => {
          const v = Math.round(55000 * S.ease.silk(cl((t - 1.54) / 1.05)));
          const s = v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ").padStart(6, " ");
          dg.forEach((el, i) => { el.textContent = s[i] === " " ? " " : s[i]; });
        };
        S.rise(tl, "#h1b", 2.56, { y: 18, blur: 8, duration: 0.6 });
        S.leave(tl, ["#h1a", "#cnt", "#h1b"], 3.08, { y: -24, duration: 0.18, stagger: 0.03 });

        // ── sous-titres : chaque mot arrive à son temps, la phrase s'efface juste avant la suivante ──
        const CAPEND = CAP_END;
        $$(".cap").forEach((cap, i) => {
          tl.set(cap, { autoAlpha: 0 }, 0); tl.set(cap, { autoAlpha: 1 }, +cap.querySelector(".w").dataset.t - 0.01);
          cap.querySelectorAll(".w").forEach((w) => tl.fromTo(w, { opacity: 0, y: 26, filter: "blur(6px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.24, ease: S.ease.swift }, +w.dataset.t));
          cap.querySelectorAll(".kw").forEach((b) => { const s = S.spring({ response: 0.32, damping: 0.62 }); tl.fromTo(b, { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, duration: s.duration, ease: s.ease }, +b.querySelector(".w").dataset.t); });
          S.leave(tl, cap, CAPEND[i] - 0.17, { y: -22, duration: 0.16 });
        });

        // ── « Moi, c'est MAMS » : le nom, le M qui se dessine, « motion designer » ; MAMS géant défile derrière lui ──
        S.rise(tl, "#n1", 6.72, { y: 18, blur: 8, duration: 0.5 });
        S.converge(tl, S.split($("#nm")), 7.40, { spread: 40, duration: 0.7, stagger: 0.04 });
        tl.set("#n2 svg", { visibility: "visible" }, 7.36);
        tl.fromTo("#n2 .mdraw", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.55, ease: S.ease.glide }, 7.36);
        S.rise(tl, "#n3", 7.62, { y: 18, blur: 8, duration: 0.5 });
        S.leave(tl, ["#n1", "#n2", "#n3"], 7.92, { y: -24, duration: 0.18, stagger: 0.03 });
        tl.set("#mq", { opacity: 0 }, 0);
        tl.fromTo("#mq", { opacity: 0 }, { opacity: 0.95, duration: 0.35, ease: S.ease.silk }, 7.30);
        tl.fromTo("#mq", { opacity: 0.95 }, { opacity: 0.38, duration: 0.6, ease: S.ease.glide, ...once }, 8.3);
        tl.fromTo("#mq", { opacity: 0.38 }, { opacity: 0, duration: 0.35, ease: S.ease.accel, ...once }, 12.4);
        const mq = $("#mq");
        const marquee = (t) => { mq.style.transform = "translateX(" + (-140 - Math.max(0, t - 7.3) * 230).toFixed(1) + "px)"; };

        // ── écrans flottants : ses vraies pubs arrivent sur le mot, sur ressort, puis vivent ──
        const cs = S.spring({ response: 0.5, damping: 0.72 });
        CARDSJS.forEach(([side, t0, t1], i) => {
          const el = "#cd" + i, dir = side === "L" ? -1 : 1, rot = side === "L" ? -6 + i * 1.5 : 6;
          tl.fromTo(el, { opacity: 0, x: 260 * dir, y: 60, rotation: rot + 22 * dir, scale: 0.8 }, { opacity: 1, x: 0, y: 0, rotation: rot, scale: 1, duration: cs.duration, ease: cs.ease }, t0);
          tl.fromTo(el, { opacity: 1, x: 0, rotation: rot }, { opacity: 0, x: 300 * dir, rotation: rot + 14 * dir, duration: 0.32, ease: S.ease.accel, ...once }, t1 - 0.32);
        });
        S.life(tl, $$(".card"), 8.6, 12.6, { x: 3, y: 6, rotate: 0.6, scale: 0.006, period: 4, seed: 11 });

        // ── carte finale : le M se dessine, @kofamali, ce qu'il fait ──
        tl.set("#e1 svg", { visibility: "visible" }, VEND + 0.05);
        tl.fromTo("#e1 .mdraw", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.7, ease: S.ease.glide }, VEND + 0.05);
        S.converge(tl, S.split($("#e2")), VEND + 0.3, { spread: 30, duration: 0.8, stagger: 0.03 });
        S.rise(tl, "#e3", VEND + 0.75, { y: 12, blur: 4, duration: 0.6 });

        S.drive(tl, 0, TOTAL, [neon, counter, marquee, S.grain($("#grain"), { fps: 60, seed: 4 })]);
'''
JS = (JS.replace('CAP_END', json.dumps([round(x, 2) for x in CAP_END]))
        .replace('CARDSJS', json.dumps([[side, t0, t1] for _, _, side, t0, t1 in CARDS])))
open(f'{P}/index.html', 'w').write(HTML.replace('%%JS%%', JS))
print('ok', TOTAL)
