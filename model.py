import config, config_defaults
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, Text, String, MetaData
from sqlalchemy.orm import sessionmaker, mapper, scoped_session
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine(config.SQL_ENGINE, echo=True, pool_size=100, max_overflow=10)
Session = scoped_session(sessionmaker(bind=engine))
metadata = MetaData()
Base = declarative_base(metadata=metadata)

_boards = {}

class CompactPost(object):
    '''A prematurely optimized post object'''

    __slots__ = [
        # columns copied directly from rowproxy
        'num', 'parent', 'timestamp', 'lasthit', 'ip', 'date', 'name', 'trip',
        'email', 'subject', 'password', 'comment', 'image', 'size', 'md5',
        'width', 'height', 'thumbnail', 'tn_width', 'tn_height', 'lastedit',
        'lastedit_ip', 'admin_post', 'stickied', 'locked',
        # extensions
        'abbrev',
    ]

    def __init__(self, rowproxy):
        for key, value in rowproxy.items():
            setattr(self, key, value)
        self.abbrev = 0
    
    def __repr__(self):
        parent = ''
        if self.parent:
            parent = ' in thread %s' % self.parent
        return '<Post >>%s%s>' % (self.num, parent)

def board(name):
    '''Generates board classes to use with the ORM'''
    if name in _boards:
        return _boards[name]

    table = Table(name, metadata,
        Column("num", Integer, primary_key=True),       # Post number, auto-increments
        Column("parent", Integer),                      # Parent post for replies in threads. For original posts, must be set to 0 (and not null)
        Column("timestamp", Integer),                   # Timestamp in seconds for when the post was created
        Column("lasthit", Integer),                     # Last activity in thread. Must be set to the same value for BOTH the original post and all replies!
        Column("ip", Text),                             # IP number of poster, in integer form!

        Column("date", Text),                           # The date, as a string
        Column("name", Text(convert_unicode=True)),     # Name of the poster
        Column("trip", Text),                           # Tripcode (encoded)
        Column("email", Text),                          # Email address
        Column("subject", Text(convert_unicode=True)),  # Subject
        Column("password", Text),                       # Deletion password (in plaintext) 
        Column("comment", Text(convert_unicode=True)),  # Comment text, HTML encoded.

        Column("image", Text),                          # Image filename with path and extension (IE, src/1081231233721.jpg)
        Column("size", Integer),                        # File size in bytes
        Column("md5", Text),                            # md5 sum in hex
        Column("width", Integer),                       # Width of image in pixels
        Column("height", Integer),                      # Height of image in pixels
        Column("thumbnail", Text),                      # Thumbnail filename with path and extension
        Column("tn_width", Text),                       # Thumbnail width in pixels
        Column("tn_height", Text),                      # Thumbnail height in pixels
        Column("lastedit", Text),                       # ADDED - Date of previous edit, as a string 
        Column("lastedit_ip", Text),                    # ADDED - Previous editor of the post, if any
        Column("admin_post", Text),                     # ADDED - Admin post?
        Column("stickied", Integer),                    # ADDED - Stickied?
        Column("locked", Text),                         # ADDED - Locked?
    )

    _boards[name] = table
    return _boards[name]


class Admin(Base):
    __tablename__ = config.SQL_ADMIN_TABLE

    num = Column(Integer, primary_key=True)             # Entry number, auto-increments
    type = Column(Text)                                 # Type of entry (ipban, wordban, etc)
    comment = Column(Text)                              # Comment for the entry
    ival1 = Column(Text)                                # Integer value 1 (usually IP)
    ival2 = Column(Text)                                # Integer value 2 (usually netmask)
    sval1 = Column(Text)                                # String value 1
    total = Column(Text)                                # ADDED - Total Ban?
    expiration = Column(Integer)                        # ADDED - Ban Expiration?

class Proxy(Base):
    __tablename__ = config.SQL_PROXY_TABLE

    num = Column(Integer, primary_key=True)             # Entry number, auto-increments
    type = Column(Text)                                 # Type of entry (black, white, etc)
    ip = Column(Text)                                   # IP address
    timestamp = Column(Integer)                         # Age since epoch
    date = Column(Text)                                 # Human-readable form of date 

class Account(Base):
    __tablename__ = config.SQL_ACCOUNT_TABLE

    username = Column(String(25), primary_key=True)     # Name of user--must be unique
    account = Column(Text, nullable=False)              # Account type/class: mod, globmod, admin
    password = Column(Text, nullable=False)             # Encrypted password
    reign = Column(Text)                                # List of board (tables) under jurisdiction: globmod and admin have global power and are exempt
    disabled = Column(Integer)                          # Disabled account?

class Activity(Base):
    __tablename__ = config.SQL_STAFFLOG_TABLE

    num = Column(Integer, primary_key=True)             # ID
    username = Column(String(25), nullable=False)       # Name of moderator involved
    action = Column(Text)                               # Action performed: post_delete, admin_post, admin_edit, ip_ban, ban_edit, ban_remove
    info = Column(Text)                                 # Information
    date = Column(Text)                                 # Date of action
    ip = Column(Text)                                   # IP address of the moderator
    admin_id = Column(Integer)                          # For associating certain entries with the corresponding key on the admin table
    timestamp = Column(Integer)                         # Timestamp, for trimming

class Common(Base):
    __tablename__ = config.SQL_COMMON_SITE_TABLE

    board = Column(String(25), primary_key=True)        # Name of comment table
    type = Column(Text)                                 # Corresponding board type? (Later use)

class Report(Base):
    __tablename__ = config.SQL_REPORT_TABLE

    num = Column(Integer, primary_key=True)             # Report number, auto-increments
    board = Column(String(25), nullable=False)          # Board name
    reporter = Column(Text, nullable=False)             # Reporter's IP address (decimal encoded)
    offender = Column(Text)                             # IP Address of the offending poster. Why the form-breaking redundancy with SQL_TABLE? If a post is deleted by the perpetrator, the trace is still logged. :)
    postnum = Column(Integer, nullable=False)           # Post number
    comment = Column(Text, nullable=False)              # Mandated reason for the report
    timestamp = Column(Integer)                         # Timestamp in seconds for when the post was created
    date = Column(Text)                                 # Date of the report
    resolved = Column(Integer)                          # Is it resolved? (1: yes 0: no)

class Backup(Base):
    __tablename__ = config.SQL_BACKUP_TABLE

    num = Column(Integer, primary_key=True)             # Primary key, auto-increments
    board_name = Column(String(25), nullable=False)     # Board name
    postnum = Column(Integer)                           # Post number
    parent = Column(Integer)                            # Parent post for replies in threads. For original posts, must be set to 0 (and not null)
    timestamp = Column(Integer)                         # Timestamp in seconds for when the post was created
    lasthit = Column(Integer)                           # Last activity in thread. Must be set to the same value for BOTH the original post and all replies!
    ip = Column(Text)                                   # IP number of poster, in integer form!

    date = Column(Text)                                 # The date, as a string
    name = Column(Text)                                 # Name of the poster
    trip = Column(Text)                                 # Tripcode (encoded)
    email = Column(Text)                                # Email address
    subject = Column(Text)                              # Subject
    password = Column(Text)                             # Deletion password (in plaintext) 
    comment = Column(Text)                              # Comment text, HTML encoded.

    image = Column(Text)                                # Image filename with path and extension (IE, src/1081231233721.jpg)
    size = Column(Integer)                              # File size in bytes
    md5 = Column(Text)                                  # md5 sum in hex
    width = Column(Integer)                             # Width of image in pixels
    height = Column(Integer)                            # Height of image in pixels
    thumbnail = Column(Text)                            # Thumbnail filename with path and extension
    tn_width = Column(Text)                             # Thumbnail width in pixels
    tn_height = Column(Text)                            # Thumbnail height in pixels
    lastedit = Column(Text)                             # ADDED - Date of previous edit, as a string 
    lastedit_ip = Column(Text)                          # ADDED - Previous editor of the post, if any
    admin_post = Column(Text)                           # ADDED - Admin post?
    stickied = Column(Integer)                          # ADDED - Stickied?
    locked = Column(Text)                               # ADDED - Locked?
    timestampofarchival = Column(Integer)               # When was this backed up?

class Passprompt(Base):
    __tablename__ = config.SQL_PASSPROMPT_TABLE

    id = Column(Integer, primary_key=True)
    host = Column(Text)
    task = Column(String(25))
    boardname = Column(String(25))
    post = Column(Integer)
    timestamp = Column(Integer)
    passfail = Column(Integer)
