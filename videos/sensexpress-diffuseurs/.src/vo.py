# Place the client's ElevenLabs voiceover (Anna, 30.5 s) on « Les Diffuseurs ». Writes assets/voice + voice.json.
# Scene starts (gen.py): 0, 4.6, 8.6, 14.8, 22.0, 27.0, 33.0, 36.0
import os, json, sys, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read(sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/sx2/vo/v.wav')
CL = [(0.00, 1.05, 1.30),    # Respirez.
      (1.25, 3.60, 4.95),    # Un parfum peut changer l'âme d'un lieu.
      (3.75, 9.70, 8.80),    # Le Prince : tactile, pilotable depuis votre téléphone, il parfume jusqu'à trois cents mètres carrés.
      (9.82, 16.95, 15.00),  # La Duchesse : silencieuse et puissante, jusqu'à cinq mille mètres carrés, pour les hôtels…
      (17.00, 20.45, 22.25), # Le Monarque : deux parfums… et un ciel d'étoiles.
      (20.60, 26.25, 27.15), # Le Nomade, DuoSens, SensPro : un diffuseur pour chaque espace.
      (26.30, 28.50, 33.50), # Six diffuseurs. Une signature.
      (28.55, len(x) / sr, 36.40)]  # SensExpress. L'art de parfumer vos espaces.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
out = []
for i, (a, b, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)].copy()
    n = int(0.015 * sr); clip[:n] *= [k / n for k in range(n)]; clip[-n:] *= [1 - k / n for k in range(n)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    out.append([f'assets/voice/{i + 1:02d}.wav', at, round(len(clip) / sr, 2)])
json.dump(out, open(f'{P}/assets/voice/voice.json', 'w'), indent=1)
for o in out: print(o, 'ends', round(o[1] + o[2], 2))
