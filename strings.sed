#!/bin/sed -rf
# usage: ./strings.sed strings_en.pl > strings.py

s/use constant S_([A-Z0-9_]+) ?=> ?(['"].*['"]|[0-9\*]+);(\s*#?.*)$/\1 = \2\3/;
s/use constant S_([A-Z0-9_]+) ?=> ?\(?(['"].*['"])\);(\s*#?.*)$/\1 = [\2]\3/;
s/use constant S_([A-Z0-9_]+) ?=> ?(['"].*['"])\. *$/\1 = \2 + \\/;

# multiline strings
s/^\s+(['"].*['"])\.\s*$/    \1 + \\/;
s/^\s+(['"].*['"]);(\s*#?.*)$/    \1\2/;

# S_OEKPAINTERS
s/use constant S_([A-Z0-9_]+) ?=> ?\[\s*$/\1 = [/;
/^\s*\{/ {
    s/\{ /{/;
    s/ \}/}/;
    s/=>/\: /g;
}
s/^\];\s*$/]/;

s/^1;$//;

# try to normalize whitespace
s/\t/        /g;

s/^(.{60})\s*#/\1 #/;
s/^(.{60}.*['"])\s*#/\1    #/;
