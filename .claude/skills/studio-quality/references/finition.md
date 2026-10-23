# Finition : lumière, profondeur, matière

## Flou de mouvement
- **Composant officiel** `motion-blur` (`npx hyperframes@0.8.177 add motion-blur`) :
  - coller le contenu de `compositions/components/motion-blur.html` à la fin du `<body>` de la composition ;
  - marquer l'élément qui bouge avec `data-hf-motion-blur` ;
  - réglages par défaut : obturateur à 720°, 16 échantillons.
- Ne l'utiliser que sur une claque, un fouetté ou un zoom brutal : 1 à 3 éléments par film.
- Il lit le `transform` : animer `x`, `y`, `scale` ou `rotation`, jamais `left` ou `top`.
- Pour un mot qui doit être lu, l'approche est floue mais l'arrivée est nette, et le mot tient ensuite.
- Le flou d'entrée simple (`filter: blur()` de 10 à 16 px vers 0) n'est pas un flou de mouvement. Il sert aux apparitions douces du preset `luxe`.

## Lueurs (glow)
- Texte : trois couches avec `.st-glow` (cœur net 2 px, halo 18 px, diffusion 64 px). La couleur passe par `--st-glow`.
- Objet : un halo radial derrière le sujet (`radial-gradient(closest-side, couleur 0.35, transparent)`) qui respire en `scale` de 0,95 à 1,05 sur 4 à 6 s. Ne jamais dépasser 0,45 d'opacité.
- Point lumineux : `box-shadow: 0 0 24px couleur` sur une petite pastille, comme les puces des pills de la démo.

## Profondeur de champ
- Par la caméra : `STUDIO.camera(..., { dof: { k: 10, max: 14 } })`. Le flou de chaque calque vaut `|profondeur - f| × k`.
- Mise au point pilotée par les clés `f` (rack focus).
- Ponctuel : composant `rack-focus` (vrai bokeh d'ouverture) ou `focus-rack` (deux cartes à deux profondeurs).
- Bokeh décoratif : des disques en dégradé radial sur le calque de premier plan (profondeur 1,7) ; la caméra les floute toute seule.

## Grain et texture
- `STUDIO.grain(canvas, { fps, seed })` piloté par `STUDIO.drive`, sur un `<canvas class="st-grain">` plein cadre.
  - Opacité de 6 à 9 % en mode `overlay`.
  - Le grain change à chaque image ; il reste déterministe.
- Le grain unifie les photos, les dégradés et le texte, et casse le côté numérique trop propre.

## Dégradés dynamiques
- Halos qui dérivent : le fond canvas d'`aura.js` (projet `nessa-paris`), ou des blobs radiaux sur le calque de fond, animés par la caméra.
- Texte : dégradé balayé avec `background-clip: text` et une animation de `backgroundPosition` (règle `gradient-text-sweep` de `hyperframes-animation`).
- Ne jamais animer la liste des couleurs d'un dégradé : déplacer un dégradé plus grand que l'élément.

## Ombres multicouches
- `.st-elev-1` : petits éléments et puces.
- `.st-elev-2` : cartes et pills.
- `.st-elev-3` : appareils et héros.
- Toujours trois couches : une courte et nette, une moyenne, une longue et diffuse.
- Ajouter `.st-rim` (liseré lumineux) sur les surfaces sombres posées sur un fond sombre.
- Une ombre portée qui bouge avec l'objet doit s'agrandir et s'adoucir quand l'objet s'élève (scale de l'ombre de 1 à 1,15, opacité de 0,5 à 0,3).

## Reflets et lumière qui passe
- `STUDIO.sweep(tl, ".st-sheen", t)` sur une surface (écran, verre, pot, carte), une fois par plan au maximum.
- Lumière qui ré-éclaire toute la scène : composant `light-sweep-pass`.

## Étalonnage et vignette
- `.st-vignette` sur tout film sombre.
- Comparer des étalonnages : `npx hyperframes@0.8.177 grade-compare --for frame.png --grades '[...]'`, ou avec des LUT `.cube` (`--luts`).
- Garder la même température d'image sur tous les plans : photos client chaudes → halos dorés, pas bleus.
