"""生成应用图标：深色底 + PLC 芯片 + 心跳波形。

运行：.venv/Scripts/python.exe tools/make_icon.py
产出：assets/app.ico（多尺寸）与 assets/icon-256.png
"""

import os

from PIL import Image, ImageDraw

S = 1024
BG = (14, 28, 43, 255)
EDGE = (38, 64, 92, 255)
CHIP_FILL = (19, 41, 62, 255)
BLUE = (61, 139, 253, 255)
GREEN = (46, 204, 113, 255)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 背景圆角方块
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=228, fill=BG)
d.rounded_rectangle([12, 12, S - 13, S - 13], radius=218, outline=EDGE, width=6)

# 芯片主体范围
cx0, cy0, cx1, cy1 = 282, 282, 742, 742
span = cx1 - cx0

# 四边引脚
pin_w, pin_len = 26, 74
for i in range(4):
    c = cx0 + span * (i + 1) // 5
    d.rectangle([c - pin_w // 2, cy0 - pin_len, c + pin_w // 2, cy0], fill=BLUE)
    d.rectangle([c - pin_w // 2, cy1, c + pin_w // 2, cy1 + pin_len], fill=BLUE)
    d.rectangle([cx0 - pin_len, c - pin_w // 2, cx0, c + pin_w // 2], fill=BLUE)
    d.rectangle([cx1, c - pin_w // 2, cx1 + pin_len, c + pin_w // 2], fill=BLUE)

# 芯片外壳
d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=64, fill=CHIP_FILL, outline=BLUE, width=24)

# 心跳波形
wave = [
    (316, 512), (392, 512), (432, 430), (478, 600),
    (520, 512), (568, 512), (612, 400), (656, 512), (708, 512),
]
d.line(wave, fill=GREEN, width=24, joint="curve")

# 波形端点圆头
for px, py in (wave[0], wave[-1]):
    r = 12
    d.ellipse([px - r, py - r, px + r, py + r], fill=GREEN)

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
assets = os.path.join(root, "assets")
os.makedirs(assets, exist_ok=True)

sizes = [16, 24, 32, 48, 64, 128, 256]
ico_path = os.path.join(assets, "app.ico")
img.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
img.resize((256, 256), Image.LANCZOS).save(os.path.join(assets, "icon-256.png"))

print("ico:", ico_path, os.path.getsize(ico_path), "bytes")
print("sizes:", sizes)
