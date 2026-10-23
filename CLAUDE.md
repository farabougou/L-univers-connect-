# Mémoire du projet (lue par Claude à chaque session)

**Task Observer** : charger le skill `task-observer` avant le premier appel d'outil de chaque session.
- Son dossier de travail est `.claude/observations/`, à la racine du dépôt.
- À la fin de chaque session, faire un commit et un push de ce dossier : c'est ce qui le conserve d'une session à
  l'autre, sur le cloud comme sur le PC.

## Qui
Mohamed, dit **Mams**. Motion designer et développeur débutant. Il crée des pubs vidéo, des sites internet et des
applis mobiles. Il est sur TikTok sous **@kofamali** (55 000 abonnés).
- Ses produits : **KOFA** (appli de livraison), un **SaaS tout-en-un** (nom à confirmer) et **Enoryx** (énergie et
  bâtiments).
- Il n'habite **pas** à Bamako. Ne jamais l'écrire ni le laisser entendre. Le mot reste possible quand il parle des
  clients ou d'un marché.

## Comment lui répondre
- En français simple, une étape à la fois.
- **Réponses courtes : ce qui est fait, ce qu'il doit faire. Pas de remplissage** (« Stop slop »).
- Textes à copier dans des blocs.

## Règles
- Ne pas refaire les vidéos déjà livrées sans qu'il le demande.
- Ne jamais lui demander de coller une clé API dans la conversation. Ne jamais versionner de fichier `.env`.
- Rien d'inventé : prix, chiffres, logos clients, avis. Demander l'accord d'une marque avant de montrer son travail
  comme une référence client.
- Voix off : il envoie des MP3 ElevenLabs (voix « Nicolas Petit IA »). Ne pas reparler de la configuration de l'API
  ElevenLabs.
- Il ne montre jamais son visage. Son personnage est l'avatar masqué au M orange. Sur TikTok, cocher « Contenu généré
  par l'IA ».

## Marque
- Couleurs : orange `#FF4F1F`, bleu `#2340FF`, encre `#141414`, crème `#F3EBDD`.
- Polices : Archivo Black, Instrument Serif italique, Plex Mono.
- Logo : le M d'un seul trait (`videos/_studio/avatar/logo-m.svg` et `logo-m-neon.svg`).
- Photo de profil : `videos/_studio/avatar/profil-tiktok.png`.
- Pas d'astérisque orange : il ressemble au logo de Claude.

## Vidéos (HyperFrames)
- Système maison : `videos/_studio` (studio.js), skills `studio-quality`, `studio-motion-system` et `studio-polish-pass`.
- Nouveau projet : `hyperframes@0.8.177`.
- Rendu en 60 i/s, son à -14 LUFS avec une crête sous -1 dB, formats 4:5 et 1:1 avec
  `videos/_studio/livraison.py`.
- Projets en cours :
  - `videos/motion-reel` : showreel de 33 s ;
  - `videos/mams-avatar` : présentation de l'avatar ;
  - `videos/_studio/serie-avatar.md` : scripts des épisodes 2 à 6 ;
  - `videos/_studio/plan-tiktok.md` : plan de publication.
  - `videos/fanta-shop` : pub de la boutique Fanta shop (@fantafofana61), voix off ElevenLabs « Anna », 9:16
    (`index.html`) et 16:9 (`paysage/`, dont `assets` est un lien vers `../assets`).
  - `videos/farmasi` : pub Farmasi « un rituel pour chaque instant » (36 s, 9:16 et 16:9), images du site officiel ;
    voix off à venir (texte dans `.src/voix-off.txt`).
- Branche de travail : `claude/upbeat-noether-hso8ah`. Sur son PC : `Documents\Univers-videos`, puis `git pull`.
