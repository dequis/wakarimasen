#!/bin/sed -rnf
# usage: ./config.sed config.pl > config.py

s/use constant ([A-Z_]+) ?=> ?(['"].*['"]|[0-9\*]+);(\s*#?.*)$/\1 = \2\3/g;
s/^1;$//;
s/^#? ?(use|no) encoding.*$//;
s/^##use constant CONVERT_COMMAND.*$//;
s/^# ffffffff.*$//;

# multiline hack
1h;1!H;
$ {
    g;
    s#SQL_DBI_SOURCE = 'DBI:([^:]+):database=([^:]+);host=([^']+)'.*\nSQL_USERNAME = '([^']+)'.*\nSQL_PASSWORD = '([^']+)'[^\n]*\n#SQL_ENGINE = '\1://\4:\5@\3/\2'\n#;
    s/\n\n+/\n/g;
    s|$|\
    BOARD_DIR = \'\'                         \# Root of board cache relative to document root.|
    p;
}
