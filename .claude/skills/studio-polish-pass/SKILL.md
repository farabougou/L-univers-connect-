---
name: studio-polish-pass
description: Faire monter une vidéo HyperFrames existante (ou en cours) au niveau studio, par passes successives — audit chiffré, chorégraphie, physique, caméra, lumière, transitions, son, puis comparaison avant/après. À utiliser quand Mohamed demande d'améliorer, polir, rendre plus fluide / plus pro / plus luxe une vidéo de videos/, ou dit qu'un rendu « fait code » ou « n'est pas top ».
---

# Passe de polish sur une vidéo existante

À appliquer avec `studio-quality` (les interdits et la grille) et `studio-motion-system` (les outils).

## Étape 1 — Audit (avant de toucher au code)
1. Rendre la version actuelle (ou partir du dernier rendu) et faire une planche de frames : une image toutes les 0,5 s pour les scènes rapides, et sur chaque transition.
2. Lister les défauts par scène, avec leur timecode, en les classant selon les 12 interdits de `studio-quality`. Par exemple : « 03 · 9,2–10,4 s : titre en bloc (interdit 4), fond immobile (6), coupe sèche vers 04 (7) ».
3. Lancer la carte d'animation : `HYPERFRAMES_SKILL_PKG_VERSION=0.8.145 HYPERFRAMES_SKILL_BOOTSTRAP_DEPS=1 node ~/.claude/skills/hyperframes-animation/scripts/animation-map.mjs videos/<projet> --out videos/<projet>/.hyperframes/anim-map`. Elle repère les temps morts, les décalages incohérents et les éléments figés.
4. Classer les corrections par impact : d'abord ce qui se voit le plus (rythme, transitions, texte), puis la finition.

## Étape 2 — Passes, dans cet ordre
| Passe | Ce qu'on change | Outils |
|---|---|---|
| Chorégraphie | Ordre d'entrée, décalages, chevauchements, sorties plus courtes | `split`, `rise`, `maskUp`, `leave`, `cap` |
| Physique | Anticipation, ressorts, follow-through, vie continue | `spring`, `pop`, `anticipate`, `life` |
| Caméra | Calques de profondeur, push-in, mise au point, parallaxe | `camera`, composants `push-in`, `rack-focus`, `camera-shake` |
| Lumière | Halos, reflets, ombres multicouches, lueurs | `sweep`, `st-elev-*`, `st-rim`, `st-glow`, composant `light-sweep-pass` |
| Matière | Grain, vignette, flou de mouvement ciblé, étalonnage | `grain`, `st-vignette`, composant `motion-blur`, `grade-compare` |
| Transitions | Liaisons motivées entre toutes les scènes | `pushThrough`, `iris`, `wipe`, morphing de fenêtre, `whip-pan-cut` |
| Son | SFX calés à l'image, musique sous la voix, -14 LUFS | `<audio>` aux bons `data-start`, `ffmpeg loudnorm` |

Règles :
- Une passe à la fois, puis un rendu `--quality draft` pour contrôler.
- Ne pas changer le contenu validé par le client (textes, photos, ordre des produits) sans le dire.
- Garder le calage sur la voix : toute retouche de timing part des cues de `.src/vo.py`.

## Étape 3 — Contrôle et livraison
1. `npx hyperframes@0.8.145 check` : 0 erreur.
2. Planche avant/après aux mêmes instants : `ffmpeg … hstack`, avant à gauche et après à droite. L'envoyer avec la vidéo.
3. Rendu final en `--quality high`, ré-encodage en `-crf 19–21` et `loudnorm=I=-14`.
4. Commit : « Polish studio : <projet> », avec la liste des passes appliquées.
5. Compte rendu à Mohamed, en français simple : ce qui a changé, scène par scène, et ce qui reste possible.

## Actions ponctuelles qu'on peut demander
- « Passe chorégraphie seulement sur la scène 3. »
- « Ajoute une vraie caméra (profondeur + mise au point) au plan produit. »
- « Remplace les coupes par des transitions motivées. »
- « Ajoute du grain et une vignette, étalonnage plus chaud. »
- « Flou de mouvement sur le mot qui claque. »
- « Recale tout sur la musique (beats) ou sur la voix (mots). »
- « Fais une version 1:1 / 16:9 de la même vidéo » : recomposer les zones sûres, ne pas étirer.
- « Exporte en MOV avec transparence » (`--format mov`) ou en séquence PNG (`--format png-sequence`) pour un autre logiciel.
