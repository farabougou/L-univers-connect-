---
format: 1080x1920
duration: 45s
message: "KOFA, bientôt disponible à Bamako : repas, courses et colis livrés en toute confiance"
arc: Hook → Produit → Atout 1 suivi en direct → Atout 2 note vocale → Atout 3 code 4 chiffres → Diaspora → Bientôt disponible
audience: Habitants de Bamako et diaspora malienne
music: none
mode: autonomous
language: fr
---

## Video direction

- palette: fond ink-black #0E0E10, surfaces #1A1A1D, texte blanc, orange KOFA #EB6834 = la couleur dominante (accent, mots clés, CTA, fond plein du final). Secondaires uniquement comme signaux fonctionnels : bleu #2A78D6 (tuile « K », tracé de la route), vert #1BAF7A (livreur en mouvement, code validé), jaune #EDA100 (onde de la note vocale), violet #4A3AA7 (arcs secondaires diaspora). Jamais plus de deux secondaires dans un même plan.
- type: Inter partout — display 900 en minuscules pour les mots-héros ; IBM Plex Mono en majuscules espacées pour les petites étiquettes (kickers, ETA, villes).
- motion grammar: entrées en `fromTo`, courbes longues `power3.out` (doux plutôt que rebondi), un seul `back.out` léger réservé aux tampons (pin de carte, chiffres du code). Révélations calées sur la voix : chaque élément arrive quand la voix le nomme. Pendant les tenues : immobile ou très léger (pulsation du point livreur, onde vocale).
- objets récurrents : un téléphone épuré (cadre arrondi #1A1A1D, bord fin) porte les trois atouts — même gabarit, centré, ~62 % de la largeur — pour que les trois démonstrations se lisent comme une seule app.
- rythme: 01 très rapide (accroche) → 02 tenue courte (marque) → 03-05 démonstrations vives → 06 plus lent et émouvant (carte) → 07 final tenu et calme.
- keep-out: tout le contenu au-dessus de y = 1600 px (bande des sous-titres).
- negative list: pas de dégradés violets « IA », pas de bokeh flottant, pas de curseur, pas de logos de marques tierces redessinés, pas de promesse non vérifiée (prix, délais, « disponible aujourd'hui »). Pas de diaporama figé, pas d'éléments qui flottent sans raison.

## Frame 1 — Tout, livré

- scene: Un seul mot change à toute vitesse au centre — « un repas ? », « des courses ? », « un colis ? » — puis « KOFA livre. » s'écrase et prend l'écran.
- voiceover: "Un bon repas ? Des courses ? Un colis à envoyer ? À Bamako, KOFA s'en occupe."
- duration: 5.1s
- transition_in: cut
- status: animated
- src: compositions/frames/01-tout-livre.html
- type: hook
- persuasion: Rule of three + category claim
- beat: curiosity → excitement
- blueprint: ticker-takeover (Adapt)
- asset_candidates:
- focal: typographie
- roles: aucun asset (plan typographique)

Adapt: garder le cycle d'un mot dans un emplacement fixe puis le « crash » du héros ; trois options au lieu de cinq, chacune avec une petite icône dessinée (assiette, panier, carton).
Scene 1 (0.0–0.9s): fond ink ; kicker mono « BAMAKO · MALI » en haut. Au centre, « un repas ? » en display blanc avec l'icône assiette orange au-dessus — Centered, le mot ~80 % de largeur.
Scene 2 (0.9–1.8s): le mot glisse vers le haut et sort de son emplacement, « des courses ? » monte à sa place (icône panier).
Scene 3 (1.8–2.9s): même relève : « un colis ? » (icône carton).
Scene 4 (2.9–5.0s): sur « KOFA s'en occupe », « kofa » en display orange géant s'écrase depuis une échelle 1.4 avec un court flash, remplaçant le cycle ; dessous « s'en occupe. » en blanc ; tenue.

## Frame 2 — KOFA

- scene: La tuile bleue « K » s'assemble, « KOFA » se pose, puis trois pastilles « repas · courses · colis » ; une étiquette « bientôt à Bamako ».
- voiceover: "KOFA, la livraison pensée pour Bamako : vos repas, vos courses et vos colis."
- duration: 5.09s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/02-kofa.html
- type: product_intro
- persuasion: Brand promise
- beat: desire + belonging
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates:
- focal: logo
- roles: aucun asset

Adapt: garder l'assemblage du logo autour d'une marque fixe ; remplacer la poussée finale vers une URL par trois pastilles de services.
Scene 1 (0.0–1.4s): quatre carrés bleus arrivent des coins et se fusionnent en tuile arrondie bleue « K » au centre-haut (y ≈ 32 %) ; « KOFA » en display blanc apparaît dessous lettre par lettre.
Scene 2 (1.4–3.6s): sur « vos repas, vos courses et vos colis », trois pastilles (fond #1A1A1D, icône + mot) se posent une à une sous le logo — repas (orange), courses (vert), colis (jaune).
Scene 3 (3.6–5.0s): une étiquette mono orange « BIENTÔT À BAMAKO » se tape sous les pastilles ; tenue.

## Frame 3 — Suivi en direct

- scene: Un téléphone montre une carte stylisée de Bamako (le fleuve Niger, des rues) ; un point vert de livreur avance le long d'une route bleue vers le pin orange « vous » ; la carte d'ETA indique « votre livreur arrive · 6 min ».
- voiceover: "Suivez votre livreur en direct, sur la carte, jusqu'à votre porte."
- duration: 5.22s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/03-suivi-direct.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: control + peace of mind
- blueprint: device-surface-showcase (Adapt)
- asset_candidates:
- focal: téléphone avec carte
- roles: téléphone = hero (reconstruction d'interface, aucun asset capturé ne montre le suivi)

Adapt: garder le téléphone comme héros et l'interface qui avance pas à pas sans curseur ; l'écran est une reconstruction (le suivi n'apparaît sur aucune capture).
Scene 1 (0.0–1.2s): kicker « ATOUT 1 » + titre « suivi en direct » (display, « en direct » orange) en haut ; le téléphone monte depuis le bas, écran : carte sombre avec le Niger en bande bleu-gris et un quadrillage de rues.
Scene 2 (1.2–3.6s): sur « en direct, sur la carte », la route bleue se dessine du restaurant au pin « vous » ; le point vert du livreur glisse le long de la route, un halo pulse autour de lui.
Scene 3 (3.6–6.0s): sur « jusqu'à votre porte », la carte ETA glisse du bas de l'écran (« votre livreur arrive · 6 min ») ; le point atteint presque le pin ; le pin rebondit légèrement ; tenue.

## Frame 4 — Note vocale

- scene: Le téléphone montre l'écran de commande : « adresse de livraison » avec un bouton micro ; on appuie, une onde jaune enregistre, puis une bulle « note vocale · 0:12 » se pose avec la transcription « derrière la mosquée, portail bleu ».
- voiceover: "Votre adresse est difficile à trouver ? Laissez une note vocale à votre livreur. Il saura où aller."
- duration: 6.75s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/04-note-vocale.html
- type: feature_showcase
- persuasion: Local insight (oralité) + friction reduction
- beat: relief + recognition
- blueprint: device-surface-showcase (Adapt)
- asset_candidates:
- focal: téléphone avec note vocale
- roles: téléphone = hero (reconstruction)

Adapt: même gabarit téléphone que le frame 3 ; le cœur du plan est le geste enregistrer → bulle envoyée.
Scene 1 (0.0–2.2s): kicker « ATOUT 2 » + titre « note vocale » (« vocale » orange) en haut ; le téléphone est déjà en place (même position que frame 3) : champ « adresse de livraison » vide avec un point d'interrogation qui clignote doucement, bouton micro orange en bas d'écran.
Scene 2 (2.2–4.6s): sur « laissez une note vocale », le bouton micro s'enfonce et grossit, une onde jaune de barres s'anime, un compteur mono 0:00→0:12 tourne.
Scene 3 (4.6–7.0s): sur « il saura où aller », la bulle « note vocale · 0:12 » se pose dans le fil avec une coche verte « envoyée au livreur » ; tenue.

## Frame 5 — Code à 4 chiffres

- scene: Le téléphone montre « votre code de confirmation » et quatre cases ; les chiffres 4 · 8 · 2 · 7 se posent un à un, puis les cases virent au vert avec « commande remise ✓ ».
- voiceover: "À la réception, donnez votre code à quatre chiffres. Votre commande est remise à la bonne personne."
- duration: 6.66s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/05-code.html
- type: feature_showcase
- persuasion: Trust / risk reversal
- beat: trust + security
- blueprint: compose
- asset_candidates:
- focal: les quatre chiffres
- roles: téléphone = hero (reconstruction)

Scene 1 (0.0–1.6s): kicker « ATOUT 3 » + titre « code à 4 chiffres » (« 4 chiffres » orange) ; téléphone en place, icône bouclier, libellé « votre code de confirmation », quatre cases vides.
Scene 2 (1.6–3.8s): sur « donnez votre code à quatre chiffres », 4 · 8 · 2 · 7 se tamponnent un par un dans les cases (léger rebond), chacun avec un petit flash orange.
Scene 3 (3.8–7.0s): sur « remise à la bonne personne », le contour des cases passe au vert, une pastille verte « commande remise ✓ » glisse sous les cases, le bouclier se remplit de vert ; tenue.

## Frame 6 — Où que vous soyez

- scene: Vraie carte du monde sombre. Des points s'allument à Paris, Bruxelles, New York, Montréal, Dakar, Abidjan, Dubaï ; des arcs orange partent de chaque ville et convergent vers Bamako, qui pulse.
- voiceover: "Vous vivez à Paris, à New York ou à Dakar ? Commandez et payez à distance pour vos proches à Bamako."
- duration: 8.13s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/06-diaspora.html
- type: feature_showcase
- persuasion: Emotional future pacing
- beat: longing → warmth
- blueprint: compose
- asset_candidates:
- focal: carte du monde
- roles: carte = background plein cadre (générée depuis les données géographiques Natural Earth)

Scene 1 (0.0–1.0s): titre « où que vous soyez » en haut (display, « vous » orange) ; la carte (Europe-Afrique-Amérique du Nord, projection centrée sur l'Atlantique) apparaît en points/contours gris, une lente poussée vers Bamako tourne dessous.
Scene 2 (1.0–4.2s): sur « Paris… New York… Dakar », chaque ville s'allume quand elle est nommée (Paris, puis New York, puis Dakar), avec son étiquette mono ; puis Bruxelles, Montréal, Abidjan, Dubaï s'allument en vague.
Scene 3 (4.2–8.0s): sur « commandez et payez à distance », des arcs orange (et violets pour les secondaires) se dessinent de chaque ville vers Bamako ; le point de Bamako pulse, étiquette « BAMAKO » en orange ; tenue sur la convergence.

## Frame 7 — Bientôt disponible

- scene: Fond orange plein. Tuile « K » + KOFA au centre, la phrase « bientôt disponible à Bamako » se pose ; deux pastilles « Play Store » et « App Store » avec « déjà téléchargeable ».
- voiceover: "KOFA, bientôt disponible à Bamako. L'application est déjà sur le Play Store et l'App Store."
- duration: 7.74s
- transition_in: blur-crossfade
- status: animated
- src: compositions/frames/07-bientot.html
- type: cta
- persuasion: Clear next step + anticipation
- beat: anticipation → urgency-to-act
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates:
- focal: logo + message de fin
- roles: aucun asset

Adapt: garder l'assemblage du logo sur fond plein ; la poussée finale devient la phrase de fin, puis les deux pastilles des stores.
Scene 1 (0.0–1.5s): fond orange ; la tuile « K » (blanche sur orange, K orange) tombe au centre-haut avec un léger rebond ; « KOFA » en display ink apparaît dessous.
Scene 2 (1.5–3.8s): sur « bientôt disponible à Bamako », « bientôt disponible » puis « à Bamako. » montent mot à mot en display ink.
Scene 3 (3.8–7.0s): sur « déjà sur le Play Store et l'App Store », deux pastilles ink (texte blanc, simples icônes géométriques — pas de logos officiels) se posent côte à côte ; tenue finale, puis léger fondu au noir sur les 0.4 dernières secondes.
