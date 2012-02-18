import re

import config, config_defaults
from urllib import quote
from util import local

MAX_UNICODE = 1114111

CONTROL_CHARS_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f]')
ENTITIES_CLEAN_RE = re.compile('&(#([0-9]+);|#x([0-9a-fA-F]+);|)')
ENTITY_REPLACES = {
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    ',': '&#44;', # "clean up commas for some reason I forgot"
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

# The following top-level code is used to build markup translation
# dictionaries to convert from an arbitrary formatting language to HTML
# or theoretically any compatible language and back again. This is used
# to streamline and potentially extend formatting routines.
# BBCODE_TABLE is used as an example markup translation definition.
# Note no regex is used in the dictionary other than group names. Constructs
# like iterators (e.g., lists) and arbitrary arguments (e.g., XML-style
# attributes) will be supported hopefully tomorrow.

# The left side of this table is the markup inputted by the user following
# the markup standard. The right-side is equivalent HTML, with the respective
# captured groups of generic text. (Picker text capturing will also be
# added.)
BBCODE_TABLE \
    = { r'[b]\1[/b]'     :  r'<strong>\1</strong>',
        r'[i]\1\[/i]'     :  r'<em>\1</em>',
        r'[del]\1[/del]' :  r'<del>\1</del>',

        # BAD IDEA but good for testing.
        r'[color="\1"]\2[/color]' \
           : r'<span style="color:\1">\2</span>'\
      }

def __build_transl_dict(key, value, append):
    original_key = key

    # Escape metacharacters and match with \\1, \\2, etc.
    key = re.compile(r'\\\\\d+').sub(r'(.*?)', re.escape(key))

    # Effectively transpose each group to the relative location in the output
    # string (likely still in order).
    value = re.compile(key).sub(value, original_key)
    append[re.compile(key)] = value

# Build markup translation dictionaries for converting to and from
HTML_TRANSL = {}
for (key, value) in BBCODE_TABLE.iteritems():
    # Clean the markup since the comment containing the code is cleaned, too.
    key = clean_string(decode_string(key))
    __build_transl_dict(key, value, HTML_TRANSL)

CODE_TRANSL = {}
for (key, value) in BBCODE_TABLE.iteritems():
    # The HTML code is raw, thus no need to decode/clean the key.
    __build_transl_dict(value, key, CODE_TRANSL)

def percent_encode(string):
    return quote(string.encode('utf-8'))

# The code above will be temporarily replaced by this wakabamark-only
# version, in this branch only.


#format_comment regexps (FC_*)
FC_HIDE_POSTLINKS = [
    (re.compile('&gt;&gt;&gt;/?([0-9a-zA-Z]+)/?&gt;&gt;([0-9]+)'),
     r'&gt&gt&gt;/\1/&gt&gt;\2'),
    (re.compile('&gt;&gt;&gt;/([0-9a-zA-Z]+)/'), r'&gt&gt&gt;/\1/'),
    (re.compile('&gt;&gt;([0-9\-]+)'), r'&gtgt;\1')
]
FC_BOARD_POST_LINK = re.compile('&gt&gt&gt;\/?([0-9a-zA-Z]+)\/?&gt&gt;([0-9]+)')
FC_BOARD_LINK = re.compile('&gt&gt&gt;\/?([0-9a-zA-Z]+)\/?')
FC_POST_LINK = re.compile('&gtgt;([0-9]+)')

def format_comment(comment):
    # hide >>1 references from the quoting code
    for pattern, repl in FC_HIDE_POSTLINKS:
        comment = pattern.sub(repl, comment)

    def unhide_postlinks(string):
        return (string
            .replace("&gt&gt&gt;", "&gt;&gt;&gt;")
            .replace("&gt&gt;", "&gt;&gt;")
            .replace("&gtgt;", "&gt;&gt;"))

    def handler(line):
        '''fix up post link references'''

        # import this here to avoid circular imports. ugly, i know.
        import board

        def board_post_link(match):
            origtext = unhide_postlinks(match.group(0))
            try:
                newboard = board.Board(match.group(1))
                res = newboard.get_post(match.group(2))
                if res:
                    return '<a href="%s" onclick="highlight(%s)">%s</a>' % (
                        newboard.get_reply_link(res.num, res.parent),
                        match.group(1), origtext)
            except board.BoardNotFound:
                pass
            return origtext
        line = FC_BOARD_POST_LINK.sub(board_post_link, line)

        def board_link(match):
            origtext = unhide_postlinks(match.group(0))
            try:
                newboard = board.Board(match.group(1))
                return '<a href="%s">%s</a>' % (
                    newboard.make_path(page=0, url=True),
                    origtext)
            except board.BoardNotFound:
                return origtext

        line = FC_BOARD_LINK.sub(board_link, line)

        def post_link(match):
            origtext = unhide_postlinks(match.group(0))
            res = local.board.get_post(match.group(1))
            if res:
                return '<a href="%s" onclick="highlight(%s)">%s</a>' % (
                    local.board.get_reply_link(res.num, res.parent),
                    res.num, origtext)
            else:
                return origtext

        line = FC_POST_LINK.sub(post_link, line)

        return line

    if local.board.options['ENABLE_WAKABAMARK']:
        raise NotImplementedError('No wakabamark support yet') # TODO
        comment = do_wakabamark(comment, handler)
    else:
        comment = "<p>" + simple_format(comment, handler) + "</p>"

    # fix <blockquote> styles for old stylesheets
    comment = comment.replace("<blockquote>", '<blockquote class="unkfunc">')

    # restore >>1 references hidden in code blocks
    comment = unhide_postlinks(comment)

    return comment


URL_PATTERN = re.compile(
    '(https?://[^\s<>"]*?)((?:\s|<|>|"|\.|\)|\]|!|\?|,|&#44;|&quot;)*'
    '(?:[\s<>"]|$))', re.I | re.S)
URL_SUB = r'<a href="\1">\1</a>\2'

GREENTEXT_PATTERN = re.compile("^(&gt;[^_]*)$")
GREENTEXT_SUB = r'<span class="unkfunc">\1</span>'

def simple_format(comment, handler):
    lines = []
    for line in comment.split("\n"):
        # make URLs into links
        line = URL_PATTERN.sub(URL_SUB, line)

        # colour quoted sections if working in old-style mode.
        if not local.board.options['ENABLE_WAKABAMARK']:
            line = GREENTEXT_PATTERN.sub(GREENTEXT_SUB, line)

        if handler:
            line = handler(line)

        lines.append(line)

    return '<br />'.join(lines)


#tag_killa regexps (TK_*)
TK_REPLACEMENTS = [
    # Strip Oekaki postfix.
    (re.compile('<p(?: class="oekinfo">|>\s*<small>)\s*<strong>(?:Oekaki post|'
        'Edited in Oekaki)</strong>\s*\(Time\:.*?</p>'), '', re.I),

    (re.compile('<br\s?/?>'), '\n'),
    (re.compile('</p>$'), ''),
    (re.compile('<code>([^\n]*?)</code>'), r'`\1`'),
    (re.compile('</blockquote>$'), ''),
    (re.compile('</blockquote>'), '\n\n'),
]

TK_CODEBLOCK = re.compile('<\s*?code>(.*?)</\s*?code>', re.S)
TK_ULIST = re.compile('<ul>(.*?)</ul>', re.S)
TK_OLIST = re.compile('<ol>(.*?)</ol>', re.S)

TK_REPLACEMENTS_2 = [
    (re.compile('</?em>'), '*'),
    (re.compile('</?strong>'), '**'),
    (re.compile('<.*?>'), ''),
]

def tag_killa(string):
    '''subroutine for stripping HTML tags and supplanting them with corresponding wakabamark'''
    for pattern, repl in TK_REPLACEMENTS:
        string = pattern.sub(repl, string)

    # TODO do <code> tags consider newlines as line breaks?
    def codeblock(match):
        return '\n'.join(['    ' + x for x in match.group(1).split("\n")]) + "\n"
    string = TK_CODEBLOCK.sub(codeblock, string)

    def ulist(match):
        return match.group(1).replace("<li>", "* ").replace("</li>", "\n") + "\n"
    string = TK_ULIST.sub(ulist, string)

    def olist(match):
        count = 0
        def replace_li(entry):
            count += 1
            return entry.replace("<li>", "%s. " % count)
        strings = match.group(1).split("</li>")
        return '\n'.join([replace_li(x) for x in strings]) + "\n"
    string = TK_OLIST.sub(olist, string)

    for pattern, repl in TK_REPLACEMENTS_2:
        string = pattern.sub(repl, string)
    return decode_string(string)
