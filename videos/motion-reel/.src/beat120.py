# Motion reel score: electro / afro-house, 120 BPM, one bar per reel section (1 bar = 2 s), 8 bars + tail.
# bars: 0–1 hook breakdown + riser · 2–13 groove (sites, apps, pubs; lead from 6, open hats 10–13) · 14–15 outro
import sys, numpy as np, soundfile as sf
SR = 44100
out, dur = sys.argv[1], float(sys.argv[2])
N = int(SR * dur); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(41)
BPM = 120; beat = 60 / BPM; s16 = beat / 4; bar = 4 * beat
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i or i < 0: return
    s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t * d)
def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR; f = 46 + 120 * np.exp(-t * 38)
    return np.tanh(1.4 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8))
def clap():
    n = int(0.25 * SR); t = np.arange(n) / SR; x = rng.standard_normal(n)
    e = sum(np.exp(-np.clip(t - o, 0, None) * 70) * (t >= o) for o in (0, 0.012, 0.024)) + 0.5 * np.exp(-t * 16)
    return (np.convolve(x, np.ones(3) / 3, 'same') - np.convolve(x, np.ones(40) / 40, 'same')) * e * 0.6
def shaker(d=60):
    n = int(0.06 * SR); x = np.diff(rng.standard_normal(n + 1)); return x * env(n, 0.006, d)
def ohat():
    n = int(0.22 * SR); x = np.diff(rng.standard_normal(n + 1)); return x * env(n, 0.002, 12)
def logdrum(f, d=0.45):
    n = int(d * SR); t = np.arange(n) / SR; fr = f * (1 + 0.25 * np.exp(-t * 30))
    return np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(fr) / SR)) * env(n, 0.003, 6)
def conga(f):
    n = int(0.2 * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * f * t * (1 + 0.1 * np.exp(-t * 40))) * env(n, 0.001, 18)
def pad(f, d):
    n = int(d * SR); t = np.arange(n) / SR; e = np.minimum(1, t / 0.6) * np.clip((d - t) / 0.8, 0, 1)
    return sum(np.sin(2 * np.pi * f * k * (1 + 0.0025 * dt) * t + dt) / k ** 1.5 for k in range(1, 6) for dt in (-1, 1)) * e
def stab(f, d=0.28):
    n = int(d * SR); t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 8)) * env(n, 0.004, 9)
def lead(f, d=0.35):
    n = int(d * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t + 2.2 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 6))) * env(n, 0.005, 5)
def riser(d):
    n = int(d * SR); t = np.arange(n) / SR; x = rng.standard_normal(n); lp = 0; o = np.zeros(n)
    for i in range(n): c = 0.01 + 0.4 * (t[i] / d) ** 2; lp += c * (x[i] - lp); o[i] = lp
    return o * (t / d) ** 1.5
# A minor: Am – F – C – G
CH = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 67])]
LOG = [(0, 0), (3, 0), (6, 7), (10, 0), (12, 5), (14, 3)]
LEAD = [76, 74, 72, 74, 76, 79, 76, 74]
nb = int(dur / bar) + 1
for b in range(nb):
    t0 = b * bar; root, ch = CH[b % 4]
    if b >= 8:  # tail: one last ringing chord after the logo
        for m in ch: add(pad(hz(m), 1.6), t0, pan=((m % 5) - 2) * 0.2, g=0.03)
        continue
    for m in ch: add(pad(hz(m), bar + 0.6), t0, pan=((m % 5) - 2) * 0.2, g=0.022)
    for k in range(4): add(kick(), t0 + k * beat, g=0.55 if b else 0.4)
    if b == 0:  # easing: sparse, ticking hats only
        for k in range(8): add(shaker(70), t0 + k * beat / 2, pan=0.35, g=0.03)
        add(riser(bar), t0, g=0.12)
        continue
    for k in (1, 3): add(clap(), t0 + k * beat, pan=0.05, g=0.38)
    if b == 6:  # kinetic type: a clap on every word
        for k in (0, 2): add(clap(), t0 + k * beat, pan=-0.05, g=0.3)
    for k in range(16): add(shaker(70 if k % 2 else 45), t0 + k * s16, pan=0.35, g=0.05 if k % 4 == 2 else 0.028)
    for st, off in LOG: add(logdrum(hz(root - 12 + off)), t0 + st * s16, g=0.33)
    for k in (2, 6, 10, 14): add(stab(hz(ch[1] + 12)) * 0.6 + stab(hz(ch[3] + 12)) * 0.5, t0 + k * s16, pan=0.2, g=0.03)
    if 2 <= b <= 5:
        for k, m in enumerate(LEAD): add(lead(hz(m + (0 if b % 2 else -2))), t0 + k * beat / 2, pan=-0.15, g=0.04)
    if b in (3, 4, 5):
        for k in range(4): add(ohat(), t0 + k * beat + beat / 2, pan=0.3, g=0.06)
    if b == 6: add(riser(bar), t0, g=0.22)
def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.2 * SR)) * np.exp(-np.arange(int(1.2 * SR)) / SR * 4.5)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.9 + verb(L, 1) * 0.22; R = R * 0.9 + verb(R, 2) * 0.22
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.05) * np.clip((dur - t) / 2.5, 0, 1)
mix = np.tanh(1.15 * np.stack([L, R], 1)) * fade[:, None]; mix /= np.abs(mix).max() / 0.9
if len(sys.argv) > 3:  # voiceover bed: about -10 dB under the voice, swelling back after its last word
    ve = float(sys.argv[3]); mix *= (0.3 + 0.7 * np.clip((t - ve) / 0.6, 0, 1))[:, None]
sf.write(out, mix, SR); print('ok', dur, 'bar', round(bar, 4))
