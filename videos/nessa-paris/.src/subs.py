# Sous-titres du film (fichier .srt à joindre sur Facebook / YouTube), calés sur les mots d'Anna.
# Les mots viennent de la transcription de la voix brute (assets/voice/words.json) ; chaque phrase a été déplacée dans
# le film par .src/vo.py, donc un mot à l'instant w de la voix tombe à  at + (w - début de sa coupe).
# Pas de sous-titres incrustés : tout ce que dit la voix est déjà écrit à l'écran (lisible sans le son).
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = json.load(open(f'{P}/assets/voice/words.json'))
CUTS = [0.00, 1.05, 3.36, 8.39, 13.14, 17.56, 21.20, 24.26]          # débuts des coupes (voir .src/vo.py)
AT = [c[1] for c in json.load(open(f'{P}/assets/voice/voice.json'))]  # où chaque coupe démarre dans le film
CHUNKS = [('Nessa Paris.', 0, 1), ('Votre peau a sa propre lumière.', 2, 7), ('Soft Glow : papaye, niacinamide…', 8, 11),
          ('pour une peau plus nette, plus lumineuse.', 12, 18), ('Papaye, carotte, curcuma :', 19, 21), ('le meilleur de la nature,', 22, 26),
          ('au service de votre éclat.', 27, 31), ('Intense Glow Skin :', 32, 34), ('la version intense,', 35, 37),
          ('pour les imperfections les plus marquées.', 38, 43), ('Nettoyer, réparer, hydrater :', 44, 46), ('le rituel visage.', 47, 49),
          ('Bridal Glow Ritual :', 50, 52), ('le rituel des grands jours.', 53, 57), ('Nessa Paris.', 58, 59), ('Révélez votre éclat.', 60, 62)]
def film(t, ref=None):
    # ref : instant qui choisit la coupe (le début du mot), pour qu'une fin de mot étirée par la transcription
    # au-delà de la coupe reste dans sa phrase
    k = max(i for i, c in enumerate(CUTS) if c <= (t if ref is None else ref))
    if k + 1 < len(CUTS): t = min(t, CUTS[k + 1])
    return AT[k] + (t - CUTS[k])
def ts(t):
    ms = int(round(t * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'
rows = [(film(W[a]['start']) - 0.05, film(W[b]['end'], W[b]['start']) + 0.3, txt) for txt, a, b in CHUNKS]
srt = ''
for i, (a, b, txt) in enumerate(rows):
    if i + 1 < len(rows): b = min(b, rows[i + 1][0] - 0.05)
    srt += f'{i + 1}\n{ts(a)} --> {ts(b)}\n{txt}\n\n'
open(f'{P}/renders/nessa-paris.srt', 'w', encoding='utf-8').write(srt)
print(srt[:400])
