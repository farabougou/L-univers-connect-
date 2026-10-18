# Place the client's ElevenLabs voiceover (Anna, 26.7 s) on the Nessa Paris film. Writes assets/voice + voice.json.
# The read is quick, so each sentence is cut out at its pause and given room inside its scene (scene starts in gen.py:
# 0, 4.6, 8.2, 14.5, 20.3, 25.9, 31.2, 35.6). Columns: cut start, cut end, first word inside the cut, where that word lands.
import os, json, sys, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read(sys.argv[1])
CL = [(0.00, 1.05, 0.04, 1.50),    # Nessa Paris.
      (1.05, 3.36, 1.28, 4.95),    # Votre peau a sa propre lumière.
      (3.36, 8.39, 3.57, 9.00),    # Soft Glow : papaye, niacinamide… pour une peau plus nette, plus lumineuse.
      (8.39, 13.14, 8.55, 14.95),  # Papaye, carotte, curcuma : le meilleur de la nature, au service de votre éclat.
      (13.14, 17.56, 13.31, 21.00),  # Intense Glow Skin : la version intense, pour les imperfections les plus marquées.
      (17.56, 21.20, 17.73, 26.40),  # Nettoyer, réparer, hydrater : le rituel visage.
      (21.20, 24.26, 21.34, 31.80),  # Bridal Glow Ritual : le rituel des grands jours.
      (24.26, len(x) / sr, 24.45, 36.05)]  # Nessa Paris. Révélez votre éclat.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
out = []
for i, (a, b, w, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)].copy()
    n = int(0.015 * sr); clip[:n] *= [k / n for k in range(n)]; clip[-n:] *= [1 - k / n for k in range(n)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    out.append([f'assets/voice/{i + 1:02d}.wav', round(at - (w - a), 2), round(len(clip) / sr, 2)])
json.dump(out, open(f'{P}/assets/voice/voice.json', 'w'), indent=1)
for o in out: print(o, 'ends', round(o[1] + o[2], 2))
