# Board Configuration

config = {}
# Board-specific Security
config['NUKE_PASS'] = "CHANGEME" # Board nuking/SQL password. Change this!

# Page look
config['TITLE'] = 'Wakarimasen image board'	# Name of this image board
config['SQL_TABLE'] = 'comment'	# IMPORTANT! Name of SQL comment table. !Must be unique for each board!
config['SHOWTITLETXT'] = 1			# Show TITLE at top (1: yes  0: no)
config['SHOWTITLEIMG'] = 0			# Show image at top (0: no, 1: single, 2: rotating)
config['TITLEIMG'] = 'title.jpg'		# Title image (point to a script file if rotating)
config['FAVICON'] = 'wakaba.ico'		# Favicon.ico file
config['IMAGES_PER_PAGE'] = 10			# Images per page
config['REPLIES_PER_THREAD'] = 5		# Replies shown
config['IMAGE_REPLIES_PER_THREAD'] = 0		# Number of image replies per thread to show, set to 0 for no limit.
config['S_ANONAME'] = 'Anonymous'		# Defines what to print if there is no text entered in the name field
config['S_ANOTEXT'] = ''			# Defines what to print if there is no text entered in the comment field
config['S_ANOTITLE'] = ''			# Defines what to print if there is no text entered into subject field
config['SILLY_ANONYMOUS'] = ''			# Make up silly names for anonymous people (0 or '': don't display, any combination of 'day' or 'board': make names change for each day or board, 'static': static names)
config['DEFAULT_STYLE'] = 'Futaba'		# Title of the default style for the board.

# Limitations
config['MAX_KB'] = 10240			# Maximum upload size in KB
config['MAX_W'] = 200				# Images exceeding this width will be thumbnailed
config['MAX_H'] = 200				# Images exceeding this height will be thumbnailed
config['MAX_RES'] = 500				# Maximum topic bumps
config['MAX_POSTS'] = 0				# Maximum number of posts (set to 0 to disable)
config['MAX_THREADS'] = 0			# Maximum number of threads (set to 0 to disable)
config['MAX_AGE'] = 0				# Maximum age of a thread in hours (set to 0 to disable)
config['MAX_MEGABYTES'] = 0			# Maximum size to use for all images in megabytes (set to 0 to disable)
config['MAX_FIELD_LENGTH'] = 100		# Maximum number of characters in subject, name, and email
config['MAX_COMMENT_LENGTH'] = 8192		# Maximum number of characters in a comment
config['MAX_LINES_SHOWN'] = 15			# Max lines shown per post (0 = no limit)
config['MAX_IMAGE_WIDTH'] = 16384		# Maximum width of image before rejecting
config['MAX_IMAGE_HEIGHT'] = 16384		# Maximum height of image before rejecting
config['MAX_IMAGE_PIXELS'] = 50000000		# Maximum width*height of image before rejecting
config['DUPLICATE_DETECTION'] = 'thread'	# How are duplicate files forbidden? (board: no duplicates on board, thread: no duplicate files in a single thread, <blank>: no duplicate detection)

# Captcha
config['ENABLE_CAPTCHA'] = 0
config['SQL_CAPTCHA_TABLE'] = 'captcha'		# Use a different captcha table for each board, if you have more than one!
config['CAPTCHA_LIFETIME'] = 1440		# Captcha lifetime in seconds
config['CAPTCHA_SCRIPT'] = 'captcha.pl'
config['CAPTCHA_HEIGHT'] = 18
config['CAPTCHA_SCRIBBLE'] = 0.2
config['CAPTCHA_SCALING'] = 0.15
config['CAPTCHA_ROTATION'] = 0.3
config['CAPTCHA_SPACING'] = 2.5

# Load Balancing
config['ENABLE_LOAD'] = 0			# Enable the distribution of image files across multiple hosts (0: no, 1: yes). May not work on a windows host. Do not enable if using STUPID_THUMBNAILING.
config['LOAD_SENDER_SCRIPT'] = './sender.pl'
config['LOAD_LOCAL'] = 120			# Gigabytes of available bandwidth relative to other hosts (please read documentation)
config['LOAD_HOSTS'] = [['http://somesite/loader.pl', 'password', 100]]
config['LOAD_KBRATE'] = 25			# minimum send rate that will be accepted without timing out

# Proxy
config['ENABLE_PROXY_CHECK'] = 1		# Enable proxy checking (0: no, 1:yes). Please read the documentation first!
config['PROXY_COMMAND'] = '/usr/bin/proxycheck -s -d achaea.com:23 -c chat::"Multi-User License: 100-0000-000" -aaaa'	# Only uncomment if you know what you're doing... 
# Proxy expirations are controlled via config.pl.

# Tweaks
config['CONVERT_COMMAND'] = ''			# ImageMagick command, may be globalized.
config['THUMBNAIL_SMALL'] = 1			# Thumbnail small images (1: yes, 0: no)
config['THUMBNAIL_QUALITY'] = 60		# Thumbnail JPEG quality
config['DELETED_THUMBNAIL'] = ''		# Thumbnail to show for deleted images (leave empty to show text message)
config['DELETED_IMAGE'] = ''			# Image to link for deleted images (only used together with DELETED_THUMBNAIL)
config['ALLOW_TEXTONLY'] = 0			# Allow textonly posts (1: yes, 0: no)
config['ALLOW_IMAGES'] = 1			# Allow image posting (1: yes, 0: no)
config['ALLOW_TEXT_REPLIES'] = 1		# Allow replies (1: yes, 0: no)
config['ALLOW_IMAGE_REPLIES'] = 1		# Allow replies with images (1: yes, 0: no)
config['ALLOW_UNKNOWN'] = 0			# Allow unknown filetypes (1: yes, 0: no)
config['MUNGE_UNKNOWN'] = '.unknown'		# Munge unknown file type extensions with this. If you remove this, make sure your web server is locked down properly.
config['FORBIDDEN_EXTENSIONS'] = ['php','php3','php4','phtml','shtml','cgi','pl','pm','py','r','exe','dll','scr','pif','asp','cfm','jsp','vbs'] # file extensions which are forbidden
config['RENZOKU'] = 5				# Seconds between posts (floodcheck)
config['RENZOKU2'] = 10				# Seconds between image posts (floodcheck)
config['RENZOKU3'] = 900			# Seconds between identical posts (floodcheck)
config['NOSAGE_WINDOW'] = 1200			# Seconds that you can post to your own thread without increasing the sage count
config['USE_SECURE_ADMIN'] = 0			# Use HTTPS for the admin panel.
config['CHARSET'] = 'utf-8'			# Character set to use, typically 'utf-8' or 'shift_jis'. Disable charset handling by setting to ''. Remember to set Apache to use the same character set for .html files! (AddCharset shift_jis html)
config['METAKEYWORDS'] = 'desuchan,rozen maiden,loli,anime,mangna,touhou,art,literature,roleplay,traps,gothloli,dollfaggotry'
config['CONVERT_CHARSETS'] = 1			# Do character set conversions internally
config['TRIM_METHOD'] = 1			# Which threads to trim (0: oldest - like futaba 1: least active - furthest back)
config['ARCHIVE_MODE'] = 0			# Old images and posts are moved into an archive dir instead of deleted (0: no 1: yes). It is HIGHLY RECOMMENDED you use TRIM_METHOD} = 1 with this, or you may end up with unreferenced pictures in your archive
config['DATE_STYLE'] = 'futaba'			# Date style ('futaba', '2ch', 'localtime', 'tiny')
config['DISPLAY_ID'] = ''			# How to display user IDs (0 or '': don't display,
						#  'day' and 'board' in any combination: make IDs change for each day or board,
						#  'mask': display masked IP address (similar IPs look similar, but are still encrypted)
						#  'sage': don't display ID when user sages, 'link': don't display ID when the user fills out the link field,
						#  'ip': display user's IP, 'host': display user's host)
config['DISPLAY_ID'] = 0			# Display user IDs (0: never, 1: if no email, 2:always)
config['EMAIL_ID'] = 'Heaven'			# ID string to use when DISPLAY_ID is 1 and the user uses an email.
config['TRIPKEY'] = '!'				# this character is displayed before tripcodes
config['ENABLE_WAKABAMARK'] = 1			# Enable WakabaMark formatting. (0: no, 1: yes)
config['APPROX_LINE_LENGTH'] = 150		# Approximate line length used by reply abbreviation code to guess at the length of a reply.
config['STUPID_THUMBNAILING'] = 0		# Bypass thumbnailing code and just use HTML to resize the image. STUPID, wastes bandwidth. (1: enable, 0: disable)
config['COOKIE_PATH'] = 'root'			# Path argument for cookies ('root': cookies apply to all boards on the site, 'current': cookies apply only to this board, 'parent': cookies apply to all boards in the parent directory)
config['FORCED_ANON'] = 0			# Force anonymous posting (0: no, 1: yes)
config['USE_XHTML'] = 0				# Send pages as application/xhtml+xml to browsers that support this (0:no, 1:yes)
config['SPAM_TRAP'] = 1				# Enable the spam trap (empty, hidden form fields that spam bots usually fill out) (0:no, 1:yes)
config['STYLE_COOKIE'] = 'wakastyle'		# Name of the board's style cookie. Generally a good idea to keep the same across all boards.

# Internal paths and files - might as well leave this alone.
config['IMG_DIR'] = 'src/'			# Image directory (needs to be writeable by the script)
config['THUMB_DIR'] = 'thumb/'			# Thumbnail directory (needs to be writeable by the script)
config['RES_DIR'] = 'res/'			# Reply cache directory (needs to be writeable by the script)
config['ARCHIVE_DIR'] = 'arch/'			# Root of archive directories (all need to be writeable by the script)
config['BACKUP_DIR'] = "backup/"		# Subdirectory in ARCHIVE_DIR for all backup images and thumbnails.
config['REDIR_DIR'] = 'redir/'			# Redir directory, used for redirecting clients when load balancing
config['HTML_SELF'] = 'wakaba.html'		# Name of main html file
config['JS_FILE'] = '/wakaba3.js'		# Location of the js file
config['CSS_DIR'] = '../include/common/css/'
						# Hints: * Set all boards to use the same file for easy updating.
						#        * Set up two files, one being the official list from
						#          http://wakaba.c3.cx/antispam/spam.txt, and one your own additions.
# Oekaki Stuff
config['ENABLE_OEKAKI'] = 0			# Enable Oekaki?
config['TMP_DIR'] = 'tmp/'			# Temp file directory (needs to be writeable by the script)

config['OEKAKI_ENABLE_MODIFY'] = 1		# Enable image modification

config['OEKAKI_DEFAULT_X'] = 300		# Default X dimension for oekaki drawings
config['OEKAKI_DEFAULT_Y'] = 300		# Default Y dimension for oekaki drawings
config['OEKAKI_MAX_X'] = 800			# Max X dimension allowed for oekaki drawings
config['OEKAKI_MAX_Y'] = 800			# Max Y dimension allowed for oekaki drawings
config['OEKAKI_MIN_X'] = 100			# Min X dimension allowed for oekaki drawings
config['OEKAKI_MIN_Y'] = 100			# Min Y dimension allowed for oekaki drawings

config['OEKAKI_DEFAULT_PAINTER'] = "shi_norm"	# Default painter selection

# Icons for filetypes - file extensions specified here will not be renamed, and will get icons
# (except for the built-in image formats). These example icons can be found in the extras/ directory.
config['FILETYPES'] = {
    # Audio files
#	mp3: '/include/icons/audio-mp3.png',
#	ogg: '/include/icons/audio-ogg.png',
#	aac: '/include/icons/audio-aac.png',
#	m4a: '/include/icons/audio-aac.png',
#	mpc: '/include/icons/audio-mpc.png',
#	mpp: '/include/icons/audio-mpp.png',
#	mod: '/include/icons/audio-mod.png',
#	it: '/include/icons/audio-it.png',
#	xm: '/include/icons/audio-xm.png',
#	fla: '/include/icons/audio-flac.png',
#	flac: '/include/icons/audio-flac.png',
#	sid: '/include/icons/audio-sid.png',
#	mo3: '/include/icons/audio-mo3.png',
#	spc: '/include/icons/audio-spc.png',
#	nsf: '/include/icons/audio-nsf.png',
   # Video files
#	avi: '/include/icons/video-avi.png',
#	ogm: '/include/icons/video-ogm.png',
#	mkv: '/include/icons/video-mkv.png',
   # Archive files
#	zip: '/include/icons/archive-zip.png',
#	rar: '/include/icons/archive-rar.png',
#	lzh: '/include/icons/archive-lzh.png',
#	lha: '/include/icons/archive-lzh.png',
#	gz: '/include/icons/archive-gz.png',
#	bz2: '/include/icons/archive-bz2.png',
#	'7z': '/include/icons/archive-7z.png',
   # Other files
#	swf: '/include/icons/flash.png',
#	torrent: '/include/icons/torrent.png',
   # To stop Wakaba from renaming image files, put their names in here like this:
#	gif: '.',
#	jpg: '.',
#	png: '.',
}

