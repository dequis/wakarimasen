from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData
from sqlalchemy.orm import sessionmaker

engine = create_engine('mysql://desu:desu@localhost/desu', echo=True, pool_size=100, max_overflow=10)
Session = sessionmaker(bind=engine)
metadata = MetaData()

boards = {}

def board_table(name):
    if name in boards:
        return boards[name]
    table = Table(name, metadata,
        Column("num", Integer, primary_key=True),       # Post number, auto-increments
        Column("parent", Integer),                      # Parent post for replies in threads. For original posts, must be set to 0 (and not null)
        Column("timestamp", Integer),                   # Timestamp in seconds for when the post was created
        Column("lasthit", Integer),                     # Last activity in thread. Must be set to the same value for BOTH the original post and all replies!
        Column("ip", Text),                             # IP number of poster, in integer form!

        Column("date", Text),                           # The date, as a string
        Column("name", Text),                           # Name of the poster
        Column("trip", Text),                           # Tripcode (encoded)
        Column("email", Text),                          # Email address
        Column("subject", Text),                        # Subject
        Column("password", Text),                       # Deletion password (in plaintext) 
        Column("comment", Text),                        # Comment text, HTML encoded.

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
    boards[name] = table
    return table

admin_table = Table(SQL_ADMIN_TABLE, metadata,
    Column("num", Integer, primary_key=True),           # Entry number, auto-increments
    Column("type", Text),                               # Type of entry (ipban, wordban, etc)
    Column("comment", Text),                            # Comment for the entry
    Column("ival1", Text),                              # Integer value 1 (usually IP)
    Column("ival2", Text),                              # Integer value 2 (usually netmask)
    Column("sval1", Text),                              # String value 1
    Column("total", Text),                              # ADDED - Total Ban?
    Column("expiration", Integer),                      # ADDED - Ban Expiration?
)

proxy_table = Table(SQL_PROXY_TABLE, metadata,
    Column("num", Integer, primary_key=True),           # Entry number, auto-increments
    Column("type", Text),                               # Type of entry (black, white, etc)
    Column("ip", Text),                                 # IP address
    Column("timestamp", Integer),                       # Age since epoch
    Column("date", Text),                               # Human-readable form of date 
)

account_table = Table(SQL_ACCOUNT_TABLE, metadata,
    Column("username", String(25), primary_key=True),   # Name of user--must be unique
    Column("account", Text, nullable=False),            # Account type/class: mod, globmod, admin
    Column("password", Text, nullable=False),           # Encrypted password
    Column("reign", Text),                              # List of board (tables) under jurisdiction: globmod and admin have global power and are exempt
    Column("disabled", Integer),                        # Disabled account?
)

activity_table = Table(SQL_STAFFLOG_TABLE, metadata,
    Column("num", Integer, primary_key=True),           # ID
    Column("username", String(25), nullable=False),     # Name of moderator involved
    Column("action", Text),                             # Action performed: post_delete, admin_post, admin_edit, ip_ban, ban_edit, ban_remove
    Column("info", Text),                               # Information
    Column("date", Text),                               # Date of action
    Column("ip", Text),                                 # IP address of the moderator
    Column("admin_id", Integer),                        # For associating certain entries with the corresponding key on the admin table
    Column("timestamp", Integer),                       # Timestamp, for trimming
)

common_site_table = Table(SQL_COMMON_SITE_TABLE, metadata,
    Column("board", String(25), primary_key=True),      # Name of comment table
    Column("type", Text),                               # Corresponding board type? (Later use)
)

report_table = Table(SQL_REPORT_TABLE, metadata,
    Column("num", Integer, primary_key=True),           # Report number, auto-increments
    Column("board", String(25), nullable=False),        # Board name
    Column("reporter", Text, nullable=False),           # Reporter's IP address (decimal encoded)
    Column("offender", Text),                           # IP Address of the offending poster. Why the form-breaking redundancy with SQL_TABLE? If a post is deleted by the perpetrator, the trace is still logged. :)
    Column("postnum", Integer, nullable=False),         # Post number
    Column("comment", Text, nullable=False),            # Mandated reason for the report
    Column("timestamp", Integer),                       # Timestamp in seconds for when the post was created
    Column("date", Text),                               # Date of the report
    Column("resolved", Integer),                        # Is it resolved? (1: yes 0: no)
)

backup_table = Table(SQL_BACKUP_TABLE, metadata,
    Column("num", Integer, primary_key=True),           # Primary key, auto-increments
    Column("board_name", String(25), nullable=False),   # Board name
    Column("postnum", Integer),                         # Post number
    Column("parent", Integer),                          # Parent post for replies in threads. For original posts, must be set to 0 (and not null)
    Column("timestamp", Integer),                       # Timestamp in seconds for when the post was created
    Column("lasthit", Integer),                         # Last activity in thread. Must be set to the same value for BOTH the original post and all replies!
    Column("ip", Text),                                 # IP number of poster, in integer form!

    Column("date", Text),                               # The date, as a string
    Column("name", Text),                               # Name of the poster
    Column("trip", Text),                               # Tripcode (encoded)
    Column("email", Text),                              # Email address
    Column("subject", Text),                            # Subject
    Column("password", Text),                           # Deletion password (in plaintext) 
    Column("comment", Text),                            # Comment text, HTML encoded.

    Column("image", Text),                              # Image filename with path and extension (IE, src/1081231233721.jpg)
    Column("size", Integer),                            # File size in bytes
    Column("md5", Text),                                # md5 sum in hex
    Column("width", Integer),                           # Width of image in pixels
    Column("height", Integer),                          # Height of image in pixels
    Column("thumbnail", Text),                          # Thumbnail filename with path and extension
    Column("tn_width", Text),                           # Thumbnail width in pixels
    Column("tn_height", Text),                          # Thumbnail height in pixels
    Column("lastedit", Text),                           # ADDED - Date of previous edit, as a string 
    Column("lastedit_ip", Text),                        # ADDED - Previous editor of the post, if any
    Column("admin_post", Text),                         # ADDED - Admin post?
    Column("stickied", Integer),                        # ADDED - Stickied?
    Column("locked", Text),                             # ADDED - Locked?
    Column("timestampofarchival", Integer),             # When was this backed up?
)

passprompt_table = Table(SQL_PASSPROMPT_TABLE, metadata,
    Column("id", Integer, primary_key=True),
    Column("host", Text),
    Column("task", String(25)),
    Column("boardname", String(25)),
    Column("post", Integer),
    Column("timestamp", Integer),
    Column("passfail", Integer),
)
