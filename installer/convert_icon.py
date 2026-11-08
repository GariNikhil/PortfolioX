from PIL import Image
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = root / "referance" / "icon.jpg"
dst = root / "referance" / "icon.ico"
img = Image.open(src)
img.save(dst, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('Icon converted successfully')
