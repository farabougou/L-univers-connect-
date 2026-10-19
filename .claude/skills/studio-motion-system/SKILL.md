---
name: studio-motion-system
description: Référence du système de design motion maison videos/_studio/studio.js (+ studio.css) pour HyperFrames — courbes de Bézier sur mesure, ressorts physiques, jetons de durée et de décalage, découpage du texte, entrées/sorties typographiques, vie continue, caméra 2.5D avec parallaxe et profondeur de champ, grain, reflets, transitions — et les trois presets de personnalité (luxe, tech, punchy). À charger dès qu'on anime une composition de ce dépôt.
---

# Système de design motion Studio

Fichiers : `videos/_studio/studio.js` et `videos/_studio/studio.css`. Démo complète : `videos/_studio/demo/.src/gen.py`.

## Installation dans un projet
```bash
cp videos/_studio/studio.js videos/_studio/studio.css videos/<projet>/assets/vendor/
```
```html
<script src="assets/vendor/gsap.min.js"></script>
<script src="assets/vendor/studio.js"></script>
<link rel="stylesheet" href="assets/vendor/studio.css" />
```
Dans le script de la composition : `const S = STUDIO;`. Tout passe par la timeline en pause de la composition (`tl`), et tout est seek-safe.

## Courbes (`S.ease`)
| Nom | cubic-bezier | Usage |
|---|---|---|
| `silk` | 0.16, 1, 0.3, 1 | Arrivée premium : départ franc, très longue décélération. Le défaut du preset `luxe`. |
| `swift` | 0.2, 0.8, 0.2, 1 | Interface, pills, cartes : vif et net. Le défaut du preset `tech`. |
| `glide` | 0.65, 0, 0.35, 1 | Caméra, morphing, déplacement d'un groupe d'un point A à un point B. |
| `accel` | 0.45, 0, 0.8, 0.35 | Sortie douce : prend de la vitesse dès le départ. |
| `exit` | 0.7, 0, 0.84, 0 | Sortie sèche : immobile puis part d'un coup (punchy). |
| `anticipate` | 0.5, -0.35, 0.25, 1 | Recule d'environ 8 % avant de partir (départ fort). |
| `overshoot` | 0.34, 1.35, 0.64, 1 | Dépasse d'environ 6 % puis revient : un accent par scène au maximum. |
| `breath` | sinus | Respiration, fondu calme, caméra lente. |

- Les courbes sont aussi enregistrées comme chaînes GSAP : `ease: "studio-silk"`.
- `S.bezier(x1, y1, x2, y2)` crée une courbe sur mesure (mêmes valeurs qu'After Effects ou CSS).
- `S.spring({ response, damping })` renvoie `{ duration, ease }` : un ressort amorti exact. Toujours utiliser la durée qu'il donne.
  - damping 1 : sans dépassement ;
  - damping 0.8 : vivant ;
  - damping 0.7 : joueur ;
  - jamais en dessous de 0.6.

## Jetons
- `S.dur` :
  - micro 0.2, short 0.4, base 0.7 ;
  - long 1.1, hero 1.6, epic 2.4.
- `S.stagger` : chars 0.028, words 0.07, lines 0.14, items 0.09.
- `S.cap(n, each, max = 0.6)` réduit le décalage pour qu'un groupe de n éléments tienne en `max` secondes.
- `S.rng(seed)` : le seul hasard autorisé.

## Texte
- `S.split(el, { by: "chars" | "words", mask })` découpe au montage et renvoie les spans.
  - `mask: true` place chaque mot dans une fenêtre `.st-mask` qui ne coupe pas les accents.
  - Le texte doit être brut : découper chaque `<em>` séparément.
- `S.rise(tl, cibles, t, { y, blur, rotate, stagger, from, duration, ease })` : montée avec flou et décalage. `from: "center"` part du milieu du mot.
- `S.maskUp(tl, motsMasqués, t, opts)` : les mots sortent d'une fenêtre, par le bas, avec une légère rotation.
- `S.converge(tl, lettres, t, { spread, blur })` : les lettres se resserrent depuis le centre. Remplace toute animation de `letter-spacing` (logos, mots-signatures).
- `S.pop(tl, cibles, t, { from, y, response, damping, stagger })` : arrivée sur ressort (pills, icônes, prix).
- `S.leave(tl, cibles, t, { y, blur, duration })` : sortie courte et décalée.

## Vie continue
`S.life(tl, éléments, début, fin, { x, y, rotate, scale, period, seed })` fait dériver chaque élément avec sa propre phase.
- Elle écrit les propriétés CSS individuelles `translate`, `rotate` et `scale`, donc elle se cumule avec les animations GSAP sur le même élément sans les écraser.
- Elle démarre en douceur sur 0,8 s.

## Caméra 2.5D
```js
S.camera(tl, [
  { el: $("#L-bg"),  depth: 0.3 },              // fond lointain : bouge peu
  { el: $("#L-mid"), depth: 1 },                // sujet
  { el: $("#L-fg"),  depth: 1.7 },              // premier plan : bouge beaucoup, se floute
  { el: $("#L-txt"), depth: 0.35, blur: false } // texte : légère parallaxe, jamais flou
], { start: 0, end: 5.4, dof: { k: 10, max: 14 }, drift: { x: 6, y: 5, r: 0.15, period: 8 },
     keys: [{ t: 0, s: 1.22, rx: 9, ry: -16, f: 1.75 }, { t: 2.4, s: 1, rx: 0, ry: 0, f: 1 }, { t: 5.4, s: 1.08, ry: 6, ease: S.ease.breath }] });
```
- Les calques sont des `.st-layer` dans une `.st-stage` (qui porte la perspective).
- Les calques ne portent QUE la caméra : le contenu animé vit à l'intérieur.
- Chaque clé hérite des valeurs de la précédente. `ease` sur une clé règle l'arrivée vers cette clé (par défaut `glide`).

## Finitions et pilotes
- `S.grain(canvas, { fps, seed, tiles, size, contrast })` renvoie un rendu.
- `S.drive(tl, début, fin, [rendu1, rendu2…])` fait avancer tous les rendus canvas avec un seul pilote.
- `S.sweep(tl, ".st-sheen", t, { duration })` fait passer un reflet. La surface doit avoir la classe `.st-sheen-host`.
- Classes CSS :
  - `st-elev-1/2/3` : ombres multicouches ;
  - `st-rim` : liseré lumineux ;
  - `st-glow` : lueur de texte en trois couches, couleur via `--st-glow` ;
  - `st-grain` : grain ;
  - `st-vignette` : vignette.

## Transitions
- `S.pushThrough(tl, sortante, entrante, t, { duration })` : traversée.
- `S.iris(tl, el, t, { x, y, r })` : ouverture circulaire.
- `S.wipe(tl, el, t, { dir: "left" | "right" | "up" | "down" })` : masque balayé.

## Presets de personnalité
| | `luxe` (Aesop, Diptyque, Apple) | `tech` (Linear, Stripe) | `punchy` (food, mode, rue) |
|---|---|---|---|
| Courbe d'arrivée | `silk` | `swift` | `overshoot` ou `spring` 0.7 |
| Durée d'entrée | 1.4–2.4 s | 0.4–0.8 s | 0.25–0.5 s |
| Texte | `rise` par mots, blur 14–20, `converge` pour les logos | `rise` par lettres, blur 6–10, y 24 | `pop` par mots, `motion-blur` sur 1–3 claques |
| Décalage | mots 0.1–0.12 | lettres 0.02–0.03 | mots 0.05 |
| Caméra | push-in très lent, mise au point, brume | bascule 3D légère, pan latéral | punch-in sur les beats, secousse sur l'impact |
| Transitions | morphing de fenêtre, fondu + zoom | traversée, masque, match cut | flash, fouetté, coupe sur le beat |
| Finition | grain 6 %, halos dorés, vignette | grain 4 %, liserés, ombres nettes | grain 8 %, flash, couleurs franches |
| Son | nappe, souffles | clics, whoosh légers | impacts, riser, beat |

## Gabarit de script de composition
```js
window.__timelines = window.__timelines || {};
(function () {
  const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
  const tl = gsap.timeline({ paused: true });
  // 1. caméra et calques ; 2. entrées (texte découpé, ressorts) ; 3. vie continue ; 4. reflets ; 5. transitions ; 6. grain
  tl.to({}, { duration: TOTAL }, 0);
  window.__timelines["main"] = tl;   // enregistrer APRÈS avoir tout construit
})();
```
