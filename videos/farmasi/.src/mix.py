# Mixage de la pub Farmasi : la voix off ElevenLabs découpée en phrases et posée sur les plans (timing.py),
# la musique (score.py) qui s'efface sous la voix (environ −9 dB) et revient entre les phrases.
# Chaque coupe tombe au point le plus silencieux à ±90 ms de la limite prévue, avec 8 ms de fondu pour éviter les clics.
import os, sys, subprocess, numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import TOTAL, VO
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', f'{P}/assets/voix-off.mp3', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True, check=True).stdout
v = np.frombuffer(raw, np.float32).astype(np.float64)
fr = int(0.01 * SR)
rms = np.sqrt(np.convolve(v ** 2, np.ones(fr) / fr, 'same'))
def quiet(t, w=0.09):
    a, b = int((t - w) * SR), int((t + w) * SR)
    a = max(a, 0); b = min(b, len(v))
    return (a + int(np.argmin(rms[a:b]))) / SR if b > a else t

N = int(TOTAL * SR); voice = np.zeros(N)
fade = int(0.008 * SR)
for i, (name, a, b, at) in enumerate(VO):
    a = 0.0 if i == 0 else quiet(a); b = len(v) / SR if i == len(VO) - 1 else quiet(b)
    seg = v[int(a * SR):int(b * SR)].copy()
    seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
    i0 = int(at * SR); j0 = min(N, i0 + len(seg)); voice[i0:j0] += seg[:j0 - i0]
    print(f'{name:9s} mp3 {a:6.2f}→{b:6.2f}  film {at:5.2f}→{at + b - a:5.2f}')
voice *= 0.89 / np.abs(voice).max()

music, msr = sf.read(f'{P}/assets/music.wav'); assert msr == SR
music = music[:N] if len(music) >= N else np.pad(music, ((0, N - len(music)), (0, 0)))
# enveloppe de la voix → gain de la musique : attaque 40 ms, relâche 350 ms
env = np.sqrt(np.convolve(voice ** 2, np.ones(int(0.03 * SR)) / int(0.03 * SR), 'same'))
on = np.clip(env / 0.02, 0, 1)
g = np.zeros(N); x = 0.0; att, rel = 1 - np.exp(-1 / (0.04 * SR)), 1 - np.exp(-1 / (0.35 * SR))
for k in range(N):
    x += (att if on[k] > x else rel) * (on[k] - x); g[k] = x
duck = 1 - 0.65 * g
mix = music * 0.55 * duck[:, None] + voice[:, None] * 1.0
mix /= np.abs(mix).max() / 0.9
sf.write(f'{P}/assets/mix.wav', mix, SR)
print('ok', TOTAL)
