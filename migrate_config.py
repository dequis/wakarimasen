'''
Script usage:
    python migrate_config.py (global|board) <input.py>

Examples:

    python migrate_config.py global config.py

...will read the config.py file from the current directory and output
the translated ini file to stdout

    python migrate_config.py board desu/board_config.py

...will do the same for a board config.

This script depends on the default ini configs to do the name mappings,
the "util" and "config_defaults" wakarimasen modules, and
base_board/board_config.py.
'''

import os
import sys
from ConfigParser import ConfigParser
import util

def run_mapping(cp, config_keys, manual_map):
    mapping = []
    unmapped = []

    for section in cp.sections():
        for option in cp.options(section):
            if (section, option) in manual_map:
                manual_name = manual_map[(section, option)]
                mapping.append((section, option, manual_name))
                continue

            if section == 'hcaptcha':
                old_name = "HCAPTCHA_" + option.upper().replace("-", "_")
            elif section == 'sql-tables':
                old_name = 'SQL_%s_TABLE' % option.upper()
            else:
                old_name = option.upper().replace("-", "_")

            if old_name in config_keys:
                mapping.append((section, option, old_name))
            else:
                unmapped.append((section, option))
    return (mapping, unmapped)


def print_mapping(mapping):
    for k,v in sorted(mapping.items(), key=lambda x:x[1]):
        print k, "\t", v


def map_global_config():
    cp = ConfigParser()
    cp.read("config.defaults.ini")
    config_keys = dir(__import__('config_defaults'))

    manual_map = {
        ('hcaptcha', 'enable'): 'HCAPTCHA',
        ('rss', 'enable'): 'ENABLE_RSS',
        ('wakarimasen', 'admin-pass'): 'ADMIN_PASS',
        ('wakarimasen', 'secret'): 'SECRET',
        ('wakarimasen', 'sql-engine'): 'SQL_ENGINE',
    }

    return run_mapping(cp, config_keys, manual_map)


def map_board_config():
    cp = ConfigParser()
    cp.read("config.boards.defaults.ini")

    module = util.import2('board_config', "base_board")
    config_keys = module.config.keys()

    manual_map_pre = {
        'max-upload-kb': 'MAX_KB',
        'max-width': 'MAX_W',
        'max-height': 'MAX_H',
        'max-topic-bumps': 'MAX_RES',
        'no-name': 'S_ANONAME',
        'no-text': 'S_ANOTEXT',
        'no-title': 'S_ANOTITLE',
        'floodcheck-posts': 'RENZOKU',
        'floodcheck-image-posts': 'RENZOKU2',
        'floodcheck-identical-posts': 'RENZOKU3',
    }

    manual_map = dict([(('board-defaults', k), v)
        for (k, v) in manual_map_pre.items()])

    return run_mapping(cp, config_keys, manual_map)


def write_new_config(mode, module_name):
    path_name = "."
    if module_name.count("."):
        module_name = module_name.rsplit(".", 1)[0]

    if module_name.count("/"):
        path_name = os.path.dirname(module_name)
        module_name = os.path.basename(module_name)

    mapped, unmapped = map_global_config() if (mode == 'global') \
        else map_board_config()

    module = util.import2(module_name, path_name)

    if mode == 'global':
        keygetter = lambda key: getattr(module, key, None)
    else:
        keygetter = lambda key: module.config.get(key, None)

    cp = ConfigParser()

    for section, option, key in mapped:
        got = keygetter(key)
        if not got:
            continue
        if not cp.has_section(section):
            cp.add_section(section)
        cp.set(section, option, got)

    if mode == 'global':
        icons = keygetter('ICONS')
        if icons:
            if not cp.has_section('icons'):
                cp.add_section('icons')

            icon_paths = icons.values()

            base_url = os.path.commonprefix(icon_paths)
            cp.set('icons', 'x-base-url', base_url)

            for ext, url in icons.iteritems():
                cp.set('icons', ext, url[len(base_url):])

    cp.write(sys.stdout)


def main():
    if len(sys.argv) < 3:
        print "Usage: migrate_config.py (global|board) <input.py>"
        return

    mode = sys.argv[1]
    module_name = sys.argv[2]

    if mode not in ('global', 'board'):
        print "Mode must be either 'global' or 'board'"
        return

    write_new_config(mode, module_name)


if __name__ == '__main__':
    main()
