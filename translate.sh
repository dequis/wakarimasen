#!/bin/sh
# usage: sh translate.sh /path/to/wakaba

echo "This script will replace config.py, config_defaults.py and strings_en.py"
if [ ! -e $1/config.pl ]; then
    echo "Usage: $0 /path/to/wakaba/"
    exit 1
fi

./config.sed $1/config.pl > config.py
./config_defaults.sed $1/config_defaults.pl > config_defaults.py
./strings.sed $1/strings_en.pl > strings_en.py
./board_config.sed $!/board_config.pl > board_config.py
