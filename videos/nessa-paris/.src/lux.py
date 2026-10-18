# Warm luxury ambient bed for Nessa Paris (instrumental, moderate tempo, soft texture) + 3 light "breath" whooshes.
# usage: python3 lux.py out_music.wav out_breath.wav duration
import sys, numpy as np, soundfile as sf
SR = 44100
out, breath_out, dur = sys.argv[1], sys.argv[2], float(sys.argv[3])
N = int(SR * dur); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(23)
BPM = 70; beat = 60 / BPM; bar = 4 * beat
def hz(m): return 440 * 2 ** ((m - 69) / 12)
# Ebmaj9 – Cm9 – Abmaj9 – Bb6/9 (voiced low-mid)
CH = [[39, 51, 55, 58, 62, 65], [36, 48, 51, 55, 58, 62], [44, 51, 56, 60, 63, 67], [46, 50, 53, 58, 60, 65]]
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i: return
    s = sig[:j - i] * g
    L[i:j] += s * (1 - pan) * 0.5 * 2 ** 0.5; R[i:j] += s * (1 + pan) * 0.5 * 2 ** 0.5
def pad(freq, d):
    n = int(d * SR); t = np.arange(n) / SR
    env = np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.4).clip(0, 1)
    s = sum(np.sin(2 * np.pi * freq * k * (1 + 0.0015 * dt) * t + dt) / k ** 1.6 for k in range(1, 6) for dt in (-1, 1))
    return s * env * (1 + 0.15 * np.sin(2 * np.pi * 0.2 * t))
def pluck(freq, d=1.6):
    n = int(d * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)) * np.exp(-t * 3.2) * np.minimum(1, t / 0.004)
def sub(freq, d):
    n = int(d * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * np.minimum(1, t / 0.05) * np.exp(-t * 0.6)
def hat():
    n = int(0.05 * SR); x = np.diff(rng.standard_normal(n + 1)); return x * np.exp(-np.arange(n) / SR * 90)
bars = int(dur / bar) + 2
for b in range(bars):
    t0 = b * bar; c = CH[b % 4]
    for m in c[1:]: add(pad(hz(m), bar + 1.2), t0, pan=((m % 5) - 2) * 0.15, g=0.022)
    add(sub(hz(c[0]), bar), t0, g=0.16)
    if t0 > 2.5:
        arp = [c[2] + 12, c[3] + 12, c[4] + 12, c[5] + 12, c[4] + 12, c[3] + 12, c[5], c[4] + 12]
        for k, m in enumerate(arp):
            add(pluck(hz(m)), t0 + k * beat / 2, pan=0.35 if k % 2 else -0.35, g=0.05 if k % 4 == 0 else 0.032)
    if t0 > 8:
        for k in range(8): add(hat(), t0 + k * beat / 2 + beat / 4, pan=0.4, g=0.012 if k % 2 else 0.02)
# reverb: exponentially decaying stereo noise impulse, FFT convolution
def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.6 * SR)) * np.exp(-np.arange(int(1.6 * SR)) / SR * 3.2)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.75 + verb(L, 1) * 0.5; R = R * 0.75 + verb(R, 2) * 0.5
t = np.arange(N) / SR
fade = np.minimum(1, t / 1.5) * np.clip((dur - t) / 2.5, 0, 1)
mix = np.stack([L, R], 1) * fade[:, None]
mix /= np.abs(mix).max() / 0.7
sf.write(out, mix, SR)
# a soft breath: band-limited noise swell
n = int(1.1 * SR); tt = np.arange(n) / SR
x = rng.standard_normal(n); x = np.convolve(x, np.ones(18) / 18, 'same') - np.convolve(x, np.ones(220) / 220, 'same')
env = np.sin(np.pi * tt / 1.1) ** 2
b = x * env; b /= np.abs(b).max() / 0.5
sf.write(breath_out, np.stack([b * 0.9, b], 1), SR)
print('ok', dur)
