# Musique de la pub Farmasi (36 s, 100 BPM), synthétisée, calée sur timing.py. Quatre couleurs pour quatre moments :
#   0–4,2   l'intro : tic-tac d'horloge, boîte à musique, nappe d'air, montée vers le matin
#   4,2     le matin : pop douce et lumineuse (do majeur), pincements en arpèges, claquements de doigts, grosse caisse légère
#   12,0    midi : le groove s'ouvre (basse, clap, accords plus brillants)
#   19,8    minuit : la mineur, demi-tempo, cloche grave, célesta, sous-basse
#   27,6    la fin : retour au majeur, tutti, impact sur le logo, trois accents pour « beauté, bien-être, opportunité »
# Chaque balayage d'horloge a son souffle et un tic. La musique laisse de la place à une voix off (niveau modéré).
import os, sys, numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import TOTAL, CUT, WIPE
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000; N = int(SR * TOTAL); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(5); BEAT, SX = 0.6, 0.15
def add(sig, t, pan=0.0, g=1.0):
    i = int(round(t * SR)); j = min(N, i + len(sig))
    if 0 <= i < N and j > i:
        s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def tt(d): return np.arange(int(d * SR)) / SR
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def noise(d): return rng.standard_normal(int(d * SR))
def env(d, a, r): t = tt(d); return np.minimum(1, t / a) * np.exp(-t * r)
def kick(soft=1.0):
    t = tt(0.4); f = 46 + 110 * np.exp(-t * 36); return np.tanh(1.3 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (8 / soft)))
def snap():
    t = tt(0.12); x = np.diff(noise(0.12), prepend=0) * np.exp(-t * 70); return x + 0.3 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90)
def clap():
    t = tt(0.25); x = np.diff(noise(0.25), prepend=0)
    e = sum(np.exp(-np.clip(t - d, 0, None) * 60) * (t >= d) for d in (0, 0.011, 0.023)) / 3
    return x * e
def hat(d=50): t = tt(0.07); return np.diff(noise(0.07), prepend=0) * np.exp(-t * d)
def tick(f=2600): t = tt(0.05); return (np.sin(2 * np.pi * f * t) + 0.3 * noise(0.05)) * np.exp(-t * 150)
def pluck(f, d=0.45, b=0.6):
    t = tt(d); return sum(np.sin(2 * np.pi * f * k * t) * b ** k for k in range(1, 6)) * env(d, 0.003, 7)
def celesta(f, d=1.4):
    t = tt(d); return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 6)) * env(d, 0.002, 3.2)
def musicbox(f, d=1.0):
    t = tt(d); return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t * 9)) * env(d, 0.002, 4.5)
def pad(fs, d, bright=0.0):
    t = tt(d); e = np.minimum(1, t / 0.8) * np.clip((d - t) / 1.0, 0, 1)
    return sum(np.sin(2 * np.pi * f * k * (1 + 0.003 * s) * t + s) / k ** (1.7 - bright) for f in fs for k in range(1, 5) for s in (-1, 1)) * e / len(fs)
def bass(f, d=0.5):
    t = tt(d); x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t); return x * env(d, 0.006, 4)
def sub(f, d=1.2): t = tt(d); return np.sin(2 * np.pi * f * t) * env(d, 0.01, 2.2)
def bell(f, d=3.0):
    t = tt(d); return sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * k) for r, a, k in ((1, 1, 1.2), (2.76, 0.4, 2.0), (5.4, 0.25, 3.5), (0.5, 0.5, 0.9)))
def whoosh(d, up=True):
    t = tt(d); x = noise(d); a = 0.02 + 0.3 * ((t / d) if up else (1 - t / d)) ** 2
    y = np.zeros_like(x); s = 0.0
    for i in range(len(x)): s += a[i] * (x[i] - s); y[i] = s
    return y * np.sin(np.pi * t / d) ** 1.5
def shimmer(d):
    t = tt(d); return sum(np.sin(2 * np.pi * hz(m) * t + m) for m in (84, 88, 91, 96)) * np.exp(-t * 2) * np.minimum(1, t / 0.05) / 4
def impact():
    t = tt(2.2); f = 36 + 70 * np.exp(-t * 7)
    return np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 2.2) + noise(2.2) * np.exp(-t * 14) * 0.2

# ── intro : horloge ──
add(pad([hz(55), hz(62), hz(67)], 4.6), 0.0, g=0.18)
for k in range(7): add(tick(2600 if k % 2 else 2000), 0.0 + k * BEAT, pan=0.25 * (1 if k % 2 else -1), g=0.1)
for t0, m in ((0.3, 79), (0.9, 76), (1.5, 74), (2.1, 72), (2.7, 76), (3.3, 79)): add(musicbox(hz(m)), t0, pan=0.2, g=0.11)
add(whoosh(1.6), CUT['s1'] - 1.4, g=0.28)
# ── matin (do majeur : do, la mineur, fa, sol) ──
MAT = [(48, [60, 64, 67, 72]), (45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (43, [55, 59, 62, 67])]
def section(t0, t1, prog, kind):
    nb = int(round((t1 - t0) / SX))
    for s in range(nb):
        t = t0 + s * SX; pos = s % 16; root, ch = prog[(s // 16) % len(prog)]
        if kind == 'matin':
            if pos in (0, 8): add(kick(0.8), t, g=0.32)
            if pos in (4, 12): add(snap(), t, pan=0.15, g=0.16)
            if pos % 2 == 0: add(hat(70), t, pan=0.3, g=0.03)
            add(pluck(hz(ch[s % 4] + 12), 0.4), t, pan=-0.3 + 0.6 * ((s // 2) % 2), g=0.045)
            if pos == 0: add(pad([hz(m) for m in ch], 2.6, 0.3), t, g=0.08); add(bass(hz(root - 12), 1.0), t, g=0.18)
        if kind == 'midi':
            if pos in (0, 6, 8, 11): add(kick(), t, g=0.42)
            if pos in (4, 12): add(clap(), t, pan=0.1, g=0.22)
            add(hat(45 if pos % 4 == 2 else 80), t, pan=0.3, g=0.05 if pos % 4 == 2 else 0.025)
            if pos in (0, 3, 6, 10, 14): add(bass(hz(root - 12 + (12 if pos == 10 else 0)), 0.3), t, g=0.22)
            if pos % 2 == 0: add(pluck(hz(ch[(s // 2) % 4] + 12), 0.3, 0.5), t, pan=0.25 * (1 if pos % 4 else -1), g=0.05)
            if pos == 0: add(pad([hz(m) for m in ch], 2.6, 0.5), t, g=0.09)
        if kind == 'minuit':
            if pos == 0: add(kick(1.4), t, g=0.4); add(sub(hz(root - 24), 2.2), t, g=0.3); add(pad([hz(m) for m in ch], 2.6, 0.1), t, g=0.1)
            if pos == 8: add(clap(), t, pan=-0.1, g=0.14)
            if pos % 4 == 2: add(hat(30), t, pan=0.3, g=0.025)
            if pos in (0, 3, 6, 10, 12): add(celesta(hz([76, 79, 81, 84, 83][[0, 3, 6, 10, 12].index(pos)] + (0 if (s // 16) % 2 == 0 else -2))), t, pan=0.2, g=0.07)
        if kind == 'fin':
            if pos in (0, 6, 8, 11) and t < 33.6: add(kick(), t, g=0.42)
            if pos in (4, 12) and t < 33.6: add(clap(), t, pan=0.1, g=0.2)
            if t < 33.6: add(hat(45 if pos % 4 == 2 else 80), t, pan=0.3, g=0.045 if pos % 4 == 2 else 0.02)
            if pos == 0: add(pad([hz(m) for m in ch], 2.8, 0.5), t, g=0.11); add(bass(hz(root - 12), 1.2), t, g=0.22)
            if pos % 2 == 0 and t < 33.6: add(pluck(hz(ch[(s // 2) % 4] + 12), 0.35, 0.55), t, pan=-0.2 + 0.4 * ((s // 2) % 2), g=0.045)
section(CUT['s1'], CUT['s2'], MAT, 'matin')
MID = [(48, [64, 67, 71, 74]), (45, [64, 67, 72, 76]), (41, [65, 69, 72, 76]), (43, [62, 67, 71, 74])]
section(CUT['s2'], CUT['s3'], MID, 'midi')
NUIT = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (43, [55, 59, 62, 67]), (40, [56, 59, 64, 68])]
section(CUT['s3'], CUT['s4'], NUIT, 'minuit')
add(bell(hz(45)), CUT['s3'] + 0.05, g=0.3); add(shimmer(2.0), CUT['s3'] + 0.1, g=0.08)
FIN = [(48, [60, 64, 67, 72]), (43, [59, 62, 67, 71]), (45, [60, 64, 69, 72]), (41, [60, 65, 69, 72])]
section(CUT['s4'], TOTAL, FIN, 'fin')
add(impact(), CUT['s4'] + 0.6, g=0.42); add(shimmer(2.0), CUT['s4'] + 0.6, g=0.07)
for t0, m in ((29.4, 84), (30.0, 88), (30.6, 91)): add(celesta(hz(m)), t0, g=0.07)   # beauté · bien-être · opportunité
add(pad([hz(48), hz(55), hz(60), hz(64), hz(67), hz(72)], 3.2, 0.6), 33.6, g=0.16)
for t0, m in ((33.6, 84), (33.75, 79), (33.9, 76), (34.05, 72)): add(musicbox(hz(m)), t0, g=0.08)
# ── balayages d'horloge : souffle + tic à la coupe ──
for k in ('s1', 's2', 's3', 's4'): add(whoosh(0.8), CUT[k] - 0.55, g=0.22); add(tick(3000), CUT[k], g=0.12)

def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.6 * SR)) * np.exp(-np.arange(int(1.6 * SR)) / SR * 3.6)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.88 + verb(L, 3) * 0.26; R = R * 0.88 + verb(R, 4) * 0.26
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.2) * np.clip((TOTAL - t) / 1.2, 0, 1)
mix = np.tanh(1.1 * np.stack([L, R], 1)) * fade[:, None]; mix /= np.abs(mix).max() / 0.9
sf.write(f'{P}/assets/music.wav', mix, SR); print('ok', TOTAL)
