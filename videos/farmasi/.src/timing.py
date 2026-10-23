# Carte des temps de la pub Farmasi « un rituel pour chaque instant » (36 s, 100 BPM, 1 temps = 0,6 s, 1 mesure = 2,4 s),
# partagée par score.py et gen.py. Chaque moment de la journée est un plan ; on passe de l'un à l'autre par un balayage
# d'horloge (l'aiguille fait le tour de l'écran). Les fenêtres VOIX sont celles du texte de voix off donné à Mams.
TOTAL, BEAT = 36.0, 0.6
CUT = {'s0': 0.0, 's1': 4.2, 's2': 12.0, 's3': 19.8, 's4': 27.6}   # intro, matin, midi, minuit, fin
WIPE = 0.7                                                           # durée du balayage d'horloge, centré sur la coupe
VOIX = [(0.3, 3.9, 'Et si chaque instant de votre journée devenait un rituel ?'),
        (4.8, 8.0, 'Le matin, le soin Age Reversist de Dr. C. Tuna.'),
        (12.5, 16.0, 'À midi, Nutriplus, pour un quotidien plus équilibré.'),
        (20.3, 25.2, 'Et à minuit… la magie commence. Midnight Ritual, en édition limitée.'),
        (28.2, 34.0, 'Farmasi. Beauté, bien-être, opportunité. Rendez-vous sur fr.farmasi.com.')]
# Voix off reçue (assets/voix-off.mp3, ElevenLabs « Anna », 22,2 s d'un seul souffle) : découpée en phrases par mix.py.
# (nom, début dans le MP3, fin dans le MP3, position dans le film) — chaque limite tombe dans un silence du MP3.
VO = [('rituel', 0.0, 3.5, 0.4),        # Et si chaque instant de votre journée devenait un rituel ?
      ('matin', 3.5, 7.3, 4.25),        # Le matin, le soin Age Reversist de Dr. C. Tuna.
      ('midi', 7.3, 11.0, 12.15),       # À midi, Nutriplus, pour un quotidien plus équilibré.
      ('minuit', 11.0, 13.72, 19.95),   # Et à minuit, la magie commence.
      ('midnight', 13.72, 16.45, 22.8), # Midnight Ritual, en édition limitée.
      ('farmasi', 16.45, 19.78, 28.1),  # Farmasi. Beauté, bien-être, opportunité.
      ('site', 19.78, 22.2, 31.5)]      # Rendez-vous sur fr.farmasi.com.
