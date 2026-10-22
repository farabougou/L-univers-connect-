# Musique de la pub Fanta shop (24 s, 100 BPM, 1 temps = 0,6 s, 1 mesure = 2,4 s), calée sur le montage :
#   0–3 s     l'accroche : nappe chaude, shaker, quelques notes de balafon, souffle qui monte
#   3,0 s     le pot arrive : impact doux, le groove démarre (djembé, grosse caisse, basse, balafon en doubles croches)
#   7,2 s     la gamme : souffle de transition, accents sur les tuiles (7,2 / 7,8 / 8,4)
#   11,4 s    le flacon : une mesure allégée, la pression du spray à 12,0
#   14,4 s    la boutique : souffle, le groove repart
#   18,0 s    l'appel : impact, accord majeur, petits clics sur les chiffres du numéro, fondu final
import os, numpy as np, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR, DUR = 48000, 24.0
N = int(SR * DUR); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)
BEAT, SX = 0.6, 0.15
def add(sig, t, pan=0.0, g=1.0):
    i = int(round(t * SR)); j = min(N, i + len(sig))
    if 0 <= i < N and j > i:
        s = sig[:j - i] * g; L[i:j] += s * (1 - pan) * 0.707; R[i:j] += s * (1 + pan) * 0.707
def tt(d): return np.arange(int(d * SR)) / SR
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def noise(d): return rng.standard_normal(int(d * SR))
def lp(x, a):
    y = np.zeros_like(x); s = 0.0
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y

def balafon(f, d=0.7):
    # lame de bois : partiels inharmoniques qui s'éteignent vite, petit clic de mailloche, léger bourdonnement de calebasse
    t = tt(d)
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * dk) for k, a, dk in ((1, 1, 7), (3.93, 0.32, 26), (9.8, 0.1, 48)))
    x += noise(d) * np.exp(-t * 300) * 0.25
    return np.tanh(1.4 * x * (1 + 0.08 * np.sin(2 * np.pi * 31 * t)))
def djembe(kind):
    t = tt(0.5)
    if kind == 'bass': f = 62 + 40 * np.exp(-t * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)
    if kind == 'tone': return (np.sin(2 * np.pi * 280 * t) + 0.5 * np.sin(2 * np.pi * 410 * t)) * np.exp(-t * 28) + noise(0.5) * np.exp(-t * 200) * 0.2
    return np.diff(noise(0.5), prepend=0) * np.exp(-t * 55) * 0.6 + np.sin(2 * np.pi * 520 * t) * np.exp(-t * 60) * 0.4   # slap
def kick():
    t = tt(0.45); f = 44 + 120 * np.exp(-t * 34); return np.tanh(1.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5))
def shaker(acc=1.0):
    t = tt(0.09); return np.diff(noise(0.09), prepend=0) * np.minimum(1, t / 0.012) * np.exp(-t * 55) * acc
def bass(f, d=0.3):
    t = tt(d); x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t)
    return x * np.minimum(1, t / 0.006) * np.exp(-t * 5)
def pad(fs, d, bright=0.0):
    t = tt(d); e = np.minimum(1, t / 0.7) * np.clip((d - t) / 0.9, 0, 1)
    return sum(np.sin(2 * np.pi * f * k * (1 + 0.003 * s) * t + s) / k ** (1.7 - bright) for f in fs for k in range(1, 5) for s in (-1, 1)) * e / len(fs)
def whoosh(d, up=True):
    t = tt(d); x = noise(d); a = 0.02 + 0.3 * ((t / d) if up else (1 - t / d)) ** 2
    y = np.zeros_like(x); s = 0.0
    for i in range(len(x)): s += a[i] * (x[i] - s); y[i] = s
    return y * np.sin(np.pi * t / d) ** 1.5
def impact():
    t = tt(2.0); f = 34 + 70 * np.exp(-t * 7)
    return np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 2.2) + noise(2.0) * np.exp(-t * 14) * 0.25
def spray():
    t = tt(0.55); x = np.diff(noise(0.55), prepend=0)
    return x * np.minimum(1, t / 0.02) * np.exp(-t * 6) * 0.7
def tick():
    t = tt(0.04); return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 180)

# grille harmonique : la mineur, fa, do, sol (une mesure chacun) ; gamme pentatonique de la mineur pour le balafon
CH = [(45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62])]
PENTA = [57, 60, 62, 64, 67, 69, 72, 74, 76]
RIFF = [4, None, 2, 3, None, 4, 2, None, 1, None, 2, 4, None, 3, 1, None]   # degrés de la pentatonique, par double croche
def bar_of(t): return CH[int(t // 2.4) % 4]

# ── l'accroche ──
add(pad([hz(45), hz(52), hz(57), hz(60)], 3.6), 0.0, g=0.30)
for k in range(20): add(shaker(1.0 if k % 2 else 0.5), k * SX, pan=0.3, g=0.05)
for t0, m in ((0.3, 69), (0.9, 72), (1.5, 76), (1.95, 74), (2.4, 72)): add(balafon(hz(m)), t0, pan=-0.2, g=0.16)
add(whoosh(1.4), 1.6, g=0.35)
# ── le groove (3,0 → 22,8) ──
add(impact(), 3.0, g=0.45)
G0, G1 = 3.0, 22.8
for s in range(int(round((G1 - G0) / SX))):
    t0 = G0 + s * SX; pos = s % 16; root, chord = bar_of(t0 - G0)
    light = 11.4 <= t0 < 13.8                                                  # la mesure du flacon : allégée
    if pos in (0, 6, 8) and not light: add(kick(), t0, g=0.5)
    if pos in (0, 10) and not light: add(bass(hz(root - 12), 0.45), t0, g=0.28)
    if pos in (6, 14) and not light: add(bass(hz(root - 12 + 7)), t0, g=0.18)
    if pos in (3, 11): add(djembe('tone'), t0, pan=-0.3, g=0.12)
    if pos in (4, 12): add(djembe('slap'), t0, pan=0.3, g=0.16 if not light else 0.1)
    if pos in (0, 8) and light: add(djembe('bass'), t0, g=0.25)
    add(shaker(1.0 if pos % 4 == 2 else 0.45), t0, pan=0.35, g=0.06)
    d = RIFF[pos]
    if d is not None and t0 >= 3.6:
        m = PENTA[(d + (2 if (s // 16) % 2 else 0)) % len(PENTA)]
        add(balafon(hz(m)), t0, pan=-0.25 + 0.5 * (pos % 2), g=0.10 if not light else 0.07)
    if pos == 0: add(pad([hz(m) for m in chord], 2.6), t0, g=0.09)
# ── accents du montage ──
add(whoosh(0.9), 6.4, g=0.3); add(whoosh(0.9), 13.6, g=0.3); add(whoosh(1.1), 17.0, g=0.32)
for t0 in (7.2, 7.8, 8.4): add(balafon(hz(81)), t0, g=0.09); add(djembe('tone'), t0, g=0.1)
add(spray(), 12.0, pan=0.15, g=0.22)
add(impact(), 18.0, g=0.5)
add(pad([hz(48), hz(55), hz(60), hz(64), hz(67)], 6.0, bright=0.5), 18.0, g=0.16)
for k in range(8): add(tick(), 19.25 + k * 0.1, pan=0.2, g=0.07)       # les chiffres du numéro qui se posent

def verb(x, seed):
    ir = np.random.default_rng(seed).standard_normal(int(1.3 * SR)) * np.exp(-np.arange(int(1.3 * SR)) / SR * 4)
    ir /= np.sqrt((ir ** 2).sum()); n = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
L = L * 0.9 + verb(L, 3) * 0.22; R = R * 0.9 + verb(R, 4) * 0.22
t = np.arange(N) / SR
fade = np.minimum(1, t / 0.3) * np.clip((DUR - t) / 1.4, 0, 1)
mix = np.tanh(1.1 * np.stack([L, R], 1)) * fade[:, None]; mix /= np.abs(mix).max() / 0.9
sf.write(f'{P}/assets/music.wav', mix, SR); print('ok', DUR)
