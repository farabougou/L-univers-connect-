# Pack de livraison d'une vidéo verticale 9:16 : versions 4:5 (fil Instagram/Facebook) et 1:1, images de couverture.
# Les formats carrés gardent tout le film : il est réduit au centre, sur un fond fait du même film agrandi, flouté et
# assombri (aucun texte coupé). Pour une vraie recomposition par format, refaire la mise en page dans gen.py.
# usage : python3 videos/_studio/livraison.py <video.mp4> [--covers 11.2,38.5] [--out dossier]
import argparse, os, subprocess

def run(args):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + args, check=True)

def adapt(src, out, w, h):
    fg_h = h; fg_w = round(1080 * h / 1920 / 2) * 2
    graph = (f'[0:v]scale={w}:-2,crop={w}:{h},boxblur=60:3,eq=brightness=-0.3:saturation=0.6[bg];'
             f'[0:v]scale={fg_w}:{fg_h}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]')
    run(['-i', src, '-filter_complex', graph, '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20',
         '-c:a', 'copy', '-movflags', '+faststart', out])

def cover(src, t, out):
    run(['-ss', str(t), '-i', src, '-frames:v', '1', '-q:v', '2', out])

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--covers', default=''); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.dirname(os.path.abspath(a.video))
    base = os.path.splitext(os.path.basename(a.video))[0]
    adapt(a.video, f'{out}/{base}-4x5.mp4', 1080, 1350)
    adapt(a.video, f'{out}/{base}-1x1.mp4', 1080, 1080)
    for k, t in enumerate(x for x in a.covers.split(',') if x):
        cover(a.video, float(t), f'{out}/{base}-couverture-{k + 1}.jpg')
    print('ok', out)
