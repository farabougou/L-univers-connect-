---
name: studio-quality
description: Passe Qualité Studio (niveau Apple / Linear / Stripe) à appliquer automatiquement à CHAQUE vidéo HyperFrames de ce dépôt — création, retouche, recalage sur une voix off. À charger avant d'écrire ou de modifier une composition dans videos/, en plus de /hyperframes. Donne les 12 interdits, le pipeline en 7 passes, les choix de direction artistique et la grille d'acceptation avant envoi.
---

# Passe Qualité Studio

But : aucune vidéo ne doit avoir l'air « générée par du code ». Chaque plan est mis en scène comme dans un studio de motion design : une intention, une hiérarchie, un rythme, une physique, une lumière, une caméra, un son.

Ce skill fixe le **niveau d'exigence**. Le contrat technique reste celui des skills HyperFrames (`/hyperframes`, `hyperframes-core`, `hyperframes-animation`) : les deux s'appliquent ensemble.

## Quand l'appliquer
- Toute nouvelle vidéo dans `videos/` (pub, film de marque, showreel, démo d'app).
- Toute retouche (« c'est pas top », « plus fluide », « plus pro », « plus luxe ») : appliquer aussi `studio-polish-pass`.
- Tout recalage sur une voix off : le recalage ne doit pas casser la chorégraphie (refaire les passes 2 à 6 sur les scènes touchées).

## Outils maison (à utiliser par défaut)
- `videos/_studio/studio.js` + `studio.css` : système de design motion (courbes, ressorts, texte découpé, vie continue, caméra 2.5D avec profondeur de champ, grain, reflets, transitions). Copier dans `<projet>/assets/vendor/`. API et presets : skill `studio-motion-system`.
- `videos/_studio/demo/` : démo de référence de 9 s qui utilise tout le système. Repartir de son `.src/gen.py` pour un nouveau projet.
- Registre HyperFrames : chercher avant de construire (`npx hyperframes@0.8.145 catalog <mot>`, puis `add <nom>`). Composants validés : `motion-blur`, `vignette`, `light-sweep-pass`, `grain-overlay`, `camera-shake`, `rack-focus`, `focus-rack`, `morph-text`, `svg-mask-reveal`, `shimmer-sweep`, `push-in`, `pull-back-reveal`, `whip-pan-cut`, `organic-light-leak-overlay`, `extended-keyframe`, `drift-hold`.
- Blocs « shader » (WebGL / WebGPU : `light-leak`, `cinematic-zoom`, `cross-warp-morph`, `whip-pan`, `godrays`, `mesh-gradient`…) : le conteneur cloud rend en logiciel (`WebGL unavailable`). Ne jamais les livrer sans un rendu de test réussi.

## Les 12 interdits
| # | Interdit (rendu « code ») | Correction studio |
|---|---|---|
| 1 | Mouvement linéaire (`ease: "none"`) | Courbes organiques. `none` seulement pour les pilotes canvas et une caméra déjà adoucie par ses clés. |
| 2 | Une seule courbe pour tout le film | 3 caractères de courbe : arrivée (`silk` ou `swift`), déplacement (`glide`), sortie (`accel` ou `exit`), plus 1 accent (ressort ou `overshoot`). |
| 3 | Tout bouge en même temps | Hiérarchie : le héros d'abord, le reste en écho. Décalages de 20 à 120 ms ; un groupe tient en 0,6 s maximum. |
| 4 | Un bloc de texte apparaît d'un coup | Texte découpé en lettres, mots ou lignes, avec masque, flou ou rotation légère (`split` + `rise` / `maskUp` / `converge`). |
| 5 | Un élément reste figé plus de 1,5 s | Vie continue : `life()`, dérive de caméra, halo qui respire, reflet qui passe. |
| 6 | Fond plat et immobile | Au moins 2 plans de profondeur (fond lointain + sujet), une lumière qui bouge, du grain. |
| 7 | Coupe sèche hors d'un temps fort | Transition motivée (traversée, masque, match cut, balayage). Une coupe franche seulement sur un beat ou un mot. |
| 8 | Une ombre grise unique, ou pas d'ombre | Élévation multicouche (`st-elev-1/2/3`) et liseré de lumière (`st-rim`). |
| 9 | Du flou de mouvement partout | Seulement sur 1 à 3 « claques » rapides par film (composant `motion-blur`). Un texte à lire arrive net. |
| 10 | Rebond cartoon (`bounce`, `elastic`, `back` au-delà de 1.7) | Ressort physique `spring()` avec damping de 0.75 à 1. |
| 11 | Animer `letter-spacing`, `width`, `height`, `top` ou `left` | Transforms, masques, `clip-path`, `converge()`. |
| 12 | Texte illisible | Au-delà de 7 mots en moins de 1,5 s, texte hors zone sûre, ou texte en mouvement au moment où il doit être lu : tenir chaque phrase nette au moins 1 s. |

## Pipeline : 7 passes dans cet ordre
Chaque passe a son livrable. Le détail, les recettes et le code sont dans `references/pipeline.md`.

| # | Passe | Livrable |
|---|---|---|
| 0 | Direction | Intention en une phrase, 3 mots d'ambiance, palette (fond, accent, neutre, lumière), 1 ou 2 polices, preset de mouvement (`luxe`, `tech` ou `punchy`), carte des temps (voix et beats), liste des plans avec le mouvement de caméra prévu. |
| 1 | Blocking | Scènes posées aux bons temps, lisibilité et zones sûres vérifiées sur une planche de frames. Pas encore de finition. |
| 2 | Chorégraphie | Ordre d'entrée, staggers, chevauchements (B part quand A en est à 50–70 %), sorties plus courtes que les entrées (environ 60 %). |
| 3 | Physique | Anticipation sur les départs forts, ressort sur les arrivées, follow-through (les enfants arrivent après le parent), vie continue. |
| 4 | Caméra et profondeur | Calques par profondeur, push-in lent sur chaque plan tenu, mise au point, parallaxe, un mouvement « signature » par film. |
| 5 | Lumière et finition | Halos, reflets, ombres multicouches, grain (6–9 %), vignette, flou de mouvement ciblé, étalonnage cohérent. |
| 6 | Transitions et son | Liaisons motivées entre scènes ; whoosh, impact et riser calés à l'image près ; musique sous la voix ; -14 LUFS en sortie. |
| 7 | QA | `check`, planches de frames, `keyframes --shot` sur les éléments héros, lecture complète, grille ci-dessous. |

## Grille d'acceptation (tout doit être OUI avant l'envoi)
- [ ] Chaque plan a un sujet clair, une entrée, une vie et une sortie.
- [ ] Aucun groupe d'éléments ne démarre ni ne s'arrête d'un bloc.
- [ ] Chaque phrase importante reste nette et immobile au moins 1 s.
- [ ] Le fond n'est jamais immobile ; chaque plan tenu plus de 2 s a un mouvement de caméra.
- [ ] Chaque transition est motivée par une forme, un mouvement, une couleur ou un son.
- [ ] Planche de frames vérifiée : début, milieu et fin de chaque scène, et chaque transition.
- [ ] `npx hyperframes@0.8.145 check` passe sans erreur, et les avertissements ont été lus.
- [ ] Son : voix intelligible, musique en dessous, pas de saturation, -14 LUFS en sortie.
- [ ] Rien d'inventé (prix, chiffres, logos, avis) sans validation du client.

## Pièges déjà rencontrés dans ce dépôt
- Un tween de `filter` qui part de `none` démarre à `brightness(0)` : poser une base CSS (`filter: brightness(1)` ou `blur(0px)`) ou utiliser `fromTo`.
- Un `transform` CSS et un `x` / `xPercent` GSAP sur le même élément : GSAP écrase le CSS. Un calque = une responsabilité (wrapper pour la caméra, enfant pour l'entrée).
- `letterSpacing` est bloqué par le lint : utiliser `STUDIO.converge`.
- Les masques de texte coupent les accents (À, Ç) : utiliser `.st-mask` (padding et marge négative).
- Plusieurs `fromTo` sur la même cible : `immediateRender: false` sur tous sauf le premier.
- Ne jamais mesurer le DOM pendant le rendu : calculer les positions au montage.
- Sous-compositions : ids préfixés (`X-` → `sNN-`) et sélecteurs limités à la scène (`R()`).
- Clips vidéo : `muted` et `data-media-start`. Envoi à l'utilisateur limité à 30 Mo : ré-encoder avec `-crf 19–21`.
