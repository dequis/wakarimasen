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

# multiline hack. remove consecutive newlines
1h;1!H;
${
    g;
    s/\n\n+/\n/g;
    s/$/\
BOARD_DIR = \'\'\
\
# add default values to config.py\
import util as _util\
_util.module_default('config', locals())/;
    p;
}

    
