# Slowed funk/phonk bed for the KOFA dev reel: cowbell hook, gliding 808, half-time drums, tape-slowed feel.
# usage: python3 phonk.py out.wav duration
import sys, numpy as np, soundfile as sf
SR = 44100
out, dur = sys.argv[1], float(sys.argv[2])
N = int(SR * dur); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)
BPM = 132 * 0.82; beat = 60 / BPM; s16 = beat / 4; bar = 4 * beat
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i or i < 0: return
    s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def cowbell(f, d=0.28):
    n = int(d * SR); t = np.arange(n) / SR
    sq = lambda fr: np.sign(np.sin(2 * np.pi * fr * t))
    x = (sq(f) + sq(f * 1.48)) * 0.5
    x = np.convolve(x, np.ones(6) / 6, 'same') - np.convolve(x, np.ones(60) / 60, 'same')
    return x * np.exp(-t * 11) * np.minimum(1, t / 0.002)
def b808(f0, f1, d):
    n = int(d * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(2.2 * np.sin(ph)) * np.minimum(1, t / 0.005) * np.exp(-t * 1.1)
def kick():
    n = int(0.3 * SR); t = np.arange(n) / SR; f = 45 + 110 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 10)
def snare():
    n = int(0.35 * SR); t = np.arange(n) / SR
    return (0.6 * rng.standard_normal(n) * np.exp(-t * 14) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 20))
def hat(d=40):
    n = int(0.05 * SR); x = np.diff(rng.standard_normal(n + 1)); return x * np.exp(-np.arange(n) / SR * d)
# C# minor phonk hook (cowbell), 2-bar phrase
HOOK = [(0, 73), (2, 76), (3, 73), (6, 71), (8, 73), (10, 76), (11, 78), (14, 76),
        (16, 73), (18, 76), (19, 73), (22, 71), (24, 69), (26, 68), (28, 69), (30, 71)]
BASS = [(0, 37, 6), (6, 37, 2), (8, 40, 6), (16, 37, 6), (22, 35, 2), (24, 33, 8)]
bars = int(dur / bar) + 2
for b in range(0, bars, 2):
    t0 = b * bar
    intro = t0 < bar * 1.99
    for st, m in HOOK: add(cowbell(hz(m)), t0 + st * s16, pan=0.15, g=0.20 if not intro else 0.14)
    if intro: continue
    for st, m, ln in BASS: add(b808(hz(m + 12), hz(m), ln * s16 + 0.25), t0 + st * s16, g=0.32)
    for k in range(2):
        tb = t0 + k * bar
        add(kick(), tb, g=0.6); add(kick(), tb + 10 * s16, g=0.45)
        add(snare(), tb + 8 * s16, pan=-0.05, g=0.32)
        for h in range(16):
            add(hat(60 if h % 2 else 40), tb + h * s16, pan=0.35, g=0.05 if h % 4 == 0 else 0.03)
        if k == 1:
            for r in range(6): add(hat(90), tb + 12 * s16 + r * s16 / 1.5, pan=0.35, g=0.03)
def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.4 * SR)) * np.exp(-np.arange(int(1.4 * SR)) / SR * 4)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.85 + verb(L, 1) * 0.3; R = R * 0.85 + verb(R, 2) * 0.3
# tape warmth: gentle low-pass + saturation
k = np.ones(5) / 5; L = np.tanh(1.3 * np.convolve(L, k, 'same')); R = np.tanh(1.3 * np.convolve(R, k, 'same'))
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.6) * np.clip((dur - t) / 2.0, 0, 1)
mix = np.stack([L, R], 1) * fade[:, None]; mix /= np.abs(mix).max() / 0.85
sf.write(out, mix, SR); print('ok', dur, 'bpm', round(BPM, 1))
