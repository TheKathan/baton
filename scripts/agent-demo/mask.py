import sys, glob
from PIL import Image
BG=(0x0D,0x11,0x17)
for f in sorted(glob.glob(sys.argv[1]+'/r*.png')):
    im=Image.open(f).convert('RGB'); w,h=im.size; px=im.load()
    rules=[]
    for y in range(h):
        n=sum(1 for x in range(0,w,4) if px[x,y]!=BG and abs(px[x,y][0]-px[x,y][2])<30 and 40<px[x,y][0]<160)
        if n>0.8*(w/4): rules.append(y)
    if rules:
        y0=max(rules)+3
        for y in range(y0,h):
            for x in range(w): px[x,y]=BG
    else: print('no rule',f)
    im.crop((0,0,w,int(sys.argv[2]))).save(f.replace('/r','/m'))
