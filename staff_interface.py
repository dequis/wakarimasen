'''Dynamic panels for administrative work.'''

import time
import os
import re
from datetime import datetime
from sqlalchemy.sql import or_, and_, not_, exists, select, func

import staff_tasks
import interboard
import strings
import staff
import model
import str_format
import misc
from util import WakaError, local, make_http_forward
from template import Template
import config

# Destination codes.
HOME_PANEL = 'mpanel'
BAN_PANEL = 'banspanel'
SPAM_PANEL = 'spampanel'
REPORTS_PANEL = 'reportspanel'
STAFF_PANEL = 'staffpanel'
TRASH_PANEL = 'trashpanel'
POST_SEARCH_PANEL = 'postsearchpanel'
SQL_PANEL = 'sqlpanel'
PROXY_PANEL = 'proxypanel'
SECURITY_PANEL = 'securitypanel'
STAFF_ACTIVITY_PANEL = 'stafflog'

BAN_POPUP = 'banpopup'
BAN_EDIT_POPUP = 'baneditwindow'

DEL_STAFF_CONFIRM = 'delstaffwindow'
DISABLE_STAFF_CONFIRM = 'disablestaffwindow'
ENABLE_STAFF_CONFIRM = 'enablestaffwindow'
EDIT_STAFF_CONFIRM = 'editstaffwindow'
ADD_STAFF_CONFIRM = 'addstaffwindow'
DELETE_ALL_CONFIRM = 'deleteallwindow'

INTERFACE_MAPPING = {}

def interface_for(dest_code):
    def decorator(f):
        INTERFACE_MAPPING[dest_code] = f
        return f
    return decorator

def admin_only(f):
    '''StaffInterface templating function decorator: Indicate and enforce
    admin-only pages.'''
    def ret_func(*args, **kwargs):
        self = args[0]
        if self.user.account != staff.ADMIN:
            raise WakaError(strings.INSUFFICIENTPRIVILEGES)
        f(*args, **kwargs)

    return ret_func

def global_only(f):
    '''StaffInterface templating function decorator: Indicate and enforce
    pages for global staff people only.'''
    def ret_func(*args, **kwargs):
        self = args[0]
        if self.user.account == staff.MODERATOR:
            raise WakaError(strings.INSUFFICIENTPRIVILEGES)
        f(*args, **kwargs)

    return ret_func

class StaffInterface(Template):
    '''Specialized template.Template class for dynamic administrative
    pages served by Wakarimasen.'''

    def __init__(self, cookie, board=None, dest=None, page=None,
                 perpage=50, **kwargs):
        try:
            self.user = staff.StaffMember.get_from_cookie(cookie)
        except staff.LoginError:
            Template.__init__(self, 'admin_login_template', login_task=dest)
            return
        if not dest:
            dest = HOME_PANEL

        self.admin = cookie

        # TODO: Check if mod is banned.
        if not page:
            if dest in (HOME_PANEL, TRASH_PANEL):
                # Adjust for different pagination scheme. (Blame Wakaba.)
                page = 0
            else:
                page = 1
        if not str(perpage).isdigit():
            perpage = 50

        # The page attribute is not always a pure integer (thread pages).
        if str(page).isdigit():
            page = int(page)
        self.page = page
        self.perpage = int(perpage)
        self.board = local.environ['waka.board']

        if dest not in INTERFACE_MAPPING:
            dest = HOME_PANEL

        INTERFACE_MAPPING[dest](self, **kwargs)

        # Convert user reign list into a list of dictionaries, for
        # templating.
        reign = []
        if self.user.account == staff.MODERATOR:
            reign = [{'board_entry' : entry} for entry in self.user.reign]
        else:
            if self.board:
                reign = interboard.get_all_boards\
                        (check_board_name=self.board.name)
            else:
                reign = interboard.get_all_boards()

        # Set global form variables.
        Template.update_parameters(self, username=self.user.username,
                                   type=self.user.account,
                                   admin=cookie,
                                   boards_select=reign,
                                   boards=reign,
                                   page=self.page,
                                   perpage=self.perpage)

    @interface_for(HOME_PANEL)
    def make_admin_home_panel(self):
        # Update perpage attribute: it is determined here by board options.
        board = self.board
        self.perpage = board.options['IMAGES_PER_PAGE']

        # Get reports.
        reports = board.get_local_reports()

        # Send to Template initializer.
        kwargs = {}
        threads = []

        if str(self.page).startswith('t'):
            self.page = self.page[1:]
            posts = board.get_thread_posts(self.page)
            threads.append({'posts' : posts})
            kwargs = {'lockedthread' : posts[0].locked,
                      'parent' : self.page,
                      'thread' : self.page}
        else:
            # Grab count of all threads.
            table = board.table
            session = model.Session()
            sql = select([func.count()], table.c.parent == 0)
            thread_count = session.execute(sql).fetchone()[0]
            total = (thread_count + self.perpage - 1) / self.perpage

            if total <= self.page and total > 0:
                # Set page number to last page if exceeding total.
                # Pages are 0-indexed.
                self.page = total - 1
            # Get partial board posts.
            pagethreads = board.get_some_threads(self.page)
            (pages, prevpage, nextpage)\
                = board.get_board_page_data(self.page, total,
                                            admin_page='mpanel')
            threads = board.parse_page_threads(pagethreads)
            kwargs = {'pages' : pages,
                      'prevpage' : prevpage,
                      'nextpage' : nextpage}

        Template.__init__(self, 'post_panel_template', 
                          postform=board.options['ALLOW_TEXTONLY'] or
                                   board.options['ALLOW_IMAGES'],
                          image_inp=board.options['ALLOW_IMAGES'],
                          threads=threads,
                          reportedposts=reports,
                          **kwargs)

    @admin_only
    @interface_for(STAFF_PANEL)
    def make_admin_staff_panel(self):
        session = model.Session()
        table = model.account
        sql = table.select().order_by(table.c.account.asc(),
                                      table.c.username.asc())

        query = session.execute(sql)
        users = [dict(row.items()) for row in query]

        rowtype = 1
        for row in users:
            # Alternate between values 1 and 2.
            rowtype ^= 0x3
            row['rowtype'] = rowtype

            # Get latest action from DB.
            action_table = model.activity
            action_grab_sql = action_table.select()\
                        .where(action_table.c.username == row['username'])\
                        .order_by(action_table.c.date.desc())
            last_action = session.execute(action_grab_sql).fetchone()

            # Copy to row.
            if last_action:
                row['action'] = last_action['action']
                row['actiondate'] = last_action['date']
            else:
                row['action'] = None
                row['actiondate'] = None

        Template.__init__(self, 'staff_management', users=users)

    @admin_only
    @interface_for(STAFF_ACTIVITY_PANEL)
    def make_admin_activity_panel(self, view='', user_to_view=None,
                                  action_to_view=None, ip_to_view=None,
                                  post_to_view=None, sortby_name='date',
                                  sortby_dir='desc'):

        board = self.board

        template_view = 'staff_activity_unfiltered'
        action_name = action_content = ''

        table = model.activity
        account_table = model.account

        dual_table_select = [account_table.c.username,
                             account_table.c.account,
                             account_table.c.disabled,
                             table.c.action,
                             table.c.info,
                             table.c.date,
                             table.c.ip]
        sql = select(dual_table_select,
                     from_obj=[table.join(account_table,
                     table.c.username == model.account.c.username)])

        rooturl_args = dict(task='stafflog', board=board.name,
            view=view, sortby=sortby_name, order=sortby_dir, _amp=True)

        if view == 'user':
            if not user_to_view:
                raise WakaError('Please select a user to view.')
            template_view = 'staff_activity_by_user'
            sql = sql.where(table.c.username == user_to_view)
            rooturl_args['usertoview'] = user_to_view

        elif view == 'action':
            if not action_to_view:
                raise WakaError('Please select an action to view.')
            template_view = 'staff_activity_by_actions'
            (action_name, action_content) \
                = staff_tasks.get_action_name(action_to_view, 1)
            sql = sql.where(table.c.action == action_to_view)
            rooturl_args['actiontoview'] = action_to_view

        elif view == 'ip':
            if not ip_to_view:
                raise WakaError('Please specify an IP address to view.')
            template_view = 'staff_activity_by_ip_address'
            sql = sql.where(table.c.info.like('%' + ip_to_view + '%'))
            rooturl_args['iptoview'] = ip_to_view

        elif view == 'post':
            if not post_to_view:
                raise WakaError('Post key missing.')
            template_view = 'staff_activity_by_post'
            sql = sql.where(table.c.info.like('%' + post_to_view + '%'))
            rooturl_args['posttoview'] = post_to_view

        rooturl = misc.make_script_url(**rooturl_args)

        # Acquire staff info.
        session = model.Session()
        staff_get = model.account.select()
        staff = session.execute(staff_get).fetchall()

        # Establish list of hidden inputs.
        inputs = [
            {'name' : 'actiontoview', 'value' : action_to_view},
            {'name' : 'task', 'value' : 'stafflog'},
            {'name' : 'posttoview', 'value' : post_to_view},
            {'name' : 'usertoview', 'value' : user_to_view},
            {'name' : 'iptoview', 'value' : ip_to_view},
            {'name' : 'order', 'value' : sortby_dir},
            {'name' : 'sortby', 'value' : sortby_name},
            {'name' : 'view', 'value': view}
        ]

        if self.board:
            inputs.append({'name' : 'board', 'value' : self.board.name})

        # Apply sorting.
        if sortby_name and hasattr(table.c, sortby_name):
            order_col = getattr(table.c, sortby_name)
            if sortby_dir.lower() == 'asc':
                sort_spec = order_col.asc()
            else:
                sort_spec = order_col.desc()
            sql = sql.order_by(sort_spec)

        res = model.Page(sql, self.page, self.perpage)

        Template.__init__(self, template_view,
                          user_to_view=user_to_view,
                          entries=res.rows,
                          staff=staff,
                          rowcount=res.total_entries,
                          numberofpages=res.total_pages,
                          view=view,
                          order=sortby_dir,
                          action_name=action_name,
                          content_name=action_content,
                          sortby=sortby_name,
                          number_of_pages=res.total_pages,
                          rooturl=rooturl,
                          inputs=inputs)

    @interface_for(BAN_PANEL)
    def make_admin_ban_panel(self, ip=''):
        session = model.Session()
        table = model.admin

        sql = select([model.activity.c.username,
                      table.c.num,
                      table.c.type,
                      table.c.comment,
                      table.c.ival1,
                      table.c.ival2,
                      table.c.sval1,
                      table.c.total,
                      table.c.expiration],
            from_obj=[table.outerjoin(model.activity,
            and_(table.c.num == model.activity.c.admin_id,
            table.c.type == model.activity.c.action))])\
            .order_by(table.c.type.asc(), table.c.num.asc())

        # TODO: We should be paginating, but the page needs to be
        # adjusted first.
        # res = model.Page(sql, self.page, self.perpage)

        query = session.execute(sql)
        bans = [dict(row.items()) for row in query]

        rowtype = 1
        prevtype = ''
        for row in bans:
            prevtype = row
            if prevtype != row['type']:
                row['divider'] = 1

            # Alternate between values 1 and 2.
            rowtype ^= 0x3
            row['rowtype'] = rowtype

            if row['expiration']:
                row['expirehuman'] = misc.make_date(row['expiration'])
            else:
                row['expirehuman'] = 'Never'

            if row['total'] == 'yes':
                row['browsingban'] = 'No'
            else:
                row['browsingban'] = 'Yes'

        Template.__init__(self, 'ban_panel_template', bans=bans, ip=ip)

    @interface_for(BAN_EDIT_POPUP)
    def make_ban_edit_popup(self, num):
        session = model.Session()
        table = model.admin
        sql = table.select().where(table.c.num == num)
        row = session.execute(sql).fetchone()

        if row.expiration:
            expiration = datetime.utcfromtimestamp(row.expiration)
        else:
            expiration = datetime.utcnow()

        Template.__init__(self, 'edit_window', hash=[row],
                          year=expiration.year,
                          month=expiration.month,
                          day=expiration.day,
                          hour=expiration.hour,
                          min=expiration.minute,
                          sec=expiration.second)

    @interface_for(BAN_POPUP)
    def make_ban_popup(self, ip, delete=''):
        Template.__init__(self, 'ban_window', ip=ip, delete=delete)

    @global_only
    @interface_for(SPAM_PANEL)
    def make_admin_spam_panel(self):
        # TODO: Paginate this, too.
        spam_list = []
        for filename in config.SPAM_FILES:
            with open(filename, 'r') as f:
                spam_list.extend([str_format.clean_string(l) for l in f])

        spamlines = len(spam_list)
        spam = ''.join(spam_list)

        Template.__init__(self, 'spam_panel_template', spam=spam,
                                                       spamlines=spamlines)

    @interface_for(REPORTS_PANEL)
    def make_admin_report_panel(self, sortby='date', order='desc'):
        sortby_type = sortby
        sortby_dir = order

        table = model.report
        sql = table.select()

        # Enforce limited moderation reign.
        if self.user.account == staff.MODERATOR:
            sql = sql.where(table.c.board.in_(self.user.reign))

        # Determine order.
        if sortby_type in ('board', 'postnum', 'date'):
            try:
                column = getattr(table.c, sortby_type)
            except AttributeError:
                raise WakaError('Sort-by column is absent from table.')
            sort = column.desc
            if sortby_dir == 'asc':
                sort = column.asc
            sql = sql.order_by(sort(), table.c.date.desc())
        else:
            sql = sql.order_by(table.c.date.desc())

        # Paginate.
        res = model.Page(sql, self.page, self.perpage)

        # Hidden input fields.
        inputs = [{'name' : 'task', 'value' : 'reports'},
                  {'name' : 'order', 'value' : sortby_dir},
                  {'name' : 'sortby', 'value' : sortby_type}]

        rooturl = misc.make_script_url(task='reports', sortby=sortby_type,
            order=sortby_dir, _amp=True)

        Template.__init__(self, 'report_panel_template',
                          reports=res.rows,
                          sortby=sortby_type,
                          order=sortby_dir,
                          number_of_pages=res.total_pages,
                          rowcount=res.total_entries,
                          inputs=inputs,
                          rooturl=rooturl)

    # NOTE: For this and other make_*_window functions, I took out
    # the sanity checks and instead delegated them to the non-interface
    # functions, the idea being that they should not come up
    # under normal usage of the interface (without compromising security).

    @interface_for(DEL_STAFF_CONFIRM)
    def make_del_staff_window(self, username):
        Template.__init__(self, 'staff_delete_template',
                                user_to_delete=username)

    @interface_for(DISABLE_STAFF_CONFIRM)
    def make_disable_staff_window(self, username):
        Template.__init__(self, 'staff_disable_template',
                                user_to_disable=username)

    @interface_for(ENABLE_STAFF_CONFIRM)
    def make_enable_staff_window(self, username):
        Template.__init__(self, 'staff_enable_template',
                                user_to_enable=username)

    @interface_for(EDIT_STAFF_CONFIRM)
    def make_edit_staff_window(self, username):
        boards = interboard.get_all_boards()
        edited_user = staff.StaffMember.get(username)

        for board in boards:
            if board in edited_user.reign:
                board['underpower'] = True

        Template.__init__(self, 'staff_edit_template',
                                user_to_edit=username,
                                boards=boards)

    @interface_for(TRASH_PANEL)
    def make_admin_trash_panel(self):
        board = self.board
        table = model.backup
        session = model.Session()
        template_kwargs = {}

        # List of current threads *and* orphaned posts.
        threads = []

        if str(self.page).startswith('t'):
            self.page = self.page[1:]
            sql = table.select().where(and_(or_(table.c.postnum == self.page,
                                                table.c.parent == self.page),
                                            table.c.board_name == board.name))\
                                .order_by(table.c.timestampofarchival.desc(),
                                          table.c.postnum.asc())
            thread = [dict(x.items()) for x in session.execute(sql).fetchall()]

            if not thread:
                raise WakaError('Thread not found.')

            threads = [{'posts' : thread}]

            template_kwargs = {
                'postform' : board.options['ALLOW_TEXTONLY'] or
                             board.options['ALLOW_IMAGES'],
                'image_inp' : board.options['ALLOW_IMAGES'],
                'textonly_inp' : 0,
                'threads' : threads,
                'thread' : self.page,
                'parent' : self.page
            }

        elif config.POST_BACKUP:
            max_res = board.options['IMAGES_PER_PAGE']

            sqlcond = and_(or_(table.c.parent == 0,
                and_(table.c.parent > 0, not_(exists([table.c.num],
                    table.c.parent == table.c.postnum)))),
                table.c.board_name == board.name)

            # Acquire the number of full threads *and* orphaned posts.
            sql = select([func.count()], sqlcond, table)\
                  .order_by(table.c.timestampofarchival.desc(),
                              table.c.postnum.asc())

            thread_ct = session.execute(sql).fetchone()[0]

            total = int(thread_ct + max_res - 1) / max_res
            offset = self.page * max_res

            (pages, prevpage, nextpage) \
                = board.get_board_page_data(self.page, total,
                                            admin_page='postbackups')

            last_page = len(pages) - 1
            if self.page > last_page and last_page > 0:
                self.page = last_page

            sql = table.select().where(sqlcond)\
                  .order_by(table.c.timestampofarchival.desc(),
                              table.c.num.asc())\
                  .limit(board.options['IMAGES_PER_PAGE'])\
                  .offset(offset)
            threads = [{'posts' : [dict(x.items())]} \
                for x in session.execute(sql)]

            # Loop through 'posts' key in each dictionary in the threads
            # list.
            for item in threads:
                thread = item['posts']
                threadnum = thread[0]['postnum']
                postcount = imgcount = shownimages = 0

                # Orphaned?
                item['standalone'] = 0

                if not thread[0]['parent']:
                    sql = select([func.count(), func.count(table.c.image)],
                                  table.c.parent == threadnum,
                                  table)

                    (postcount, imgcount) = session.execute(sql).fetchone()

                    max_res = board.options['REPLIES_PER_THREAD']
                    offset = postcount - imgcount if postcount > max_res \
                                                  else 0

                    sql = table.select().where(table.c.parent == threadnum)\
                            .order_by(table.c.timestampofarchival.desc(),
                                      table.c.postnum.asc())\
                            .limit(max_res)\
                            .offset(offset)
                    thread.extend([dict(x.items()) \
                                       for x in session.execute(sql)])

                else:
                    item['standalone'] = 1

                for post in thread:
                    #image_dir \
                    #    = os.path.join(board.path, board.options['IMG_DIR'])

                    #thumb_dir \
                    #    = os.path.join(board.path, board.options['THUMB_DIR'])

                    base_thumb = os.path.basename(post['thumbnail'] or '')
                    base_image = os.path.basename(post['image'] or '')

                    #base_filename = (post['image'] or '')\
                    #    .replace(image_dir, '').lstrip('/')

                    backup_dir = os.path.join(board.url,
                                              board.options['ARCHIVE_DIR'],
                                              board.options['BACKUP_DIR'])

                    if post['image']:
                        post['image'] = os.path.join(backup_dir, base_image)
                        shownimages += 1

                    if re.match(board.options['THUMB_DIR'],
                                post['thumbnail'] or ''):
                        post['thumbnail'] \
                            = os.path.join(backup_dir, base_thumb)

                item['omit'] = postcount - max_res if postcount > max_res\
                                                   else 0

                item['omitimages'] = imgcount - shownimages \
                                     if imgcount > shownimages else 0

                template_kwargs = {'postform' \
                                      : board.options['ALLOW_TEXTONLY'] or
                                        board.options['ALLOW_IMAGES'],
                                  'image_inp' : board.options['ALLOW_IMAGES'],
                                   'textonly_inp' \
                                      : board.options['ALLOW_IMAGES'] and
                                        board.options['ALLOW_TEXTONLY'],
                                   'nextpage' : nextpage,
                                   'prevpage' : prevpage,
                                   'threads' : threads,
                                   'pages' : pages}

        Template.__init__(self, 'backup_panel_template', **template_kwargs)


    @interface_for(POST_SEARCH_PANEL)
    def make_admin_post_search_panel(self, search, text, caller='internal'):
        board = self.board
        session = model.Session()
        table = board.table

        self.user.check_access(board.name)

        popup = caller != 'board'

        if search.find('IP Address') != -1:
            try:
                sql = table.select()\
                           .where(table.c.ip == misc.dot_to_dec(text))
            except ValueError:
                raise WakaError('Please enter a valid IP.')
            search_type = 'IP'
        elif search.find('Text String') != -1:
            sql = table.select().where(table.c.comment.like('%'+text+'%'))
            search_type = 'text string'
        elif search.find('Author') != -1:
            sql = table.select().where(or_(table.c.name.like('%'+text+'%'),
                table.c.trip.like('%'+text+'%')))
            search_type = 'author'
        else:
            sql = table.select().where(table.c.num == text)
            search_type = 'ID'

        if search_type != 'ID':
            page = model.Page(sql, self.page, self.perpage)
            rowcount = page.total_entries
            total_pages = page.total_pages
            posts = page.rows
            if not posts:
                raise WakaError("No posts found for %s %s" % (search_type, text))
        else:
            rowcount = total_pages = 1
            row = session.execute(sql).fetchone()
            if not row:
                raise WakaError("Post not found. (It may have just been"
                                " deleted.)")
            posts = [row]


        inputs = [
            {'name': 'board', 'value': board.name},
            {'name' : 'task', 'value' : 'searchposts'},
            {'name' : 'text', 'value' : text},
            {'name': 'caller', 'value': caller},
            {'name' : 'search', 'value': search}
        ]

        rooturl = misc.make_script_url(task='searchposts', board=board.name,
            caller=caller, search=search, text=text, _amp=True)

        Template.__init__(self, 'post_search', num=id,
                          posts=posts, search=search, text=text,
                          inputs=inputs, number_of_pages=total_pages,
                          rooturl=rooturl, rowcount=rowcount, popup=popup)

    @interface_for(SQL_PANEL)
    def make_sql_interface_panel(self, sql='', nuke=''):
        if self.user.account != staff.ADMIN:
            raise WakaError(strings.INSUFFICIENTPRIVILEGES)

        results = []

        if sql or nuke:
            if nuke != local.environ['waka.board'].options['NUKE_PASS']:
                raise WakaError(strings.WRONGPASS)

            session = model.Session()
            if sql:
                for sql in sql.split('\r\n'):
                    # Execute teh string.
                    try:
                        results.append('>>> ' + sql)
                        row = session.execute(sql)
                    except Exception as errstr:
                        results.append('ERROR: %s' % (errstr))
                    else:
                        try:
                            results.append(str(row.fetchall()))
                        except:
                            results.append('OK')
            else:
                # Remove board table contents and board list entry.
                try:
                    board = local.environ['waka.board']
                    board.table.drop(bind=model.engine, checkfirst=True)
                    del model._boards[board.name]
                    model.common.delete().where(model.common.c.board \
                                                == board.name)
                except Exception as errstr:
                    results.append('ERROR %s' % (errstr))
                else:
                    results.append('Comment table dropped. You should '
                                   'delete/move the board folder now.')
        else:
            results.append('Leave textarea blank to delete the board.\n\n'
                           '(It is recommended that you disable site access '
                           'while entering SQL or deleting boards.)')

        Template.__init__(self, 'sql_interface_template',
                          results='<br />'.join(results))

    @interface_for(PROXY_PANEL)
    def make_admin_proxy_panel(self):
        session = model.Session()
        table = model.proxy
        query = table.select().order_by(table.c.timestamp.asc())
        rows = session.execute(query)

        Template.__init__(self, 'proxy_panel_template',
            scanned=rows, now=time.time())

    @interface_for(SECURITY_PANEL)
    def make_admin_script_security_panel(self):
        session = model.Session()
        table = model.passprompt
        rows = session.execute(table.select())

        now = time.time()

        entries = []
        for row in rows:
            row = dict(row)
            if row['passfail']:
                row['expiration']\
                    = config.PASSFAIL_ROLLBACK - now + row['timestamp']
            else:
                row['expiration']\
                    = config.PASSPROMPT_EXPIRE_TO_FAILURE - now \
                      + row['timestamp']
            entries.append(row)

        Template.__init__(self, 'script_security_panel', entries=entries)

    @interface_for(DELETE_ALL_CONFIRM)
    def make_delete_all_window(self, **kwargs):
        Template.__init__(self, 'delete_crap_confirm', **kwargs)

def add_staff_proxy(cookie, mpass, usertocreate, passtocreate, account, reign):
    user = staff.StaffMember.get_from_cookie(cookie)

    if user.account != staff.ADMIN:
        raise WakaError(strings.INSUFFICIENTPRIVILEGES)

    if account == staff.ADMIN and mpass != config.ADMIN_PASS:
        raise WakaError('Incorrect management password.')

    staff.add_staff(usertocreate, passtocreate, account, reign)

    board = local.environ['waka.board']
    return make_http_forward(misc.make_script_url(task='staff',
        board=board.name), config.ALTERNATE_REDIRECT)

def del_staff_proxy(cookie, mpass, username):
    user = staff.StaffMember.get_from_cookie(cookie)

    if user.account != staff.ADMIN:
        raise WakaError(strings.INSUFFICIENTPRIVILEGES)

    user_to_kill = staff.StaffMember.get(username)
    if user_to_kill.account == staff.ADMIN and mpass != config.ADMIN_PASS:
        raise WakaError('Incorrect management password.')

    staff.del_staff(username)

    board = local.environ['waka.board']
    return make_http_forward(misc.make_script_url(task='staff',
        board=board.name), config.ALTERNATE_REDIRECT)

def edit_staff_proxy(cookie, mpass, username, newpassword=None, newclass=None,
                     originalpassword='', reign=None, disable=None):

    user = staff.StaffMember.get_from_cookie(cookie)

    if user.username == username:
        if misc.hide_critical_data(originalpassword, config.SECRET) \
           != user.password:
            raise WakaError(strings.WRONGPASS)
        newclass = None
        reign = None
    elif user.account == staff.ADMIN:
        edited_user = staff.StaffMember.get(username)
        if edited_user.account == staff.ADMIN and mpass != config.ADMIN_PASS:
            raise WakaError('Incorrect management password.')
    else:
        raise WakaError(strings.INSUFFICIENTPRIVILEGES)

    staff.edit_staff(username, clear_pass=newpassword, new_class=newclass,
                     reign=reign, disable=disable)

    board = local.environ['waka.board']

    forward_task = 'admin' if user.username == username else 'staff'

    return make_http_forward(misc.make_script_url(task=forward_task,
        board=board.name), config.ALTERNATE_REDIRECT)


def clear_login_cookies():
    misc.make_cookies(wakaadmin='', wakaadminsave='0', expires=0)

def do_login(username=None, password=None, save_login=False,
             cookie=None, board=None, nexttask=HOME_PANEL):

    bad_pass = False
    staff_entry = None

    if not staff.staff_exists():
        return make_first_time_setup_gateway()
    elif username and password:
        # Login via login form entry.
        try:
            staff_entry = staff.StaffMember.get(username)
        except staff.LoginError:
            # Bad username.
            bad_pass = True
        else:
            crypt_pass = misc.hide_critical_data(password, config.SECRET)
            if crypt_pass == staff_entry.password:
                remote = local.environ['REMOTE_ADDR']
                staff_entry.login_host(remote)
            else:
                bad_pass = True
    elif cookie:
        # Attempt automatic login.
        try:
            staff_entry = staff.StaffMember.get_from_cookie(cookie)
        except staff.LoginError:
            clear_login_cookies()
            bad_pass = True
    else:
        # No login credentials given.
        bad_pass = True

    if bad_pass:
        return Template('admin_login_template')
    else:
        login = staff_entry.login_data
        login.make_cookie(save_login=save_login)
        return StaffInterface(login.cookie, dest=nexttask, board=board)

def do_logout(cookie):
    # Clear login cache.
    try:
        user = staff.StaffMember.get_from_cookie(cookie)
        user.logout_user()
    except staff.LoginError:
        pass

    clear_login_cookies()

    board = local.environ['waka.board']
    return make_http_forward(misc.make_script_url(task='admin',
        board=board.name), config.ALTERNATE_REDIRECT)

def make_first_time_setup_gateway():
    # TODO: Make sure we're in secure mode (HTTPS)
    return Template('first_time_setup')

def do_first_time_setup(cookie, username, password):
    # Checks.
    if cookie != staff.crypt_pass(config.ADMIN_PASS,
                                 local.environ['REMOTE_ADDR']):
        return make_first_time_setup_gateway()
    if not username:
        raise WakaError('Missing username.')
    if not password:
        raise WakaError('Missing password.')

    staff.add_staff(username, password, staff.ADMIN, [])

    board = local.environ['waka.board']
    return make_http_forward(misc.make_script_url(task='loginpanel',
        board=board.name), config.ALTERNATE_REDIRECT)


def make_first_time_setup_page(cookie):
    if not hasattr(config, 'ADMIN_PASS'):
        raise WakaError("ADMIN_PASS not set in config")

    if cookie == config.ADMIN_PASS:
        cookie = staff.crypt_pass(cookie, local.environ['REMOTE_ADDR'])
        return Template('account_setup', admin=cookie)
    else:
        return make_first_time_setup_gateway()
