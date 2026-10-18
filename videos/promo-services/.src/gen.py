# Pub « services » de Mohamed : sites internet, applications, pubs vidéo. Vertical 1080×1920, 25 i/s, 64 temps à 124 BPM (31 s),
# cut on Anna's voiceover (assets/voice/voice.wav): each section and each pill lands on the word that names it.
# Proof, not promises: the live sites (ktf-shipping.com, sensexpress.com, captured full-page), the KOFA app screens,
# and real ad renders. Same identity as the showreel (ink, orange, Inter 900, Plex Mono).
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
B = 60 / 124
T = lambda b: round(b * B, 3)
TOTAL = T(64)
ACC, INK, WHITE, MUTE = '#FF5A1F', '#0A0A0C', '#F4F2EE', '#9A98A0'
# voiceover cues in seconds (whisper words refined on the voice energy)
V = dict(jecree=2.66, moderne=5.27, rapide=5.96, adapte=6.28, telephone=7.16, comme=9.25, motion=12.77, neuf=15.22,
         resto=17.80, bout=18.83, trans=19.58, beaute=20.21, activite=21.55, aide=22.12, demarquer=22.80, internet=23.37,
         projet=24.45, prochain=25.25, ecrivez=26.40)
HOOK_WORDS = [0.02, 0.32, 0.9, 1.4]

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
      <div class="pills" style="top:1560px"><span>Moderne</span><span>Rapide</span><span>Adapté au téléphone</span></div>
    </section>'''
# section 2 — app
SCREENS = ['accueil', 'diaspora', 'restaurant-onboarding', 'compte']
app_inner = ''.join(f'<img class="kscr" id="k{i}" src="assets/images/{n}.jpg" alt="">' for i, n in enumerate(SCREENS)) + '<div class="tap" id="tap"></div>'
CARDS = [('c1', 40, 760, 'Suivi du livreur', 'en direct sur la carte'), ('c2', 700, 1180, 'Code à 4 chiffres', 'remis à la livraison')]
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
    inner = ad_video(a[0], j, T(24), round(V['neuf'] + 0.1 - T(24), 3)) + ad_video(b2[0], j + 3, V['neuf'], round(V['resto'] - V['neuf'], 3))
    s3_ph += phone(f'p3{j}', x, y, w, h, inner, rot, 'z-index:' + ('3' if j == 1 else '1'))
    s3_ph += f'<div class="brand" id="bA{j}" style="left:{x}px; width:{w}px; top:{y + h + 26}px">{a[1]}</div><div class="brand" id="bB{j}" style="left:{x}px; width:{w}px; top:{y + h + 26}px; opacity:0">{b2[1]}</div>'
s3 = f'''
    <section id="sec3" class="sec">
      <div class="num">03</div><div class="ttl">Pubs vidéo</div>
      <div class="sub">Du motion design qui arrête le scroll.</div>
      {s3_ph}
      <div class="stat" id="st1"><em>9</em> marques</div>
      <div class="cap" id="st2" style="top:1610px">m'ont fait confiance</div>
    </section>'''
# section S — « Restaurants, boutiques, transports, beauté » : one real ad per word, hard cuts
CUTS = [('restaurants', 'Restaurants', "Founerou Grill's", V['resto']), ('boutiques', 'Boutiques', 'Cassia Dressing', V['bout']),
        ('transports', 'Transports', 'KTF Shipping', V['trans']), ('beaute', 'Beauté', 'SensExpress', V['beaute'])]
CUT_END = [c[3] for c in CUTS[1:]] + [T(43)]
sS = '''
    <section id="secS" class="sec">'''
for i, ((k, lab, br, t0), t1) in enumerate(zip(CUTS, CUT_END)):
    sS += f'''
      <video id="s-{k}" class="clip full" src="assets/clips/sec-{k}.mp4" data-start="{t0}" data-duration="{round(t1 - t0, 3)}" data-track-index="{8 + i}" muted playsinline></video>'''
sS += '''
      <div class="shade"></div>'''
for i, (k, lab, br, t0) in enumerate(CUTS):
    sS += f'''
      <div class="slab" id="sl{i}">{lab}</div><div class="stag" id="sg{i}">{br}</div>'''
sS += '''
    </section>'''
# section D — « peu importe votre activité, je vous aide à vous démarquer »
TILES = ['Restaurant', 'Boutique', 'Transport', 'Beauté', 'Votre business', 'Immobilier', 'École', 'Santé', 'Événementiel']
tiles = ''.join(f'<div class="tile" id="t{i}" style="left:{60 + (i % 3) * 330}px; top:{600 + (i // 3) * 250}px">{n}</div>' for i, n in enumerate(TILES))
sD = f'''
    <section id="secD" class="sec">
      <div class="big" id="d1" style="top:200px; font-size:120px">Peu importe</div>
      <div class="big" id="d2" style="top:330px; font-size:120px">votre activité,</div>
      {tiles}
      <div class="big" id="d3" style="top:1440px; font-size:76px">je vous aide à vous</div>
      <div class="big" id="d4" style="top:1540px; font-size:160px"><em>démarquer.</em></div>
      <div class="cap" id="d5" style="top:1740px">sur internet</div>
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
      <div class="cap" id="h4" style="top:1160px; color:#F4F2EE; font-size:40px">Je crée pour vous</div>
    </section>'''

js = []
J = js.append
# living background
J(f'tl.fromTo("#grid", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "0px -240px", duration: {TOTAL}, ease: "none" }}, 0);')
J(f'tl.fromTo("#glow1", {{ x: -120, y: 0 }}, {{ x: 160, y: 300, duration: {TOTAL}, ease: "sine.inOut" }}, 0);')
J(f'tl.fromTo("#glow2", {{ x: 100, y: 0 }}, {{ x: -140, y: -260, duration: {TOTAL}, ease: "sine.inOut" }}, 0);')
# section visibility windows + exits (sec3 and secS cut hard on the spoken word)
WIN = [('sec0', 0, T(8), 'soft'), ('sec1', T(8), T(17), 'soft'), ('sec2', T(17), T(24), 'soft'), ('sec3', T(24), V['resto'], 'hard'),
       ('secS', V['resto'], T(43), 'hard'), ('secD', T(43), T(50), 'soft'), ('sec4', T(50), TOTAL, None)]
for sid, a, b, ex in WIN:
    J(f'tl.set("#{sid}", {{ autoAlpha: 1 }}, {a});')
    if ex == 'soft':
        J(f'tl.to("#{sid}", {{ y: -140, autoAlpha: 0, filter: "blur(14px)", duration: 0.28, ease: "power3.in" }}, {b - 0.28:.3f});')
    elif ex == 'hard':
        J(f'tl.set("#{sid}", {{ autoAlpha: 0 }}, {b});')
for sid, a, sub in (('sec1', T(8), T(9)), ('sec2', T(17), V['comme']), ('sec3', T(24), V['motion'])):
    J(f'tl.fromTo("#{sid} .num", {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: "expo.out" }}, {a});')
    J(f'tl.fromTo("#{sid} .ttl", {{ opacity: 0, y: 50, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {a + 0.05:.3f});')
    J(f'tl.fromTo("#{sid} .sub", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {sub});')
# hook — each word as Anna says it
J(f'gsap.utils.toArray("#h1 .w, #h2 .w").forEach((w, i) => tl.fromTo(w, {{ opacity: 0, y: 50, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.4, ease: "expo.out" }}, {HOOK_WORDS}[i]));')
J(f'tl.fromTo("#h3", {{ opacity: 0, scale: 2.2, filter: "blur(24px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, 1.78);')
J(f'tl.fromTo("#h4", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, {V["jecree"]});')
# section 1 — laptop rises, sites scroll, switch on beat 12, phone pops on « téléphone »
J(f'tl.fromTo(".lap", {{ y: 500, rotationX: 28, opacity: 0 }}, {{ y: 0, rotationX: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(8) + 0.1:.3f});')
J(f'tl.fromTo("#p1", {{ x: 400, rotation: 14, opacity: 0 }}, {{ x: 0, rotation: 4, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(9)});')
for n, a, b in [('ktf', 8, 12), ('sx', 12, 17)]:
    dh = desk_h['ktf' if n == 'ktf' else 'sensexpress']
    J(f'tl.fromTo("#d-{n}", {{ y: 0 }}, {{ y: {-(dh - SCR_H) * 0.45:.0f}, duration: {T(b) - T(a) - 0.4:.3f}, ease: "power1.inOut" }}, {T(a) + 0.4:.3f});')
    J(f'tl.fromTo("#m-{n}", {{ y: 0 }}, {{ y: {-(mob_h - 596) * 0.3:.0f}, duration: {T(b) - T(a) - 0.4:.3f}, ease: "power1.inOut" }}, {T(a) + 0.4:.3f});')
J(f'tl.fromTo(["#d-sx", "#m-sx"], {{ opacity: 0, x: 120 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }}, {T(12)});')
J(f'tl.to(["#d-ktf", "#m-ktf"], {{ opacity: 0, x: -120, duration: 0.3, ease: "power3.in" }}, {T(12)});')
J(f'tl.fromTo("#u1", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, {T(9)}); tl.to("#u1", {{ opacity: 0, duration: 0.2 }}, {T(12) - 0.1:.3f});')
J(f'tl.fromTo("#u2", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, {T(12) + 0.1:.3f});')
J(f'gsap.utils.toArray("#sec1 .pills span").forEach((p, i) => tl.fromTo(p, {{ opacity: 0, y: 24, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(2)" }}, {[V["moderne"], V["rapide"], V["adapte"]]}[i]));')
J(f'tl.to("#p1", {{ scale: 1.08, duration: 0.2, ease: "power2.out", yoyo: true, repeat: 1 }}, {V["telephone"]});')
# section 2 — KOFA phone, push transitions, two feature cards
J(f'tl.fromTo("#p2", {{ y: 700, rotation: -6, opacity: 0 }}, {{ y: 0, rotation: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, {T(17) + 0.1:.3f});')
J(f'tl.fromTo("#p2", {{ rotationY: 0 }}, {{ rotationY: -10, duration: {T(24) - T(18):.3f}, ease: "sine.inOut", immediateRender: false }}, {T(18)});')
for i, t0 in enumerate((T(19.5), T(21), T(22.5)), 1):
    J(f'tl.fromTo("#tap", {{ opacity: 0.85, scale: 0.4 }}, {{ opacity: 0, scale: 1.7, duration: 0.4, ease: "power2.out", immediateRender: false }}, {t0 - 0.3:.3f});')
    J(f'tl.fromTo("#k{i}", {{ xPercent: 100 }}, {{ xPercent: 0, duration: 0.42, ease: "power3.inOut", immediateRender: false }}, {t0});')
    J(f'tl.set("#k{i}", {{ opacity: 1 }}, {t0});')
    J(f'tl.to("#k{i - 1}", {{ xPercent: -30, filter: "brightness(0.55)", duration: 0.42, ease: "power3.inOut" }}, {t0});')
for j, ((cid, x, y, t_, s_), t0) in enumerate(zip(CARDS, (9.45, 10.15))):
    J(f'tl.fromTo("#{cid}", {{ opacity: 0, x: {-120 if x < 300 else 120}, filter: "blur(10px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {t0});')
    J(f'tl.to("#{cid}", {{ y: -14, duration: 0.8, ease: "sine.inOut", yoyo: true, repeat: 1 }}, {t0 + 0.5:.2f});')
# section 3 — three phones, swap ads on « neuf marques »
for j in range(3):
    J(f'tl.fromTo("#p3{j}", {{ y: 900, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.7, ease: "expo.out" }}, {T(24) + 0.08 * j:.3f});')
    J(f'tl.fromTo("#bA{j}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {T(25)}); tl.to("#bA{j}", {{ opacity: 0, duration: 0.2 }}, {V["neuf"] - 0.1:.3f});')
    J(f'tl.fromTo("#bB{j}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {V["neuf"] + 0.1:.3f});')
    J(f'tl.fromTo("#p3{j}", {{ scale: 1.06 }}, {{ scale: 1, duration: 0.35, ease: "power3.out", immediateRender: false }}, {V["neuf"]});')
J(f'tl.fromTo("#st1", {{ opacity: 0, scale: 1.8, filter: "blur(20px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, {V["neuf"]});')
J(f'tl.fromTo("#st2", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, {V["neuf"] + 0.65:.2f});')
# section S — one ad per sector, label slams on the word
for i, ((k, lab, br, t0), t1) in enumerate(zip(CUTS, CUT_END)):
    J(f'tl.fromTo("#s-{k}", {{ scale: 1.14 }}, {{ scale: 1, duration: {t1 - t0:.3f}, ease: "power2.out" }}, {t0});')
    J(f'tl.fromTo("#sl{i}", {{ opacity: 0, scale: 1.5, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.3, ease: "expo.out" }}, {t0});')
    J(f'tl.fromTo("#sg{i}", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }}, {t0 + 0.1:.2f});')
    if i < 3:
        J(f'tl.set(["#sl{i}", "#sg{i}"], {{ opacity: 0 }}, {t1});')
# section D — grid of activities, « votre business » stands out on « démarquer »
J(f'tl.fromTo("#d1", {{ opacity: 0, y: 50, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, {T(43)});')
J(f'tl.fromTo("#d2", {{ opacity: 0, y: 50, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, {V["activite"]});')
for n, i in enumerate((0, 2, 6, 8, 1, 3, 5, 7, 4)):
    J(f'tl.fromTo("#t{i}", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.8)" }}, {T(43) + 0.1 + n * 0.07:.2f});')
J(f'tl.fromTo("#d3", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, {V["aide"]});')
J(f'tl.to([{", ".join(f"{chr(34)}#t{i}{chr(34)}" for i in range(9) if i != 4)}], {{ opacity: 0.22, scale: 0.92, duration: 0.35, ease: "power2.out" }}, {V["demarquer"]});')
J(f'tl.to("#t4", {{ scale: 1.32, backgroundColor: "{ACC}", borderColor: "{ACC}", color: "{INK}", boxShadow: "0 0 90px rgba(255,90,31,0.65)", duration: 0.4, ease: "back.out(2)" }}, {V["demarquer"]});')
J(f'tl.fromTo("#d4", {{ opacity: 0, scale: 1.6, filter: "blur(20px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.4, ease: "expo.out" }}, {V["demarquer"]});')
J(f'tl.fromTo("#d5", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }}, {V["internet"]});')
# section 4 — CTA
J(f'tl.fromTo("#q1", {{ opacity: 0, y: 60, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {V["projet"]});')
J(f'tl.fromTo("#q2", {{ opacity: 0, y: 60, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {V["prochain"]});')
J(f'gsap.utils.toArray("#q3 span").forEach((p, i) => tl.fromTo(p, {{ opacity: 0, y: 24, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(2)" }}, {V["prochain"] + 0.5:.2f} + i * 0.12));')
J(f'tl.fromTo("#q6", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2)" }}, {V["ecrivez"]});')
J(f'tl.fromTo("#q4", {{ opacity: 0, scale: 1.3, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out" }}, 27.2);')
J(f'tl.fromTo("#q5", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, 27.6);')
J(f'tl.to("#q6", {{ scale: 1.05, duration: {B:.4f}, ease: "sine.inOut", yoyo: true, repeat: 7 }}, 27.0);')
# flash on the drops and on the sector cuts
for t0, o in ((T(8), 0.6), (T(17), 0.45), (T(24), 0.6), (V['resto'], 0.6), (V['bout'], 0.3), (V['trans'], 0.3), (V['beaute'], 0.3), (T(43), 0.5), (T(50), 0.6)):
    J(f'tl.fromTo("#flash", {{ opacity: {o} }}, {{ opacity: 0, duration: 0.25, ease: "power2.out", immediateRender: false }}, {t0});')

SFX = [('riser', T(5), 0.2), ('impact', T(8), 0.45), ('whoosh', T(12) - 0.1, 0.25), ('impact', T(17), 0.3), ('impact', T(24), 0.4),
       ('impact', V['neuf'], 0.3), ('whoosh', V['resto'] - 0.1, 0.3), ('whoosh', V['bout'] - 0.1, 0.22), ('whoosh', V['trans'] - 0.1, 0.22),
       ('whoosh', V['beaute'] - 0.1, 0.22), ('impact', T(43), 0.4), ('impact', V['demarquer'], 0.3), ('impact', T(50), 0.45)]
import soundfile as _sf
LEN = {n: round(_sf.info(f'{P}/assets/{n}.wav').duration, 2) for n in ('impact', 'whoosh', 'riser')}
VO = round(_sf.info(f'{P}/assets/voice/voice.wav').duration, 2)
lanes, sfx = [], ''
for i, (f, t, v) in enumerate(SFX):  # first free lane, so no two sounds share a track at once
    k = next((n for n, e in enumerate(lanes) if e <= t), len(lanes))
    lanes[k:k + 1] = [t + LEN[f]]
    sfx += f'      <audio id="sfx{i}" src="assets/{f}.wav" data-start="{round(t, 3)}" data-duration="{LEN[f]}" data-track-index="{20 + k}" data-volume="{v}"></audio>\n'
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
      .stat {{ position: absolute; left: 0; right: 0; top: 1440px; text-align: center; font: 900 150px/1 "Inter"; color: {WHITE}; letter-spacing: -0.045em; }}
      .stat em {{ font-style: normal; color: {ACC}; }}
      .full {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; }}
      .shade {{ position: absolute; left: 0; right: 0; bottom: 0; height: 820px; background: linear-gradient(180deg, rgba(10,10,12,0), rgba(10,10,12,0.97) 56%); }}
      .slab {{ position: absolute; left: 0; right: 0; top: 1460px; text-align: center; font: 900 170px/1 "Inter"; color: {WHITE}; letter-spacing: -0.05em; opacity: 0; }}
      .stag {{ position: absolute; left: 0; right: 0; top: 1660px; text-align: center; font: 500 34px "Plex Mono"; color: {ACC}; letter-spacing: 0.08em; opacity: 0; }}
      .tile {{ position: absolute; width: 300px; height: 220px; padding: 0 20px; border-radius: 26px; display: flex; align-items: center; justify-content: center; text-align: center; font: 700 36px/1.15 "Inter"; color: {WHITE}; background: rgba(244,242,238,0.05); border: 2px solid rgba(244,242,238,0.16); }}
      #t4 {{ z-index: 3; }}
      #flash {{ position: absolute; inset: 0; background: {WHITE}; opacity: 0; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <div id="stage" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="grid"></div>
        <div class="glow" id="glow1" style="left:-200px; top:200px"></div>
        <div class="glow" id="glow2" style="left:400px; top:1100px"></div>
{hook}{s1}{s2}{s3}{sS}{sD}{s4}
        <div id="flash"></div>
      </div>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="15" data-volume="0.9"></audio>
      <audio id="vo" src="assets/voice/voice.wav" data-start="0" data-duration="{VO}" data-track-index="16" data-volume="1"></audio>
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
