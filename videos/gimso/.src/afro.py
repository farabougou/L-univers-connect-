# Afro-pop fashion bed for GimSo: warm bass, balafon-like marimba, djembe/shaker groove, soft pads.
# usage: python3 afro.py out.wav duration
import sys, numpy as np, soundfile as sf
SR = 44100
out, dur = sys.argv[1], float(sys.argv[2])
N = int(SR * dur); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(31)
BPM = 112; beat = 60 / BPM; bar = 4 * beat; s16 = beat / 4
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i or i < 0: return
    s = sig[:j - i] * g
    L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t * d)
def marimba(f, d=0.9):
    n = int(d * SR); t = np.arange(n) / SR
    return (np.sin(2*np.pi*f*t) + 0.45*np.sin(2*np.pi*f*3.93*t)*np.exp(-t*14) + 0.2*np.sin(2*np.pi*f*9.2*t)*np.exp(-t*30)) * env(n, 0.002, 5.5)
def bass(f, d):
    n = int(d * SR); t = np.arange(n) / SR
    return np.tanh(1.6*(np.sin(2*np.pi*f*t) + 0.3*np.sin(4*np.pi*f*t))) * np.minimum(1, t/0.01) * np.exp(-t*2.2)
def kick():
    n = int(0.35*SR); t = np.arange(n)/SR; f = 48 + 90*np.exp(-t*30)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*9)
def djembe(f, d=12):
    n = int(0.25*SR); t = np.arange(n)/SR
    return (np.sin(2*np.pi*f*t)*np.exp(-t*d) + 0.4*rng.standard_normal(n)*np.exp(-t*60))
def shaker():
    n = int(0.06*SR); x = np.diff(rng.standard_normal(n+1)); return x*env(n, 0.008, 70)
def pad(f, d):
    n = int(d*SR); t = np.arange(n)/SR
    e = np.minimum(1, t/1.0)*np.clip((d-t)/1.2, 0, 1)
    return sum(np.sin(2*np.pi*f*k*(1+0.002*dt)*t+dt)/k**1.8 for k in range(1,5) for dt in (-1,1))*e
# A minor pentatonic-ish progression: Am – F – C – G (Mande feel on top)
CH = [(45, [57,60,64,67]), (41, [57,60,65,69]), (48, [55,60,64,67]), (43, [55,59,62,67])]
MEL = [[69,72,76,72,74,72,69,67], [69,72,74,77,76,72,69,72], [67,72,76,79,76,74,72,76], [67,71,74,79,74,72,71,67]]
bars = int(dur / bar) + 2
for b in range(bars):
    t0 = b*bar; root, ch = CH[b % 4]
    for m in ch: add(pad(hz(m), bar+1.0), t0, pan=((m%5)-2)*0.2, g=0.016)
    # bass: syncopated
    for st, ln in [(0, 3), (3, 3), (6, 2), (10, 2), (12, 4)]:
        add(bass(hz(root + (12 if st == 10 else 0) - 12), ln*s16*1.1), t0 + st*s16, g=0.18 if t0 > 1.5 else 0.08)
    if t0 >= bar*0.99:
        for k in (0, 6, 8, 11): add(kick(), t0+k*s16, g=0.5 if k in (0,8) else 0.3)
        for k in range(16): add(shaker(), t0+k*s16, pan=0.45, g=(0.05 if k%4==2 else 0.025))
        for k, f, g in [(2, 220, 0.12), (3, 330, 0.08), (7, 220, 0.12), (10, 330, 0.1), (14, 180, 0.12), (15, 330, 0.07)]:
            add(djembe(f), t0+k*s16, pan=-0.3, g=g)
    # balafon melody (from bar 2)
    if t0 >= bar*1.99:
        for k, m in enumerate(MEL[b % 4]):
            st = [0, 3, 4, 6, 8, 10, 12, 14][k]
            add(marimba(hz(m)), t0+st*s16, pan=0.3 if k%2 else -0.2, g=0.11)
            if k % 2 == 0: add(marimba(hz(m)), t0+st*s16+s16, pan=0.4, g=0.04)  # flam echo
def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.2*SR))*np.exp(-np.arange(int(1.2*SR))/SR*4.5)
    ir /= np.sqrt((ir**2).sum()); n = len(x)+len(ir)
    return np.fft.irfft(np.fft.rfft(x, n)*np.fft.rfft(ir, n), n)[:len(x)]
L = L*0.82 + verb(L, 1)*0.32; R = R*0.82 + verb(R, 2)*0.32
t = np.arange(N)/SR
fade = np.minimum(1, t/0.8)*np.clip((dur-t)/2.0, 0, 1)
mix = np.stack([L, R], 1)*fade[:, None]
mix /= np.abs(mix).max()/0.8
sf.write(out, mix, SR); print('ok', dur)
