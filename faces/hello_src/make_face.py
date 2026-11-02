from PIL import Image, ImageDraw, ImageFont
W, H = 368, 448
BG = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)
ACCENT = (255, 106, 61)

def font(path, size):
    return ImageFont.truetype(path, size)

BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
MED = "/usr/share/fonts/truetype/lato/Lato-Medium.ttf"

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

def centered(text, y, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)

centered("hi,", 120, font(MED, 40), GRAY)
centered("Onkar", 170, font(BOLD, 92), WHITE)
d.rounded_rectangle((W / 2 - 60, 300, W / 2 + 60, 306), radius=3, fill=ACCENT)
centered("product + software", 335, font(MED, 24), GRAY)
img.save("background000.bmp")
img.resize((200, 243), Image.LANCZOS).save("001.bmp")   # preview, last blob
print("ok")
