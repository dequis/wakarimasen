import os
import re
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

TEMPLATES_DIR = 'templates'
HTDOCS_HARDCODED_PATH = '/home/desuchan/public_html/desuchan.net/htdocs/'

FUTABA_STYLE_DEBUG = 0
EXPRESSION_DEBUG = 1

TEMPLATE_RE = re.compile(r'^use constant ([A-Z_]+) => (.*?;)\s*\n\n', re.M | re.S)
TEMPLATE_SECTION_RE = re.compile(
    r'('
        r'q{((?:[^{}]|{[^{}]*})*)}|'    # allow non-nested braces inside the q{}
        r'include\("([a-z_/\.]*?)"\)|'
        r'"(.*?)"|'
        r'([A-Z][A-Z_]+)|'
        r'sprintf\(S_ABBRTEXT,[\'"](.*?)[\'"]\)'
    r')[\.;] *',
    re.S | re.M)

COMPILE_TEMPLATE_RE = re.compile(
    r'^compile_template ?\((.*?)\);$',
    re.S)

# regex copied from wakautils.pl
TAG_RE = re.compile(
    r'(.*?)(<(/?)(var|const|if|loop)(?:|\s+(.*?[^\\]))>|$)',
    re.S)

# i should write a decent tokenizer/parser instead
PERL_EXP_RE = re.compile(
    # 1-2 board option, path
    r'\$board->option\((\'[A-Z_]+\'|"[A-Z_]+")\)|'
    r'\$board->(path\(?\)?)|'
    # 3 advanced include (ignore most of it)
    r'encode_string\(\(compile_template\(include\(\$board->path\(\).\'/\'.'
        '"([a-z/\.]+?)"\)\)\)->\(board=>\$board\)\)|'
    # 4-5 function call (evaluate recursively)
    r'([a-z_]+)\(|'
    r'(\))|'
    # 6-7 variables and constants
    r'\$([A-Za-z_{}]+)|'
    r'([A-Z_]+)|'
    # 8 sprintf without brackets
    r'sprintf (.+)$|'
    # 9 regex
    r'([!=]~ /.+?/[i]*)|'
    # 10-11 operators and comma
    r'(\+|-|/|\*|<=|>=|<|>|==|eq|!=|ne|&&|and|\|\||or|!|\?|:|\.)|'
    r'(,)|'
    # 12-13 values (string/number), whitespace
    r'(".*?"|\'.*?\'|[0-9]+)|'
    r'(\s+)|'
    # 14 single opening bracket (turns into void function)
    r'(\()',
    re.S | re.M)

REMOVE_BACKSLASHES_RE = re.compile(r'\\([^\\])')
def remove_backslashes(string):
    return REMOVE_BACKSLASHES_RE.sub(r'\1', string)

def debug_item(name, value='', match=None, span=''):
    span = match and match.span() or span
    if value:
        value = repr(value)[1:-1]
        if len(value) > 50:
            value = value[:50] + "[...]"
    print ' %14s %-8s %s' % (span, name, value)

class FutabaStyleParser(object):
    FILENAME = "futaba_style.pl"
    
    def __init__(self):
        self.lastend = 0

        self.current = None

        if not os.path.exists(TEMPLATES_DIR):
            os.mkdir(TEMPLATES_DIR)

        self.tl = Jinja2Translator(self)

        TEMPLATE_RE.sub(self.do_constant,
            open(FutabaStyleParser.FILENAME).read())

    def debug_item(self, *args, **kwds):
        if not FUTABA_STYLE_DEBUG:
            return
        debug_item(*args, **kwds)

    def do_constant(self, match):
        name, template = match.groups()
        
        if FUTABA_STYLE_DEBUG:
            print name
        
        # remove compile_template(...)
        compile = COMPILE_TEMPLATE_RE.match(template)
        if compile:
            self.debug_item('compiled', '1')
            template = compile.group(1) + ';'
        
        # init variables for the self.do_section loop
        self.lastend = 0
        self.current = StringIO()

        TEMPLATE_SECTION_RE.sub(self.do_section, template)
        
        # after the self.do_section loop
        current = self.current.getvalue()
        current = self.parse_template_tags(current)
        file = open(template_filename(name), 'w')
        file.write(current)

        if len(template) != self.lastend:
            self.debug_item("NOT MATCHED (end)", template[lastend:],
                span=(lastend, len(template)))

    def do_section(self, match):
        if not match.group():
            return

        if match.start() > self.lastend:
            span = (self.lastend, match.start())
            self.debug_item("NOT MATCHED", match.string[span[0]:span[1]],
                span=span)
        
        names = ['html', 'include', 'string', 'const', 'abbrtext']
        groups = list(match.groups())[1:]

        for groupname, value in map(None, names, groups):
            if value:
                self.debug_item(groupname, value, match)
                self.current.write(self.tl.handle_item(groupname, value))

        self.lastend = match.end()

    def parse_template_tags(self, template):
        return TemplateTagsParser().run(template)

class TemplateTagsParser(object):
    TAGS_TEMPLATES = {
        'var': ('{{ %s }}', ''),
        'const': ('{{ %s }}', ''),
        'if': ('{%% if %s %%}', '{% endif %}'),
        'loop': ('{%% for %s in %s %%}', '{% endfor %}'),
    }
    def __init__(self):
        self.output = None
    
    def run(self, template):
        self.output = StringIO()
        
        for match in TAG_RE.finditer(template):
            html, tag, closing, name, args = match.groups()

            if html:
                self.output.write(html)

            if args:
                args = remove_backslashes(args)

            if tag:
                if closing:
                    self.end_tag(name)
                else:
                    self.start_tag(tag, name, args)

        return self.output.getvalue()

    def start_tag(self, tag, name, args):
        self.parse_expression(args)
        
        template = TemplateTagsParser.TAGS_TEMPLATES[name][0]
        if name == 'loop':
            # TODO
            args = ('...', args)
        self.output.write(template % args)
    
    def end_tag(self, name):
        self.output.write(TemplateTagsParser.TAGS_TEMPLATES[name][1])

    def parse_expression(self, exp, tmp=None):
        lastend = 0

        if tmp is None:
            result = []
        else:
            result = tmp

        if EXPRESSION_DEBUG:
            print "Expression\t", exp
        for match in PERL_EXP_RE.finditer(exp):
            if not match.group():
                continue

            if EXPRESSION_DEBUG and match.start() > lastend:
                span = (lastend, match.start())
                debug_item("unknown token", match.string[span[0]:span[1]],
                    span=span)
            
            names = ['option', 'path', 'advinclude', 'function', 'funcend',
                     'var', 'const', 'sprintf', 'regex', 'operator', 'comma',
                     'value', 'whitespace', 'void']
            groups = list(match.groups())

            for groupname, value in map(None, names, groups):
                if value and groupname == 'function':
                    pass
                if value:
                    if EXPRESSION_DEBUG:
                        debug_item(groupname, value, match)
                    result.append(self.handle_token(groupname, value))
            lastend = match.end()
            
        if EXPRESSION_DEBUG and len(exp) != lastend:
            debug_item("unknown token", exp[lastend:],
                span=(lastend, len(exp)))
    
    def handle_token(self, type, value):
        pass


class Jinja2Translator(object):
    '''Just to keep jinja2-specific code separate'''
    TAG_INCLUDE = "{%% include '%s' %%}"
    TAG_FILTER = "{%% filter %s %%}%s{%% endfilter %%}"
    
    def __init__(self, parent):
        # not sure if needed
        self.parent = parent
    
    def handle_item(self, type, value):
        if type == 'string':
            return value.decode('string-escape')
        elif type == 'html':
            return value
        elif type == 'include':
            value = value.replace(HTDOCS_HARDCODED_PATH, '')
            return self.TAG_INCLUDE % value
        elif type == 'const':
            return self.TAG_INCLUDE % template_filename(value)
        elif type == 'abbrtext':
            return self.TAG_FILTER % ('reverse_format(S_ABBRTEXT)',
                remove_backslashes(value))
        return value


def template_filename(constname):
    return os.path.join(TEMPLATES_DIR, '%s.html' % constname.lower())


if __name__ == '__main__':
    FutabaStyleParser()
