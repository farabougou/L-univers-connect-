# Shot list for the showreel: (id, source render, media start, beats). 124 BPM → 1 beat = 0.4839 s.
# Cut with ffmpeg into short 1080×1920 25 fps muted clips with dense keyframes (fast, exact seeking).
import os, subprocess, sys, json
V = '/home/user/L-univers-connect-/videos'
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 60 / 124
SHOTS = {
 # intro flashes
 'i1': ('gimso', 1.0), 'i2': ('enoryx-pub', 26.6), 'i3': ('sensexpress-diffuseurs', 34.7), 'i4': ('kofa-3d', 2.7),
 # motion design montage
 'm01': ('sensexpress-diffuseurs', 1.6), 'm02': ('sensexpress-diffuseurs', 10.3), 'm03': ('founerou-grill', 1.2),
 'm04': ('founerou-grill', 5.0), 'm05': ('founerou-grill', 12.5), 'm06': ('cassia-dress', 2.4), 'm07': ('cassia-dress', 17.4),
 'm08': ('cassia-dress', 22.2), 'm09': ('gimso', 7.6), 'm10': ('gimso', 24.4), 'm11': ('enoryx-distance', 2.6),
 'm12': ('enoryx-energie/renders/video-3d.mp4', 9.9), 'm13': ('enoryx-pub', 15.8), 'm14': ('sk-print', 7.4), 'm15': ('sk-print', 15.0),
 'm16': ('fleche-bamako', 7.3), 'm17': ('ktf-shipping-vertical', 44.5), 'm18': ('sensexpress-diffuseurs', 25.3),
 # vibe coding
 'v1': ('kofa-ecran/renders/ecran-kofa.mp4', 56.0), 'v2': ('kofa-dev', 9.8), 'v3': ('kofa-promo', 11.2), 'v4': ('kofa-promo', 26.2),
 'v5': ('kofa-3d', 12.2), 'v6': ('ktf-shipping-vertical', 10.5),
 # wall (one per brand)
 'w1': ('sensexpress-pub', 10.5), 'w2': ('founerou-grill', 14.5), 'w3': ('cassia-dress', 9.6), 'w4': ('gimso', 10.2), 'w5': ('enoryx-mali', 14.6),
 'w6': ('sk-print', 7.0), 'w7': ('fleche-bamako', 3.0), 'w8': ('ktf-shipping-vertical', 30.0), 'w9': ('kofa-promo', 11.0),
}
def src(s): return f'{V}/{s}' if s.endswith('.mp4') else f'{V}/{s}/renders/video.mp4'
if __name__ == '__main__':
    out = f'{P}/assets/clips'; os.makedirs(out, exist_ok=True)
    for k, (s, ms) in SHOTS.items():
        dur = 4.2 if k.startswith('w') else 2.6
        vf = 'crop=607:1080:140:0,scale=1080:1920:flags=lanczos,fps=25' if 'ecran-kofa' in s else 'scale=1080:1920,fps=25'
        if k.startswith('w'): vf = vf.replace('scale=1080:1920', 'scale=360:640')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(ms), '-t', str(dur), '-i', src(s), '-an', '-vf', vf,
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-g', '5', '-pix_fmt', 'yuv420p', f'{out}/{k}.mp4'], check=True)
        print('ok', k)
