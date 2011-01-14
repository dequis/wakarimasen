import re

import config, config_defaults

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

def format_comment(comment):
    '''Format an already decoded string following the markup translation
    dictionary.'''
    for (input_code, output_html) in HTML_TRANSL.iteritems():
        comment = input_code.sub(output_html, comment)

    return comment

def tag_killa(comment):
    for (input_html, output_code) in CODE_TRANSL.iteritems():
        comment = input_html.sub(output_code, comment)

    return comment
