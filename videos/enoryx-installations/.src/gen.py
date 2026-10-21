# Enoryx « sur de vraies installations » : pub verticale de 30 s, 100 BPM (1 temps = 0,6 s), coupes sur les temps.
# Histoire : la nuit, une chambre froide dérive ; Enoryx le voit, alerte, un technicien intervient avant la panne ;
# retour à la normale ; tous les équipements suivis en direct ; logo. Photos réelles (Wikimedia Commons) étalonnées
# par prep.py, données « en direct » accrochées aux équipements (cartes de verre, ligne de rappel, courbe vivante).
# Charte Enoryx (videos/enoryx-pub/frame.md) : bleu nuit, cyan, orange réservé à la dérive, vert à l'état normal,
# Inter 900 en minuscules, IBM Plex Mono en capitales. Musique : score.py.
import os, json, re
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, TOTAL, BEAT = 1080, 1920, 60, 30.0, 0.6
NAVY, NAVY2, CYAN, BLUE, ORANGE, GREEN, CREAM, MUTED, LINE = '#050B1A', '#0C1730', '#38BDF8', '#1D4ED8', '#EA580C', '#16A34A', '#F8FAFC', '#94A3B8', '#1E2A44'

# plans : id, photo, début, fin, zoom de départ, zoom d'arrivée, flou (téléphone par-dessus)
SC = [('s1', 'hk', 0.0, 3.0, 1.0, 1.08, 0), ('s2', 'fns', 3.0, 6.0, 1.02, 1.1, 0), ('s3', 'chiller', 6.0, 8.4, 1.0, 1.07, 0),
      ('s4', 'chiller', 8.4, 13.8, 1.07, 1.13, 1), ('s6', 'valve', 13.8, 16.2, 1.0, 1.06, 0), ('s7', 'fns', 16.2, 18.6, 1.1, 1.03, 0),
      ('s8a', 'rooftop', 18.6, 19.8, 1.0, 1.05, 0), ('s8b', 'dctower', 19.8, 21.0, 1.0, 1.05, 0), ('s8c', 'genset', 21.0, 22.2, 1.0, 1.05, 0),
      ('s8d', 'chiller', 22.2, 23.4, 1.0, 1.05, 0), ('s9', None, 23.4, 26.4, 1, 1, 0), ('s10', None, 26.4, TOTAL, 1, 1, 0)]
# titres : plan, temps, lignes (<em> cyan, <em class=o> orange), petite ligne au-dessus
HL = {'s1': (0.6, ['tout le monde dort.'], 'MARDI · 03:12'), 's2': (3.2, ['sauf votre', '<em class="o">chambre froide.</em>'], None),
      's3': (6.2, ['elle dérive.', 'personne ne le voit.'], None), 's4': (8.6, ['<em>enoryx</em> le voit.'], 'ALERTE EN DIRECT'),
      's6': (14.0, ['on intervient', '<em>avant</em> la panne.'], None), 's7': (16.4, ['retour à la normale.'], None),
      's9': (23.6, ['tous vos sites.', 'un seul écran.'], None)}
# données accrochées aux équipements : plan, début, cible (x, y), carte (x, y), étiquette, unité, valeurs [(t, v)] ou texte,
# états [(t, texte, ton)]
AR = [('s2', 3.4, (600, 820), (70, 380), 'CHAMBRE FROIDE 02', '°C', [(4.0, -18.0), (5.9, -14.6)], [(3.4, 'NORMAL', 'ok'), (4.7, 'DÉRIVE', 'warn')]),
      ('s3', 6.2, (560, 560), (430, 780), 'GROUPE FROID', 'kW', [(6.6, 13.0), (8.3, 17.9)], [(6.2, 'SURCHARGE', 'warn')]),
      ('s6', 14.0, (330, 690), (470, 330), 'INTERVENTION', '', 'clock', [(14.0, 'EN COURS', 'info')]),
      ('s7', 16.3, (600, 820), (70, 380), 'CHAMBRE FROIDE 02', '°C', [(16.4, -14.6), (17.7, -18.0)], [(16.3, 'RETOUR', 'info'), (17.5, 'NORMAL', 'ok')]),
      ('s8a', 18.7, (480, 990), (80, 520), 'UNITÉ DE TOITURE', 'kW', [(18.7, 4.2), (19.8, 4.2)], [(18.7, 'OK', 'ok')]),
      ('s8b', 19.9, (470, 420), (470, 700), 'CONDENSEURS', 'kW', [(19.9, 8.4), (21.0, 8.4)], [(19.9, 'OK', 'ok')]),
      ('s8c', 21.1, (190, 820), (440, 520), 'GROUPE ÉLECTROGÈNE', '', 'À L’ARRÊT', [(21.1, 'PRÊT', 'ok')]),
      ('s8d', 22.3, (560, 560), (430, 780), 'GROUPE FROID', 'kW', [(22.3, 13.0), (23.4, 13.0)], [(22.3, 'OK', 'ok')])]
TILES = [('Chambre froide 02', '−18,0 °C'), ('Groupe froid', '13,0 kW'), ('Condenseurs', '8,4 kW'), ('Unité de toiture', '4,2 kW'),
         ('Groupe électrogène', 'À l’arrêt'), ('Compteur général', '28,7 kW')]
CREDITS = 'PHOTOS RÉELLES RECADRÉES ET ÉTALONNÉES · ESO (CC BY 4.0) · MTA CAPITAL CONSTRUCTION (CC BY 2.0) · WIKIMEDIA COMMONS (DOMAINE PUBLIC, CC0)'

def atom(size, i, draw=True):
    orbs = ''.join(f'<ellipse class="orb{" mdraw" if draw else ""}" cx="0" cy="0" rx="100" ry="36" transform="rotate({a})" pathLength="100"/>' for a in (0, 60, 120))
    els = ''.join(f'<circle class="el" id="el{i}{k}" r="7"/>' for k in range(3)) if draw else ''
    return (f'<svg viewBox="-120 -120 240 240" width="{size}" height="{size}"><defs><radialGradient id="core{i}" cx="40%" cy="35%" r="65%">'
            f'<stop offset="0" stop-color="#E0F2FE"/><stop offset="0.35" stop-color="#7DD3FC"/><stop offset="0.75" stop-color="{BLUE}"/><stop offset="1" stop-color="#0B1E5B"/></radialGradient>'
            f'<filter id="gl{i}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>'
            f'<g filter="url(#gl{i})" opacity="0.8">{orbs}</g><g>{orbs}</g><circle class="core" r="34" fill="url(#core{i})"/>{els}</svg>')

def words(line):
    # un mot = un masque ; un passage <em> garde sa couleur mot par mot (découper la balise elle-même la casserait)
    out = []
    for tok in re.findall(r'<em[^>]*>.*?</em>|[^<\s]+', line):
        m = re.match(r'(<em[^>]*>)(.*?)</em>', tok)
        out += [f'{m.group(1)}{w}</em>' for w in m.group(2).split()] if m else [tok]
    return ' '.join(f'<span class=st-mask><span class=st-word>{w}</span></span>' for w in out)

def headline(sid):
    t, lines, kick = HL[sid]
    k = f'<div class="kick mono" id="k-{sid}">{kick}</div>' if kick else ''
    return f'<div class="hlz" id="h-{sid}">{k}' + ''.join(f'<div class="hl">{words(l)}</div>' for l in lines) + '</div>'

def ar_html(i, sid, t0, tgt, card, label, unit, vals, chips):
    tx, ty = tgt; cx, cy = card; cw, chh = 500, 236
    lx, ly = (cx + cw, cy + chh / 2) if cx + cw / 2 < tx else (cx, cy + chh / 2)
    return f'''
          <svg class="arl" width="{W}" height="{H}"><line id="ln{i}" x1="{tx}" y1="{ty}" x2="{lx}" y2="{ly}" pathLength="100"/></svg>
          <div class="tgt" id="tg{i}" style="left:{tx}px; top:{ty}px"><b></b><i></i></div>
          <div class="card" id="cd{i}" style="left:{cx}px; top:{cy}px">
            <div class="lab"><span class="live"></span>{label}</div>
            <div class="val"><span id="v{i}"></span><small>{unit}</small></div>
            <div class="row"><span class="chip" id="ch{i}"></span><svg class="spark" width="230" height="64"><polyline id="sp{i}" points=""/></svg></div>
          </div>'''

scenes = ''
for sid, ph, t0, t1, z0, z1, blur in SC:
    inner = ''
    if ph:
        inner += f'<div class="ph" id="ph-{sid}"><img src="assets/photos/{ph}.jpg" alt="" /></div><div class="tint" id="ti-{sid}"></div>'
    if sid == 's4':
        inner += '''<div id="phone"><div id="scr">
              <div class="sbar mono"><span>03:12</span><span>●●● 4G</span></div>
              <div class="apph"><span class="ax">AX</span><b>ENORYX</b><span class="live"></span></div>
              <div id="st1">
                <div class="acard warn"><div class="mono al">ALERTE · CHAMBRE FROIDE 02</div><div class="big">−14,6 <small>°C</small></div>
                  <svg width="440" height="110"><polyline id="psp" points=""/></svg><div class="msg">Température en hausse depuis 03:04. Intervention recommandée.</div></div>
                <div class="btn" id="pbtn">Créer un ordre de travail</div>
              </div>
              <div id="st2">
                <div class="mono al2">ORDRE DE TRAVAIL · CHAMBRE FROIDE 02</div>
                <div class="step" id="sp0"><i></i><div><b>Créé</b><span>03:12 · par Enoryx</span></div></div>
                <div class="step" id="sp1"><i></i><div><b>Assigné</b><span>Équipe maintenance</span></div></div>
                <div class="step" id="sp2"><i></i><div><b>En route</b><span>Arrivée estimée 03:40</span></div></div>
                <div class="step" id="sp3"><i></i><div><b>Clôturé</b><span>—</span></div></div>
                <div id="track"><div id="trackf"></div></div>
              </div>
              <div id="notif" data-layout-allow-overlap><span class="ax">AX</span><div><b>ENORYX · maintenant</b><span>Chambre froide 02 : −14,6 °C. Température en hausse.</span></div></div>
            </div></div>'''
    if sid == 's9':
        tiles = ''.join(f'<div class="tile" id="tl{i}"><div class="tn">{n}</div><div class="tv">{v}</div><span class="tdot"></span><svg width="180" height="44"><polyline id="ts{i}" points=""/></svg></div>' for i, (n, v) in enumerate(TILES))
        inner += f'''<div id="dash"><div class="mono dk">VUE D’ENSEMBLE · EN DIRECT</div><div id="tot"><span id="totv">0,0</span><small>kW</small></div>
              <div class="mono dk2">CONSOMMATION TOTALE</div><div id="tiles">{tiles}</div></div>'''
    if sid == 's10':
        inner += f'''<div id="logo">{atom(420, 'L')}</div><div id="word">ENORYX</div>
              <div id="tag">chaque <em>kilowattheure</em> compte.</div><div id="cta">demandez votre démo →</div>
              <div id="cred" class="mono">{CREDITS}</div>'''
    for i, a in enumerate(AR):
        if a[0] == sid: inner += ar_html(i, *a)
    if sid in HL: inner += headline(sid)
    if sid == 's8a': inner += f'<div class="hlz" id="h-s8"><div class="hl">{words("chaque équipement.")}</div><div class="hl" id="h-s8b">{words("<em>en temps réel.</em>")}</div></div>'
    scenes += f'\n        <div class="sc" id="{sid}">{inner}\n        </div>'

HTML = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      @font-face {{ font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 700; src: url("assets/fonts/inter-latin-700-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {NAVY}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {NAVY}; font-family: "Inter", sans-serif; color: {CREAM}; }}
      .mono {{ font-family: "Plex Mono", monospace; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; }}
      .sc {{ position: absolute; inset: 0; visibility: hidden; overflow: hidden; }}
      .ph {{ position: absolute; inset: 0; }}
      .ph img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; transform-origin: 594px 1056px; }}
      .tint {{ position: absolute; inset: 0; background: radial-gradient(ellipse 75% 60% at 50% 45%, rgba(5,11,26,0) 40%, rgba(5,11,26,0.55) 100%), linear-gradient(rgba(5,11,26,0) 52%, rgba(5,11,26,0.82) 76%, rgba(5,11,26,0.9) 100%); }}
      #ti-s2, #ti-s3 {{ box-shadow: inset 0 0 0 rgba(234,88,12,0); }}
      /* titres : une seule zone, au-dessus de l'interface TikTok */
      .hlz {{ position: absolute; left: 70px; right: 70px; top: 1250px; }}
      .hl {{ font: 900 96px/1.02 "Inter"; letter-spacing: -0.04em; color: {CREAM}; text-shadow: 0 6px 30px rgba(0,0,0,0.5); white-space: nowrap; }}
      .hl em {{ font-style: normal; color: {CYAN}; }} .hl em.o {{ color: #FB923C; }}
      .kick {{ font-size: 24px; color: {CYAN}; margin-bottom: 18px; }}
      #h-s8 {{ top: 1250px; }}
      /* habillage */
      #chrome {{ position: absolute; left: 70px; right: 70px; top: 250px; display: flex; justify-content: space-between; align-items: center; font-size: 22px; color: {CREAM}; }}
      #chrome .l {{ display: flex; align-items: center; gap: 14px; }}
      #chrome .l i {{ width: 12px; height: 12px; border-radius: 6px; background: {GREEN}; box-shadow: 0 0 12px {GREEN}; }}
      #hair {{ position: absolute; left: 70px; right: 70px; top: 296px; height: 1px; background: rgba(248,250,252,0.22); transform-origin: 0 50%; }}
      /* données accrochées aux équipements */
      .arl {{ position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }}
      .arl line {{ stroke: {CYAN}; stroke-width: 2.5; stroke-dasharray: 100 100; stroke-dashoffset: 100; filter: drop-shadow(0 0 6px rgba(56,189,248,0.8)); }}
      .tgt {{ position: absolute; width: 0; height: 0; }}
      .tgt b {{ position: absolute; left: -11px; top: -11px; width: 22px; height: 22px; border-radius: 11px; background: {CYAN}; box-shadow: 0 0 22px {CYAN}; }}
      .tgt i {{ position: absolute; left: -40px; top: -40px; width: 80px; height: 80px; border-radius: 40px; border: 3px solid {CYAN}; opacity: 0.7; }}
      .card {{ position: absolute; width: 500px; height: 236px; padding: 24px 28px; border-radius: 24px; background: rgba(12,23,48,0.72); border: 1.5px solid rgba(56,189,248,0.38);
               backdrop-filter: blur(16px); box-shadow: 0 2px 4px rgba(0,0,0,0.3), 0 20px 50px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08); }}
      .card .lab {{ display: flex; align-items: center; gap: 12px; font: 500 21px "Plex Mono"; letter-spacing: 0.14em; color: {CYAN}; white-space: nowrap; }}
      .live {{ width: 10px; height: 10px; border-radius: 5px; background: {GREEN}; box-shadow: 0 0 10px {GREEN}; }}
      .card .val {{ font: 900 84px/1 "Inter"; letter-spacing: -0.04em; margin-top: 14px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
      .card .val small {{ font-size: 40px; font-weight: 700; margin-left: 10px; color: {MUTED}; letter-spacing: 0; }}
      .card .row {{ display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }}
      .chip {{ padding: 8px 16px; border-radius: 20px; font: 700 20px "Inter"; letter-spacing: 0.06em; }}
      .chip.ok {{ background: rgba(22,163,74,0.18); color: #4ADE80; border: 1.5px solid rgba(74,222,128,0.5); }}
      .chip.warn {{ background: rgba(234,88,12,0.2); color: #FB923C; border: 1.5px solid rgba(251,146,60,0.6); }}
      .chip.info {{ background: rgba(56,189,248,0.16); color: {CYAN}; border: 1.5px solid rgba(56,189,248,0.5); }}
      .spark polyline, #psp, .tile polyline {{ fill: none; stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; }}
      #scan {{ position: absolute; left: 0; right: 0; top: 0; height: 220px; background: linear-gradient(rgba(56,189,248,0), rgba(56,189,248,0.22) 70%, rgba(186,230,253,0.55) 98%, rgba(56,189,248,0)); mix-blend-mode: screen; opacity: 0; }}
      #flash {{ position: absolute; inset: 0; background: #E0F2FE; opacity: 0; }}
      /* téléphone */
      #ph-s4 img {{ filter: blur(14px) brightness(0.45); }}
      #phone {{ position: absolute; left: 245px; top: 290px; width: 590px; height: 900px; border-radius: 70px; background: #0B1220; padding: 16px; box-shadow: 0 0 0 2px #26324A, 0 30px 80px rgba(0,0,0,0.6), 0 0 120px rgba(56,189,248,0.18); }}
      #scr {{ position: relative; width: 100%; height: 100%; border-radius: 56px; overflow: hidden; background: linear-gradient(#081329, #050B1A); }}
      .sbar {{ display: flex; justify-content: space-between; padding: 26px 40px 0; font-size: 20px; color: {MUTED}; }}
      .apph {{ display: flex; align-items: center; gap: 14px; padding: 26px 36px 10px; }}
      .apph b {{ font: 900 34px "Inter"; letter-spacing: 0.02em; color: {CREAM}; }}
      .apph .live {{ margin-left: auto; }}
      .ax {{ width: 46px; height: 46px; border-radius: 14px; background: radial-gradient(circle at 40% 35%, #7DD3FC, {BLUE} 70%); color: #fff; font: 900 18px "Inter"; display: flex; align-items: center; justify-content: center; }}
      #st1, #st2 {{ position: absolute; left: 30px; right: 30px; top: 170px; }}
      #st2 {{ opacity: 0; }}
      .acard {{ border-radius: 28px; padding: 26px; background: rgba(234,88,12,0.12); border: 1.5px solid rgba(251,146,60,0.55); }}
      .al, .al2 {{ font-size: 19px; color: #FB923C; }} .al2 {{ color: {CYAN}; margin-bottom: 24px; }}
      .big {{ font: 900 96px/1.05 "Inter"; letter-spacing: -0.04em; margin-top: 10px; }} .big small {{ font-size: 44px; color: {MUTED}; }}
      #psp {{ stroke: #FB923C; }}
      .msg {{ font: 600 24px/1.35 "Inter"; color: #E2E8F0; margin-top: 6px; }}
      .btn {{ margin-top: 26px; height: 92px; border-radius: 46px; background: {CYAN}; color: {NAVY}; font: 800 28px "Inter"; display: flex; align-items: center; justify-content: center; }}
      .step {{ display: flex; gap: 20px; align-items: center; height: 104px; }}
      .step i {{ width: 34px; height: 34px; border-radius: 17px; border: 3px solid #334155; background: transparent; flex: none; }}
      .step b {{ display: block; font: 800 30px "Inter"; color: {CREAM}; }} .step span {{ font: 600 22px "Inter"; color: {MUTED}; }}
      #track {{ position: absolute; left: 15px; top: 64px; width: 4px; height: 330px; background: #1E293B; }}
      #trackf {{ width: 100%; height: 100%; background: {CYAN}; transform-origin: 50% 0; transform: scaleY(0); }}
      #notif {{ position: absolute; left: 22px; right: 22px; top: 20px; display: flex; gap: 18px; align-items: center; padding: 22px; border-radius: 30px; background: rgba(30,41,59,0.92); border: 1.5px solid rgba(148,163,184,0.25); box-shadow: 0 20px 40px rgba(0,0,0,0.5); }}
      #notif b {{ display: block; font: 800 22px "Inter"; color: {CREAM}; }} #notif span {{ font: 600 22px/1.3 "Inter"; color: #CBD5E1; }}
      /* tableau de bord */
      #dash {{ position: absolute; inset: 0; background: radial-gradient(ellipse 90% 60% at 50% 30%, #0C1A3A, {NAVY} 70%); }}
      #dash::before {{ content: ""; position: absolute; inset: 0; background-image: linear-gradient(rgba(56,189,248,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.06) 1px, transparent 1px); background-size: 60px 60px; }}
      .dk {{ position: absolute; left: 70px; top: 270px; font-size: 22px; color: {CYAN}; }}
      #tot {{ position: absolute; left: 70px; top: 310px; font: 900 150px/1 "Inter"; letter-spacing: -0.05em; font-variant-numeric: tabular-nums; }}
      #tot small {{ font-size: 60px; color: {MUTED}; margin-left: 14px; letter-spacing: 0; }}
      .dk2 {{ position: absolute; left: 74px; top: 470px; font-size: 20px; color: {MUTED}; }}
      #tiles {{ position: absolute; left: 70px; top: 540px; width: 940px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
      .tile {{ position: relative; height: 196px; border-radius: 24px; padding: 22px 24px; background: rgba(12,23,48,0.85); border: 1.5px solid {LINE}; }}
      .tn {{ font: 600 23px "Inter"; color: {MUTED}; }} .tv {{ font: 900 52px/1.2 "Inter"; letter-spacing: -0.03em; margin-top: 8px; white-space: nowrap; }}
      .tdot {{ position: absolute; right: 24px; top: 26px; width: 14px; height: 14px; border-radius: 7px; background: {GREEN}; box-shadow: 0 0 12px {GREEN}; }}
      .tile svg {{ position: absolute; right: 18px; bottom: 16px; }} .tile polyline {{ stroke: {CYAN}; stroke-width: 3; opacity: 0.8; }}
      /* logo */
      #s10 {{ background: radial-gradient(ellipse 80% 55% at 50% 40%, #0C1A3A, {NAVY} 72%); }}
      #logo {{ position: absolute; left: 330px; top: 440px; }}
      .orb {{ fill: none; stroke: {CYAN}; stroke-width: 6; }}
      .mdraw {{ stroke-dasharray: 100 100; stroke-dashoffset: 100; }}
      .el {{ fill: #E0F2FE; filter: drop-shadow(0 0 6px {CYAN}); }}
      #word {{ position: absolute; left: 0; right: 0; top: 910px; text-align: center; font: 900 150px/1 "Inter"; letter-spacing: 0.04em; color: {CREAM}; }}
      #tag {{ position: absolute; left: 0; right: 0; top: 1100px; text-align: center; font: 900 60px "Inter"; letter-spacing: -0.02em; white-space: nowrap; }}
      #tag em {{ font-style: normal; color: {CYAN}; }}
      #cta {{ position: absolute; left: 50%; top: 1240px; transform: translateX(-50%); padding: 24px 48px; border-radius: 50px; border: 2px solid {CYAN}; color: {CYAN}; font: 800 36px "Inter"; white-space: nowrap; }}
      #cred {{ position: absolute; left: 90px; right: 90px; top: 1430px; text-align: center; font-size: 15px; line-height: 1.6; color: #64748B; letter-spacing: 0.08em; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">{scenes}
        <div id="scan"></div>
        <div id="chrome" class="mono"><div class="l"><i></i>ENORYX · EN DIRECT</div><div id="clock">03:12:00</div></div>
        <div id="hair"></div>
        <div id="flash"></div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.07"></canvas>
      </div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }}), cl = (x) => Math.min(1, Math.max(0, x)), once = {{ immediateRender: false }};
        const TOTAL = {TOTAL}, BEAT = {BEAT}, SC = {json.dumps(SC)}, AR = {json.dumps(AR, ensure_ascii=False)}, HL = {json.dumps({k: v[0] for k, v in HL.items()})};
%%JS%%
        tl.to({{}}, {{ duration: TOTAL }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
  </body>
</html>
'''
JS = r'''
        // ── plans : coupe franche sur le temps, mouvement de caméra lent sur chaque photo ──
        SC.forEach(([sid, ph, t0, t1, z0, z1]) => {
          tl.set("#" + sid, { visibility: "visible" }, t0); if (t1 < TOTAL) tl.set("#" + sid, { visibility: "hidden" }, t1);
          if (ph) tl.fromTo("#ph-" + sid + " img", { scale: z0, y: 0 }, { scale: z1, y: -24, duration: t1 - t0, ease: S.ease.glide }, t0);
        });
        tl.fromTo("#s1", { opacity: 0 }, { opacity: 1, duration: 0.9, ease: S.ease.silk }, 0);

        // ── titres : mots qui montent dans leur masque ──
        Object.entries(HL).forEach(([sid, t]) => {
          const k = $("#k-" + sid); if (k) S.rise(tl, k, t - 0.1, { y: 12, blur: 6, duration: 0.5 });
          S.maskUp(tl, $$("#h-" + sid + " .st-word"), t, { duration: 0.6, stagger: 0.07 });
        });
        S.maskUp(tl, $$("#h-s8 .hl:first-child .st-word"), 18.7, { duration: 0.6, stagger: 0.07 });
        S.maskUp(tl, $$("#h-s8b .st-word"), 19.9, { duration: 0.6, stagger: 0.07 });
        // le titre du montage traverse les quatre plans : il vit au-dessus d'eux
        const h8 = $("#h-s8"); $("#frame").insertBefore(h8, $("#scan"));
        tl.set(h8, { visibility: "hidden" }, 0); tl.set(h8, { visibility: "visible" }, 18.6); tl.set(h8, { visibility: "hidden" }, 23.4);

        // ── habillage : apparaît après le premier titre, disparaît sur le logo ──
        S.rise(tl, "#chrome", 0.4, { y: -10, blur: 4, duration: 0.6 });
        tl.fromTo("#hair", { scaleX: 0 }, { scaleX: 1, duration: 0.8, ease: S.ease.swift }, 0.5);
        tl.set(["#chrome", "#hair"], { visibility: "hidden" }, 26.4);
        const clock = $("#clock"), fmt = (s) => [Math.floor(s / 3600), Math.floor(s / 60) % 60, Math.floor(s) % 60].map((x) => String(x).padStart(2, "0")).join(":");
        const T0 = 3 * 3600 + 12 * 60, T1 = 3 * 3600 + 41 * 60;
        const clk = (t) => { let s; if (t < 8.4) s = T0 + t; else if (t < 16.2) s = T0 + 8.4 + (T1 - T0 - 8.4) * S.ease.glide((t - 8.4) / 7.8); else s = T1 + (t - 16.2); clock.textContent = fmt(s); };

        // ── données accrochées : cible, ligne de rappel, carte de verre ; valeur, état et courbe vivent avec le temps ──
        const cs = S.spring({ response: 0.42, damping: 0.72 });
        const fr = (v) => (v < 0 ? "−" : "") + Math.abs(v).toFixed(1).replace(".", ",");
        const live = AR.map(([sid, t0, tgt, card, label, unit, vals, chips], i) => {
          S.pop(tl, "#tg" + i, t0, { from: 0.2, damping: 0.6, response: 0.35 });
          tl.fromTo("#tg" + i + " i", { scale: 0.6, opacity: 0.9 }, { scale: 1.6, opacity: 0, duration: 1.2, ease: S.ease.silk, repeat: 2 }, t0 + 0.1);
          tl.fromTo("#ln" + i, { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.35, ease: S.ease.swift }, t0 + 0.12);
          tl.fromTo("#cd" + i, { opacity: 0, scale: 0.86, y: 24 }, { opacity: 1, scale: 1, y: 0, duration: cs.duration, ease: cs.ease }, t0 + 0.3);
          const v = $("#v" + i), ch = $("#ch" + i), sp = $("#sp" + i);
          return (t) => {
            if (t < t0 - 0.05 || t > t0 + 8) return;
            if (vals === "clock") v.textContent = fmt(T1 - 60 + Math.max(0, t - t0) * 9).slice(0, 5);
            else if (typeof vals === "string") v.textContent = vals;
            else { const [[a, va], [b, vb]] = vals; v.textContent = fr(va + (vb - va) * S.ease.glide(cl((t - a) / (b - a)))); }
            let c = chips[0]; chips.forEach((x) => { if (t >= x[0]) c = x; });
            if (ch.textContent !== c[1]) { ch.textContent = c[1]; ch.className = "chip " + c[2]; }
            sp.style.stroke = c[2] === "warn" ? "#FB923C" : c[2] === "ok" ? "#4ADE80" : "#38BDF8";
            const trend = Array.isArray(vals) ? (vals[1][1] - vals[0][1]) / Math.max(1, Math.abs(vals[0][1])) : 0;
            let pts = [];
            for (let j = 0; j < 32; j++) {
              const u = t - (31 - j) * 0.06, k = Array.isArray(vals) ? S.ease.glide(cl((u - vals[0][0]) / (vals[1][0] - vals[0][0]))) : 0;
              const y = 34 - 26 * k * Math.sign(trend || 0) * Math.min(1, Math.abs(trend) * 4) + 6 * Math.sin(u * 5.1 + i) + 3 * Math.sin(u * 13.7 + 2 * i);
              pts.push((j * 7.2).toFixed(1) + "," + Math.max(4, Math.min(60, y)).toFixed(1));
            }
            sp.setAttribute("points", pts.join(" "));
          };
        });
        // balayage de détection sur les photos quand une carte s'accroche
        AR.forEach(([sid, t0]) => tl.fromTo("#scan", { y: -240, opacity: 0.9 }, { y: 1920, opacity: 0.9, duration: 0.7, ease: S.ease.glide, ...once }, t0));
        tl.set("#scan", { opacity: 0 }, 0);
        // la dérive : la photo se réchauffe à l'orange, puis revient au calme
        tl.fromTo(["#ti-s2"], { boxShadow: "inset 0 0 0px rgba(234,88,12,0)" }, { boxShadow: "inset 0 0 260px rgba(234,88,12,0.55)", duration: 1.6, ease: S.ease.glide }, 4.4);
        tl.fromTo(["#ti-s3"], { boxShadow: "inset 0 0 180px rgba(234,88,12,0.4)" }, { boxShadow: "inset 0 0 300px rgba(234,88,12,0.7)", duration: 2.2, ease: S.ease.glide }, 6.0);

        // ── l'alerte : éclair, téléphone sur ressort, notification ; puis l'ordre de travail ──
        tl.set(["#notif"], { opacity: 0 }, 0); tl.set("#pbtn", { scale: 1 }, 0);
        tl.set("#flash", { opacity: 0 }, 0);
        tl.fromTo("#flash", { opacity: 0.85 }, { opacity: 0, duration: 0.45, ease: S.ease.accel, ...once }, 8.4);
        const ps = S.spring({ response: 0.55, damping: 0.75 });
        tl.fromTo("#phone", { y: 900, rotation: 4 }, { y: 0, rotation: 0, duration: ps.duration, ease: ps.ease }, 8.4);
        tl.fromTo("#notif", { y: -180, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: S.ease.swift }, 8.9);
        tl.fromTo("#notif", { y: 0, opacity: 1 }, { y: -180, opacity: 0, duration: 0.35, ease: S.ease.accel, ...once }, 10.3);
        S.rise(tl, $$("#st1 > *"), 9.5, { y: 30, blur: 8, stagger: 0.1, duration: 0.6 });
        tl.fromTo("#pbtn", { scale: 1 }, { scale: 0.94, duration: 0.1, ease: "none", ...once }, 11.0);
        tl.fromTo("#pbtn", { scale: 0.94 }, { scale: 1, duration: 0.25, ease: S.ease.overshoot, ...once }, 11.1);
        tl.set("#st1", { opacity: 0 }, 11.4); tl.set("#st2", { opacity: 1 }, 11.4);
        S.rise(tl, $$("#st2 .step, #st2 .al2"), 11.4, { y: 20, blur: 6, stagger: 0.08, duration: 0.5 });
        [11.6, 12.2, 12.8].forEach((t, k) => tl.fromTo("#sp" + k + " i", { backgroundColor: "rgba(56,189,248,0)", borderColor: "#334155" }, { backgroundColor: k < 2 ? "#38BDF8" : "rgba(56,189,248,0)", borderColor: "#38BDF8", duration: 0.25, ease: S.ease.swift }, t));
        tl.fromTo("#trackf", { scaleY: 0 }, { scaleY: 0.66, duration: 1.4, ease: S.ease.glide }, 11.6);
        const psp = $("#psp");
        const phoneLine = (t) => { if (t < 8.4 || t > 11.5) return; const p = []; for (let j = 0; j < 40; j++) { const u = j / 39, y = 90 - 70 * Math.pow(u, 2.2) + 5 * Math.sin(u * 23 + t * 3); p.push((u * 440).toFixed(1) + "," + y.toFixed(1)); } psp.setAttribute("points", p.join(" ")); };

        // ── tableau de bord : total qui monte, tuiles sur ressort, courbes vivantes ──
        S.pop(tl, $$(".tile"), 23.5, { from: 0.85, y: 40, stagger: 0.06, damping: 0.75 });
        S.rise(tl, ["#dash .dk", "#tot", "#dash .dk2"], 23.4, { y: 20, blur: 8, stagger: 0.06, duration: 0.6 });
        const totv = $("#totv"), tsp = $$(".tile polyline");
        const dash = (t) => {
          if (t < 23.3 || t > 26.5) return;
          totv.textContent = (28.7 * S.ease.silk(cl((t - 23.5) / 1.2)) + 0.15 * Math.sin(t * 2.3)).toFixed(1).replace(".", ",");
          tsp.forEach((pl, i) => { const p = []; for (let j = 0; j < 24; j++) { const u = t - (23 - j) * 0.08; p.push((j * 7.6).toFixed(1) + "," + (22 + 9 * Math.sin(u * 3.1 + i * 1.7) + 4 * Math.sin(u * 9.3 + i)).toFixed(1)); } pl.setAttribute("points", p.join(" ")); });
        };

        // ── logo : les orbites se dessinent, les électrons tournent, le mot et la promesse arrivent ──
        tl.fromTo("#flash", { opacity: 0.7 }, { opacity: 0, duration: 0.5, ease: S.ease.accel, ...once }, 26.4);
        const ls = S.spring({ response: 0.6, damping: 0.7 });
        tl.fromTo("#logo .core", { scale: 0 }, { scale: 1, duration: ls.duration, ease: ls.ease, svgOrigin: "0 0" }, 26.45);
        tl.fromTo("#logo .mdraw", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.9, ease: S.ease.glide, stagger: 0.08 }, 26.5);
        S.converge(tl, S.split($("#word")), 26.9, { spread: 50, duration: 0.9, stagger: 0.04 });
        S.maskUp(tl, S.split($("#tag"), { by: "words", mask: true }), 27.5, { duration: 0.7, stagger: 0.07 });
        S.pop(tl, "#cta", 28.1, { from: 0.8, damping: 0.75 });
        S.rise(tl, "#cred", 28.4, { y: 8, blur: 4, duration: 0.6 });
        const els = [0, 1, 2].map((k) => $("#elL" + k));
        const electrons = (t) => { if (t < 26.3) return; els.forEach((e, k) => { const a = (t - 26.4) * (2.2 + k * 0.4) + k * 2.1, r = (k * 60) * Math.PI / 180, x = 100 * Math.cos(a), y = 36 * Math.sin(a); e.setAttribute("cx", (x * Math.cos(r) - y * Math.sin(r)).toFixed(1)); e.setAttribute("cy", (x * Math.sin(r) + y * Math.cos(r)).toFixed(1)); e.setAttribute("opacity", cl((t - 26.9) / 0.4).toFixed(2)); }); };

        S.drive(tl, 0, TOTAL, [clk, ...live, phoneLine, dash, electrons, S.grain($("#grain"), { fps: 60, seed: 8 })]);
'''
open(f'{P}/index.html', 'w').write(HTML.replace('%%JS%%', JS))
print('ok', TOTAL)
