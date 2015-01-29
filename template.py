import os
import glob
import random
import re

import jinja2

import config, config_defaults
import strings
import misc
from util import local, FileLock
import str_format
import staff_tasks

TEMPLATES_DIR = os.path.join('templates')
CACHE_DIR = os.path.join(TEMPLATES_DIR, '.cache')

_filters = []
_functions = []

def filter(f):
    _filters.append(f.__name__)
    return f

def function(f):
    _functions.append(f.__name__)
    return f

class Template(object):
    def __init__(self, name, **vars):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

        # Environment init
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
            bytecode_cache=jinja2.FileSystemBytecodeCache(CACHE_DIR)
        )

        for filter in _filters:
            self.env.filters[filter] = getattr(self, filter)

        for function in _functions:
            self.env.globals[function] = getattr(self, function)

        # Current template init
        self.template = self.env.get_template(name + '.html')

        self.environ = local.environ
        self.board = self.environ['waka.board']

        vars['environ'] = self.environ
        vars['board'] = self.board
        vars['stylesheets'] = list(self.get_stylesheets(self.board))
        self.env.globals['config'] = config
        self.env.globals['strings'] = strings

        self.vars = vars

    def __iter__(self):
        yield self.template.render(**self.vars).encode("utf-8")

    def render_to_file(self, filename):
        contents = self.template.render(**self.vars).encode("utf-8")

        if config.USE_TEMPFILES:
            tempname = os.path.join(os.path.dirname(filename),
                'tmp' + str(random.randint(1, 1000000000)))

            with FileLock(tempname):
                with open(tempname, 'w') as rc:
                    rc.write(contents)

            with FileLock(filename) as rc:
                os.rename(tempname, filename)
        else:
            with FileLock(filename) as rc:
                with open(filename, 'w') as rc:
                    rc.write(contents)

        os.chmod(filename, 0644)

    def update_parameters(self, **kwargs):
        self.vars.update(kwargs)

    @filter
    def reverse_format(self, value, tplstring):
        return tplstring % value

    @filter
    def expand_url(self, filename, force_http=False):
        return self.board.expand_url(filename, force_http)

    @filter
    def expand_image_url(self, filename):
        # TODO: load balancing support?
	return self.expand_url(filename, '/')

    @filter
    def root_path_to_filename(self, filename):
        if filename.startswith("/") or filename.startswith("http"):
            return filename

        return self.environ['waka.rootpath'] + filename

    @filter
    def basename(self, path):
        return os.path.basename(path)

    @filter
    def get_captcha_key(self, thread):
        # TODO: captcha not implemented
        pass

    @function
    def get_script_name(self):
        return misc.get_script_name()

    @function
    def get_secure_script_name(self):
        return misc.get_secure_script_name()

    @filter
    def get_reply_link(self, reply, parent, abbreviated=False,
                       force_http=False):
        return self.board.get_reply_link(reply, parent, abbreviated,
            force_http)

    @filter
    def redirect_reply_links(self, comment, min_res):
        res_re = re.compile('(' + os.path.join(self.board.url,
                                               self.board.options['RES_DIR'],
                                               r')(?P<op_num>\d+)('
                                               + config.PAGE_EXT + r'#?)'
                                               r'(?P<res_num>\d+)?'), re.I)

        # If the reply number is at least
        def change_to_abbr(match):
            res_num = match.group('res_num')
            op_num = match.group('op_num')
            if not res_num or int(res_num) >= min_res:
                op_num = op_num + '_abbr'

            if not res_num:
                return match.group(1) + op_num + match.group(3)
            return match.group(1) + op_num + match.group(3) + res_num

        return res_re.sub(change_to_abbr, comment)

    @filter
    def clean_string(self, string):
        return str_format.clean_string(string)

    @filter
    def tag_killa(self, string):
        return str_format.tag_killa(string)

    @filter
    def dec_to_dot(self, numip):
        if not numip:
            return ''
        return misc.dec_to_dot(numip)

    @filter
    def get_action_name(self, action, debug=0):
        return staff_tasks.get_action_name(action, debug=debug)

    @filter
    def make_date(self, timestamp, style='futaba'):
        return misc.make_date(timestamp, style)

    @function
    def get_filetypes(self):
        filetypes = self.board.options.get('EXTRA_FILETYPES', [])
        ret_list = []
        for pictype in ('gif', 'jpg', 'png'):
            if pictype not in filetypes:
                ret_list.append(pictype.upper())
        ret_list.extend(filetypes)

        return ', '.join(ret_list)

    def get_stylesheets(self, board=None):
        files = glob.glob(os.path.abspath\
                         (os.path.join(self.environ['DOCUMENT_ROOT'],
                                       config.BOARD_DIR,
                                       'include/boards/css/*.css')))
        if board is not None:
            # Add board CSS directory, if present.
            files.extend(glob.glob(os.path.abspath\
                                   (os.path.join(board.path, 'css/*.css'))))

        for file in files:
            title = os.path.basename(file) \
                .replace('.css', '') \
                .replace('_', ' ').title()

            default = (title == self.board.options['DEFAULT_STYLE'].title())

            url = file.replace(self.environ['DOCUMENT_ROOT'].rstrip("/"), '')

            yield {
                'filename': url,
                'title': title,
                'default': default,
            }
