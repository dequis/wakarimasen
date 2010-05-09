# misc.py: Temporary place for new functions
import os
import struct
from subprocess import Popen, PIPE

import util

def check_password(admin, task_redirect, editing=None):
    raise NotImplementedError()

def get_file_size(file):
    return 0

def dot_to_dec(ip):
    return 0

def dec_to_dot(numip):
    return '0.0.0.0'

def is_whitelisted(numip):
    return False

def process_tripcode(name, tripkey='', secret='', charset='', nonamedecoding=''):
    return (name, '')

def ban_check(numip, name, subject, comment):
    pass

def spam_engine(environ, trap_fields, spam_files, charset):
    pass

def is_trusted(trip):
    # needed only when captcha is enabled?
    pass

def check_captcha(*args):
    # broken in wakaba+desuchan?
    pass

def proxy_check(ip):
    pass

def clean_string(string, cleanentities=False):
    return string

def decode_string(string, charset='', noentities=False):
    return string

def format_comment(comment):
    return comment

def flood_check(ip, timestamp, comment, file, no_repeat, report_check):
    pass

def make_date(timestamp, style, locdays=[]):
    return 'today'

def find_pch(filename):
    pass

def copy_animation_file(pch, image_filename):
    pass

def make_cookies(name, email, password, _charset, _autopath, environ):
    # yum!
    pass

def get_secure_script_name():
    return 'wakaba.pl'

def analyze_image(file, name):
    types = [("jpg", analyze_jpeg), ("png", analyze_png), ("gif", analyze_gif)]
    for ext, analyze in types:
        res = analyze(file)
        if res:
            return (ext, res[0], res[1])

    # find file extension for unknown files
    ext = ''
    if name.find(".") != -1:
        ext = name.split(".")[-1].lower()
    return (ext, 0, 0)

def analyze_jpeg(file):
    # TODO: requires testing
    try:
        buffer = file.read(2)
        if buffer != '\xff\xd8':
            return

        while True:
            while True:
                buffer = file.read(1)
                if not buffer:
                    return
                if buffer == '\xff':
                    break

            mark, size = struct.unpack(">BH", file.read(3))

            if mark in (0xda, 0xd9): # SOS/EOI
                break

            if size < 2:
                # MS GDI+ JPEG exploit uses short chunks
                raise util.WakaError("Possible virus in image")

            if mark >= 0xc0 and mark <= 0xc2: # SOF0..SOF2 - what the hell are the rest? 
                bits, height, width = struct.unpack(">BHH", file.read(5))
                return (width, height)

            file.seek(size - 2, 1)
    except struct.error:
        return
    finally:
        file.seek(0)

PNG_MAGIC = '\x89PNG\r\n\x1a\n'
PNG_IHDR = 'IHDR'

def analyze_png(file):
    buffer = file.read(24)
    file.seek(0)
    if len(buffer) != 24:
        return

    magic, length, ihdr, width, height = struct.unpack(">8sL4sLL", buffer)
    if magic != PNG_MAGIC and ihdr != PNG_IHDR:
        return
    return (width, height)

GIF_MAGICS = ('GIF87a', 'GIF89a')
def analyze_gif(file):
    buffer = file.read(10)
    file.seek(0)
    if len(buffer) != 10:
        return

    magic, width, height = struct.unpack("<6sHH", buffer)
    if magic not in GIF_MAGICS:
        return
    return (width, height)

def make_thumbnail(filename, thumbnail, width, height, quality, convert):
    magickname = filename
    if magickname.endswith(".gif"):
        magickname += '[0]'

    convert = convert or 'convert' # lol
    print quality
    process = Popen([convert, "-size", "%sx%s" % (width, height),
        "-geometry", "%sx%s!" % (width, height), "-quality", str(quality),
        magickname, thumbnail])

    if process.wait() == 0 and os.path.exists(thumbnail) and \
       os.path.getsize(thumbnail) != 0:
        return True
    elif os.path.exists(thumbnail):
        os.unlink(thumbnail)
    return False

    # other methods supported by the original wakaba
    # but not by wakaba+desuchan aren't included here
