---
format: 1080x1920
duration: 30s
message: "Enoryx rend visible le gaspillage d'énergie des bâtiments et aide à le corriger avant qu'il ne coûte"
arc: Gaspillage invisible → Enjeu réglementaire → Enoryx → Détecter → Agir → Signature
audience: Gestionnaires et exploitants de bâtiments tertiaires
music: none
mode: autonomous
language: fr
---

## Video direction

- palette: fond navy #050B1A, surfaces #0C1730, texte #F8FAFC ; cyan #38BDF8 = Enoryx / données ; bleu #1D4ED8 pour la profondeur ; orange #EA580C = dérive / gaspillage ; vert #16A34A = état normal, économie.
- type: Inter 900 pour les mots-héros, IBM Plex Mono majuscules pour les étiquettes de données.
- motion: entrées fromTo power3.out, révélations calées sur la voix, données qui se tracent (courbes, anneaux orbitaux). Tenue calme en fin de plan.
- keep-out: rien sous y = 1600 px (sous-titres).
- negative: aucun chiffre d'économie promis ; pas de dégradés violets « IA » ; pas de stock photo.

## Frame 1 — Gaspillage invisible

- scene: Un immeuble de bureaux la nuit, fenêtres éteintes ; pourtant des ondes de chaleur orange s'échappent et un compteur kWh tourne tout seul. Mot-héros « invisible ».
- voiceover: "La nuit, le chauffage tourne encore. Le gaspillage d'énergie est souvent invisible."
- duration: 6.17s
- transition_in: cut
- status: animated
- src: compositions/frames/01-invisible.html
- type: hook
- blueprint: compose
- asset_candidates:

## Frame 2 — L'enjeu

- scene: Trois barres-objectifs du décret tertiaire se posent : -40 % 2030, -50 % 2040, -60 % 2050, la consommation descend en escalier.
- voiceover: "Le décret tertiaire impose moins quarante pour cent d'ici 2030."
- duration: 5.5s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/02-enjeu.html
- type: pain_point
- blueprint: dataviz-countup
- asset_candidates:

## Frame 3 — Enoryx

- scene: Le symbole orbital Enoryx s'assemble ; des pastilles d'équipements (chaudière, clim, CTA, compteur) se connectent à lui par des lignes cyan ; protocoles BACnet · Modbus · OPC UA · MQTT.
- voiceover: "Enoryx connecte vos équipements et les surveille en continu."
- duration: 4.46s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/03-enoryx.html
- type: product_intro
- blueprint: constellation-hub
- asset_candidates:

## Frame 4 — Détecter

- scene: Graphique : courbe de référence corrigée de la météo (cyan) et consommation réelle ; la réelle décroche en orange, une alerte « écart à la consigne » puis « cycles courts » s'épingle sur le pic.
- voiceover: "Il compare chaque consommation à la météo et détecte les dérives."
- duration: 4.86s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/04-detecter.html
- type: feature_showcase
- blueprint: compose
- asset_candidates:

## Frame 5 — Agir

- scene: Une carte « ordre de travail » est créée depuis l'alerte, un technicien intervient, la courbe redescend sur la référence et passe au vert ; étiquette « conformité OPERAT ».
- voiceover: "Puis il déclenche l'intervention, avant que la facture ne s'envole."
- duration: 5.01s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/05-agir.html
- type: benefit_highlight
- blueprint: compose
- asset_candidates:

## Frame 6 — Signature

- scene: Le symbole Enoryx au centre, nom ENORYX, signature « chaque kilowattheure compte ».
- voiceover: "Enoryx. Chaque kilowattheure compte."
- duration: 4.33s
- transition_in: blur-crossfade
- status: animated
- src: compositions/frames/06-signature.html
- type: cta
- blueprint: logo-assemble-lockup
- asset_candidates:
