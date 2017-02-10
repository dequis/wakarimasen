import model
import staff_interface

from template import Template
from util import WakaError
from staff_interface import StaffInterface
from staff_tasks import StaffAction
from board import Board
from misc import get_cookie_from_request, kwargs_from_params, make_cookies
from wakapost import WakaPost

def no_task(environ, start_response):
    board = environ['waka.board']
    start_response('302 Found', [('Location', board.url)])
    return []

def init_database():
    model.metadata.create_all(model.engine)

# Cache building
def task_rebuild(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        admin=True,
    )
    kwargs['board'] = environ['waka.board']
    kwargs['action'] = 'rebuild'

    return StaffAction(**kwargs).execute()

def task_rebuildglobal(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        admin=True,
    )
    kwargs['action'] = 'rebuild_global'

    return StaffAction(**kwargs).execute()

# Posting
def task_post(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    if request.method != 'POST':
        raise WakaError("POST only accepted")

    cookie = get_cookie_from_request(request, 'wakaadmin')

    wakapost = WakaPost.from_request(request)

    if wakapost.admin_post:
        return StaffAction(cookie, 'admin_post', wakapost=wakapost,
            board=board).execute()


    # not admin, so let's check for hcaptcha

    style_cookie = get_cookie_from_request(request,
        board.options.get('STYLE_COOKIE', 'wakastyle'))
    hcaptcha = request.values.get('hcaptcha', '').lower()
    is_nokosage = wakapost.email.lower() in ['noko', 'sage']

    import config
    if (config.HCAPTCHA and
        hcaptcha != config.HCAPTCHA_ANSWER and
        not (config.HCAPTCHA_COOKIE_BYPASS and style_cookie != '') and
        not (config.HCAPTCHA_NOKOSAGE_BYPASS and is_nokosage)):

        return Template('hcaptcha_failed',
            question=config.HCAPTCHA_QUESTION,
            answer=config.HCAPTCHA_ANSWER,
        )

    return board.post_stuff(wakapost)

# Post Deletion
def task_delpostwindow(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = {}
    kwargs['post_num'] = request.values.get('num', '')

    return board.delete_gateway_window(**kwargs)

def task_delete(environ, start_response, archiving=False):
    # TODO review compatibility with wakaba or refactor
    request = environ['werkzeug.request']
    board = environ['waka.board']

    singledelete = (request.values.get("singledelete", '') == 'OK')

    formparams = ['password', 'file_only', 'from_window', 'admindelete']
    kwargs = kwargs_from_params(request,
        form=formparams,
        admin=True,
    )

    if singledelete:
        # NOTE: from_window parameter originates from pop-up windows
        #       brought up by clicking "Delete" without JS enabled.
        params_single = ['postpassword', 'postfileonly', 'from_window']
        for param, single in map(None, formparams[:3], params_single):
            kwargs[param] = request.form.get(single, '')

        kwargs['posts'] = [request.values.get('deletepost', '')]
    else:
        kwargs['posts'] = request.form.getlist('num')
    kwargs['archiving'] = archiving

    if kwargs['admindelete']:
        kwargs['board'] = board
        kwargs['action'] = 'admin_delete'
        return StaffAction(**kwargs).execute()

    del kwargs['cookie']
    return board.delete_stuff(**kwargs)

def task_deleteall(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['ip', 'mask', 'global'],
        admin=True,
    )

    if kwargs.pop('global'):
        kwargs['action'] = 'delete_by_ip_global'
    else:
        kwargs['board'] = environ['waka.board']
        kwargs['action'] = 'delete_by_ip'

    # Perform action: returns nothing.
    StaffAction(**kwargs).execute()

    return task_mpanel(environ, start_response)

def task_archive(environ, start_response):
    return task_delete(environ, start_response, archiving=True)

# Post Editing
def task_edit(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        form=['num'],
    )
    kwargs['post_num'] = kwargs.pop('num')

    return board.edit_gateway_window(**kwargs)

def task_editpostwindow(environ, start_response):
    # This is displayed in a "pop-up window" UI.
    environ['waka.fromwindow'] = True

    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        form=['num', 'password', 'admineditmode'],
        admin=True,
    )
    kwargs['admin_mode'] = kwargs.pop('admineditmode')
    kwargs['post_num'] = kwargs.pop('num')

    return board.edit_window(**kwargs)

def task_editpost(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    if request.method != 'POST':
        raise WakaError("POST only accepted")

    cookie = get_cookie_from_request(request, 'wakaadmin')

    request_post = WakaPost.from_request(request)

    if request_post.admin_post:
        return StaffAction(cookie, 'admin_edit', request_post=request_post,
            board=board).execute()
    else:
        return board.edit_stuff(request_post)


def task_report(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    num = request.form.getlist('num')
    from_window = request.values.get('popupwindow', '')

    return board.make_report_post_window(num, from_window)

def task_confirmreport(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        form=['num', 'comment', 'referer'],
    )
    kwargs['posts'] = kwargs.pop('num').split(', ')

    return board.report_posts(**kwargs)

def task_resolve(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['delete'],
        admin=True,
    )

    posts = {}
    for post in request.form.getlist('num'):
        (board_name, num) = post.split('-')
        try:
            posts[board_name].append(num)
        except KeyError:
            posts[board_name] = [num]
    kwargs['posts'] = posts
    kwargs['action'] = 'report_resolve'

    return StaffAction(**kwargs).execute()

def task_restorebackups(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        form=['handle'],
        admin=True,
    )
    kwargs['posts'] = request.form.getlist('num')
    kwargs['restore'] = kwargs.pop('handle').lower() == 'restore'
    kwargs['board'] = board
    kwargs['action'] = 'backup_remove'

    return StaffAction(**kwargs).execute()

def _toggle_thread_state(environ, start_response, operation):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        admin=True,
    )
    kwargs['num'] = request.values.get('thread', 0)
    kwargs['board'] = board
    kwargs['action'] = 'thread_' + operation

    return StaffAction(**kwargs).execute()

def task_sticky(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'sticky')

def task_unsticky(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'unsticky')

def task_lock(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'lock')

def task_unlock(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'unlock')

# Panels

def task_entersetup(environ, start_response):
    request = environ['werkzeug.request']

    admin = request.values.get('berra', '')

    return staff_interface.make_first_time_setup_page(admin)

def task_setup(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['admin', 'username', 'password'],
    )

    return staff_interface.do_first_time_setup(**kwargs)

def task_loginpanel(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['nexttask', 'nexttask', 'berra', 'desu', 'savelogin'],
        cookies=['wakaadminsave'], admin=True,
    )

    # Why are we doing this again?
    kwargs['username'] = kwargs.pop('desu')
    kwargs['password'] = kwargs.pop('berra')

    # Login saving.
    wakaadminsave = kwargs.pop('wakaadminsave')
    savelogin = kwargs.pop('savelogin')
    kwargs['save_login'] = wakaadminsave or savelogin

    return staff_interface.do_login(**kwargs)

task_admin = task_loginpanel

def task_logout(environ, start_response):
    request = environ['werkzeug.request']

    cookie = get_cookie_from_request(request, 'wakaadmin')
    return staff_interface.do_logout(cookie)

def si_task_factory(dest, *form):
    '''Factory of task functions for StaffInterface'''
    def task(environ, start_response):
        request = environ['werkzeug.request']
        kwargs = kwargs_from_params(request,
            form=form,
            admin=True,
        )
        kwargs['dest'] = getattr(staff_interface, dest)
        return StaffInterface(**kwargs)
    return task

task_mpanel = si_task_factory('HOME_PANEL', 'page')
task_bans = si_task_factory('BAN_PANEL', 'ip')
task_baneditwindow = si_task_factory('BAN_EDIT_POPUP', 'num')
task_banpopup = si_task_factory('BAN_POPUP', 'ip', 'delete')
task_staff = si_task_factory('STAFF_PANEL')
task_spam = si_task_factory('SPAM_PANEL')
task_reports = si_task_factory('REPORTS_PANEL',
    'page', 'perpage', 'sortby','order')
task_postbackups = si_task_factory('TRASH_PANEL', 'page')

task_sql = si_task_factory('SQL_PANEL', 'sql', 'nuke')
task_proxy = si_task_factory('PROXY_PANEL')
task_security = si_task_factory('SECURITY_PANEL')

task_deleteuserwindow = si_task_factory('DEL_STAFF_CONFIRM', 'username')
task_disableuserwindow = si_task_factory('DISABLE_STAFF_CONFIRM', 'username')
task_enableuserwindow = si_task_factory('ENABLE_STAFF_CONFIRM', 'username')
task_edituserwindow = si_task_factory('EDIT_STAFF_CONFIRM', 'username')

task_searchposts = si_task_factory('POST_SEARCH_PANEL',
    'search', 'caller', 'text')

task_deleteall_confirm = si_task_factory('DELETE_ALL_CONFIRM',
    'ip', 'mask', 'global')

def task_addip(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['type', 'comment', 'ip', 'mask', 'total', 'expiration'],
        admin=True,
    )
    kwargs['option'] = kwargs.pop('type')
    kwargs['action'] = 'admin_entry'

    return StaffAction(**kwargs).execute()

def task_addipfrompopup(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = kwargs_from_params(request,
        form=['ip', 'mask', 'total', 'expiration', 'comment', 'delete',
              'deleteall_confirm', 'globaldeleteall_confirm'],
        admin=True,
    )
    kwargs['action'] = 'admin_entry'
    kwargs['option'] = 'ipban'
    kwargs['caller'] = 'window'
    delete = kwargs.pop('delete')
    delete_all = kwargs.pop('deleteall_confirm')
    globaldelete_all = kwargs.pop('globaldeleteall_confirm')

    try:
        if globaldelete_all:
            StaffAction(kwargs['cookie'], 'delete_by_ip_global',
                        ip=kwargs['ip'], caller='internal').execute()
        elif delete_all:
            StaffAction(kwargs['cookie'], 'delete_by_ip',
                        ip=kwargs['ip'], board=board).execute()
        elif delete:
            StaffAction(kwargs['cookie'], 'admin_delete', board=board,
                        posts=[delete], from_window=True, password='',
                        file_only=False, archiving=False, caller='internal')\
                .execute()
    except WakaError:
        pass

    make_cookies(ban_mask=kwargs['mask'], ban_expiration=kwargs['expiration'],
        ban_comment=kwargs['comment'])

    return StaffAction(**kwargs).execute()

def task_addstring(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['type', 'string', 'comment'],
        admin=True,
    )
    kwargs['action'] = 'admin_entry'
    kwargs['option'] = kwargs.pop('type')
    kwargs['sval1'] = kwargs.pop('string')

    return StaffAction(**kwargs).execute()

def task_adminedit(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['num', 'ival1', 'ival2', 'sval1', 'total', 'year',
              'month', 'day', 'hour', 'min', 'sec', 'comment',
              'noexpire'],
        admin=True,
    )
    kwargs['action'] = 'edit_admin_entry'

    return StaffAction(**kwargs).execute()

def task_removeban(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['num'],
        admin=True,
    )
    kwargs['action'] = 'remove_admin_entry'

    return StaffAction(**kwargs).execute()

def task_addproxy(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['type', 'ip', 'timestamp'],
        admin=True,
    )
    kwargs['action'] = 'add_proxy_entry'

    return StaffAction(**kwargs).execute()

def task_removeproxy(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['num'],
        admin=True,
    )
    kwargs['action'] = 'remove_proxy_entry'

    return StaffAction(**kwargs).execute()


# Interboard management.

def task_updatespam(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['spam'],
        admin=True,
    )
    kwargs['action'] = 'update_spam'

    return StaffAction(**kwargs).execute()

def task_createuser(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['mpass', 'usertocreate', 'passtocreate', 'account', 'reign'],
        admin=True,
    )
    kwargs['reign'] = kwargs.pop('reign').split(',')

    return staff_interface.add_staff_proxy(**kwargs)

def task_deleteuser(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['mpass', 'username'],
        admin=True,
    )

    return staff_interface.del_staff_proxy(**kwargs)

def task_disableuser(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['mpass', 'username'],
        admin=True,
    )
    kwargs['disable'] = True

    return staff_interface.edit_staff_proxy(**kwargs)

def task_enableuser(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['mpass', 'username'],
        admin=True,
    )
    kwargs['disable'] = False

    return staff_interface.edit_staff_proxy(**kwargs)

def task_edituser(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['mpass', 'usernametoedit', 'newpassword', 'newclass',
              'originalpassword'],
        admin=True,
    )
    kwargs['username'] = kwargs.pop('usernametoedit')
    kwargs['reign'] = request.form.getlist('reign')

    return staff_interface.edit_staff_proxy(**kwargs)

def task_move(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        admin=True
    )
    kwargs['parent'] = request.values.get('num', '')
    kwargs['src_brd_obj'] = environ['waka.board']
    kwargs['dest_brd_obj'] = Board(request.values.get('destboard', ''))
    kwargs['action'] = 'thread_move'

    return StaffAction(**kwargs).execute()

def task_stafflog(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = kwargs_from_params(request,
        form=['sortby', 'order', 'iptoview', 'view', 'perpage',
              'page', 'actiontoview', 'posttoview', 'usertoview'],
        admin=True,
    )
    kwargs['sortby_name'] = kwargs.pop('sortby')
    kwargs['sortby_dir'] = kwargs.pop('order')
    kwargs['ip_to_view'] = kwargs.pop('iptoview')
    kwargs['post_to_view'] = kwargs.pop('posttoview')
    kwargs['action_to_view'] = kwargs.pop('actiontoview')
    kwargs['user_to_view'] = kwargs.pop('usertoview')

    kwargs['dest'] = staff_interface.STAFF_ACTIVITY_PANEL

    return StaffInterface(**kwargs)

# Error-handling

def error(environ, start_response, error=None):

    message = error.message if error else 'Unhandled exception'

    if not (error and error.plain):
        mini = '_mini' if environ['waka.fromwindow'] else ''
        try:
            return Template('error_template' + mini, error=message)
        except:
            # if for some reason we can't render templates,
            # fallback to text/plain error reporting
            pass

    environ['waka.headers']['Content-Type'] = 'text/plain'
    return [str(message)]

# Initial setup

def check_setup(environ, start_response):
    import os, config
    import interboard
    from template import TEMPLATES_DIR, CACHE_DIR

    issues = []

    ENV_CHECKS = ['DOCUMENT_ROOT', 'SCRIPT_NAME', 'SERVER_NAME']
    MISSING_ENV = [x for x in ENV_CHECKS if x not in environ]
    if MISSING_ENV:
        return ['Environment not complete. Missing: %s\n' %
                ', '.join(MISSING_ENV)]

    full_board_dir = os.path.join(environ['DOCUMENT_ROOT'], config.BOARD_DIR)
    if not os.access(full_board_dir, os.W_OK):
        issues.append("No write access to DOCUMENT_ROOT+BOARD_DIR (%s)" %
            full_board_dir)

    include_dir = os.path.join(environ['DOCUMENT_ROOT'],
        config.BOARD_DIR, "include")
    if not os.access(include_dir, os.F_OK | os.R_OK):
        issues.append("No read access to includes dir (%s). Wrong BOARD_DIR?" %
            include_dir)

    script_name_dir = os.path.join(environ['DOCUMENT_ROOT'],
        os.path.dirname(environ['SCRIPT_NAME']).lstrip("/"))
    if not os.access(script_name_dir, os.W_OK):
        issues.append("No write access to DOCUMENT_ROOT+SCRIPT_NAME dir (%s)" %
            script_name_dir)

    templates_dir = os.path.abspath(TEMPLATES_DIR)
    if not os.access(templates_dir, os.W_OK):
        issues.append("No write access to templates dir (%s)" % templates_dir)

    cache_dir = os.path.abspath(CACHE_DIR)
    if not os.access(cache_dir, os.W_OK):
        issues.append("No write access to templates cache dir (%s)" % cache_dir)

    try:
        model.metadata.create_all(model.engine)
        interboard.remove_old_bans()
        interboard.remove_old_backups()
    except model.OperationalError, e:
        issues.append("Error writing to database: %s" % e.args[0])

    if issues:
        return ["<p>Setup issues found:</p> <ul>"] + \
            ["<li>%s</li>\n" % x for x in issues] + ["</ul>"]
    elif model.Session().query(model.account).count() == 0:
        return Template("first_time_setup")
    else:
        return ["Nothing to do."]
