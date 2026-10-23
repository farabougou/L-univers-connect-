# Carte des temps de la pub Fanta shop (31,2 s, 100 BPM, 1 temps = 0,6 s), partagée par score.py, mix.py et gen.py.
# La voix off (assets/voix-off.mp3, ElevenLabs « Anna ») fait 20,9 s d'un seul souffle : elle est découpée en phrases
# et chaque phrase est posée au début de son plan, avec un temps de musique entre deux plans.
TOTAL, BEAT = 31.2, 0.6
# plans : début de chaque scène (coupe sur un temps)
CUT = {'s1': 0.0, 's2': 3.0, 's3': 7.8, 's4': 11.4, 's5': 14.4, 's6': 18.6, 's7': 22.8}
# phrases : (nom, début dans le MP3, fin approximative dans le MP3, position dans le film)
# les fins exactes sont cherchées par mix.py dans le silence le plus proche
VO = [('tu-veux', 0.0, 1.62, 0.4),          # Tu veux que ta maison sente bon ?
      ('decouvre', 1.62, 5.06, 3.3),        # Découvre le woussoulan Soumadouman, de chez Madame Traoré.
      ('rouge', 5.06, 7.41, 8.0),           # Rouge ou doré ? À toi de choisir !
      ('flacon', 7.41, 9.13, 11.6),         # Il existe aussi en flacon spray.
      ('pas-tout', 9.13, 10.10, 14.5),      # Et ce n'est pas tout !
      ('savons', 10.10, 11.94, 15.9),       # Des savons et des foulards !
      ('abonnes', 11.94, 14.77, 18.9),      # Déjà plus de 12 000 abonnés nous suivent sur TikTok.
      ('commande', 14.77, 18.70, 23.0),     # Commande maintenant au 77 22 42 50.
      ('fin', 18.70, 20.93, 27.6)]          # Fanta shop, ça sent bon chez toi !
# mots repères dans le film (position = mot dans le MP3 + décalage de sa phrase), pour caler l'image sur la voix
WORD = {'bon': 1.63, 'woussoulan': 3.82, 'soumadouman': 4.38, 'traore': 6.08, 'rouge': 8.06, 'dore': 8.58, 'choisir': 9.62,
        'flacon': 12.54, 'spray': 12.95, 'tout': 15.06, 'savons': 16.07, 'foulards': 16.88, 'douze-mille': 19.36,
        'abonnes': 20.02, 'tiktok': 21.27, 'numero': 24.11, 'fanta-shop': 27.65, 'sent-bon': 28.5}
PAIRS = [24.3, 25.0, 25.7, 26.4]            # 77 · 22 · 42 · 50 : chaque paire de chiffres se pose quand elle est dite
