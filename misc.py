# misc.py: Temporary place for new functions

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
