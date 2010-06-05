# misc.py: Temporary place for new functions
import os
import re
import crypt
import struct
from subprocess import Popen, PIPE

import util
import crypto  # part of wakarimasen

import config, config_defaults

MAX_UNICODE = 1114111

def check_password(admin, task_redirect, editing=None):
    raise NotImplementedError()

def dot_to_dec(ip):
    parts = [int(x) for x in ip.split(".")]
    return struct.unpack('>L', struct.pack('>4B', *parts))[0]

def dec_to_dot(numip):
    parts = struct.unpack('>4B', struct.pack('>L', numip))
    return '.'.join([str(x) for x in parts])

def is_whitelisted(numip):
    return False

TRIP_RE = '^(.*?)((?<!&)#|%s)(.*)$'
SECURE_TRIP_RE = '(?:%s)(?<!&#)(?:%s)*(.*)$'
SALT_CLEAN_RE = re.compile('[^\.-z]')

def process_tripcode(name, tripkey='!'):
    match = re.match(TRIP_RE % re.escape(tripkey), name)
    if not match:
        return (clean_string(decode_string(name)), '')

    trip = ''
    namepart, marker, trippart = match.groups()
    namepart = clean_string(decode_string(namepart))

    # do we want secure trips, and is there one?
    if config.SECRET:
        regexp = re.compile(SECURE_TRIP_RE.replace("%s", re.escape(marker)))
        smatch = regexp.match(trippart)
        if smatch:
            trippart = regexp.sub('', trippart)
            maxlen = 255 - len(config.SECRET)
            string = smatch.group(1)[:maxlen]
            trip = tripkey * 2 + hide_data(smatch.group(1), 6, "trip",
                config.SECRET, True)

            if not trippart: # return directly if there's no normal tripcode
                return (namepart, trip)

    # 2ch trips are processed as Shift_JIS whenever possible
    trippart = decode_string(trippart).encode("shiftjis", "xmlcharrefreplace")

    trippar = clean_string(trippart)
    salt = (trippart + "H..")[1:3]
    salt = SALT_CLEAN_RE.sub('.', salt)
    for old, new in map(None, ':;<=>?@[\\]^_`', 'ABCDEFGabcdef'):
        salt = salt.replace(old, new)
    trip = tripkey + crypt.crypt(trippart, salt)[-10:] + trip

    return (namepart, trip)

def make_key(key, secret, length):
    return crypto.rc4('\0' * length, key + secret)

def hide_data(data, bytes, key, secret, base64=False):
    ret = crypto.rc4('\0' * bytes, make_key(key, secret, 32) + str(data))
    if base64:
        return ret.encode("base64").rstrip('\n')
    return ret

def ban_check(numip, name, subject, comment):
    pass

def compile_spam_checker(spam_files):
    # TODO caching this by timestamps would be nice
    regexps = []
    for file in spam_files:
        for line in open(file).readlines():
            line = re.sub("(^|\s+)#.*", "", line).strip()
            if not line:
                continue

            match = re.match("^/(.*)/([xism]*)$", line)
            if match:
                pattern, modifiers = match.groups()
                flags = sum([getattr(re, x.upper()) for x in modifiers])
            else:
                pattern = re.escape(line)
                flags = re.I
            regexps.append(re.compile(pattern, flags))

    def spam_checker(string):
        for regexp in regexps:
            if regexp.search(string) is not None:
                return True
        return False

    return spam_checker

def spam_engine(environ, trap_fields, spam_files):
    def spam_screen():
        raise util.WakaError("Anti-spam filters triggered.")

    request = environ['werkzeug.request']
    for field in trap_fields:
        if request.values.get('request', None) is not None:
            spam_screen()

    spam_checker = compile_spam_checker(spam_files)
    fields = request.values.keys() 
    
    fulltext = '\n'.join([decode_string(request.values[x])
                          for x in fields])

    if spam_checker(fulltext):
        spam_screen()

def is_trusted(trip):
    # needed only when captcha is enabled?
    pass

def check_captcha(*args):
    # broken in wakaba+desuchan?
    pass

def proxy_check(ip):
    pass

CONTROL_CHARS_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f]')
ENTITIES_CLEAN_RE = re.compile('&(#([0-9]+);|#x([0-9a-fA-F]+);|)')
ENTITY_REPLACES = {
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    ',': '&44;', # "clean up commas for some reason I forgot"
}

def clean_string(string, cleanentities=False):
    if cleanentities:
        string = string.replace("&", "&amp;") # clean up &
    else:
        def repl(match):
            g = match.groups()
            if not g[0]:                    # change simple ampersands
                return '&amp;'
            ordinal = int(g[1] or int(g[2], 16))
            if forbidden_unicode(ordinal):  # strip forbidden unicode chars
                return ''
            else:                           # and leave the rest as-is.
                return '&' + g[0]

        string = ENTITIES_CLEAN_RE.sub(repl, string)

    # replace <, >, ", ' and "," with html entities
    for old, new in ENTITY_REPLACES.iteritems():
        string = string.replace(old, new)

    # remove control chars
    string = CONTROL_CHARS_RE.sub('', string)

    return string

ENTITIES_DECODE_RE = re.compile('(&#([0-9]*)([;&])|&#([x&])([0-9a-f]*)([;&]))', re.I)

def decode_string(string, noentities=False):
    '''Returns unicode string'''

    string = string.decode(config.CHARSET, "ignore")

    def repl(match):
        g = match.groups()
        ordinal = int(g[1] or int(g[4], 16))
        if '&' in g: # nested entities, leave as-is.
            return g[0]
        elif ordinal in (35, 38): # don't convert & or #
            return g[0]
        elif forbidden_unicode(ordinal): # strip forbidden unicode chars
            return ''
        else: # convert all entities to unicode chars
            return unichr(ordinal)

    if not noentities:
        string = ENTITIES_DECODE_RE.sub(repl, string)

    # remove control chars
    string = CONTROL_CHARS_RE.sub('', string)
    return string

def forbidden_unicode(num):
    return ((len(str(num)) > 7) or               # too long numbers
            (num > MAX_UNICODE) or               # outside unicode range
            (num < 32) or                        # control chars
            (num >= 0xd800 and num <= 0xdfff) or # surrogate code points
            (num >= 0x202a and num <= 0x202e))   # text direction

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

def get_filestorage_size(filestorage):
    filestorage.stream.seek(0, 2)
    size = filestorage.stream.tell()
    filestorage.stream.seek(0, 0)
    return size

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
