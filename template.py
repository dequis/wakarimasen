import os
import sys
import glob
from urllib import quote_plus
import random
import re

import jinja2

import config, config_defaults
import strings
from util import local
import str_format

TEMPLATES_DIR = 'templates'
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
        vars['stylesheets'] = list(self.get_stylesheets())
        self.env.globals['config'] = config
        self.env.globals['strings'] = strings

        self.vars = vars

    def __iter__(self):
        yield self.template.render(**self.vars).encode("utf-8")

    def render_to_file(self, filename):
        contents = self.template.render(**self.vars).encode("utf-8")

        if config.USE_TEMPFILES:
            tempname = os.path.join(self.board.path,
                self.board.options['RES_DIR'],
                'tmp' + str(random.randint(1, 1000000000)))

            with open(tempname, "w") as rc:
                rc.write(contents)

            os.rename(tempname, filename)
        else:
            with open(filename, "w") as rc:
                rc.write(contents)

        os.chmod(filename, 0644)

    @filter
    def reverse_format(self, value, tplstring):
        return tplstring % value

    @filter
    def expand_url(self, filename, force_http=False):
        return self.board.expand_url(filename, force_http)

    @filter
    def expand_image_url(self, filename):
        # TODO: load balancing support?
	    return self.expand_url(quote_plus(filename, '/'))

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
	return self.environ['SCRIPT_NAME']

    @function
    def get_secure_script_name(self):
        if config.USE_SECURE_ADMIN:
            return 'https://' + self.environ['SERVER_NAME'] + \
            self.environ['SCRIPT_NAME']
	return self.environ['SCRIPT_NAME']

    @filter
    def get_reply_link(self, reply, parent, abbreviated=False,
                       force_http=False):
        path_tpl = (self.board.options['RES_DIR'] + "%s" +
                    ("_abbr" if abbreviated else "") +
                    config.PAGE_EXT + "%s")
        if parent:
            path = path_tpl % (parent, "#" + reply)
        else:
            path = path_tpl % (reply, '')

        return self.board.expand_url(path, force_http)

    @filter
    def clean_string(self, string):
        return str_format.clean_string(string)

    @filter
    def tag_killa(self, string):
        return str_format.tag_killa(string)
    
    def get_stylesheets(self):
        # FIXME: don't hardcode the path
        for file in glob.glob("include/common/css/*.css"):
            title = os.path.basename(file) \
                .replace(".css", "") \
                .replace("_", " ").title()

            if title == self.board.options['DEFAULT_STYLE']:
                default = 1
            else:
                default = 0

            yield {
                # FIXME: web root hardcoded here too
                'filename': '/' + file,
                'title': title,
                'default': default,
            }
