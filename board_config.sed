#!/bin/sed -rnf
# usage: ./config.sed config.pl > config.py

s/^my %config;$/config = {}/
s/\$config\{([A-Z0-9_]+)\} ?= ?(.+);(\s*#?.*)$/config['\1'] = \2\3/;
s/\$config\{([A-Z0-9_]+)\} ?= ?\{$/config['\1'] = {/;

s/(config\['[A-Z0-9_]+'\] = )\((.+)\)/\1[\2]/;

s/\};/}/;
s/ => /: /;
s/^\\%config;$//;
s/^#? ?(use|no) encoding.*$//;


# multiline hack
1h;1!H;
$ {
    g;
    s/\n\n\n+/\n/g;
    p
}
