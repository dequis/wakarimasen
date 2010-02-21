import os
import re
import optparse
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import config, config_defaults
except ImportError:
    config = None

TEMPLATES_DIR = 'templates'
HTDOCS_HARDCODED_PATH = '/home/desuchan/public_html/desuchan.net/htdocs/'

FUTABA_STYLE_DEBUG = 0
EXPRESSION_DEBUG = 0
EXPRESSION_TRANSLATOR_DEBUG = 0
LOOP_TAG_DEBUG = 0
VARIABLES_DEBUG = 0

TEMPLATE_RE = re.compile(r'^use constant ([A-Z_]+) => (.*?;)\s*\n\n', re.M | re.S)
TEMPLATE_SECTION_RE = re.compile(
    r'('
        r'q{((?:[^{}]|{[^{}]*})*)}|'    # allow non-nested braces inside the q{}
        r'include\("([a-z_/\.]*?)"\)|'
        r'"(.*?)"|'
        r'([A-Z][A-Z_]+)|'
        r'sprintf\(S_ABBRTEXT,([\'"].*?[\'"])\)'
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
    r'\$([A-Za-z0-9_{}]+)|'
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


# post and admin table columns
_POST_TABLE = ['num', 'parent', 'timestamp', 'lasthit', 'ip', 'date', 'name',
    'trip', 'email', 'subject', 'password', 'comment', 'image', 'size', 'md5',
    'width', 'height', 'thumbnail', 'tn_width', 'tn_height', 'lastedit',
    'lastedit_ip', 'admin_post', 'stickied', 'locked']

_ADMIN_TABLE = ['username', 'num', 'type', 'comment', 'ival1', 'ival2',
    'sval1', 'total', 'expiration', 'divider']

# oh god what is this
KNOWN_LOOPS = {
    'stylesheets': ('stylesheet', ['filename', 'title', 'default']),
    'inputs': ('input', ['name', 'value']),
    'S_OEKPAINTERS': ('painters', ['painter', 'name']),
    'threads': ('thread', ['posts', 'omit', 'omitimages']),
    'posts': ('post', _POST_TABLE + ['abbrev']),
    'pages': ('page', ['page', 'filename', 'current']),
    'loop': ('post', _POST_TABLE),
    'boards_select': ('board', ['board_entry']),
    'reportedposts': ('rpost', ['reporter', 'offender', 'postnum',
                                'comment', 'date', 'resolved']),
    'users': ('user', ['username', 'account', 'password', 'reign', 'disabled']),
    'boards': ('board', ['board_entry', 'underpower']),
    'staff': ('account', ['username']),
    # this is actually three different loops
    'entries': ('entry', ['num', 'username', 'action', 'info', 'date', 'ip',
                          'admin_id', 'timestamp', 'rowtype', 'disabled',
                          'account', 'expiration', 'id', 'host', 'task',
                          'boardname', 'post', 'timestamp', 'passfail']),
    'edits': ('edit', ['username', 'date', 'info', 'num']),
    'bans': ('ban', _ADMIN_TABLE + ['rowtype', 'expirehuman', 'browsingban']),
    'hash': ('row', _ADMIN_TABLE),
    'scanned': ('proxy', ['num', 'type', 'ip', 'timestamp',
                          'date', 'divider', 'rowtype']),
    'errors': ('error', ['error']),
    'items': ('post', _POST_TABLE + ['mime_type']),
}

RENAME = {
    'sprintf': 'reverse_format',
    'OEKAKI_DEFAULT_PAINTER': 'board.options.OEKAKI_DEFAULT_PAINTER',
}

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
    def __init__(self, filename="futaba_style.pl", only=None, dry_run=False):
        self.only = only
        self.dry_run = dry_run

        self.lastend = 0
        self.current = None

        if not os.path.exists(TEMPLATES_DIR) and not self.dry_run:
            os.mkdir(TEMPLATES_DIR)

        self.tl = Jinja2Translator(self)

        TEMPLATE_RE.sub(self.do_constant, open(filename).read())

    def debug_item(self, *args, **kwds):
        if not FUTABA_STYLE_DEBUG:
            return
        debug_item(*args, **kwds)

    def do_constant(self, match):
        name, template = match.groups()
        
        if self.only and self.only != name:
            return
        
        if FUTABA_STYLE_DEBUG or LOOP_TAG_DEBUG or VARIABLES_DEBUG:
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

        if not self.dry_run:
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
        return TemplateTagsParser(self.tl).run(template)

class TemplateTagsParser(object):
    def __init__(self, tl):
        self.tl = tl
        self.output = None

        self.loops = []
    
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
        template = self.tl.TAGS[name][0]
        try:
            args = self.tl.translate_expression(self.parse_expression(args),
                name, self.loops)
        except AdvInclude, e:
            template = self.tl.TAGS['include']
            args = e.value

        if name == 'loop':
            if LOOP_TAG_DEBUG:
                print "Enter loop", args
            self.loops.append(args[1].split('.')[-1])
            
        self.output.write(template % args)
    
    def end_tag(self, name):
        if name == 'loop':
            loop = self.loops.pop()
            if LOOP_TAG_DEBUG:
                print "Exit loop", loop
        self.output.write(self.tl.TAGS[name][1])

    def parse_expression(self, exp):
        lastend = 0

        if EXPRESSION_DEBUG or EXPRESSION_TRANSLATOR_DEBUG:
            print "Expression\t", exp
        
        result = self.parse_subexpression(exp)[0]
        if EXPRESSION_DEBUG:
            print ' ', result

        return result

    def parse_subexpression(self, exp, tmp=None):
        '''return value: tuple
            [0] list of tokens
            [1] the remaining 
        if tmp is set, results are appended to that list instead of returning
        a new one (useful when parsing the remaining)
        '''
        lastend = 0
        if tmp is None:
            result = []
        else:
            result = tmp

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
            groups = match.groups()

            for groupname, value in map(None, names, groups):
                if value:
                    break

            retval = self.handle_token(groupname, value, match, result)
            if retval is not None:
                return retval

            lastend = match.end()
            
        if EXPRESSION_DEBUG and len(exp) != lastend:
            debug_item("unknown token", exp[lastend:],
                span=(lastend, len(exp)))

        return (result, '')

    def call_function(self, name, args, result):
        function, remaining = self.parse_subexpression(args)
        result.append(('function', (name, function)))
        return self.parse_subexpression(remaining, result)
        
    def handle_token(self, type, value, match, result):
        if type == 'sprintf':
            return self.call_function('sprintf', value + ')', result)
        elif type == 'void':
            type, value = 'function', 'void'
            
        if type == 'function':
            return self.call_function(value, match.string[match.end():],
                result)
        elif type == 'funcend':
            remaining = match.string[match.end():]
            return (result, remaining)

        if type == 'option':
            value = value.strip('\'"')

        if type == 'regex':
            if value.startswith("!"):
                result.append(('operator', '!'))
            value = value[2:].strip(' ')
            
        if type != 'whitespace':
            result.append((type, value))


class Jinja2Translator(object):
    '''Just to keep jinja2-specific code separate'''
    TAGS = {
        'var': ('{{ %s }}', ''),
        'const': ('{{ %s }}', ''),
        'if': ('{%% if %s %%}', '{% endif %}'),
        'loop': ('{%% for %s in %s %%}', '{% endfor %}'),
        'include': "{%% include '%s' %%}",
        'filter': '{%% filter %s %%}%s{%% endfilter %%}',
    }
    
    OPERATORS = {
        '!': 'not',
        'eq': '==',
        'ne': '!=',
        '||': 'or',
        '&&': 'and',
        '?': 'and', # h4x
        ':': 'or',  # ^
        '.': '+',
    }
    def __init__(self, parent):
        # not sure if needed
        self.parent = parent

        self.loops = None
    
    def handle_item(self, type, value):
        if type == 'string':
            return value.decode('string-escape')
        elif type == 'html':
            return value
        elif type == 'include':
            value = value.replace(HTDOCS_HARDCODED_PATH, '')
            return self.TAGS['include'] % value
        elif type == 'const':
            return self.TAGS['include'] % template_filename(value)
        elif type == 'abbrtext':
            if value.startswith('"'):
                value = remove_backslashes(value)
            return self.TAGS['filter'] % ('reverse_format(strings.ABBRTEXT)',
                value.strip('\'"'))
        return value

    def translate_expression(self, exp, tagname, loops):
        mode = None
        if tagname == 'loop':
            mode = 'loop'
        
        self.loops = loops
        result = self._translate_expression(exp, mode=mode)

        if LOOP_TAG_DEBUG and loops:
            print " > exp(%s) :: %s" % (', '.join(loops), result)
        
        if EXPRESSION_TRANSLATOR_DEBUG:
            print "->", repr(result)
        return result

    def _translate_expression(self, exp, mode=None):
        parts = []
        result = []

        for type, value in exp:
            if type == 'option':
                value = 'board.option.%s' % value

            elif type == 'path':
                value = 'board.path'

            elif type == 'advinclude':
                raise AdvInclude(value)

            elif type == 'function':
                name, subexp = value
                if name in RENAME:
                    name = RENAME[name]

                parsed = self._translate_expression(subexp, mode='function')
                if name == 'void':
                    value = '(%s)' % ', '.join(parsed)
                elif len(parsed) > 1:
                    value = '%s|%s(%s)' % (parsed[0], name, ', '.join(parsed[1:]))
                elif len(parsed) == 1 and ''.join(parsed):
                    value = '%s|%s' % (parsed[0], name)
                else:
                    value = '%s()' % name
                
                if VARIABLES_DEBUG and name != 'void':
                    print " filter", name

            elif type == 'var':
                if value in RENAME:
                    value = RENAME[value]

                for loop in self.loops[::-1]:
                    if loop in KNOWN_LOOPS and value in KNOWN_LOOPS[loop][1]:
                        value = '%s.%s' % (KNOWN_LOOPS[loop][0], value)

                if VARIABLES_DEBUG:
                    print " var", value

            elif type == 'const':
                if value in RENAME:
                    value = RENAME[value]

                if value.startswith("S_"):
                    value = 'strings.%s' % value[2:]
                elif config and hasattr(config, value):
                    value = 'config.%s' % value

                if VARIABLES_DEBUG:
                    print " const", value

            elif type == 'regex':
                do_lower = value.endswith('i')
                action = value.startswith('/^') and 'startswith' or 'count'
                value = value.strip('/i^')

                variable = result.pop()

                if variable == 'not':
                    variable = result.pop()
                    result.append('not')

                result.append('%s.%s("%s")' % (variable, action, value))
                value = None

            elif type == 'operator':
                value = self.OPERATORS.get(value, value)

            elif type == 'comma':
                parts.append(result)
                result = []
                value = None

            if value:
                result.append(value)
        
        if mode == 'function':
            parts.append(result)
            return [' '.join(x) for x in parts]
        elif mode == 'loop':
            itervarname = 'i'
            if len(exp) == 1:
                type, value = exp[0]
                if type in ('var', 'const'):
                    if value in KNOWN_LOOPS:
                        itervarname = KNOWN_LOOPS[value][0]
                    elif value.lower().endswith('s'):
                        itervarname = value.lower().rstrip('s')
                    else:
                        itervarname = value.lower() + '_item'
            return (itervarname, ' '.join(result))
        else:
            return ' '.join(result)

class AdvInclude(Exception):
    '''This is not an exception but an exceptional condition
    Advincludes are complete includes with template tags parsing
    and everything, but inside a <var> tag, so the most sensible
    way to handle them was to raise an exception'''
    def __init__(self, value):
        self.value = value

def template_filename(constname):
    return os.path.join(TEMPLATES_DIR, '%s.html' % constname.lower())

def main():
    parser = optparse.OptionParser()
    parser.add_option("-f", "--filename", default="futaba_style.pl",
        help="Location of the futaba_style.pl file")
    parser.add_option("-o", "--only", default=None, metavar="CONST",
        help="Parse only one constant in futaba_style.pl")
    parser.add_option("-n", "--dry-run", action="store_true", 
        help="Don't write templates to disk")

    group = optparse.OptionGroup(parser, "Debug channels")
    group.add_option("--futaba-style-debug", action="store_true")
    group.add_option("--expression-debug", action="store_true")
    group.add_option("--translator-debug", action="store_true")
    group.add_option("--loop-debug", action="store_true")
    group.add_option("--variables-debug", action="store_true")
    parser.add_option_group(group)
    
    (options, args) = parser.parse_args()

    # set debug channels. oh god h4x
    global FUTABA_STYLE_DEBUG, EXPRESSION_DEBUG, EXPRESSION_TRANSLATOR_DEBUG
    global LOOP_TAG_DEBUG, VARIABLES_DEBUG
    FUTABA_STYLE_DEBUG = options.futaba_style_debug
    EXPRESSION_DEBUG = options.expression_debug
    EXPRESSION_TRANSLATOR_DEBUG = options.translator_debug
    LOOP_TAG_DEBUG = options.loop_debug
    VARIABLES_DEBUG = options.variables_debug

    FutabaStyleParser(filename=options.filename,
                      only=options.only,
                      dry_run=options.dry_run)


if __name__ == '__main__':
    main()
