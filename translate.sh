#!/bin/sh
# usage: sh translate.sh /path/to/wakaba

./config.sed $1/config.pl > config.py
./config_defaults.sed $1/config_defaults.pl > config_defaults.py
