'''Operations that affect multiple boards or the entire site,
e.g., transferring and merging threads.'''

import time
import re
import os
import sys
import traceback
from datetime import datetime
from calendar import timegm
from subprocess import Popen

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

from sqlalchemy.sql import or_, and_, select

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

# Board looping (andwich pattern).

def loop_thru_boards(board_obj_task, exc_msg, *args, **kwargs):
    try:
        boards = kwargs.pop('boards')
    except KeyError:
        boards = None

    if not boards:
        boards = [x['board_entry'] for x in get_all_boards()]

    for board_str in boards:
        try:
            board_obj = board.Board(board_str)
            local.environ['waka.board'] = board_obj
            getattr(board_obj, board_obj_task)(*args, **kwargs)
            board_obj.rebuild_cache()
        except:
            if exc_msg:
                sys.stderr.write(exc_msg % board_str + '\n')
                traceback.print_exc(file=sys.stderr)

# Global rebuilding

def global_cache_rebuild():
    loop_thru_boards('rebuild_cache', 'Error in global cache rebuild in %s')

def global_cache_rebuild_proxy(task_data):
    if task_data.user.account != staff.ADMIN:
        raise WakaError(strings.INSUFFICIENTPRIVILEGES)
    Popen([sys.executable, sys.argv[0], 'rebuild_global_cache'],
        env=util.proxy_environ())
    referer = local.environ['HTTP_REFERER']
    task_data.contents.append(referer)
    return util.make_http_forward(referer, config.ALTERNATE_REDIRECT)

# Global post management.

def process_global_delete_by_ip(ip, boards):
    loop_thru_boards(
        'delete_by_ip',
        'Error in deleting posts from %s in %%s' % ip,
        task_data = None,
        ip = ip,
        boards = boards
    )

# Bans and Whitelists

def add_admin_entry(task_data, option, comment, ip='', mask='255.255.255.255',
                    sval1='', total='', expiration=0,
                    caller=''):
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
            try:
                if int(row.ival1) & int(row.ival2) == ival1 & ival2:
                    raise WakaError('IP address and mask match ban #%d.' % \
                                    (row.num))
            except ValueError:
                raise WakaError("Entry #%s on ban table is inconsistent. "
                    "This shouldn't happen." % row.num)
        # Add info to task data.
        content = ip + (' (' + mask + ')' if mask else '')

        if total == 'yes':
            add_htaccess_entry(ip)
            content += ' (no browse)'

        content += ' "' + comment + '"'
        task_data.contents.append(content)
    else:
        if not sval1:
            raise WakaError(strings.STRINGFIELDMISSING)
        sql = table.select().where(and_(table.c.sval1 == sval1,
                                        table.c.type == option))
        row = session.execute(sql).fetchone()

        if row:
            raise WakaError('Duplicate String in ban #%d.' % (row.num))
        # Add ifno to task data.
        task_data.contents.append(sval1)

    comment = str_format.clean_string(\
        str_format.decode_string(comment, config.CHARSET))
    expiration = int(expiration) if expiration else 0
    if expiration:
        expiration = expiration + time.time()

    sql = table.insert().values(type=option, comment=comment, ival1=int(ival1),
                                ival2=int(ival2), sval1=sval1, total=total,
                                expiration=expiration)
    result = session.execute(sql)

    task_data.admin_id = result.inserted_primary_key[0]

    # Add specific action name to task data.
    task_data.action = option

    board = local.environ['waka.board']
    forward_url = misc.make_script_url(task='bans', board=board.name)

    if caller == 'window':
        return Template('edit_successful')
    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

def remove_admin_entry(task_data, num, override_log=False, no_redirect=False):
    session = model.Session()
    table = model.admin
    sql = table.select().where(table.c.num == num)
    row = session.execute(sql).fetchone()

    if not row:
        raise WakaError('Entry not found. Deleted?')

    ival1 = row['ival1']
    ip = misc.dec_to_dot(ival1) if ival1 else ''
    string_val = row['sval1']

    if row['total']:
        remove_htaccess_entry(ip)

    sql = table.delete().where(table.c.num == num)
    session.execute(sql)
    task_data.action = row['type'] + '_remove'
    if string_val:
        task_data.contents.append(row['sval1'])
    else:
        task_data.contents.append(ip + ' (' + misc.dec_to_dot(row['ival2']) \
                                  + ')')

    board = local.environ['waka.board']
    forward_url = misc.make_script_url(task='bans', board=board.name)

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
                and re.match(board_obj.options['THUMB_DIR'], row.thumbnail):
            filename = os.path.join(backup_path,
                                    os.path.basename(row.thumbnail))
            if os.path.exists(filename):
                os.unlink(filename)

    # Perform SQL DELETE
    sql = table.delete().where(table.c.timestampofarchival.op('+')\
                              (config.POST_BACKUP_EXPIRE) <= time.time())
    session.execute(sql)

def add_htaccess_entry(ip):
    htaccess = os.path.join(local.environ['DOCUMENT_ROOT'],
                            config.HTACCESS_PATH, '.htaccess')

    with util.FileLock(htaccess):
        with open(htaccess, 'r') as f:
            ban_entries_found = False

            line = f.readline()
            while line:
                if line.count('RewriteEngine On'):
                    ban_entries_found = True
                    break
                line = f.readline()

        with open(htaccess, 'a') as f:
            if not ban_entries_found:
                f.write("\n"+'# Bans added by Wakarimasen'+"\n")
                f.write("\n"+'RewriteEngine On'+"\n")

            ip = ip.replace('.', r'\.')
            f.write('RewriteCond %{REMOTE_ADDR} ^'+ip+'$'+"\n")
            f.write('RewriteRule !(\+pl|\+js$|\+css$|\+png'\
                    '|ban_images) '+local.environ['SCRIPT_NAME']+'?'\
                    'task=banreport&board='\
                    +local.environ['waka.board'].name+"\n")

def remove_htaccess_entry(ip):
    ip = ip.replace('.', r'\.')
    htaccess = os.path.join(local.environ['DOCUMENT_ROOT'],
                            config.HTACCESS_PATH, '.htaccess')

    with util.FileLock(htaccess):
        lines = []
        with open(htaccess, 'r') as f:
            line = f.readline()
            while line:
                if not line.count('RewriteCond %{REMOTE_ADDR} ^' + ip + '$'):
                    lines.append(line)
                else:
                    # Do not write, and skip the next line.
                    line = f.readline()
                if line:
                    line = f.readline()

        with open(htaccess, 'w') as f:
            f.write(''.join(lines))

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

def mark_resolved(task_data, delete, posts):
    referer = local.environ['HTTP_REFERER']
    user = task_data.user

    errors = []
    board_obj = None
    old_board_obj = local.environ['waka.board']

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

            # Log the resolved post.
            task_data.contents.append('/'.join(['', board_name, post]))

        if delete:
            try:
                board_obj = board.Board(board_name)
                local.environ['waka.board'] = board_obj
            except WakaError:
                errors.append({'error' : '%s,*: Error loading board.'\
                                         % (board_name)})
                continue
            try:
                board_obj.delete_stuff(posts, '', False, False,
                                       admindelete=True,
                                       admin_data=task_data)
            except WakaError:
                errors.append({'error' : '%s,%d: Post already deleted.'\
                                         % (board_name, int(post))})

    local.environ['waka.board'] = old_board_obj

    # TODO: This probably should be refactored into StaffInterface.
    return Template('report_resolved', errors=errors,
                                       error_occurred=len(errors)>0,
                                       admin=user.login_data.cookie,
                                       username=user.username,
                                       type=user.account,
                                       boards_select=user.reign,
                                       referer=referer)


def edit_admin_entry(task_data, num, comment='', ival1=None,
                     ival2='255.255.255.255', sval1='', total=False,
                     sec=None, min=None, hour=None, day=None, month=None,
                     year=None, noexpire=False):
    session = model.Session()
    table = model.admin
    sql = table.select().where(table.c.num == num)
    row = session.execute(sql).fetchone()

    if not row:
        raise WakaError('Entry was not created or was removed.')

    task_data.action = row.type + '_edit'

    if row.type in ('ipban', 'whitelist'):
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
        task_data.contents.append(ival1 + ' (' + ival2 + ')')
    else:
        expiration = 0
        task_data.contents.append(sval1)

    sql = table.update().where(table.c.num == num)\
               .values(comment=comment, ival1=ival1, ival2=ival2, sval1=sval1,
                       total=total, expiration=expiration)
    row = session.execute(sql)

    return Template('edit_successful')

def delete_by_ip(task_data, ip, mask='255.255.255.255', caller=''):
    task_data.contents.append(ip)
    user = task_data.user

    if user.account == staff.MODERATOR:
        reign = user.reign
    else:
        reign = [x['board_entry'] for x in get_all_boards()]

    Popen([sys.executable, sys.argv[0], 'delete_by_ip', ip, ','.join(reign)],
        env=util.proxy_environ())

    board_name = local.environ['waka.board'].name
    redir = misc.make_script_url(task='mpanel', board=board_name)

    if caller != 'internal':
        return util.make_http_forward(redir, config.ALTERNATE_REDIRECT)

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

def trim_activity():
    mintime = time.time() - config.STAFF_LOG_RETENTION
    session = model.Session()
    table = model.activity
    sql = table.delete().where(table.c.timestamp <= mintime)
    session.execute(sql)

def update_spam_file(task_data, spam):
    if task_data.user.account == staff.MODERATOR:
        raise WakaError(strings.INSUFFICIENTPRIVILEGES)

    # Dump all contents to first spam file.
    with open(config.SPAM_FILES[0], 'w') as f:
        f.write(spam)

    board = local.environ['waka.board']
    forward_url = misc.make_script_url(task='spam', board=board.name)

    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

# Thread Transfer

def move_thread(task_data, parent, src_brd_obj, dest_brd_obj):
    if not parent:
        raise WakaError('No thread specified.')
    if src_brd_obj.name == dest_brd_obj.name:
        raise WakaError('Source and destination boards match.')

    # Check administrative access rights to both boards.
    user = task_data.user
    user.check_access(src_brd_obj.name)
    user.check_access(dest_brd_obj.name)

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
                               '%d%s' % (int((new_parent), config.PAGE_EXT))),
                post['comment'])

            post['comment'] = new_comment

        sql = dest_table.insert().values(**post)
        result = session.execute(sql)

        if not new_parent:
            new_parent = result.inserted_primary_key[0]

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

    forward_url = misc.make_script_url(task='mpanel',
        board=dest_brd_obj.name, page=('t%s' % new_parent))

    # Log.
    task_data.contents.append('/%s/%d to /%s/%d' \
                              % (src_brd_obj.name, int(parent),
                                 dest_brd_obj.name, int(new_parent)))

    return util.make_http_forward(forward_url)


# proxy

def add_proxy_entry(task_data, type, ip, timestamp):
    session = model.Session()
    table = model.proxy

    if not misc.validate_ip(ip):
        raise WakaError(strings.BADIP)

    age = config.PROXY_WHITE_AGE if type == 'white' else config.PROXY_BLACK_AGE
    timestamp = int(timestamp or '0') - age + time.time()
    date = misc.make_date(time.time(), style=config.DATE_STYLE)

    query = table.delete().where(table.c.ip == ip)
    session.execute(query)

    query = table.insert().values(
        type=type,
        ip=ip,
        timestamp=timestamp,
        date=date
    )
    session.execute(query)

    board = local.environ['waka.board']
    forward_url = misc.make_script_url(task='proxy', board=board.name)

    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

def remove_proxy_entry(task_data, num):
    session = model.Session()
    table = model.proxy

    query = table.delete().where(table.c.num == num)
    session.execute(query)

    board = local.environ['waka.board']
    forward_url = misc.make_script_url(task='proxy', board=board.name)

    return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)
