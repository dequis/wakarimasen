#!/bin/sed -rnf 
# usage: ./config_defaults.sed config_defaults.pl > config_defaults.py

s/\(('[^']*')\)/[\1]/g;
s/\teval "use constant ([A-Z_]+) ?=> ?('.*'|[0-9\*]+|\[.*\])" unless.*$/\1 = \2/g;
s/^1;$//;
s/^BEGIN \{$//;
s/^\}$//;
s/^use strict;$//;
s/^\tuse constant S_.*$//g;
s/^\tdie S_.*$//g;
s/ENABLE_POST_BACKUPS/POST_BACKUP/g;

# multiline hack. remove consecutive newlines
1h;1!H;
${
    g;
    s/\n\n+/\n/g;
    s/$/\
BOARD_DIR = \'\'\
DEBUG = False\
SERVER_NAME = 'localhost'\
IDENTIFY_COMMAND = 'identify'\
FG_ANIM_COLOR = 'white'\
BG_ANIM_COLOR = '#660066'\
# add default values to config.py\
import util as _util\
_util.module_default('config', locals())/;
    p;
}

    
