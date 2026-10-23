# Founerou Grill's — energetic trap/afro beat (140 BPM) + SFX (whoosh, impact, sizzle, riser).
# usage: python3 beat.py <out dir> <duration>
import sys, numpy as np, soundfile as sf
SR = 44100
out, dur = sys.argv[1], float(sys.argv[2])
N = int(SR * dur); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(19)
BPM = 140; beat = 60 / BPM; s16 = beat / 4; bar = 4 * beat
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(sig, t, pan=0.0, g=1.0, buf=None):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i or i < 0: return
    s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t * d)
def kick():
    n = int(0.4 * SR); t = np.arange(n) / SR; f = 42 + 140 * np.exp(-t * 40)
    return np.tanh(1.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7))
def b808(f0, d, glide=None):
    n = int(d * SR); t = np.arange(n) / SR
    f = f0 * np.ones(n) if glide is None else f0 * (glide / f0) ** np.clip((t - d * 0.55) / (d * 0.35), 0, 1)
    return np.tanh(2.0 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.minimum(1, t / 0.004) * np.exp(-t * 0.9)
def clap():
    n = int(0.3 * SR); t = np.arange(n) / SR; x = rng.standard_normal(n)
    e = sum(np.exp(-np.clip(t - o, 0, None) * 60) * (t >= o) for o in (0, 0.01, 0.022)) + 0.6 * np.exp(-t * 14)
    x = np.convolve(x, np.ones(3) / 3, 'same') - np.convolve(x, np.ones(40) / 40, 'same')
    return x * e * 0.6
def hat(d=55):
    n = int(0.05 * SR); x = np.diff(rng.standard_normal(n + 1)); return x * np.exp(-np.arange(n) / SR * d)
def pluck(f, d=0.5):
    n = int(d * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.3 for k in range(1, 6))
    return x * env(n, 0.003, 7)
def brass(f, d):
    n = int(d * SR); t = np.arange(n) / SR
    saw = sum(np.sin(2 * np.pi * f * k * t + 0.3 * k) / k for k in range(1, 12))
    return saw * np.minimum(1, t / 0.02) * np.exp(-t * 3.5)
# G minor-ish: Gm – Eb – Bb – F, afro-trap bounce
ROOTS = [43, 39, 46, 41]
MEL = [[67, 70, 74, 72], [67, 70, 75, 74], [70, 74, 77, 74], [65, 69, 72, 70]]
bars = int(dur / bar) + 2
for b in range(bars):
    t0 = b * bar; r = ROOTS[b % 4]
    intro = b < 1
    # pluck arp (log drum-ish counter)
    for k, st in enumerate([0, 3, 6, 8, 10, 12, 14]):
        m = MEL[b % 4][k % 4]
        add(pluck(hz(m)), t0 + st * s16, pan=0.25 if k % 2 else -0.25, g=0.09 if not intro else 0.06)
    if intro:
        continue
    # drums
    for st in (0, 7, 10): add(kick(), t0 + st * s16, g=0.55 if st == 0 else 0.4)
    for st in (4, 12): add(clap(), t0 + st * s16, g=0.42)
    for h in range(16):
        add(hat(70 if h % 2 else 45), t0 + h * s16, pan=0.3, g=0.05 if h % 4 == 0 else 0.03)
    if b % 2 == 1:
        for rr in range(6): add(hat(110), t0 + 13 * s16 + rr * s16 / 2, pan=0.3, g=0.03)
    # 808
    add(b808(hz(r), 3 * s16 * 2), t0, g=0.32)
    add(b808(hz(r), 2 * s16 * 2, glide=hz(r + 5) if b % 2 else None), t0 + 10 * s16, g=0.28)
    # brass stabs every 2 bars
    if b % 2 == 0:
        for st, m in ((0, r + 24), (3, r + 24)): add(brass(hz(m), 0.25) * 0.5 + brass(hz(m + 7), 0.25) * 0.4, t0 + st * s16, pan=-0.1, g=0.035)
def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.0 * SR)) * np.exp(-np.arange(int(1.0 * SR)) / SR * 5)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.9 + verb(L, 1) * 0.18; R = R * 0.9 + verb(R, 2) * 0.18
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.3) * np.clip((dur - t) / 1.6, 0, 1)
mix = np.tanh(1.2 * np.stack([L, R], 1)) * fade[:, None]; mix /= np.abs(mix).max() / 0.85
sf.write(f'{out}/music.wav', mix, SR)
# ── SFX ──
def save(name, x, g=0.9):
    x = x / (np.abs(x).max() + 1e-9) * g; sf.write(f'{out}/{name}.wav', np.stack([x, x], 1), SR)
n = int(0.55 * SR); tt = np.arange(n) / SR
w = rng.standard_normal(n); bp = np.zeros(n); lp = 0
cut = 0.02 + 0.5 * np.sin(np.pi * tt / 0.55) ** 2
for i in range(n): lp += cut[i] * (w[i] - lp); bp[i] = lp
save('whoosh', bp * np.sin(np.pi * tt / 0.55) ** 1.5, 0.7)
n = int(1.2 * SR); tt = np.arange(n) / SR; f = 38 + 90 * np.exp(-tt * 18)
boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.2) + 0.5 * rng.standard_normal(n) * np.exp(-tt * 25)
save('impact', np.tanh(2 * boom), 0.95)
n = int(1.6 * SR); tt = np.arange(n) / SR; x = rng.standard_normal(n)
crack = (rng.random(n) < 0.0016) * rng.standard_normal(n) * 6
hiss = np.convolve(x, [1, -0.95], 'same') * 0.25
siz = (hiss + np.convolve(crack, np.exp(-np.arange(200) / 30), 'same')) * np.minimum(1, tt / 0.05) * np.clip((1.6 - tt) / 0.5, 0, 1)
save('sizzle', siz, 0.6)
n = int(1.4 * SR); tt = np.arange(n) / SR
rise = rng.standard_normal(n); lp = 0; o = np.zeros(n)
for i in range(n): c = 0.01 + 0.35 * (tt[i] / 1.4) ** 2; lp += c * (rise[i] - lp); o[i] = lp
save('riser', o * (tt / 1.4) ** 1.5, 0.6)
print('ok', dur)
