# Bruitages du néon : allumage (grésillement + claquements qui suivent le scintillement du M) et petit grésillement
# de « changer ». Le motif de scintillement est le même que dans gen.py (FLICK), pour que le son colle à l'image.
import os, sys, json, numpy as np, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
rng = np.random.default_rng(7)
def neon(steps, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    hum = sum(np.sin(2 * np.pi * 100 * k * t + k) / k for k in range(1, 7)) * 0.35
    crackle = rng.standard_normal(n) * 0.25
    on = np.zeros(n)
    for a, b in steps: on[int(a * SR):int(b * SR)] = 1
    sm = np.convolve(on, np.ones(96) / 96, 'same')
    sig = (hum + crackle * (0.4 + 0.6 * sm)) * sm
    for a, _ in steps:  # un claquement à chaque allumage
        i = int(a * SR); k = np.arange(min(2400, n - i)); sig[i:i + len(k)] += np.sin(2 * np.pi * 1800 * k / SR) * np.exp(-k / 240) * 0.8
    sig *= np.minimum(1, (dur - t) / 0.25).clip(0, 1)
    return sig / np.abs(sig).max() * 0.7
FLICK = json.load(open(f'{P}/.src/flick.json'))
sf.write(f'{P}/assets/sfx/neon-on.wav', neon(FLICK['on'], 1.0), SR)
sf.write(f'{P}/assets/sfx/neon-glitch.wav', neon(FLICK['glitch'], 0.7), SR)
print('ok')
