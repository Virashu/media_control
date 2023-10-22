from PIL import Image
from os.path import exists


def get_color(image: bytes):
    im = Image.frombytes("RGB", (500, 500), image)
    return max(im.getcolors(im.size[0] * im.size[1]))[1]
