# Musique d'Enoryx « installations » (30 s, 100 BPM, 1 temps = 0,6 s), calée sur le montage :
#   0–8,4 s   la nuit : nappe grave, horloge qui tique, pulsation sourde ; la dérive monte (glissando + souffle)
#   8,4 s     l'alerte : notification à deux notes, la batterie entre
#   8,4–16,2  l'action : grosse caisse, charleston, basse en doubles croches, accords mineurs
#   16,2–26,4 le retour à la normale : accords majeurs, arpèges clairs, coupes du montage sur 2 temps
#   26,4 s    le logo : impact, nappe qui brille, fin en fondu
import os, numpy as np, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR, DUR = 48000, 33.4
N = int(SR * DUR); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(12)
BEAT = 0.6
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if 0 <= i < N and j > i:
        s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def tt(d): return np.arange(int(d * SR)) / SR
def env(d, a, r): t = tt(d); return np.minimum(1, t / a) * np.exp(-t * r)
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def kick():
    t = tt(0.4); f = 42 + 110 * np.exp(-t * 32); return np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7))
def hat(d=40):
    t = tt(0.08); return np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t * d)
def tick(f):
    t = tt(0.05); return (np.sin(2 * np.pi * f * t) + 0.4 * rng.standard_normal(len(t))) * np.exp(-t * 160)
def pluck(f, d=0.35):
    t = tt(d); return sum(np.sin(2 * np.pi * f * k * t) * 0.6 ** k for k in range(1, 6)) * env(d, 0.003, 9)
def pad(fs, d, bright=0.0):
    t = tt(d); e = np.minimum(1, t / 0.8) * np.clip((d - t) / 1.0, 0, 1)
    return sum(np.sin(2 * np.pi * f * k * (1 + 0.003 * s) * t + s) / k ** (1.6 - bright) for f in fs for k in range(1, 6) for s in (-1, 1)) * e / len(fs)
def bass(f, d=0.14):
    t = tt(d); x = np.sign(np.sin(2 * np.pi * f * t)) * 0.6 + np.sin(2 * np.pi * f * t)
    return np.convolve(x, np.ones(24) / 24, 'same') * env(d, 0.004, 14)
def chime(fs):
    t = tt(1.2); return sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 4) + 0.3 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t * 7) for f in fs)
def riser(d):
    t = tt(d); x = rng.standard_normal(len(t)); o = np.zeros_like(x); lp = 0
    for i in range(len(x)): lp += (0.01 + 0.35 * (t[i] / d) ** 2) * (x[i] - lp); o[i] = lp
    return o * (t / d) ** 1.6
def boom():
    t = tt(2.5); f = 30 + 60 * np.exp(-t * 6); return np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 1.6) + rng.standard_normal(len(t)) * np.exp(-t * 9) * 0.3

# ── acte 1 : la nuit ──
add(pad([hz(33), hz(40), hz(45)], 9.0), 0.0, g=0.30)                     # nappe grave (la mineur)
for k in range(14): add(tick(2400 if k % 2 else 1800), k * BEAT, pan=0.3 * (1 if k % 2 else -1), g=0.16)
for k in range(0, 14, 2): add(kick() * 0.5, k * BEAT, g=0.22)            # pulsation sourde, comme un cœur
t = tt(5.4); gl = np.sin(2 * np.pi * np.cumsum(hz(64) * (1 + 0.5 * (t / 5.4) ** 2)) / SR) * (t / 5.4) ** 1.3
add(gl, 3.0, pan=0.2, g=0.05)                                            # la dérive : une note qui glisse vers le haut
add(riser(2.4), 6.0, g=0.30)
# ── l'alerte ──
add(chime([hz(88), hz(84)]), 8.4, g=0.16); add(chime([hz(84)]), 8.62, g=0.12)
# ── acte 2 : l'action (la mineur, fa, ré mineur, mi) ──
ACT = [(45, [57, 60, 64]), (41, [53, 57, 60]), (38, [50, 53, 57]), (40, [52, 56, 59])]
for b in range(13):                                                      # 13 temps de 8,4 à 16,2
    t0 = 8.4 + b * BEAT; root, ch = ACT[(b // 4) % 4]
    add(kick(), t0, g=0.55)
    add(hat(), t0 + BEAT / 2, pan=0.35, g=0.10); add(hat(70), t0, pan=-0.3, g=0.05)
    for s in range(4): add(bass(hz(root - 12 + (12 if s == 2 else 0))), t0 + s * BEAT / 4, g=0.20)
    if b % 4 == 0: add(pad([hz(m) for m in ch], 2.6), t0, g=0.10)
add(riser(1.8), 14.4, g=0.22)
# ── acte 3 : retour à la normale (do majeur, sol, la mineur, fa) ──
RES = [(48, [60, 64, 67, 72]), (43, [59, 62, 67, 71]), (45, [60, 64, 69, 72]), (41, [60, 65, 69, 72])]
for b in range(17):                                                      # 17 temps de 16,2 à 26,4
    t0 = 16.2 + b * BEAT; root, ch = RES[(b // 4) % 4]
    add(kick(), t0, g=0.5)
    if b % 2: add(hat(30), t0, pan=0.1, g=0.06)
    add(hat(), t0 + BEAT / 2, pan=0.35, g=0.09)
    for s in range(4): add(pluck(hz(ch[(b * 4 + s) % 4] + 12)), t0 + s * BEAT / 4, pan=-0.25 + 0.5 * (s % 2), g=0.06)
    for s in range(2): add(bass(hz(root - 12), 0.22), t0 + s * BEAT / 2, g=0.2)
    if b % 4 == 0: add(pad([hz(m) for m in ch], 2.8, bright=0.4), t0, g=0.11)
add(riser(1.2), 25.2, g=0.18)
# ── le logo ──
add(boom(), 26.4, g=0.55)
add(pad([hz(48), hz(55), hz(60), hz(64), hz(67)], 4.2, bright=0.6), 26.4, g=0.22)
add(chime([hz(84), hz(91)]), 26.5, g=0.08)
# ── la signature (29,4 s) : le néon s'allume, une nappe chaude tient jusqu'à la fin ──
add(pad([hz(45), hz(52), hz(57), hz(60), hz(64)], 4.0, bright=0.3), 29.4, g=0.16)
add(kick() * 0.6, 29.4, g=0.3)

def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.6 * SR)) * np.exp(-np.arange(int(1.6 * SR)) / SR * 3.5)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.88 + verb(L, 3) * 0.26; R = R * 0.88 + verb(R, 4) * 0.26
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.4) * np.clip((DUR - t) / 1.6, 0, 1)
mix = np.tanh(1.1 * np.stack([L, R], 1)) * fade[:, None]; mix /= np.abs(mix).max() / 0.9
sf.write(f'{P}/assets/music.wav', mix, SR); print('ok', DUR)
