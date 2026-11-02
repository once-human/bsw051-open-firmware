import sys, glob, os
from PIL import Image, ImageDraw
names = sys.argv[2:]
cols = 4
W, H = 368, 448
rows = (len(names) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (W + 12), rows * (H + 34)), (60, 60, 60))
d = ImageDraw.Draw(sheet)
for i, n in enumerate(names):
    im = Image.open(f"out/{n}.ppm")
    x, y = (i % cols) * (W + 12), (i // cols) * (H + 34)
    sheet.paste(im, (x, y + 26))
    d.text((x + 4, y + 6), n, fill=(255, 255, 0))
sheet.save(sys.argv[1])
