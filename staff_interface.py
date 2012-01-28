'''Dynamic panels for administrative work.'''

from sqlalchemy.sql import case, or_, and_, select, func, null
from urllib import urlencode

import strings
import staff
import interboard
import model
import str_format
import misc
from util import WakaError, local, make_http_forward
from template import Template
import config

# Destination codes.
HOME_PANEL = 'mpanel'
BOARD_PANEL = 'mbpanel'
BAN_PANEL = 'banspanel'
SPAM_PANEL = 'spampanel'
REPORTS_PANEL = 'reportspanel'
STAFF_PANEL = 'staffpanel'
TRASH_PANEL = 'trashpanel'

DEL_STAFF_CONFIRM = 'delstaffwindow'
DISABLE_STAFF_CONFIRM = 'disablestaffwindow'
ENABLE_STAFF_CONFIRM = 'enablestaffwindow'
EDIT_STAFF_CONFIRM = 'editstaffwindow'
ADD_STAFF_CONFIRM = 'addstaffwindow'

def admin_only(f):
    '''StaffInterface templating function decorator: Indicate and enforce
    admin-only pages.'''
    def ret_func(*args, **kwargs):
        self = args[0]
        if self.user.account != staff.ADMIN:
            raise WakaError(strings.INUSUFFICENTPRIVLEDGES)
        f(*args, **kwargs)

    return ret_func

def global_only(f):
    '''StaffInterface templating function decorator: Indicate and enforce
    pages for global staff people only.'''
    def ret_func(*args, **kwargs):
        self = args[0]
        if self.user.account == staff.MODERATOR:
            raise WakaError(strings.INUSUFFICENTPRIVLEDGES)
        f(*args, **kwargs)

    return ret_func

class StaffInterface(Template):
    '''Specialized template.Template class for dynamic administrative
    pages served by Wakarimasen.'''

    def __init__(self, admin, board=None, dest=HOME_PANEL, page=None,
                 perpage=50, **kwargs):
        try:
            self.user = staff.check_password(admin)
        except staff.LoginError:
            Template.__init__(self, 'admin_login_template', nexttask=dest)
        else:
            # TODO: Check if mod is banned.

            if not page:
                if dest in (HOME_PANEL, BOARD_PANEL):
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
            self.board = board

            self._init_template(dest, **kwargs)

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
                                       admin=admin,
                                       boards_select=reign,
                                       boards=reign,
                                       page=self.page,
                                       perpage=self.perpage)

    def _init_template(self, dest, **kwargs):
            TEMPLATE_SELECTIONS = {HOME_PANEL : self.make_admin_home_panel,
                BOARD_PANEL : self.make_admin_board_panel,
                BAN_PANEL : self.make_admin_ban_panel,
                REPORTS_PANEL : self.make_admin_report_panel,
                STAFF_PANEL : self.make_admin_staff_panel,
                SPAM_PANEL : self.make_admin_spam_panel,
                TRASH_PANEL : self.make_admin_trash_panel,
                DEL_STAFF_CONFIRM : self.make_del_staff_window,
                DISABLE_STAFF_CONFIRM : self.make_disable_staff_window,
                ENABLE_STAFF_CONFIRM : self.make_enable_staff_window,
                EDIT_STAFF_CONFIRM : self.make_edit_staff_window}

            # Initialize underlying parent class instance.
            if dest not in TEMPLATE_SELECTIONS.keys():
                dest = HOME_PANEL

            template_function = TEMPLATE_SELECTIONS[dest]

            TEMPLATE_SELECTIONS[dest](**kwargs)

    def make_admin_board_panel(self):
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
            session = model.Session
            sql = table.select(table.c.parent == 0).count()
            thread_count = session.execute(sql).fetchone()
            total = (thread_count + self.perpage - 1) / self.perpage

            if total <= page:
                # Set page number to last page if exceeding total.
                # Pages are 0-indexed.
                page = total - 1
            # Get partial board posts.
            pagethreads = board.get_some_threads(self.page)
            (pages, prevpage, nextpage)\
                = board.get_board_page_data(self.page, total)
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

    make_admin_home_panel = make_admin_board_panel

    @admin_only
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
                row['action'] = 'None'
                row['actiondate'] = 'Never'

        Template.__init__(self, 'staff_management', users=users)

    @admin_only
    def make_admin_activity_panel(self, admin, view=None, user_to_view=None,
                                  action_to_view=None, ip_to_view=None,
                                  post_to_view=None, sortby_name='date',
                                  sortby_dir='desc'):

        template_view = 'staff_activity_unfiltered'
        action_name = action_content = ''

        table = model.activity
        account_table = model.account
        sql = table.select()
        
        dual_table_select = [account_table.c.username,
                             account_table.c.account,
                             account_table.c.disabled,
                             account_table.c.info,
                             table.c.date,
                             table.c.date,
                             table.c.ip]

        rooturl=''.join((misc.get_secure_script_name(),
                       '?task=stafflog&amp;board=', board.path,
                       '&amp;view=', view,
                       '&amp;sortby=', sortby_name,
                       '&amp;order=', sortby_dir)),

        if view == 'user':
            if not user_to_view:
                raise WakaError('Please select a user to view.')
            template_view = 'staff_activity_by_user'
            sql = table.select().where(table.c.username == user_to_view)
            rooturl += '&amp;usertoview=%s' % (user_to_view)

        elif view == 'action':
            if not action_to_view:
                raise WakaError('Please select an action to view.')
            template_view = 'staff_activity_by_actions'
            (action_name, action_content) \
                = misc.get_action_name(action_to_view, 1)
            sql = select(dual_table_select,
                         from_obj=[table.join(account_table,
                         table.c.username == model.account.c.username)])\
                  .where(table.c.action == action_to_view)
            rooturl += '&amp;actiontoview=%s' % (action_to_view)

        elif view == 'ip':
            if not ip_to_view:
                raise WakaError('Please specify an IP address to view.')
            template_view = 'staff_activity_by_ip_address'
            sql = select(dual_table_select,
                         from_obj=[table.join(account_table,
                         table.c.username == model.account.c.username)])\
                  .where(table.c.info.like_(ip_to_view))
            rooturl += '&amp;iptoview=%s' % (ip_to_view)

        elif view == 'post':
            if not post_to_view:
                raise WakaError('Post key missing.')
            template_view = 'staff_activity_by_post'
            sql = select(dual_table_select,
                         from_obj=[join(table, account_table,
                         table.c.username == model.account.c.username)])\
                  .where(table.c.info.like_(post_to_view))
            rooturl += '&amp;posttoview=%s' % (post_to_view)

        # Acquire staff info.
        session = model.Session()
        staff_sql = table.select(username)
        staff = session.execute(staff_get).fetchall()

        # Establish list of hidden inputs.
        inputs = [{'name' : 'actiontoview', 'value' : action_to_view},
                  {'name' : 'task', 'value' : 'stafflog'},
                  {'name' : 'posttoview', 'value' : post_to_view},
                  {'name' : 'usertoview', 'value' : user_to_view},
                  {'name' : 'iptoview', 'value' : ip_to_view},
                  {'name' : 'order', 'value' : sortby_dir},
                  {'name' : 'sortby', 'value' : sortby_name}]

        if self.board:
            inputs.append({'name' : 'board', 'value' : self.board.name})

        res = model.Page(sql, self.page, self.perpage)

        Template.__init__(self, template_view, post_to_view,
                          entries=res.rows,
                          staff=staff,
                          rowcount=res.total_entries,
                          numberofpages=res.total_pages,
                          view=view,
                          order=sortby_dir,
                          action_name=action_name,
                          content_name=action_content,
                          sortby=sortby_name,
                          rooturl=rooturl,
                          boards_select=user.reign,
                          inputs=inputs)

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
                row['browsingban'] = 'Yes'
            else:
                row['browsingban'] = 'No'

        Template.__init__(self, 'ban_panel_template', bans=bans, ip=ip)

    @global_only
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

    def make_admin_report_panel(self, sortby_type='date', sortby_dir='desc'):
        session = model.Session()
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

        rooturl = '%s?task=reports&amp;sortby=%s&amp;order=%s' \
                % (misc.get_secure_script_name(), sortby_type, sortby_dir)

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
    def make_del_staff_window(self, username):
        Template.__init__(self, 'staff_delete_template',
                                user_to_delete=username)

    def make_disable_staff_window(self, username):
        Template.__init__(self, 'staff_disable_template',
                                user_to_disable=username)

    def make_enable_staff_window(self, username):
        Template.__init__(self, 'staff_enable_template',
                                user_to_enable=username)

    def make_edit_staff_window(self, username):
        boards = interboard.get_all_boards()
        edited_user = staff.StaffMember.get(username)

        for board in boards:
            if board in edited_user.reign:
                board['underpower'] = True
            
        Template.__init__(self, 'staff_edit_template',
                                user_to_edit=username,
                                boards=boards)

    def make_admin_trash_panel(self):
        # Get reports. (Why again?)
        board = self.board
        reports = board.get_local_reports()

        if self.page.startswith('t'):
            pass
        else:
            pass

        Template.__init__(self, 'backup_panel_template',
                          postform=board.options['ALLOW_TEXTONLY'] or
                                   board.options['ALLOW_IMAGES'],
                          image_inp=board.options['ALLOW_IMAGES'],
                          textonly_inp=0,
                          threads=threads,
                          thread=page,
                          reportedposts=reportedposts,
                          parent=page)

    def make_admin_proxy_panel(self):
        pass

def add_staff_proxy(admin, mpass, usertocreate, passtocreate, account, reign):
    user = staff.check_password(admin)

    if user.account != staff.ADMIN:
        raise WakaError(strings.INUSUFFICENTPRIVLEDGES)

    if account == staff.ADMIN and mpass != config.ADMIN_PASS:
        raise WakaError('Incorrect management password.')

    staff.add_staff(usertocreate, passtocreate, account, reign)

    return make_http_forward('?'.join((misc.get_secure_script_name(),
        urlencode({'task' : 'staff'}))), config.ALTERNATE_REDIRECT)

def del_staff_proxy(admin, mpass, username):
    user = staff.check_password(admin)

    if user.account != staff.ADMIN:
        raise WakaError(strings.INUSUFFICENTPRIVLEDGES)

    user_to_kill = staff.StaffMember.get(username)
    if user_to_kill.account == staff.ADMIN and mpass != config.ADMIN_PASS:
        raise WakaError('Incorrect management password.')

    staff.del_staff(username)

    return make_http_forward('?'.join((misc.get_secure_script_name(),
        urlencode({'task' : 'staff'}))), config.ALTERNATE_REDIRECT)

def edit_staff_proxy(admin, mpass, username, newpassword=None, newclass=None,
                     originalpassword='', reign=None, disable=None):

    user = staff.check_password(admin)

    if user.account == staff.ADMIN:
        edited_user = staff.StaffMember.get(username)
        if edited_user.account == staff.ADMIN and mpass != config.ADMIN_PASS:
            raise WakaError('Incorrect management password.')
    else:
        if user.username != username:
            raise WakaError(strings.INUSUFFICENTPRIVLEDGES)
        newclass = None
        reign = None

    staff.edit_staff(username, clear_pass=newpassword, new_class=newclass,
                     reign=reign, disable=disable)

    forward = ''
    if user.username == username:
        forward = '?'.join((misc.get_secure_script_name(),
                            urlencode({'task' : 'admin'})))
    else:
        forward = '?'.join((misc.get_secure_script_name(),
                            urlencode({'task' : 'staff'})))

    return make_http_forward(forward, config.ALTERNATE_REDIRECT)

def clear_login_cookies():
    misc.make_cookies(wakaadmin='', wakaadminsave='0', expires=0)

def do_login(username=None, password=None, save_login=False,
             admin=None, board=None, nexttask='mpanel'):

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
    elif admin:
        # Attempt automatic login.
        try:
            staff_entry = staff.check_password(admin)
        except staff.LoginError:
            clear_login_cookies()
            bad_pass = True
    else:
        # No login credentials given.
        bad_pass = True

    if bad_pass:
        return make_login_panel()
    else:
        login = staff_entry.login_data
        login.make_cookie(save_login=save_login)
        return StaffInterface(login.cookie, dest=nexttask, board=board)

def do_logout(admin):
    # Clear login cache.
    try:
        user = staff.check_password(admin)
        user.logout_user()
    except staff.LoginError:
        pass

    clear_login_cookies()

    return make_http_forward('?'.join((misc.get_secure_script_name(),
                                       urlencode({'task' : 'admin'}))),
                                       config.ALTERNATE_REDIRECT)

def make_first_time_setup_gateway():
    # TODO: Make sure we're in secure mode (HTTPS)
    return Template('first_time_setup')

def do_first_time_setup(admin, username, password):
    # Checks.
    if admin != staff.crypt_pass(config.ADMIN_PASS,
                                 local.environ['REMOTE_ADDR']):
        return staff_interface.make_first_time_setup_gateway()
    if not username:
        raise WakaError('Missing username.')
    if not password:
        raise WakaError('Missing password.')

    staff.add_staff(username, password, staff.ADMIN, [])
    return make_http_forward('?'.join((misc.get_secure_script_name(),
                              urlencode({'task' : 'loginpanel'}))),
                              config.ALTERNATE_REDIRECT)


def make_first_time_setup_page(admin):
    if admin == config.ADMIN_PASS:
        admin = staff.crypt_pass(admin, local.environ['REMOTE_ADDR'])
        return Template('account_setup', admin=admin)
    else:
        return make_first_time_setup_gateway()
        
def make_login_panel(dest=HOME_PANEL):
    dest = HOME_PANEL

    return Template('admin_login_template', login_task=dest)
