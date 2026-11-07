from PIL import Image

img = Image.open(r'<repo>\referance\icon.jpg')
img.save(r'<repo>\referance\icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
print('Icon converted successfully')