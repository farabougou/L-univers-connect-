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
