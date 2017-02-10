# misc.py: Temporary place for new functions
import os
import re
import time
import crypt
import struct
from subprocess import Popen, PIPE

import util
import crypto  # part of wakarimasen
import config, config_defaults
import str_format
import urllib
from util import local

def dot_to_dec(ip):
    try:
        parts = [int(x) for x in ip.split(".")]
        return struct.unpack('>L', struct.pack('>4B', *parts))[0]
    except ValueError:
        return ip

def dec_to_dot(numip):
    try:
        # Parse 64-bit integer for compatibility with database written
        # with Perl's 'N' packing format.
        parts = struct.unpack('>8B', struct.pack('>Q', long(numip)))
        return '.'.join([str(x) for x in parts[4:8]])
    except ValueError:
        return numip

def validate_ip(ip):
    try:
        if isinstance(dot_to_dec(ip), int):
            return True
    except:
        pass
    return False

def is_whitelisted(numip):
    return False

TRIP_RE = '^(.*?)((?<!&)#|%s)(.*)$'
SECURE_TRIP_RE = '(?:%s)(?<!&#)(?:%s)*(.*)$'
SALT_CLEAN_RE = re.compile('[^\.-z]')

def process_tripcode(name, tripkey='!'):
    match = re.match(TRIP_RE % re.escape(tripkey), name)
    if not match:
        return (str_format.clean_string(str_format.decode_string(name)), '')

    trip = ''
    namepart, marker, trippart = match.groups()
    namepart = str_format.clean_string(str_format.decode_string(namepart))

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
    trippart = trippart.encode("shiftjis", "xmlcharrefreplace")

    trippar = str_format.clean_string(trippart)
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

def hide_critical_data(string, key):
    rc6 = crypto.RC6(key)
    ret = ''
    i = 0
    while i < len(string):
        ret += rc6.encrypt(string[i:i+15]).encode("base64")[:-1]
        i += 15
    return ret

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

def spam_engine(trap_fields, spam_files):
    def spam_screen():
        raise util.SpamError()

    request = local.request
    for field in trap_fields:
        if request.values.get('request', None) is not None:
            spam_screen()

    spam_checker = compile_spam_checker(spam_files)
    fields = request.values.keys()

    fulltext = '\n'.join([str_format.decode_string(request.values[x])
                          for x in fields])

    if spam_checker(fulltext):
        spam_screen()

def is_trusted(trip):
    # needed only when captcha is enabled?
    pass

def check_captcha(*args):
    # broken in wakaba+desuchan?
    pass

def make_date(timestamp, style='futaba'):
    '''Generate a date string from a passed timestamp based on a requested
    style. The string formatting power of the time module's strftime()
    method is used here. The optional locale array from Wakaba is dropped
    in favor of using the local day and month abbreviations provided by the
    module. The format used can also be inputted directly into the style
    parameter.'''

    localtime = time.localtime(timestamp + config.TIME_OFFSET)
    gmt = time.gmtime(timestamp)

    time_str = ''

    if style.lower() == '2ch':
        time_str = time.strftime('%Y-%m-%d %H:%M', localtime)
    elif style.lower() == '2ch-gmt':
        time_str = time.strftime('%Y-%m-%d %H:%M GMT', gmt)
    elif style.lower() == 'futaba' or style == 0:
        time_str = time.strftime('%y/%m/%d(%a)%H:%M', localtime)
    elif style.lower() == 'futaba-gmt':
        time_str = time.strftime('%y/%m/%d(%a)%H:%M GMT', gmt)
    elif style.lower() == 'tiny':
        time_str = time.strftime('%m/%d %H:%M', localtime)
    elif style.lower() == 'cookie':
        time_str = time.strftime('%a, %d-%b-%Y %H:%M:%S GMT', gmt)
    elif style.lower() == 'http':
        time_str = time.strftime('%a, %d %b %Y %H:%M:%S GMT', gmt)
    elif style.lower() == 'month':
        time_str = time.strftime('%b %Y', gmt)
    elif style.lower() == 'us-en':
        time_str = time.strftime('%A, %B %d, %Y @ %h:%M %p', localtime)
    elif style.lower() == 'uk-en':
        time_str = time.strftime('%A, %d %B %Y @ %h:%M %p', localtime)
    elif style.lower() == 'ctime' or style.lower() == 'c':
        time_str = time.asctime(localtime)
    elif style.lower() == 'localtime':
        time_str = str(timestamp)
    elif style.lower() == '2ch-sep93': # Damn AOLers! Get offa mah lawn!
        # September 1, 1993 as a timestamp.
        SEP_1_1993 = 746884800L
        seconds_past = long(timestamp) - SEP_1_1993
        days_past = seconds_past / 86400L
        time_str = '1993-09-%u' % (days_past + 1)
        time_str = ' '.join([time_str, time.strftime('%H:%M', localtime)])
    else:
        # Let the style parameter default to a format string.
        time_str = time.strftime(style, timestamp)

    return time_str

def make_cookies(**kwargs):
    expires = kwargs.pop('expires', time.time() + 14 * 24 * 3600)
    path = kwargs.pop('path', '/')
    httponly = kwargs.pop('httponly', False)

    expire_date = make_date(expires, "cookie")

    environ = local.environ

    cookies = environ['waka.cookies']
    for key, value in kwargs.iteritems():
        cookies[key] = urllib.quote(value.encode('unicode-escape'))
        cookies[key]['expires'] = expire_date
        cookies[key]['path'] = path
        if httponly:
            cookies[key]['httponly'] = True

def get_script_name():
    return local.environ['SCRIPT_NAME']

def get_secure_script_name():
    script_name = get_script_name()
    if config.USE_SECURE_ADMIN:
        return 'https://' + local.environ['SERVER_NAME'] + script_name
    return script_name

def make_script_url(**kwargs):
    '''Builds an url pointing to the cgi script
    Optional params:
        - _secure: set to False to avoid enforcing https
        - _amp: set to True to html escape ampersands
    Everything else is included as url parameters'''

    secure = kwargs.pop('_secure', True)
    amp = kwargs.pop('_amp', False)

    base = get_secure_script_name() if secure else get_script_name()

    url = '%s?%s' % (base, urllib.urlencode(kwargs))
    if amp:
        url = url.replace('&', '&amp;')
    return url

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

    magic, width, height = struct.unpack('<6sHH', buffer)
    if magic not in GIF_MAGICS:
        return
    return (width, height)

def make_thumbnail(filename, thumbnail, width, height, quality, convert):
    is_animated = False
    magickname = filename
    convert = convert or 'convert' # lol
    popen_array = [convert, '-resize', '%sx%s!' % (width, height),
                   '-quality', str(quality)]

    if magickname.endswith(".gif"):
        identify = config.IDENTIFY_COMMAND
        gif_check = Popen([identify, '-format', '%n', magickname],
                          stdout=PIPE).communicate()[0]
        try:
            if int(gif_check) > 1:
                magickname += '[0]'
                is_animated = True
        except ValueError:
            pass

    if is_animated:
        popen_array.extend([magickname, '-background', config.BG_ANIM_COLOR,
                            '-gravity', 'Center',
                            '-fill', config.FG_ANIM_COLOR,
                            '-size', '100x15',
                            'label:Animated', '-append', thumbnail])

        height += 15
    else:
        popen_array.extend([magickname, thumbnail])
    process = Popen(popen_array)

    if process.wait() == 0 and os.path.exists(thumbnail) and \
           os.path.getsize(thumbnail) != 0:
        return width, height
    elif os.path.exists(thumbnail):
        os.unlink(thumbnail)
    return 0, 0

    # other methods supported by the original wakaba
    # but not by wakaba+desuchan aren't included here
    # because they suck.

def get_cookie_from_request(request, key):
    return urllib.unquote(request.cookies.get(key, '')).decode('unicode-escape')

def kwargs_from_params(request, params_arg=None, **params):
    '''Associate function to convert CGI request data with dictionary
    of parameter keys to a dictionary of keyword arguments for passing
    to an application function.

    Dictonary format: {'cookies': ['cookie_keys'],
                       'form':    ['html_form_input_names'],
                       'file':    ['file_keys']}

    Not all keys are necessary. Invalid keys are ignored.'''

    if params_arg:
        params = params_arg

    kwargs = {}

    if 'admin' in params.keys():
        kwargs['cookie'] = get_cookie_from_request(request, 'wakaadmin')

    if 'cookies' in params.keys():
        for param in params['cookies']:
            kwargs[param] = get_cookie_from_request(request, param)

    if 'form' in params.keys():
        for param in params['form']:
            kwargs[param] = request.values.get(param, '')

    if 'file' in params.keys():
        for param in params['file']:
            kwargs[param] = request.files.get(param, None)

    return kwargs
