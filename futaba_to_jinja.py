import re
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

file = open("futaba_style.pl", "r").read()

TEMPLATE_RE = re.compile(r'^use constant ([A-Z_]+) => (.*?;) ?\n\n', re.M | re.S)
TEMPLATE_SECTION_RE = re.compile(
    r'('
        r'q{((?:[^{}]|{[^{}]*})*)}|'    # allow non-nested braces inside the q{}
        r'include\("([a-z_/\.]*?)"\)|'
        r'"(.*?)"|'
        r'([A-Z][A-Z_]+)|'
        r'sprintf\(S_ABBRTEXT,[\'"](.*?)[\'"]\)'
    r')[\.;] *',
    re.S | re.M)

COMPILE_TEMPLATE = re.compile(
    r'^compile_template ?\((.*?)\);$',
    re.S)

class FutabaStyleParser(object):
    FILENAME = "futaba_style.pl"
    
    def __init__(self, debuglevel=1):
        self.debug = debuglevel

        self.lastend = 0

        self.templates = {}
        self.current = None

        self.tl = Jinja2Translator(self)

        TEMPLATE_RE.sub(self.do_constant,
            open(FutabaStyleParser.FILENAME).read())

    def debug_item(self, name, value='', match=None, span=''):
        if not self.debug:
            return
        span = match and match.span() or span
        if value and self.debug < 2:
            value = repr(value)[1:-1]
            if len(value) > 50:
                value = value[:50] + "[...]"
        print ' %14s %-8s %s' % (span, name, value)

    def do_constant(self, match):
        name, template = match.groups()
        
        if self.debug:
            print name
        
        # remove compile_template(...)
        compile = COMPILE_TEMPLATE.match(template)
        if compile:
            self.debug_item('compiled', '1')
            template = compile.group(1) + ';'
        
        # init variables for the self.block loop
        self.lastend = 0
        self.current = StringIO()

        TEMPLATE_SECTION_RE.sub(self.block, template)
        
        # after the self.block loop
        self.templates[name] = self.current.getvalue()

        if len(template) != self.lastend:
            self.debug_item("NOT MATCHED (end)", template[lastend:],
                span=(lastend, len(template)))

    def block(self, match):
        if not match.group():
            return

        if match.start() > self.lastend:
            span = (lastend, match.start())
            self.debug_item("NOT MATCHED", match.string[span[0]:span[1]],
                span=span)
        
        names = ['html', 'include', 'string', 'const', 'abbrtext']
        groups = list(match.groups())[1:]

        for groupname, value in map(None, names, groups):
            if value:
                self.debug_item(groupname, value, match)
                self.current.write(self.tl.handle_item(groupname, value))

        self.lastend = match.end()


class Jinja2Translator(object):
    '''Just to keep jinja2-specific code separate'''
    TAG_INCLUDE = "{%% include '%s' %%}"
    
    def __init__(self, parent):
        # not sure if needed
        self.parent = parent
    
    def handle_item(self, type, value):
        if type == 'string':
            return self.translate_tags(value.decode('string-escape'))
        elif type == 'html':
            return self.translate_tags(value)
        elif type == 'include':
            return self.TAG_INCLUDE % value
        elif type == 'const':
            return self.TAG_INCLUDE % template_filename(value)
        return value

    def translate_tags(self, value):
        return value

def template_filename(constname):
    return 'templates/%s.html' % constname.lower()


if __name__ == '__main__':
    FutabaStyleParser()
