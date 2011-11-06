HOME = 'Home'                                                # Forwards to home page
ADMIN = 'Manage'                                             # Forwards to Management Panel
RETURN = 'Return'                                            # Returns to image board
POSTING = 'Posting mode: Reply'                              # Prints message in red bar atop the reply screen

NAME = 'Name'                                                # Describes name field
EMAIL = 'Link'                                               # Describes e-mail field
SUBJECT = 'Subject'                                          # Describes subject field
SUBMIT = 'Submit'                                            # Describes submit button
COMMENT = 'Comment'                                          # Describes comment field
UPLOADFILE = 'File'                                          # Describes file field
NOFILE = 'No File'                                           # Describes file/no file checkbox
CAPTCHA = 'Verification'                                     # Describes captcha field
PARENT = 'Parent'                                            # Describes parent field on admin post page
DELPASS = 'Password'                                         # Describes password field
DELEXPL = '(for post and file deletion and editing)'         # Prints explanation for password box (to the right)
SPAMTRAP = 'Leave these fields empty (spam trap): '

THUMB = 'Thumbnail displayed, click image for full size.'    # Prints instructions for viewing real source
HIDDEN = 'Thumbnail hidden, click filename for the full image.'    # Prints instructions for viewing hidden image reply
NOTHUMB = 'No<br />thumbnail'                                # Printed when there's no thumbnail
PICNAME = 'File: '                                           # Prints text before upload name/link
REPLY = 'Reply'                                              # Prints text for reply link
OLD = 'Marked for deletion (old).'                           # Prints text to be displayed before post is marked for deletion, see: retention
ABBR = '%d posts omitted. Click Reply to view.'              # Prints text to be shown when replies are hidden
ABBR_LOCK = '%d posts omitted. Click View to see them.'
ABBRIMG = '%d posts and %d images omitted. Click Reply to view.'    # Prints text to be shown when replies and images are hidden
ABBRTEXT = 'Comment too long. Click <a href="%s">here</a> to view the full text.'
ABBRIMG_LOCK = '%d posts and %d images omitted. Click View to see them.'    # Prints text to be shown when replies and images are hidden

REPDEL = 'Delete Post '                                      # Prints text next to S_DELPICONLY (left)
DELPICONLY = 'File Only'                                     # Prints text next to checkbox for file deletion (right)
DELKEY = 'Password '                                         # Prints text next to password field for deletion (left)
DELETE = 'Delete'                                            # Defines deletion button's name

PREV = 'Previous'                                            # Defines previous button
FIRSTPG = 'Previous'                                         # Defines previous button
NEXT = 'Next'                                                # Defines next button
LASTPG = 'Next'                                              # Defines next button

WEEKDAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']       # Defines abbreviated weekday names.

MANARET = 'Return'                                           # Returns to HTML file instead of PHP--thus no log/SQLDB update occurs
MANAMODE = 'Manager Mode'                                    # Prints heading on top of Manager page

MANALOGIN = 'Manager Login'                                  # Defines Management Panel radio button--allows the user to view the management panel (overview of all posts)
ADMINPASS = 'Admin password:'                                # Prints login prompt

MANAPANEL = 'Management Panel'                               # Defines Management Panel radio button--allows the user to view the management panel (overview of all posts)
MANABANS = 'Bans/Whitelist'                                  # Defines Bans Panel button
MANAPROXY = 'Proxy Panel'
MANASPAM = 'Spam'                                            # Defines Spam Panel button
MANASQLDUMP = 'SQL Dump'                                     # Defines SQL dump button
MANASQLINT = 'SQL Interface'                                 # Defines SQL interface button
MANAPOST = 'Manager Post'                                    # Defines Manager Post radio button--allows the user to post using HTML code in the comment box
MANAREBUILD = 'Rebuild caches'                               # 
MANANUKE = 'Nuke board'                                      # 
MANALOGOUT = 'Log out'                                       # 
MANASAVE = 'Remember me on this computer'                    # Defines Label for the login cookie checbox
MANASUB = 'Go'                                               # Defines name for submit button in Manager Mode

NOTAGS = 'HTML tags allowed. No formatting will be done, you must use HTML for line breaks and paragraphs.'    # Prints message on Management Board

MPDELETEIP = 'Delete all'
MPDELETE = 'Delete'                                          # Defines for deletion button in Management Panel
MPARCHIVE = 'Archive'
MPRESET = 'Reset'                                            # Defines name for field reset button in Management Panel
MPONLYPIC = 'File Only'                                      # Sets whether or not to delete only file, or entire post/thread
MPDELETEALL = 'Del&nbsp;all'                                 # 
MPBAN = 'Ban'                                                # Sets whether or not to delete only file, or entire post/thread
MPTABLE = '<th>Post No.</th><th>Time</th><th>Subject</th>' + \
    '<th>Name</th><th>Comment</th><th>Options</th><th>IP</th>'    # Explains names for Management Panel
IMGSPACEUSAGE = '[ Space used: %d KB ]'                      # Prints space used KB by the board under Management Panel

BANTABLE = '<th>Type</th><th>Value</th><th>Comment</th><th>Expires</th><th>Can Browse</th><th>Creator</th><th>Action</th>'    # EDITED Explains names for Ban Panel
BANIPLABEL = 'IP'
BANMASKLABEL = 'Mask'
BANCOMMENTLABEL = 'Comment'
BANWORDLABEL = 'Word'
BANIP = 'Ban IP'
BANWORD = 'Ban word'
BANWHITELIST = 'Whitelist'
BANREMOVE = 'Remove'
BANCOMMENT = 'Comment'
BANTRUST = 'No captcha'
BANTRUSTTRIP = 'Tripcode'

PROXYTABLE = '<th>Type</th><th>IP</th><th>Expires</th><th>Date</th>'    # Explains names for Proxy Panel
PROXYIPLABEL = 'IP'
PROXYTIMELABEL = 'Seconds to live'
PROXYREMOVEBLACK = 'Remove'
PROXYWHITELIST = 'Whitelist'
PROXYDISABLED = 'Proxy detection is currently disabled in configuration.'
BADIP = 'Bad IP value'

SPAMEXPL = 'This is the list of domain names Wakaba considers to be spam.<br />' + \
    'You can find an up-to-date version <a href="http://wakaba.c3.cx/antispam/antispam.pl?action=view&amp;format=wakaba">here</a>, ' + \
    'or you can get the <code>spam.txt</code> file directly <a href="http://wakaba.c3.cx/antispam/spam.txt">here</a>.'
SPAMSUBMIT = 'Save'
SPAMCLEAR = 'Clear'
SPAMRESET = 'Restore'

SQLNUKE = 'Nuke password:'
SQLEXECUTE = 'Execute'

TOOBIG = 'This image is too large!  Upload something smaller!'
TOOBIGORNONE = 'Either this image is too big or there is no image at all.  Yeah.'
REPORTERR = 'Error: Cannot find reply.'                      # Returns error when a reply (res) cannot be found
UPFAIL = 'Error: Upload failed.'                             # Returns error for failed upload (reason: unknown?)
NOREC = 'Error: Cannot find record.'                         # Returns error when record cannot be found
NOCAPTCHA = 'Error: No verification code on record - it probably timed out.'    # Returns error when there's no captcha in the database for this IP/key
BADCAPTCHA = 'Error: Wrong verification code entered.'       # Returns error when the captcha is wrong
BADFORMAT = 'Error: File format not supported.'              # Returns error when the file is not in a supported format.
STRREF = 'Error: String refused.'                            # Returns error when a string is refused
UNJUST = 'Error: Unjust POST.'                               # Returns error on an unjust POST - prevents floodbots or ways not using POST method?
NOPIC = 'Error: No file selected. Did you forget to click "Reply"?'    # Returns error for no file selected and override unchecked
NOTEXT = 'Error: No comment entered.'                        # Returns error for no text entered in to subject/comment
TOOLONG = 'Error: Too many characters in text field.'        # Returns error for too many characters in a given field
NOTALLOWED = 'Error: Posting not allowed.'                   # Returns error for non-allowed post types
UNUSUAL = 'Error: Abnormal reply.'                           # Returns error for abnormal reply? (this is a mystery!)
BADHOST = 'Host is banned.'                                  # Returns error for banned host ($badip string)
BADHOSTPROXY = 'Error: Proxy is banned for being open.'      # Returns error for banned proxy ($badip string)
RENZOKU = 'Error: Flood detected, post discarded.'           # Returns error for $sec/post spam filter
RENZOKU2 = 'Error: Flood detected, file discarded.'          # Returns error for $sec/upload spam filter
RENZOKU3 = 'Error: Flood detected.'                          # Returns error for $sec/similar posts spam filter.
PROXY = 'Error: Open proxy detected.'                        # Returns error for proxy detection.
DUPE = 'Error: This file has already been posted <a href="%s">here in this thread</a>.'    # Returns error when an md5 checksum already exists.
DUPENAME = 'Error: A file with the same name already exists.'    # Returns error when an filename already exists.
NOTHREADERR = 'Error: Thread does not exist.'                # Returns error when a non-existant thread is accessed
BADDELPASS = 'Error: Incorrect password for deletion.'       # Returns error for wrong password (when user tries to delete file)
WRONGPASS = 'Error: Management password incorrect, or login timed out.'    # Returns error for wrong password (when trying to access Manager modes)
VIRUS = 'Error: Possible virus-infected file.'               # Returns error for malformed files suspected of being virus-infected.
NOTWRITE = 'Error: Could not write to directory.'            # Returns error when the script cannot write to the directory, the chmod (777) is wrong
SPAM = 'Spammers are not welcome here.'                      # Returns error when detecting spam

SQLCONF = 'SQL connection failure'                           # Database connection failure
SQLFAIL = 'Critical SQL problem!'                            # SQL Failure

REDIR = 'If the redirect didn\'t work, please choose one of the following mirrors:'    # Redir message for html in REDIR_DIR

BADHOST_ADMIN = 'Error: Manager Functions not Available Due to Banned Host.'    # Error message that appears when a banned IP tries to access moderator features
BAN_WHY = 'You or another user of this IP or IP range was banned.'    # Subheader for banned IP page
BAN_MISSING_REASON = 'No reason given. You should try refreshing this page, or you may need to speak with staff as this may be in error.'    # Appears if no Reason for the Ban is on Record
BAN_APPEAL_HEADER = 'How to Appeal'                          # Header for appealing instructions
# Instructions on Appealing. Feel free to customize.
BAN_APPEAL = 'To appeal your ban, please visit <a href="http://desuchan.net/sugg/">the suggestions board</a>.<br /> Abusing this may result in permanent banishment from Desuchan\'s services.' 
BAN_NO_APPEAL = 'You may not appeal this ban.'               # Appears on banned IP page if no appealing is allowed. (NOT USED. KEPT IN CASE OF A REQUEST.)
BANEXPIRE = 'Length of Ban, in Seconds<br />(Use 0 if permanent.)'    # Option in Ban Panel for adjusting ban length
TOTALBAN = 'Ban from Browsing?'                              # Option in Ban Panel for setting a ban prohibiting browsing content.
BAN_REASON = 'Reason'                                        # Header for ban comment on the banned IP page
CURRENT_IP = 'Your current IP is'                            # Informs the user of the affected IP on the banned IP page.
BAN_WILL_EXPIRE = 'This ban is set to expire'                # Appears before expiration date on banned IP page
BAN_WILL_NOT_EXPIRE = 'This ban is not set to expire.'       # Appears on banned IP page if IP is permanently banned (or ban info is missing)
COMMENT_A_MUST = 'Error: A Reason/Comment is Required'       # Returned if no reason/comment is entered when banning an IP 
BANEXPIRE_EDIT = 'Time Ban Ends'                             # Precedes the expiration date for the ban on the banned IP page
UPDATE = 'Update'                                            # Name of submit button in the editor windows
BANEDIT = 'Edit'                                             # Link name for the ban editor window
ADMINOVERRIDE = 'To override, please input nuke password.'   # Precedes the field for typing in the admin's nuke password when a moderator is banned
DATEPROBLEM = 'There is a problem with the date entered.'    # Appears if a bad date is entered on the ban editor page
SETNOEXPIRE = 'No expiration'                                # Appears in the ban panel for all permanent bans
HTACCESSCANTREMOVE = 'Error: Cannot Remove .htaccess Entry.' # Returned if an error occurs accessing .htaccess to remove a ban entry.
HTACCESSPROBLEM = "Error: Ban Processed, but Error Accessing .htaccess."    # Returned if an error occurs when accessing .htaccess to add a ban
THREADLOCKEDERROR = "Error: Thread Locked."                  # Returned if a user attempts to add a post or edit an existing post in a locked thread.
ALREADYSTICKIED = "Error: Already Stickied."                 # Returned if a moderator attempts to sticky a thread that was already stickied
NOTATHREAD = "Error: What Was Specified is Not a Thread."    # Returned if a moderator tries to sticky or lock a single post
NOTSTICKIED = "Error: Does not Exist or is Already Unstickied"    # Returned if a moderator tries to lock a thread that was deleted or was already stickied
ALREADYLOCKED = "Error: Already Locked."                     # Returned if a moderator tries to lock a thread that was already locked
NOTLOCKED = "Error: Already Unlocked or Does Not Exist."     # Returned if a moderator tries to unlock a thread that was deleted or already locked
BADEDITPASS = "Error: Incorrect password for editing."       # Returned if a user inputs the wrong password for editing
NOPASS = "Error: No password was specified for this post.<br />It cannot be edited."    # Returned if a bad password was given by a user when attempting to edit a post
LASTEDITED = "Last edited"                                   # Precedes the editing date on the thread page if a post was edited
BYMOD = "by moderator"                                       # Tagged to previous if the editing was done by a moderator
STICKIED = "Sticky"                                          # Title for sticky image
LOCKED = "Locked"                                            # Title for lock image
STICKIEDALT = "(sticky)"                                     # Alternative text for sticky image
LOCKEDALT = "(locked)"                                       # Alternative text for locked image
STICKYOPTION = "Sticky"                                      # Option for stickying a thread in the moderator post panel
LOCKOPTION = "Lock"                                          # Option for locking a thread in the moderator post panel
UNSTICKYOPTION = "Unsticky"                                  # Option for unstickying a thread in the moderator post panel
UNLOCKOPTION = "Unlock"                                      # Option for unlocking a thread in the moderator post panel
LOCKEDANNOUNCE = "This thread is locked. You may not reply to this thread."    # An announcement that appears in place of the post form in a locked thread
VIEW = "View"                                                # Link to viewing the thread page if the thread is locked (and does not allow replies).
# Prompt for management password when editing a moderator post or moderator-edited post.
PROMPTPASSWORDADMIN = "This post was created and/or edited by a moderator."
# Prompt for editing/deletion password for usual circumstances.
PROMPTPASSWORD = "Please enter the deletion/editing password. "
NEWFILE = "New File"                                         # Prompt for replacement file in post-editing window
STRINGFIELDMISSING = "Please input string to ban."
MODDELETEONLY = "This was posted by a moderator or admin and cannot be deleted this way."
POSTNOTFOUND = "Post %d not found on %s."
INUSUFFICENTPRIVLEDGES = 'Insufficient privileges'

#
# Oekaki
#

OEKPAINT = 'Painter: '                                       # Describes the oekaki painter to use
OEKSOURCE = 'Source: '                                       # Describes the source selector
OEKNEW = 'New image'                                         # Describes the new image option
OEKMODIFY = 'Modify No.%d'                                   # Describes an option to modify an image
OEKX = 'Width: '                                             # Describes x dimension for oekaki
OEKY = 'Height: '                                            # Describes y dimension for oekaki
OEKSUBMIT = 'Paint!'                                         # Oekaki button used for submit
OEKIMGREPLY = 'Reply'

OEKIMGREPLY = 'Reply'
OEKREPEXPL = 'Picture will be posted as a reply to thread <a href="%s">%s</a>.'

OEKTOOBIG = 'The requested dimensions are too large.'
OEKTOOSMALL = 'The requested dimensions are too small.'
OEKUNKNOWN = 'Unknown oekaki painter requested.'
HAXORING = 'Stop hax0ring the Gibson!'

OEKPAINTERS = [
        {"painter": "shi_norm", "name": "Shi Normal"},
        {"painter": "shi_pro", "name": "Shi Pro"},
        {"painter": "shi_norm_selfy", "name": "Shi Normal+Selfy"},
        {"painter": "shi_pro_selfy", "name": "Shi Pro+Selfy"},
]
