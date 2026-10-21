# Avatar HeyGen de Mams (TikTok @kofamali)

Mams ne montre jamais son visage. L'avatar devient son visage de marque : toujours le même, aux couleurs du studio
(orange #FF4F1F, bleu #2340FF), présenté honnêtement comme un avatar IA (« je m'en suis créé un »).

## Les deux styles à comparer

Coller la description dans HeyGen (Avatars → Créer un avatar → générer avec l'IA / à partir d'une description).

**1 · Personnage 3D (recommandé)**

> Stylized 3D animated character in the style of a modern animated feature film, a young West African man in his late
> twenties, warm dark brown skin, short twisted hair, neat short beard, friendly confident smile, wearing a bright orange
> hoodie (#FF4F1F) with small cobalt blue details (#2340FF) and modern headphones around his neck, soft studio lighting
> with an orange rim light on one side and a blue rim light on the other, clean dark charcoal background, chest-up
> framing, looking straight at the camera, vertical 9:16, high detail.

**2 · Humain réaliste IA**

> Photorealistic portrait of a young West African man in his late twenties, short twisted hair, neat short beard,
> confident friendly expression, wearing a plain black t-shirt under an orange overshirt, modern creative studio
> background with soft bokeh lights in orange and blue, natural soft light, chest-up framing, looking straight at the
> camera, vertical 9:16, high detail.

TikTok : pour l'avatar réaliste, cocher « Contenu généré par l'IA » à la publication.

## Premier script (≈ 20 s, présentation)

> Vous êtes cinquante-cinq mille à me suivre… et vous n'avez jamais vu mon visage.
> Alors je m'en suis créé un.
> Moi, c'est Mams. Je crée des pubs vidéo, des sites internet et des applis mobiles. Cent pour cent en code.
> Votre prochaine pub… c'est peut-être moi qui la fais. Écrivez-moi en message.

Montage prévu : l'avatar en plan poitrine dans la carte du reel, habillage du motion reel (HUD, sous-titres
mot à mot, extraits du mur de pubs pendant « pubs vidéo, sites, applis »), fin sur @kofamali.

## Brancher HeyGen pour que Claude génère tout seul

- **Sans réglage technique** : créer l'avatar et la vidéo sur heygen.com, puis envoyer le MP4 à Claude, comme les voix
  off ElevenLabs.
- **En automatique** :
  1. Créer une clé sur app.heygen.com/settings?nav=API (elle consomme des crédits API HeyGen).
  2. L'ajouter dans les réglages de l'environnement Claude (menu de l'environnement dans la barre de titre → Modifier →
     Network secrets, sinon variable d'environnement) sous le nom `HEYGEN_API_KEY`.
  3. Ouvrir une nouvelle session : elle lit la clé.
  4. Ne jamais coller la clé dans la conversation.

  Outil côté Claude : `curl -fsSL https://static.heygen.ai/cli/install.sh -o install.sh`, relire, `bash install.sh`, puis
  `heygen avatar create` (type `prompt`) et `heygen video create --wait` (type `avatar`). La connexion par code
  (`--device`) est réservée à une personne devant un terminal : ne pas la forcer.
