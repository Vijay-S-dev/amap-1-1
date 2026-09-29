#!/usr/bin/env python3
"""Build Y4M fake-webcam feeds from hand photos (Pillow only).
Usage: python make_feeds.py <input.jpg> <output.y4m> [pct_of_frame_width]
pct defaults to full-frame cover-crop; e.g. 0.30 renders the hand at 30% of
the frame width (simulating distance / wide-FOV cameras)."""
import sys
from PIL import Image

def to_y4m(src, dst, pct=None, w=640, h=480, fps=30, frames=150):
    img = Image.open(src).convert("RGB")
    if pct:
        tw = int(w * pct); th = int(img.height * (tw / img.width))
        if th > h: th = h; tw = int(img.width * (th / img.height))
        img = img.resize((tw, th), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (200, 200, 200))
        canvas.paste(img, ((w - tw)//2, (h - th)//2)); img = canvas
    tr = w / h; sr = img.width / img.height
    if sr > tr:
        nw = int(img.height * tr); x = (img.width - nw)//2; img = img.crop((x, 0, x+nw, img.height))
    else:
        nh = int(img.width / tr); y = (img.height - nh)//2; img = img.crop((0, y, img.width, y+nh))
    img = img.resize((w, h), Image.LANCZOS); px = img.load()
    Y = bytearray(w*h); Cb = bytearray(w*h//4); Cr = bytearray(w*h//4)
    for j in range(h):
        for i in range(w):
            r,g,b = px[i,j]; Y[j*w+i] = max(0, min(255, int(0.299*r+0.587*g+0.114*b)))
    for j in range(0, h, 2):
        for i in range(0, w, 2):
            r,g,b = px[i,j]; k = (j//2)*(w//2)+(i//2)
            Cb[k] = max(0, min(255, int(128-0.168736*r-0.331264*g+0.5*b)))
            Cr[k] = max(0, min(255, int(128+0.5*r-0.418688*g-0.081312*b)))
    with open(dst, "wb") as f:
        f.write(f"YUV4MPEG2 W{w} H{h} F{fps}:1 Ip A1:1 C420jpeg\n".encode())
        for _ in range(frames):
            f.write(b"FRAME\n"); f.write(Y); f.write(Cb); f.write(Cr)

if __name__ == "__main__":
    pct = float(sys.argv[3]) if len(sys.argv) > 3 else None
    to_y4m(sys.argv[1], sys.argv[2], pct)
    print("wrote", sys.argv[2])
