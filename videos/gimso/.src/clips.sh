# Cut the best TikTok moments (Gims) into muted 1080×1920 clips, black borders removed. usage: clips.sh <dir with vNN.mp4> <out dir>
S=$1; O=$2
declare -A CROP=([06]=572:964:2:31 [08]=572:1020:2:2 [09]=572:1016:2:4 [10]=572:984:2:20 [11]=572:996:2:14 [12]=552:1020:12:2)
cut() { ffmpeg -loglevel error -y -ss $3 -t $4 -i $S/v$2.mp4 -an -vf "crop=${CROP[$2]},scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,eq=saturation=1.08:contrast=1.04,fps=25" -c:v libx264 -preset slow -crf 19 -g 12 -pix_fmt yuv420p -movflags +faststart $O/$1.mp4; }
cut cape-capuche   09 19.3 3.4
cut poncho-blanc   10 3.2 3.4
cut poncho-noir    12 2.0 3.4
cut gilet-franges  08 6.3 3.4
cut casquettes     06 4.8 3.8
cut capuche-gros   11 23.4 3.2
cut noir-gros      12 13.2 2.4
cut cape-gros      09 0.2 2.0
cut blanc-gros     10 0.2 2.0
