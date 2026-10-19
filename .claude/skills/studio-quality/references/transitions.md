# Transitions : lier deux scènes sans coupure sèche

Règle : une transition est **motivée**. Elle reprend une forme, un mouvement, une couleur ou un son de la scène qui part. Une coupe franche n'est permise que sur un beat ou sur un mot.

| Transition | Quand | Comment |
|---|---|---|
| Traversée (push-through) | Changement d'idée, énergie moyenne | `STUDIO.pushThrough(tl, sortante, entrante, t)` : la sortante fonce vers la caméra en se floutant, l'entrante arrive de derrière avec 40 % de chevauchement. |
| Match cut géométrique | Même forme d'une scène à l'autre (rond → pastille → logo) | Placer la forme d'arrivée exactement à la position et à la taille de la forme de départ, puis la transformer (`scale`, `borderRadius`, `clip-path`). Règle `card-morph-anchor`, composant `morph-swap`. |
| Morphing de fenêtre | Photo → photo (film de marque) | La fenêtre se referme en `clip-path inset(... round ...)` et la suivante s'ouvre depuis la même forme. Voir `morph_in` / `morph_out` dans `videos/nessa-paris/.src/gen.py`. |
| Iris | Révélation d'un produit ou d'un logo | `STUDIO.iris(tl, entrante, t, { x, y })`, centré sur le sujet qui arrive. |
| Masque balayé | Liste, comparaison, avant / après | `STUDIO.wipe(tl, entrante, t, { dir })`, avec un liseré lumineux (`.st-sheen`) qui suit le bord. |
| Fouetté (whip pan) | Énergie haute, `punchy` | Composant `whip-pan-cut` (flou directionnel plafonné). |
| Flash | Temps fort musical | Calque blanc ou couleur de lumière de 0,6 vers 0 en 0,25 s, sur l'image du beat. Composant `editorial-flash-overlay` pour une version plus organique. |
| Fondu enchaîné | Film luxe, entre deux plans calmes | Opacité de 0,5 à 0,6 s, courbe `breath`, et toujours un autre mouvement en même temps (zoom ou flou), jamais un fondu seul. |
| Texte qui se transforme | Mot → mot | Composant `morph-text` (fusion gluante). |

À éviter :
- iris en étoile ;
- tilt-shift ;
- faux lens flare en CSS ;
- charnière ou porte ;
- toute transition shader non testée dans le conteneur.
