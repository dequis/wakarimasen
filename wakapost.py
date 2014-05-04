import re
import misc
import strings
import str_format
from util import WakaError, local

class ValidationError(WakaError):
    pass

class WakaPost(object):
    '''A post object that uses __slots__ for no good reason'''

    __slots__ = [
        # columns copied directly from model.board
        'num', 'parent', 'timestamp', 'lasthit', 'ip', 'date', 'name', 'trip',
        'email', 'subject', 'password', 'comment', 'image', 'size', 'md5',
        'width', 'height', 'thumbnail', 'tn_width', 'tn_height', 'lastedit',
        'lastedit_ip', 'admin_post', 'stickied', 'locked',
        # extensions
        'abbrev', 'nofile', 'req_file', 'filename', 'req_no_format',
        'killtrip', 'postfix', 'ninja',
    ]

    def __init__(self, rowproxy=None, **kwargs):

        self.date = ''
        self.filename = ''
        self.thumbnail = ''
        self.md5 = ''
        self.comment = ''
        self.name = ''
        self.email = ''
        self.subject = ''
        self.trip = ''
        self.password = ''
        self.lastedit = ''
        self.postfix = ''
        self.lasthit = 0
        self.ip = 0
        self.lastedit_ip = 0
        self.num = 0
        self.size = 0
        self.width = 0
        self.height = 0
        self.tn_width = 0
        self.tn_height = 0
        self.parent = 0
        self.timestamp = 0

        self.abbrev = 0

        # tri-state: True, False, or None for unset
        self.stickied = None
        self.locked = None
        self.nofile = None
        self.req_no_format = None
        self.ninja = None
        self.killtrip = None

        self.req_file = None

        self.admin_post = False

        if rowproxy:
            self.update(items=rowproxy.items())
        else:
            self.update(**kwargs)

    def __repr__(self):
        parent = ''
        if self.parent:
            parent = ' in thread %s' % self.parent
        return '<Post >>%s%s>' % (self.num, parent)

    @property
    def noko(self):
        return ((self.subject.lower() == 'noko') or
                (self.email.lower() == 'noko'))

    @property
    def db_values(self):
        '''Return a kwargs dict of values to set in the db'''

        return dict(
            parent=self.parent,
            timestamp=self.timestamp,
            ip=self.ip,
            date=self.date,
            name=self.name,
            trip=self.trip,
            email=self.email,
            subject=self.subject,
            password=self.password,
            comment=self.comment,
            image=self.filename,
            size=self.size,
            md5=self.md5,
            width=self.width,
            height=self.height,
            thumbnail=self.thumbnail,
            tn_width=self.tn_width,
            tn_height=self.tn_height,
            admin_post=self.admin_post,
            stickied=self.stickied,
            locked=self.locked,
            lastedit_ip=self.lastedit_ip,
            lasthit=self.lasthit,
            lastedit=self.lastedit)

    @classmethod
    def from_request(cls, request):
        '''Creates a Post object based on a request

        This function does not do ANY kind of validation!'''

        self = cls()

        # direct fields - assigned to attributes
        # same name in the input as the database
        for key in ['num', 'parent', 'email', 'subject', 'comment',
                    'password', 'killtrip', 'postfix', 'ninja', 'nofile']:
            setattr(self, key, request.values.get(key, ''))

        # modify these a bit here
        self.name = request.values.get('field1', '')
        self.admin_post = (request.values.get('adminpost', '0') == '1' or
                           request.values.get('adminedit', '0') == '1')
        self.stickied = request.values.get('sticky', '0') == '1'
        self.locked = request.values.get('lock', '0') == '1'
        self.req_no_format = request.values.get('no_format', '0') == '1'
        self.req_file = request.files.get('file', None)
        self.name = request.values.get('field1', '')

        return self

    def update(self, items=None, **kwargs):
        for key, value in (items or kwargs.iteritems()):
            setattr(self, key, value)

    def set_ip(self, numip, editing=None):
        '''Sets the ip or the lastedit ip'''
        if editing:
            self.lastedit_ip = numip
        else:
            self.ip = numip

    def set_date(self, editing, date_style):
        '''Sets the date or lastedit according to the timestamp'''
        if not editing:
            self.date = misc.make_date(self.timestamp, date_style)
        else:
            self.date = editing.date
            if not self.ninja:
                self.lastedit = misc.make_date(self.timestamp, date_style)

    def set_tripcode(self, tripkey):
        '''Splits the name by the tripcode'''
        self.name, temp = misc.process_tripcode(self.name, tripkey)
        self.trip = self.trip or temp

    def validate(self, editing, admin_mode, options):
        '''Validates the post contents, raises ValidationError'''

        if not admin_mode:
            if self.req_no_format or \
               (self.stickied and not self.parent) or self.locked:
                # the user is not allowed to do this
                raise ValidationError(strings.NOTALLOWED)

            file_ = self.req_file
            if self.parent:
                if file_ and not options['ALLOW_IMAGE_REPLIES']:
                    raise ValidationError(strings.NOTALLOWED)
                if not file_ and not options['ALLOW_TEXT_REPLIES']:
                    raise ValidationError(strings.NOTALLOWED)
            else:
                if file_ and not options['ALLOW_IMAGES']:
                    raise ValidationError(strings.NOTALLOWED)
                if not file_ and self.nofile and options['ALLOW_TEXTONLY']:
                    raise ValidationError(strings.NOTALLOWED)

        try:
            if len(self.parent) == 0:
                self.parent = 0
            elif len(self.parent) > 10:
                raise ValueError
            else:
                self.parent = int(self.parent)
        except ValueError:
            raise ValidationError(strings.UNUSUAL)

        # Check for weird characters
        has_crlf = lambda x: '\n' in x or '\r' in x

        if [True for x in (self.name, self.email, self.subject)
                if has_crlf(x)]:
            raise ValidationError(strings.UNUSUAL)

        # Check for excessive amounts of text
        if (len(self.name) > options['MAX_FIELD_LENGTH'] or
            len(self.email) > options['MAX_FIELD_LENGTH'] or
            len(self.subject) > options['MAX_FIELD_LENGTH'] or
            len(self.comment) > options['MAX_COMMENT_LENGTH']):

            raise ValidationError(strings.TOOLONG)

        # check to make sure the user selected a file, or clicked the checkbox
        if (not editing and not self.parent and
            not self.req_file and not self.nofile):

            raise ValidationError(strings.NOPIC)

        # check for empty reply or empty text-only post
        if not self.comment.strip() and not self.req_file:
            raise ValidationError(strings.NOTEXT)

        # get file size, and check for limitations.
        if self.req_file:
            self.size = misc.get_filestorage_size(self.req_file)
            if self.size > (options['MAX_KB'] * 1024):
                raise ValidationError(strings.TOOBIG)
            if self.size == 0:
                raise ValidationError(strings.TOOBIGORNONE)

    def clean_fields(self, editing, admin_mode, options):
        '''Modifies fields to clean them'''

        # kill the name if anonymous posting is being enforced
        if options['FORCED_ANON']:
            self.name = ''
            self.trip = ''
            if self.email.lower() == 'sage':
                self.email = 'sage'
            else:
                self.email = ''

        # fix up the email/link, if it is not a generic URI already.
        if self.email and not re.search(r"(?:^\w+:)|(?:\:\/\/)", self.email):
            self.email = "mailto:" + self.email

        # clean up the inputs
        self.subject = str_format.clean_string(
            str_format.decode_string(self.subject))

        # format comment
        if not self.req_no_format:
            self.comment = str_format.format_comment(str_format.clean_string(
                str_format.decode_string(self.comment)))

        # insert default values for empty fields
        if not (self.name or self.trip):
            self.name = options['S_ANONAME']

        self.subject = self.subject or options['S_ANOTITLE']
        self.comment = self.comment or options['S_ANOTEXT']

    def process_file(self, board, editing):
        '''Wrapper around board.process_file to use wakapost'''

        self.filename, self.md5, self.width, self.height, \
            self.thumbnail, self.tn_width, self.tn_height = \
            board.process_file(self.req_file, self.timestamp,
                self.parent, editing is not None)

    def make_post_cookies(self, options, url):
        '''Sets the name, email and password cookies'''
        c_name = self.name
        c_email = self.email
        c_password = self.password

        autopath = options['COOKIE_PATH']
        if autopath == 'current':
            path = url
        elif autopath == 'parent':
            path = local.environ['waka.rootpath']
        else:
            path = '/'

        misc.make_cookies(name=c_name, email=c_email, password=c_password,
                          path=path) # yum !
