import os
import sys
import jinja2

TEMPLATES_DIR = 'templates'
CACHE_DIR = os.path.join(TEMPLATES_DIR, '.cache')

class Template(object):
    def __init__(self, name, **vars):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

        # Environment init
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
            bytecode_cache=jinja2.FileSystemBytecodeCache(CACHE_DIR)
        )
        self.env.filters['reverse_format'] = self.reverse_format

        # Current template init
        self.template = self.env.get_template(name + '.html')

        if 'environ' in vars:
            self.environ = vars['environ']
            self.board = self.environ['waka.board']
            vars['stylesheets'] = []
            vars['board'] = self.board

        self.vars = vars

    def __iter__(self):
        yield self.template.render(**self.vars)

    def reverse_format(self, value, tplstring):
        return tplstring % value


