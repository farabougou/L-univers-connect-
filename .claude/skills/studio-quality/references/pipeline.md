# Pipeline studio : recettes passe par passe

Toutes les recettes utilisent `STUDIO` (`videos/_studio/studio.js`) et une seule timeline GSAP en pause par composition.

## Passe 0 — Direction
1. **Intention** : une phrase. Par exemple : « Nessa révèle l'éclat de la peau comme une lumière qui naît dans le noir. »
2. **Trois mots d'ambiance**, qui choisissent le preset de mouvement (`studio-motion-system`) :
   - « luxe, apaisant, sensoriel » → `luxe` ;
   - « net, moderne, produit » → `tech` ;
   - « énergique, rue, food » → `punchy`.
3. **Palette** : fond, un seul accent, un neutre, une couleur de lumière (le halo). L'accent ne sert qu'aux mots-clés.
4. **Typographie** : 1 police d'affichage et 1 police de texte ou mono. Graisse et taille créent la hiérarchie, pas la couleur.
5. **Carte des temps** : beats de la musique (`npx hyperframes@0.8.145 beats`) et mots de la voix (`transcribe -m small -l fr`). Chaque scène commence sur un beat ou sur un mot.
6. **Liste des plans** : pour chaque plan, le sujet, ce qu'on lit, le mouvement de caméra et la transition de sortie.

## Passe 1 — Blocking
- Poser les scènes en sous-compositions (`compositions/frames/NN-nom.html`), avec un chevauchement de 0,4 à 0,6 s pour les fondus.
- Zones sûres en 1080×1920 :
  - texte entre y = 160 et y = 1700 ;
  - marges latérales de 60 px minimum ;
  - rien d'important dans les 300 px du bas (interface TikTok et Reels).
- Faire une planche de frames (6 à 15 instants) et ne passer à la suite que si tout est lisible.

## Passe 2 — Chorégraphie
- **Ordre** : fond → sujet → titre → détails → appel à l'action. Le regard suit l'ordre d'apparition.
- **Décalages** (`STUDIO.stagger`) : lettres 28 ms, mots 70 ms, lignes 140 ms, objets 90 ms. Plafonner le groupe à 0,6 s (`cap()`).
- **Chevauchement** : l'élément suivant démarre quand le précédent en est à 50–70 % de son mouvement, jamais après sa fin.
- **Sorties** : environ 60 % de la durée d'entrée, courbe `accel` ou `exit`, petit décalage inverse (le dernier arrivé sort le premier) ou `leave()`.
- **Respiration** : laisser 0,3 à 0,8 s de calme après chaque temps fort.

## Passe 3 — Physique
- **Anticipation** : un départ fort recule d'abord légèrement. Utiliser la courbe `anticipate`, ou un petit `fromTo` de 0,12 s en sens inverse avant le mouvement principal.
- **Arrivée sur ressort** : `pop()` ou `spring({ response, damping })`.
  - damping 1 : sérieux ;
  - damping 0.8 : vivant ;
  - damping 0.7 : joueur ;
  - toujours prendre la durée donnée par le ressort.
- **Follow-through** : les éléments enfants (icône, sous-titre, ombre) arrivent 60 à 120 ms après le parent, avec la même courbe.
- **Overshoot maîtrisé** : `overshoot` (environ 6 %) pour un accent par scène au maximum.
- **Inertie continue** : `life(tl, els, début, fin)` sur tout élément qui reste à l'écran plus de 1,5 s.
  - amplitude : 4 à 8 px, 0,3 à 0,5°, 0,5 % d'échelle ;
  - période : 4 à 6 s.

## Passe 4 — Caméra et profondeur
- Ranger le décor en calques `.st-layer` dans une `.st-stage` :
  - fond (depth 0.25–0.4) ;
  - sujet (1) ;
  - premier plan (1.5–1.8) ;
  - texte (0.3–0.5, `blur: false`).
- `STUDIO.camera(tl, calques, { keys, dof, drift })`. Chaque clé peut porter :
  - `s` : zoom ;
  - `x` et `y` : pan ;
  - `rx` et `ry` : bascule 3D ;
  - `rz` : roulis ;
  - `f` : profondeur nette, c'est-à-dire la mise au point.
- Mouvements de base :
  - push-in lent : `s` de 1 à 1,06 sur toute la durée du plan ;
  - révélation : `s` de 1,2 à 1, avec une bascule `ry` de -16 à 0 ;
  - mise au point : `f` du premier plan vers le sujet en 1,5 à 2,5 s.
- La dérive « à l'épaule » (`drift`) est toujours active, mais légère : 4 à 6 px, 0,1 à 0,15°.
- Secousse de caméra sur un impact : composant `camera-shake` (profils mesurés). Ne jamais en improviser une avec un hasard.

## Passe 5 — Lumière et finition
Les recettes détaillées sont dans `finition.md`. Ordre des calques, de bas en haut :
1. fond et halos ;
2. contenu ;
3. reflets (`.st-sheen`) ;
4. grain (`.st-grain`) ;
5. vignette (`.st-vignette`).

## Passe 6 — Transitions et son
Les recettes sont dans `transitions.md`. Pour le son :
- whoosh 0,1 s avant un mouvement rapide ;
- impact exactement sur l'image d'arrivée ;
- riser qui se termine sur le temps fort ;
- musique à environ -10 dB sous la voix (gain de la musique 0,24 à 0,3, ou ducking intégré) ;
- sortie : `ffmpeg -af loudnorm=I=-14:TP=-1.0 -ar 48000 -c:a aac -b:a 192k`.

## Passe 7 — QA
1. `npx hyperframes@0.8.145 check` : 0 erreur ; lire les avertissements de contraste et de débordement.
2. Planche de frames : `ffmpeg -ss T -i rendu.mp4 -frames:v 1` sur début, milieu et fin de chaque scène et sur chaque transition, assemblées avec `xstack`.
3. Éléments héros : `npx hyperframes@0.8.145 keyframes --selector "#hero" --shot hero.png` (pelure d'oignon de la trajectoire). La courbe doit être fluide, sans saut.
4. Chorégraphie globale : `HYPERFRAMES_SKILL_PKG_VERSION=0.8.145 HYPERFRAMES_SKILL_BOOTSTRAP_DEPS=1 node ~/.claude/skills/hyperframes-animation/scripts/animation-map.mjs <projet> --out <projet>/.hyperframes/anim-map`. Chercher les temps morts et les staggers incohérents.
5. Rendus d'itération en `--quality draft` ; rendu final en `--quality high`, puis ré-encodage en `-crf 19–21` pour l'envoi.
