'''Operations that affect multiple boards or the entire site,
e.g., transferring and merging threads.'''

import time
import re
import os
import sys
import traceback
from datetime import datetime
from calendar import timegm
from urllib import urlencode
from subprocess import Popen, PIPE

import config
import strings
import board
import staff
import model
import util
import str_format
import misc
from template import Template
from util import WakaError, local

from sqlalchemy.sql import case, or_, and_, select, func, null

# Staff Action Logging

# Dictionary of what action keywords mean. It's like a real dictionary!
ACTION_TRANSLATION \
    = {'ipban' : {'name' : 'IP Ban', 'content' : 'Affected IP Address'},
       'ipban_edit'
            : {'name' : 'IP Ban Revision', 'content' : 'Revised Data'},
       'ipban_remove'
            : {'name' : 'IP Ban Removal',
                'content' : 'Unbanned IP Address'},
       'wordban' : {'name' : 'Word Ban', 'content' : 'Banned Phrase'},
       'wordban_edit' : {'name' : 'Word Ban Revision',
                         'content' : 'Revised Data'},
       'wordban_remove' : {'name' : 'Word Ban Removal',
                           'content' : 'Unbanned Phrase'},
       'whitelist' : {'name' : 'IP Whitelist',
                      'content' : 'Whitelisted IP Address'},
       'whitelist_edit' : {'name' : 'IP Whitelist Revision',
                           'content' : 'Revised Data'},
       'whitelist_remove' : {'name' : 'IP Whitelist Removal',
                                      'content' : 'Removed IP Address'},
       'trust' : {'name' : 'Captcha Exemption',
                  'content' : 'Exempted Tripcode'},
       'trust_edit' : {'name' : 'Revised Captcha Exemption',
                       'content' : 'Revised Data'},
       'trust_remove' : {'name' : 'Removed Captcha Exemption',
                         'content' : 'Removed Tripcode'},
       'admin_post' : {'name' : 'Manager Post', 'content' : 'Post'},
       'admin_edit' : {'name' : 'Administrative Edit',
                       'content' : 'Post'},
       'admin_delete' : {'name' : 'Administrative Deletion',
                         'content' : 'Post'},
       'thread_sticky' : {'name' : 'Thread Sticky',
                          'content' : 'Thread Parent'},
       'thread_unsticky' : {'name' : 'Thread Unsticky',
                            'content': 'Thread Parent'},
       'thread_lock' : {'name' : 'Thread Lock',
                        'content' : 'Thread Parent'},
       'thread_unlock' : {'name' : 'Thread Unlock',
                          'content' : 'Thread Parent'},
       'report_resolve' : {'name' : 'Report Resolution',
                           'content' : 'Resolved Post'},
       'backup_restore' : {'name' : 'Restoration From Trash Bin',
                           'content' : 'Restored Post'},
       'backup_remove' : {'name' : 'Deletion From Trash Bin',
                          'content' : 'Deleted Post'},
       'thread_move' : {'name' : 'Thread Move',
                        'content' : 'Source and Destination'},
       'script_ban_forgive' : {'name' : 'Script Access Restoration',
                               'content' : 'IP Address'}}

def get_action_name(action_to_view, debug=0):
    try:
        name = ACTION_TRANSLATION[action_to_view]['name']
        content = ACTION_TRANSLATION[action_to_view]['content'] 
    except KeyError:
        raise WakaError('Missing action key or unknown action key.')

    if not debug:
        return name
    elif debug == 1:
        return (name, content)
    else:
        return content

# Common Site Table!

def get_all_boards(check_board_name=''):
    '''Get all the board names. All of them.'''

    session = model.Session()
    table = model.common
    sql = select([table.c.board]).order_by(table.c.board)

    query = session.execute(sql)

    board_present = False
    boards = []
    for row in query:
        boards.append({'board_entry' : row['board']})
        if row['board'] == check_board_name:
            board_present = True

    if check_board_name and not board_present:
        add_board_to_index(check_board_name)
        boards.append({'board_entry' : check_board_name})

    return boards

def add_board_to_index(board_name):
    session = model.Session()
    table = model.common
    sql = table.insert().values(board=board_name, type='')

    session.execute(sql)

def remove_board_from_index(board_name):
    session = model.Session()
    table = model.common
    sql = table.delete().where(table.c.board == board_name)

    session.execute(sql)

# Global rebuilding

def global_cache_rebuild():
    boards = [x['board_entry'] for x in get_all_boards()]
    for board_str in boards:
        try:
            board_obj = board.Board(board_str)
            local.environ['waka.board'] = board_obj
            board_obj.rebuild_cache()
        except:
            sys.stderr.write('Error in global cache rebuild in '\
                             + board_str + '\n')
            traceback.print_exc(file=sys.stderr)

def global_cache_rebuild_proxy(admin):
    user = staff.check_password(admin)
    if user.account != staff.ADMIN:
        raise WakaError(strings.INUSUFFICENTPRIVLEDGES)
    Popen(['python', 'wakarimasen.py', 'rebuild_global_cache',
           local.environ['DOCUMENT_ROOT'],
           local.environ['SCRIPT_NAME'],
           local.environ['SERVER_NAME']])
    referer = local.environ['HTTP_REFERER']
    return util.make_http_forward(referer, config.ALTERNATE_REDIRECT)

# Bans and Whitelists

def add_admin_entry(admin, option, comment, ip='', mask='255.255.255.255',
                    sval1='', total='', expiration=0,
                    caller=''):
    staff.check_password(admin)

    session = model.Session()
    table = model.admin

    ival1 = ival2 = 0

    if not comment:
        raise WakaError(strings.COMMENT_A_MUST)
    if option in ('ipban', 'whitelist'):
        if not ip:
            raise WakaError('IP address required.')
        if not mask:
            mask = '255.255.255.255'
        # Convert to decimal.
        (ival1, ival2) = (misc.dot_to_dec(ip), misc.dot_to_dec(mask))
        sql = table.select().where(table.c.type == option)
        query = session.execute(sql)

        for row in query:
            if row.ival1 & row.ival2 == ival1 & ival2:
                raise WakaError('IP address and mask match ban #%d.' % \
                                (row.num))
    else:
        if not sval1:
            raise WakaError(STRINGFIELDMISSING)
        sql = table.select().where(and_(table.c.sval1 == sval1,
                                        table.c.type == option))
        row = session.execute(sql).fetchone()

        if row:
            raise WakaError('Duplicate String in ban #%d.' % (row.num))

    comment = str_format.clean_string(\
        str_format.decode_string(comment, config.CHARSET))
    expiration = int(expiration) if expiration else 0
    if expiration:
        expiration = expiration + time.time()

    sql = table.insert().values(type=option, comment=comment, ival1=ival1,
                                ival2=ival2, sval1=sval1, total=total,
                                expiration=expiration)
    session.execute(sql)

    if total:
        add_htaccess_entry(ip)

    # TODO: Log this.

    board = local.environ['waka.board']
    forward_url = '?'.join((misc.get_secure_script_name(),
                            urlencode({'task' : 'bans',
                                       'board': board.name})))

    if caller == 'window':
        return Template('edit_successful')
    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

def remove_admin_entry(admin, num, override_log=False, no_redirect=False):
    staff.check_password(admin)

    session = model.Session()
    table = model.admin
    sql = table.select().where(table.c.num == num)
    row = session.execute(sql).fetchone()

    if row:
        if row['total']:
            ip = misc.dec_to_dot(row['ival1'])
            remove_htaccess_entry(ip)

        sql = table.delete().where(table.c.num == num)
        session.execute(sql)

    board = local.environ['waka.board']
    forward_url = '?'.join((misc.get_secure_script_name(),
                            urlencode({'task': 'bans',
                                       'board': board.name})))

    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

def remove_old_bans():
    session = model.Session()
    table = model.admin
    sql = select([table.c.ival1, table.c.total],
                 and_(table.c.expiration <= time.time(),
                      table.c.expiration != 0))
    query = session.execute(sql)

    for row in query:
        sql = table.delete().where(table.c.ival1 == row['ival1'])
        session.execute(sql)
        if row['total']:
            ip = misc.dec_to_dot(row['ival1'])
            remove_htaccess_entry(ip)

def remove_old_backups():
    session = model.Session()
    table = model.backup
    sql = table.select().where(table.c.timestampofarchival.op('+')\
                               (config.POST_BACKUP_EXPIRE) <= time.time())
    query = session.execute(sql)

    for row in query:
        board_obj = board.Board(row['board_name'])
        backup_path = os.path.join(board_obj.path,
                                   board_obj.options['ARCHIVE_DIR'],
                                   board_obj.options['BACKUP_DIR'], '')
        if row.image:
            # Delete backup image; then, mark post for deletion.
            filename = os.path.join(backup_path, os.path.basename(row.image))
            if os.path.exists(filename):
                os.unlink(filename)
        if row.thumbnail \
                and re.match(src_brd_obj.options['THUMB_DIR'], row.thumbnail):
            filename = os.path.join(backup_path,
                                    os.path.basename(row.thumbnail))
            if os.path.exists(filename):
                os.unlink(filename)
        session.delete(row)

def add_htaccess_entry(ip):
    with open(os.path.join(local.environ['DOCUMENT_ROOT'],
                           config.HTACCESS_PATH, '.htaccess'), 'a+') as f:
        ban_entries_found = False

        line = f.read()
        while line:
            if line.index('RewriteEngine On') != -1:
                ban_entries_found = True
                break
            line = f.read()

        if not ban_entries_found:
            f.write("\n"+'RewriteEngine On'+"\n")

        ip = ip.replace('.', r'\.')
        f.write("\n"+'# Ban added by Wakarimasen'+"\n")
        f.write('RewriteCond %{REMOTE_ADDR} ^'+ip+'$'+"\n")
        f.write('RewriteRule !(\+pl|\+js$|\+css$|\+png'\
                '|ban_images) '+local.environ['SCRIPT_NAME']+'?'\
                'task=banreport&board='+local.environ['waka.board'].name+"\n")

def remove_htaccess_entry(ip):
    ip = ip.replace('.', r'\.')

    with open(os.path.join(local.environ['DOCUMENT_ROOT'],
                           config.HTACCESS_PATH, '.htaccess'), 'w+') as f:
        line = f.read()
        while line:
            if not line.startswith('RewriteCond %{REMOTE_ADDR} ^%s$' % ip):
                f.write(line)
            else:
                # Do not write, and skip the next line.
                line = f.read()
            if line:
                line = f.read()

def ban_check(numip, name, subject, comment):
    '''This function raises an exception if the IP address is banned, or
    the post contains a forbidden (non-spam) string. It otherwise returns
    nothing.'''

    session = model.Session()
    table = model.admin

    # IP Banned?
    sql = table.select().where(and_(table.c.type == 'ipban',
                                    table.c.ival1.op('&')(table.c.ival2) \
                                        == table.c.ival2.op('&')(numip)))
    ip_row = session.execute(sql).fetchone()

    if ip_row:
        raise WakaError('Address %s banned. Reason: %s' % \
            (misc.dec_to_dot(numip), ip_row.comment))
    
    # To determine possible string bans, first normalize input to lowercase.
    comment = comment.lower()
    subject = subject.lower()
    name = name.lower()

    sql = select([table.c.sval1], table.c.type == 'wordban')
    query = session.execute(sql)

    for row in query:
        bad_string = row.sval1.lower()
        if comment.count(bad_string) or subject.count(bad_string) or \
                name.count(bad_string):
            raise WakaError(strings.STRREF)

def mark_resolved(admin, delete, posts):
    user = staff.check_password(admin)

    referer = local.environ['HTTP_REFERER']

    errors = []
    board_obj = None
    for (board_name, posts) in posts.iteritems():
        # Access rights enforcement.
        if user.account == staff.MODERATOR and board_name not in user.reign:
            errors.append({'error' : '/%s/*: Sorry, you lack access rights.'\
                                     % (board_name)})
            continue

        for post in posts:
            session = model.Session()
            table = model.report
            sql = table.select().where(and_(table.c.postnum == post,
                                            table.c.board == board_name))
            row = session.execute(sql).fetchone()
            if not row:
                errors.append({'error' : '%s,%d: Report not found.'\
                                         % (board_name, int(post))})
                continue

            sql = table.delete().where(and_(table.c.postnum == post,
                                            table.c.board == board_name))
            session.execute(sql)

        if delete:
            try:
                board_obj = board.Board(board_name)
            except WakaError:
                errors.append({'error' : '%s,*: Error loading board.'\
                                         % (board_name)})
                continue
            try:
                board_obj.delete_stuff(posts, '', False, False, admin=admin)
            except WakaError:
                errors.append({'error' : '%s,%d: Post already deleted.'\
                                         % (board_name, int(post))})

    # TODO: Staff logging

    # TODO: This probably should be refactored into StaffInterface.
    return Template('report_resolved', errors=errors,
                                       error_occurred=len(errors)>0,
                                       admin=admin,
                                       username=user.username,
                                       type=user.account,
                                       boards_select=user.reign,
                                       referer=referer)


def edit_admin_entry(admin, num, comment='', ival1=None,
                     ival2='255.255.255.255', sval1='', total=False,
                     sec=None, min=None, hour=None, day=None, month=None,
                     year=None, noexpire=False):

    staff.check_password(admin)

    session = model.Session()
    table = model.admin
    sql = table.select().where(table.c.num == num)
    row = session.execute(sql).fetchone()

    if not row:
        raise WakaError('Entry was not created or was removed.')

    if row.type == 'ipban':
        if not noexpire:
            try:
                expiration = datetime(int(year), int(month), int(day),
                                      int(hour), int(min), int(sec))
            except:
                raise WakaError('Invalid date.')
            expiration = timegm(expiration.utctimetuple())
        else:
            expiration = 0
        ival1 = misc.dot_to_dec(ival1)
        ival2 = misc.dot_to_dec(ival2)
    else:
        expiration = 0

    sql = table.update().where(table.c.num == num)\
               .values(comment=comment, ival1=ival1, ival2=ival2, sval1=sval1,
                       total=total, expiration=expiration)
    row = session.execute(sql)

    return Template('edit_successful')

def delete_by_ip(admin, ip, mask='255.255.255.255'):
    user = staff.check_password(admin)

    if user.account == staff.MODERATOR:
        reign = user.reign
    else:
        reign = [x['board_entry'] for x in get_all_boards()]

    for board_name in reign:
        board_obj = board.Board(board_name)
        # TODO: Fork this.
        board_obj.delete_by_ip(admin, ip, mask=mask)

def trim_reported_posts(date=0):
    mintime = 0
    if date:
        mintime = time.time() - date
    elif config.REPORT_RETENTION:
        mintime = time.time() - config.REPORT_RETENTION

    if mintime > 0:
        session = model.Session()
        table = model.report
        sql = table.delete().where(table.c.timestamp <= mintime)
        session.execute(sql)

def update_spam_file(admin, spam):
    user = staff.check_password(admin)
    if user.account == staff.MODERATOR:
        raise WakaError(strings.INUSUFFICENTPRIVLEDGES)

    # Dump all contents to first spam file.
    with open(config.SPAM_FILES[0], 'w') as f:
        f.write(spam)

    board = local.environ['waka.board']
    forward_url = '?'.join([misc.get_secure_script_name(),
                            urlencode({'task' : 'spam',
                                       'board': board.name})])
    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

# Thread Transfer

def move_thread(admin, parent, src_brd_obj, dest_brd_obj):
    if not parent:
        raise WakaError('No thread specified.')
    if src_brd_obj.name == dest_brd_obj.name:
        raise WakaError('Source and destination boards match.')

    # Check administrative access rights to both boards.
    src_brd_obj.check_access(admin)
    dest_brd_obj.check_access(admin)

    session = model.Session()
    src_table = src_brd_obj.table
    dest_table = dest_brd_obj.table

    sql = select([src_table.c.parent], src_table.c.num == parent)
    row = session.execute(sql).fetchone()

    if not row:
        raise WakaError('Thread not found.')
    elif row[0]:
        # Automatically correct if reply instead of thread was given.
        parent = row[0]

    sql = src_table.select().where(or_(src_table.c.num == parent,
                                       src_table.c.parent == parent))\
                            .order_by(src_table.c.num.asc())
    thread = [dict(x.items()) for x in session.execute(sql).fetchall()]

    # Indicate OP post number after insertion.
    new_parent = 0

    # List of images/thumbs to move around.
    image_move = []
    thumb_move = []

    lasthit = time.time()

    # DB operations
    for post in thread:
        # Grab post contents as dictionary of updates. Remove primary key.
        del post['num']

        post['lasthit'] = lasthit
        image = post['image']
        thumbnail = post['thumbnail']

        if image:
            image_move.append(image)
        if re.match(src_brd_obj.options['THUMB_DIR'], thumbnail):
            thumb_move.append(thumbnail)

        # Update post reference links.
        if new_parent:
            post['parent'] = new_parent

            new_comment = re.sub(r'a href="(.*?)'
                + os.path.join(src_brd_obj.path,
                               src_brd_obj.options['RES_DIR'],
                               '%d%s' % (int(parent)), config.PAGE_EXT),
                r'a href="\1' + os.path.join(\
                               dest_brd_obj.path,
                               dest_brd_obj.options['RES_DIR'],
                               '%d%s' % (int((new_parent), config.PAGE_EXT)),
                post['comment']))

            post['comment'] = new_comment

        sql = dest_table.insert().values(**post)
        result = session.execute(sql)

        if not new_parent:
            new_parent = result.last_inserted_ids()[0]

    # Nested associate for moving files in bulk.
    def rename_files(filename_list, dir_type):
        for filename in filename_list:
            src_filename = os.path.join(src_brd_obj.path, filename)
            dest_filename = re.sub('^/?' + src_brd_obj.options[dir_type],
                                   dest_brd_obj.options[dir_type],
                                   filename)
            dest_filename = os.path.join(dest_brd_obj.path, dest_filename)
            os.rename(src_filename, dest_filename)

    # File transfer operations.
    rename_files(image_move, 'IMG_DIR')
    rename_files(thumb_move, 'THUMB_DIR')

    dest_brd_obj.build_cache()
    dest_brd_obj.build_thread_cache(new_parent)

    src_brd_obj.delete_stuff([parent], '', False, False, caller='internal')

    forward_url = '?'.join((misc.get_secure_script_name(),
                            urlencode({'task' : 'mpanel',
                                       'board' : dest_brd_obj.name,
                                       'page' : 't' + str(new_parent)})))

    return util.make_http_forward(forward_url)
