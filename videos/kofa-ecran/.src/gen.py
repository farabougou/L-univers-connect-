# KOFA — « enregistrement d'écran » 1920×1080 à lancer en plein écran sur le PC, puis à filmer au téléphone.
# À gauche, la fenêtre iPhone 15 Pro Max ; à droite, VS Code. Le code de HomeScreen.tsx est tapé à vitesse humaine
# (rafales, pauses, autocomplétion) et chaque bloc sauvegardé fait apparaître sa partie du vrai écran d'accueil KOFA
# (rechargement à chaud). Toutes les durées sont précalculées : rendu déterministe.
import os, re, html, json
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1920, 1080, 30
ORANGE = '#EB6834'
rng = np.random.default_rng(11)

PRE = '''import React from 'react';
import { ScrollView, View, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Header, Avatar, SearchBar, Section } from '../components';
import { CategoryChip, RestaurantCard } from '../components';
import { PromoCard, TabBar } from '../components';
import { useSession } from '../hooks/useSession';
import { colors, styles } from './HomeScreen.styles';

const CATEGORIES = [
  { id: 'repas', label: 'Repas', icon: 'plate' },
  { id: 'courses', label: 'Courses', icon: 'cart' },
  { id: 'colis', label: 'Colis', icon: 'box' },
  { id: 'grillades', label: 'Grillades', icon: 'grill' },
];

export default function HomeScreen({ navigation }) {
  const { user, city, restaurants } = useSession();
  const openCart = () => navigation.navigate('Panier');

  return (
    <SafeAreaView style={styles.screen}>'''.split('\n')
TAIL = ['    </SafeAreaView>', '  );', '}']
# blocks typed live → region of the real KOFA home screen revealed on save (y0, y1 in the 860×1864 screenshot)
BLOCKS = [
 (['      <Header logo="KOFA" lang="FR" onCart={openCart} />'], [(110, 228)]),
 (['      <ScrollView contentContainerStyle={styles.content}>',
   '        <View style={styles.helloRow}>',
   '          <View>',
   '            <Text style={styles.hello}>Bonjour {user.firstName}</Text>',
   '            <Text style={styles.city}>{city}, Mali</Text>',
   '          </View>',
   '          <Avatar user={user} />',
   '        </View>'], [(262, 385)]),
 (['        <Text style={styles.title}>',
   "          Le goût de Bamako,{'\\n'}",
   '          <Text style={{ color: colors.orange }}>livré chez vous.</Text>',
   '        </Text>'], [(392, 552)]),
 (['        <SearchBar placeholder="Un plat, un restaurant..." />'], [(560, 700)]),
 (['        <View style={styles.categories}>',
   '          {CATEGORIES.map((c) => (',
   '            <CategoryChip',
   '              key={c.id}',
   '              {...c}',
   '              onPress={() => navigation.navigate(c.label)}',
   '            />',
   '          ))}',
   '        </View>'], [(712, 935)]),
 (['        <Section title="Nos restaurants" action="Voir tout" />',
   '        <RestaurantCard restaurant={restaurants[0]} />'], [(960, 1400)]),
 (['        <PromoCard variant="blue" title="Parrainez un ami" reward={-500} />',
   '        <PromoCard variant="orange" every={5} reward={-500} />',
   '      </ScrollView>'], [(1420, 1864)]),
 (['      <TabBar active="Accueil" navigation={navigation} />'], [('nav',)]),
]
AUTO = {'Header', 'ScrollView', 'contentContainerStyle', 'helloRow', 'firstName', 'Avatar', 'SearchBar', 'placeholder',
        'categories', 'CATEGORIES', 'CategoryChip', 'navigation', 'navigate', 'Section', 'RestaurantCard', 'restaurant',
        'restaurants', 'PromoCard', 'variant', 'TabBar', 'openCart', 'colors', 'styles', 'content', 'orange', 'active'}

# ── human typing model → per-character reveal times ──
LH, CH = 31, 13.2          # line height, monospace advance (Plex Mono 22px)
lines = list(PRE)          # final file, in order
ev = []                    # (t, kind, payload)
t = 2.2
cur_line = len(PRE) - 1
popups = []                # (t_show, t_hide, word, line, col)
saves = []                 # (t, block index)
line_start = {}            # line index → time it appears
for bi, (blk, regs) in enumerate(BLOCKS):
    for text in blk:
        cur_line += 1; lines.append(text)
        ind = len(text) - len(text.lstrip())
        t += 0.12
        line_start[cur_line] = t
        ev.append((t, 'col', (cur_line, ind)))
        col = ind; s = text
        words = {m.start(): m.group(0) for m in re.finditer(r'[A-Za-z_]+', s)}
        while col < len(s):
            w = words.get(col)
            if w and w in AUTO and len(w) >= 6:
                k = 2 + int(rng.integers(0, 2))
                for _ in range(k):
                    t += 0.05 * float(rng.lognormal(0, 0.3)); col += 1; ev.append((t, 'col', (cur_line, col)))
                popups.append((t + 0.03, t + 0.22, w, cur_line, col - k))
                t += 0.22; col += len(w) - k; ev.append((t, 'col', (cur_line, col)))
                continue
            ch = s[col]
            d = 0.046 * float(rng.lognormal(0, 0.3))
            if ch == ' ': d *= 1.15
            if ch in '({<"\'=': d *= 1.25
            if rng.random() < 0.025: d += 0.25 + 0.25 * float(rng.random())   # hesitation
            t += d; col += 1; ev.append((t, 'col', (cur_line, col)))
        t += 0.18 + 0.22 * float(rng.random())        # end of line → Enter
    t += 0.35
    saves.append((round(t, 2), bi))                    # Ctrl+S
    t += 0.45 + 0.5 * float(rng.random())
END_TYPING = t
TOTAL = round(END_TYPING + 4.5, 1)
lines += TAIL
NPRE = len(PRE); NTOT = len(lines)

# ── syntax highlight ──
def hl(line):
    out, i = '', 0
    pat = re.compile(r"(//.*$)|('[^']*'|\"[^\"]*\")|(\b(?:import|from|export|default|function|const|return)\b)|(</?[A-Z][A-Za-z]*|/?>)|(\b[A-Z][A-Z_]{2,}\b)|(\b[a-z][A-Za-z]*(?=\())|(\b(?:true|false|null)\b|-?\b\d+\b)|([{}()\[\]])")
    for m in pat.finditer(line):
        out += html.escape(line[i:m.start()])
        cls = {1: 'cm', 2: 'st', 3: 'kw', 4: 'tg', 5: 'cn', 6: 'fn', 7: 'nb', 8: 'br'}[m.lastindex]
        out += f'<span class="{cls}">{html.escape(m.group(0))}</span>'; i = m.end()
    return out + html.escape(line[i:])

# ── editor geometry & scrolling ──
ED_TOP = 34 + 30 + 2      # tabs + breadcrumb
ED_H = H - ED_TOP - 26     # minus status bar
ROWS = int(ED_H // LH)
def scroll_for(line): return max(0, (line - (ROWS - 7)) * LH)

code_html, tail_html = '', ''
for n, ln in enumerate(lines):
    ind = len(ln) - len(ln.lstrip())
    guides = f'<u style="width:{ind * CH:.1f}px"></u>' if ind >= 4 else ''
    if n >= NTOT - len(TAIL):   # closing lines: start right under the prefilled code
        tail_html += f'          <div class="ln" id="L{n}" style="top:{(NPRE + n - (NTOT - len(TAIL))) * LH}px">{guides}<b id="B{n}">{hl(ln)}</b></div>\n'
        continue
    typed = n >= NPRE
    code_html += f'        <div class="ln{" ty" if typed else ""}" id="L{n}" style="top:{n * LH}px">{guides}<b id="B{n}">{hl(ln) or "&nbsp;"}</b></div>\n'
code_html += '        <div id="tail">\n' + tail_html + '        </div>\n        <div id="caret"></div>\n        <div id="pop"></div>\n'
gutter = ''.join(f'<div class="gn{" hid" if n >= NPRE + len(TAIL) else ""}" id="G{n}" style="top:{n * LH}px">{n + 1}</div>' for n in range(NTOT))

# ── timeline JS ──
js = []
# tail block + gutter grow as lines are inserted
typed_lines = sorted(line_start)
for k, n in enumerate(typed_lines):
    ts = round(line_start[n], 3)
    js.append(f'tl.set("#L{n}", {{ opacity: 1 }}, {ts});')
    js.append(f'tl.set("#tail", {{ y: {(k + 1) * LH} }}, {ts});')
    js.append(f'tl.set("#G{NPRE + len(TAIL) + k}", {{ opacity: 1 }}, {ts});')
# characters + caret
last_scroll = scroll_for(NPRE - 1)
js.append(f'gsap.set("#code", {{ y: {-last_scroll} }}); gsap.set("#gut", {{ y: {-last_scroll} }});')
for (te, kind, (n, col)) in ev:
    te = round(te, 3)
    js.append(f'tl.set("#B{n}", {{ clipPath: "inset(0 calc(100% - {col * CH:.1f}px) 0 0)" }}, {te});')
    js.append(f'tl.set("#caret", {{ x: {col * CH:.1f}, y: {n * LH} }}, {te});')
    sc = scroll_for(n)
    if sc != last_scroll:
        js.append(f'tl.to(["#code", "#gut"], {{ y: {-sc}, duration: 0.14, ease: "power2.out" }}, {te});')
        last_scroll = sc
for (a, b, w, n, col) in popups:
    js.append(f'tl.set("#pop", {{ opacity: 1, x: {col * CH:.1f}, y: {(n + 1) * LH + 4}, textContent: {json.dumps(w)} }}, {round(a, 3)});')
    js.append(f'tl.set("#pop", {{ opacity: 0 }}, {round(b, 3)});')
# dirty dot while typing, cleared on each save; hot reload reveals the region
SC_ = 402 / 860
first_typing = round(ev[0][0], 2)
js.append(f'tl.set("#dirty", {{ opacity: 1 }}, {first_typing});')
for k, (ts, bi) in enumerate(saves):
    js.append(f'tl.set("#dirty", {{ opacity: 0 }}, {ts});')
    if k + 1 < len(saves):
        nxt = [e[0] for e in ev if e[0] > ts]
        if nxt: js.append(f'tl.set("#dirty", {{ opacity: 1 }}, {round(nxt[0], 3)});')
    js.append(f'tl.fromTo("#R{bi}", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power2.out" }}, {round(ts + 0.45, 2)});')
    js.append(f'tl.fromTo("#reload", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, yoyo: true, repeat: 1, ease: "none" }}, {round(ts + 0.3, 2)});')

regions = ''
for bi, (blk, regs) in enumerate(BLOCKS):
    r = regs[0]
    if r[0] == 'nav':
        regions += (f'<div class="rg" id="R{bi}" style="left:{110 * SC_:.1f}px; top:{1628 * SC_:.1f}px; width:{640 * SC_:.1f}px; height:{142 * SC_:.1f}px; '
                    f'background-position:{-110 * SC_:.1f}px {-1628 * SC_:.1f}px; border-radius:40px"></div>')
    else:
        y0, y1 = r
        regions += f'<div class="rg" id="R{bi}" style="left:0; top:{y0 * SC_:.1f}px; width:402px; height:{(y1 - y0) * SC_:.1f}px; background-position:0 {-y0 * SC_:.1f}px"></div>'

ICON = lambda d: f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#8b90a8" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{d}</svg>'
ACT = [ICON('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'),
       ICON('<circle cx="11" cy="11" r="6"/><path d="m20 20-4.3-4.3"/>'),
       ICON('<circle cx="6" cy="6" r="2.2"/><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="8" r="2.2"/><path d="M6 8.2v7.6M18 10.2c0 4-6 3-10.6 6"/>') + '<i class="badge">46</i>',
       ICON('<path d="m7 4 12 8-12 8z"/>'),
       ICON('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>'),
       ICON('<path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/>')]
act = ''.join(f'<div class="ai{" on" if i == 0 else ""}">{a}</div>' for i, a in enumerate(ACT))
SIMI = lambda d: f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c9cbe0" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{d}</svg>'

idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 700; src: url("assets/fonts/inter-latin-700-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #14151f; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #14151f; font-family: "Inter", sans-serif; }}
      /* simulator window */
      #sim {{ position: absolute; left: 0; top: 0; width: 760px; height: {H}px; background: #2b2e45; border-right: 1px solid #1a1b28; }}
      #simbar {{ position: absolute; left: 0; top: 0; width: 760px; height: 64px; display: flex; align-items: center; padding: 0 24px; gap: 22px; }}
      #simbar .nm b {{ display: block; font: 700 19px "Inter"; color: #e9eaf6; }}
      #simbar .nm span {{ display: block; font: 400 14px "Inter"; color: #a3a6c2; margin-top: 2px; }}
      #simbar .sp {{ flex: 1; }}
      #phone {{ position: absolute; left: {(760 - 430) // 2}px; top: 82px; width: 430px; height: 900px; border-radius: 68px; background: #050506; box-shadow: 0 0 0 3px #6d7392, 0 0 0 6px #23253a, 0 24px 60px rgba(0,0,0,0.5); }}
      #disp {{ position: absolute; left: 14px; top: 14px; width: 402px; height: 872px; border-radius: 56px; overflow: hidden; background: #0d0d0d; }}
      #isl {{ position: absolute; left: 50%; top: 13px; width: 122px; height: 36px; margin-left: -61px; border-radius: 18px; background: #000; z-index: 9; }}
      .rg {{ position: absolute; background-image: url(assets/images/accueil.jpg); background-size: 402px auto; opacity: 0; }}
      #statusb {{ opacity: 1; }}
      #reload {{ position: absolute; inset: 0; background: rgba(255,255,255,0.05); opacity: 0; z-index: 8; }}
      #simtools {{ position: absolute; left: 0; width: 760px; top: 1012px; display: flex; justify-content: center; gap: 34px; }}
      /* VS Code */
      #vs {{ position: absolute; left: 760px; top: 0; width: 1160px; height: {H}px; background: #1a1b2a; }}
      #actbar {{ position: absolute; left: 0; top: 0; width: 56px; height: {H - 26}px; background: #16172a; border-right: 1px solid #23253a; padding-top: 10px; }}
      .ai {{ position: relative; height: 54px; display: flex; justify-content: center; align-items: center; opacity: 0.85; }}
      .ai.on {{ border-left: 2px solid #e9eaf6; }}
      .ai.on svg {{ stroke: #e9eaf6; }}
      .badge {{ position: absolute; left: 31px; top: 30px; min-width: 20px; height: 16px; border-radius: 8px; background: #3b82f6; font: 600 10px/16px "Inter"; color: #fff; text-align: center; font-style: normal; }}
      #tabs {{ position: absolute; left: 56px; top: 0; right: 0; height: 34px; background: #16172a; }}
      .tab {{ position: absolute; left: 0; top: 0; height: 34px; padding: 0 16px 0 14px; background: #1a1b2a; border-top: 1px solid #3b82f6; font: 400 15px/34px "Inter"; color: #e2e4f3; display: flex; align-items: center; gap: 8px; }}
      .tab .rx {{ color: #61dafb; font-size: 15px; }}
      .tab .u {{ color: #73c991; font-size: 13px; }}
      .tab .x {{ position: relative; width: 14px; height: 14px; color: #a3a6c2; font-size: 15px; line-height: 14px; text-align: center; }}
      #dirty {{ position: absolute; left: 3px; top: 3px; width: 8px; height: 8px; border-radius: 4px; background: #e2e4f3; opacity: 0; }}
      #crumb {{ position: absolute; left: 56px; top: 34px; right: 0; height: 30px; padding-left: 18px; font: 400 14px/30px "Inter"; color: #a3a6c2; border-bottom: 1px solid #23253a; }}
      #crumb i {{ font-style: normal; color: #61dafb; }}
      #edw {{ position: absolute; left: 56px; top: {ED_TOP}px; right: 0; height: {ED_H}px; overflow: hidden; }}
      #gut {{ position: absolute; left: 0; top: 0; width: 70px; }}
      .gn {{ position: absolute; right: 14px; height: {LH}px; font: 500 20px/{LH}px "Plex Mono"; color: #7d82a8; }}
      .gn.hid {{ opacity: 0; }}
      #gut .gn {{ }}
      #code {{ position: absolute; left: 86px; top: 0; right: 0; }}
      .ln {{ position: absolute; left: 0; height: {LH}px; font: 500 22px/{LH}px "Plex Mono"; color: #c8cbe6; white-space: pre; }}
      .ln.ty {{ opacity: 0; }}
      .ln u {{ position: absolute; left: 0; top: 0; height: {LH}px; background: repeating-linear-gradient(90deg, rgba(120,126,170,0.22) 0 1px, transparent 1px {2 * CH:.1f}px); }}
      .ln b {{ font-weight: 500; }}
      .ln.ty b {{ display: inline-block; clip-path: inset(0 100% 0 0); }}
      .kw {{ color: #c792ea; }} .st {{ color: #c3e88d; }} .tg {{ color: #ff7a93; }} .cn {{ color: #ffcb6b; }} .fn {{ color: #82aaff; }} .br {{ color: #89ddff; }} .cm {{ color: #676e95; font-style: italic; }} .nb {{ color: #f78c6c; }}
      #tail {{ position: absolute; left: 0; top: 0; width: 100%; }}
      #caret {{ position: absolute; left: 0; top: 4px; width: 2px; height: 23px; background: #e2e4f3; }}
      #pop {{ position: absolute; left: -24px; top: 0; padding: 4px 10px 4px 30px; background: #222439; border: 1px solid #3a3d5c; border-radius: 4px; font: 500 18px "Plex Mono"; color: #82aaff; opacity: 0; white-space: nowrap; box-shadow: 0 6px 18px rgba(0,0,0,0.35); }}
      #pop::before {{ content: "⬚"; position: absolute; left: 9px; color: #c792ea; font-size: 15px; }}
      #status {{ position: absolute; left: 760px; bottom: 0; width: 1160px; height: 26px; background: #2f6fd8; font: 400 14px/26px "Inter"; color: #fff; padding-left: 14px; display: flex; gap: 22px; }}
      #status .r {{ margin-left: auto; padding-right: 18px; display: flex; gap: 22px; }}
      #mini {{ position: absolute; right: 14px; top: {ED_TOP + 6}px; width: 60px; height: 420px; opacity: 0.35; background: repeating-linear-gradient(180deg, rgba(200,203,230,0.35) 0 2px, transparent 2px 6px); -webkit-mask: linear-gradient(90deg, #000 40%, transparent); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="scene" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="sim">
          <div id="simbar">{SIMI('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>')}<div class="nm"><b>iPhone 15 Pro Max</b><span>iOS 18.6</span></div><div class="sp"></div>{SIMI('<path d="m6 17 5-5-5-5M13 17l5-5-5-5"/>')}{SIMI('<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>')}{SIMI('<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M10 7h4"/>')}{SIMI('<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>')}</div>
          <div id="phone"><div id="disp"><div id="isl"></div>
            <div class="rg" id="statusb" style="left:0; top:0; width:402px; height:{108 * SC_:.1f}px; background-position:0 0"></div>
            {regions}
            <div id="reload"></div>
          </div></div>
          <div id="simtools">{SIMI('<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01"/>')}{SIMI('<path d="M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4"/><circle cx="12" cy="12" r="3"/>')}{SIMI('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>')}{SIMI('<path d="M7 4h7l5 5v11H7z"/><path d="M3 8v12h12"/>')}</div>
        </div>
        <div id="vs">
          <div id="actbar">{act}</div>
          <div id="tabs"><div class="tab"><span class="rx">⚛</span>HomeScreen.tsx<span class="u">U</span><span class="x"><span id="dirty"></span>×</span></div></div>
          <div id="crumb">src › screens › <i>⚛</i> HomeScreen.tsx › <i>⚛</i> HomeScreen</div>
          <div id="edw">
            <div id="gut">{gutter}</div>
            <div id="code">
{code_html}            </div>
            <div id="mini"></div>
          </div>
        </div>
        <div id="status"><span>⎇ main*</span><span>⊗ 0  ⚠ 0</span><span>Expo Go : iPhone 15 Pro Max</span><div class="r"><span>Espaces : 2</span><span>UTF-8</span><span>TypeScript JSX</span><span>Prettier ✓</span></div></div>
      </div>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
      {chr(10).join('      ' + j for j in js)}
      tl.fromTo("#caret", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.53, ease: "steps(1)", repeat: {int(TOTAL / 0.53)}, yoyo: true }}, 0);
      tl.set({{}}, {{}}, {TOTAL});
    </script>
  </body>
</html>
'''
# tail lines move inside #tail; gutter numbers for not-yet-existing lines start hidden
tail_start = NTOT - len(TAIL)
for n in range(tail_start, NTOT):
    pass
open(f'{P}/index.html', 'w').write(idx)
assert max(len(l) for l in lines) <= 76, max(lines, key=len)
print('total', TOTAL, 'typing ends', round(END_TYPING, 1), 'saves', [s for s, _ in saves], 'rows', ROWS)
