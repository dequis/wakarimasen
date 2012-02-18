import model
import staff_interface
import interboard
import urllib

from template import Template
from util import WakaError
from staff_interface import StaffInterface
from board import Board
from misc import get_cookie_from_request, kwargs_from_params

def no_task(environ, start_response):
    board = environ['waka.board']
    start_response('302 Found', [('Location', board.url)])
    return []

def init_database():
    model.metadata.create_all(model.engine)

# Cache building
def task_rebuild(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']
    params = {'cookies': ['wakaadmin']}
    
    kwargs = kwargs_from_params(request, params)

    return board.rebuild_cache_proxy(**kwargs)

def task_rebuildglobal(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']
    params = {'cookies': ['wakaadmin']}
    
    kwargs = kwargs_from_params(request, params)

    return interboard.global_cache_rebuild_proxy(**kwargs)

# Posting
def task_post(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = {'form':     ['parent', 'field1', 'email', 'subject', 'comment',
                           'password', 'nofile', 'captcha', 'no_captcha',
                           'no_format', 'sticky', 'lock', 'adminpost'],
              'cookies':  ['wakaadmin'],
              'file':     ['file']}
   
    kwargs = kwargs_from_params(request, params)
 
    kwargs['name'] = kwargs.pop('field1')
    kwargs['admin_post_mode'] = kwargs.pop('adminpost')
    kwargs['oekaki_post'] = kwargs['srcinfo'] = kwargs['pch'] = None
    # kwargs['environ'] = environ
    
    return board.post_stuff(**kwargs)

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

    kwargs = {}
    params = {'form': ['password', 'file_only', 'from_window', 'admindelete'],
              'cookies': ['wakaadmin']}

    if singledelete:
        # NOTE: from_window parameter originates from pop-up windows
        #       brought up by clicking "Delete" without JS enabled.
        #       Not implemented yet.
        params_single = ['postpassword', 'postfileonly', 'from_window']
        for param, single in map(None, params['form'][:3], params_single):
            kwargs[param] = request.form.get(single, '')

        kwargs['posts'] = [request.values.get('deletepost', '')]
    else:
        for param in params:
            kwargs[param] = request.form.get(param, '')

        # Parse posts string into array.
        kwargs['posts'] = request.form.getlist('num')

    kwargs['archiving'] = archiving
    return board.delete_stuff(**kwargs)

def task_archive(environ, start_response):
    return task_delete(environ, start_response, archiving=True)

# Post Editing
def task_edit(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = {'form': ['num'], 'cookies': ['wakaadmin']}
   
    kwargs = kwargs_from_params(request, params)
    kwargs['post_num'] = kwargs.pop('num')
    try:
        kwargs['admin_post'] = kwargs.pop('admin')
    except KeyError:
        kwargs['admin_post'] = False

    return board.edit_gateway_window(**kwargs)

def task_editpostwindow(environ, start_response):
    # This is displayed in a "pop-up window" UI.
    environ['waka.fromwindow'] = True

    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = {'form':    ['num', 'password', 'admineditmode'],
              'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)
    kwargs['admin_edit_mode'] = kwargs.pop('admineditmode')
    kwargs['post_num'] = kwargs.pop('num')

    return board.edit_window(**kwargs)

def task_editpost(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = {'form': ['num', 'field1', 'email', 'subject', 'comment',
                       'password', 'nofile', 'captcha', 'no_captcha',
                       'no_format', 'sticky', 'lock', 'adminedit', 'killtrip',
                       'postfix'],
              'cookies': ['wakaadmin'],
              'file':    ['file']}

    kwargs = kwargs_from_params(request, params)
    kwargs['name'] = kwargs.pop('field1')
    kwargs['post_num'] = kwargs.pop('num')
    kwargs['admin_edit_mode'] = kwargs.pop('adminedit')
    kwargs['oekaki_post'] = kwargs['srcinfo'] = kwargs['pch'] = None
    # kwargs['environ'] = environ

    return board.edit_stuff(**kwargs)

def task_report(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    num = request.form.getlist('num')
    from_window = request.values.get('popupwindow', '')

    return board.make_report_post_window(num, from_window)

def task_confirmreport(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = {'form': ['num', 'comment', 'referer']}

    kwargs = kwargs_from_params(request, params)
    kwargs['posts'] = kwargs.pop('num').split(', ')
    
    return board.report_posts(**kwargs)

def task_resolve(environ, start_response):
    request = environ['werkzeug.request']
    params = {'cookies': ['wakaadmin'], 'form': ['delete']}

    kwargs = kwargs_from_params(request, params)

    posts = {}
    for post in request.form.getlist('num'):
        (board_name, num) = post.split('-')
        try:
            posts[board_name].append(num)
        except KeyError:
            posts[board_name] = [num]
    kwargs['posts'] = posts

    return interboard.mark_resolved(**kwargs)

def _toggle_thread_state(environ, start_response, operation, enable=True):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = {}
    kwargs['num'] = request.values.get('thread', 0)
    kwargs['enable_state'] = enable
    kwargs['operation'] = operation
    try:
        kwargs['admin'] = get_cookie_from_request(request, 'wakaadmin')
    except KeyError:
        kwargs['admin'] = ''

    return board.toggle_thread_state(**kwargs)

def task_sticky(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'sticky')

def task_unsticky(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'sticky',
                                enable=False)

def task_lock(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'lock')

def task_unlock(environ, start_response):
    return _toggle_thread_state(environ, start_response, 'lock', enable=False)

# Panels

def task_entersetup(environ, start_response):
    request = environ['werkzeug.request']

    admin = request.values.get('berra', '')

    return staff_interface.make_first_time_setup_page(admin)

def task_setup(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['admin', 'username', 'password']}
    kwargs = kwargs_from_params(request, params)

    return staff_interface.do_first_time_setup(**kwargs)

def task_loginpanel(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['nexttask', 'wakaadminsave', 'nexttask', 'berra',
                       'desu'],
              'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)

    # Why are we doing this again?
    kwargs['username'] = kwargs.pop('desu')
    kwargs['password'] = kwargs.pop('berra')

    kwargs['save_login'] = kwargs.pop('wakaadminsave')
    kwargs['board'] = environ['waka.board']

    return staff_interface.do_login(**kwargs)

task_admin = task_loginpanel

def task_logout(environ, start_response):
    request = environ['werkzeug.request']
    
    admin = ''
    try:
        admin = request.cookies['wakaadmin']
    except KeyError:
        pass

    return staff_interface.do_logout(admin)

def task_mpanel(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['page'], 'cookies': ['wakaadmin']}
    kwargs = kwargs_from_params(request, params)
    kwargs['dest'] = staff_interface.BOARD_PANEL
    kwargs['board'] = environ['waka.board']

    return StaffInterface(**kwargs)

def task_bans(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = {}
    kwargs['ip'] = request.values.get('ip', '')
    kwargs['admin'] = get_cookie_from_request(request, 'wakaadmin')
    kwargs['dest'] = staff_interface.BAN_PANEL

    return StaffInterface(**kwargs)

def task_staff(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = {}
    try:
        kwargs['admin'] = get_cookie_from_request(request, 'wakaadmin')
    except KeyError:
        kwargs['admin'] = ''
    kwargs['dest'] = staff_interface.STAFF_PANEL

    return StaffInterface(**kwargs)

def task_spam(environ, start_response):
    request = environ['werkzeug.request']

    kwargs = {}
    try:
        kwargs['admin'] = get_cookie_from_request(request, 'wakaadmin')
    except KeyError:
        kwargs['admin'] = ''
    kwargs['dest'] = staff_interface.SPAM_PANEL

    return StaffInterface(**kwargs)

def task_reports(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form':    ['page', 'perpage', 'sortby', 'order'],
              'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)
    kwargs['sortby_type'] = kwargs.pop('sortby')
    kwargs['sortby_dir'] = kwargs.pop('order')
    kwargs['dest'] = staff_interface.REPORTS_PANEL

    return StaffInterface(**kwargs)

def task_addip(environ, start_response):
    request = environ['werkzeug.request']
    
    params = {'form':    ['type', 'comment', 'ip', 'mask', 'total',
                          'expiration'],
              'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)
    kwargs['option'] = kwargs.pop('type')

    return interboard.add_admin_entry(**kwargs)

def task_addstring(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['type', 'string', 'comment']}

    kwargs = kwargs_from_params(request, params)
    kwargs['option'] = kwargs.pop('type')
    kwargs['sval1'] = kwargs.pop('string')

    return interboard.add_admin_entry(**kwargs)

def task_removeban(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['num'], 'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)

    return interboard.remove_admin_entry(**kwargs)

# Interboard management.

def task_updatespam(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['spam'], 'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)

    return interboard.update_spam_file(**kwargs)

def task_deleteuserwindow(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['dest'] = staff_interface.DEL_STAFF_CONFIRM

    return StaffInterface(**kwargs)

def task_disableuserwindow(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['dest'] = staff_interface.DISABLE_STAFF_CONFIRM

    return StaffInterface(**kwargs)

def task_enableuserwindow(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['dest'] = staff_interface.ENABLE_STAFF_CONFIRM

    return StaffInterface(**kwargs)

def task_edituserwindow(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['dest'] = staff_interface.EDIT_STAFF_CONFIRM

    return StaffInterface(**kwargs)

def task_createuser(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'],
              'form':    ['mpass', 'usertocreate', 'passtocreate', 'account',
                          'reign']}

    kwargs = kwargs_from_params(request, params)
    kwargs['reign'] = kwargs.pop('reign').split(',')

    return staff_interface.add_staff_proxy(**kwargs)

def task_deleteuser(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['mpass', 'username']}

    kwargs = kwargs_from_params(request, params)

    return staff_interface.del_staff_proxy(**kwargs)

def task_disableuser(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['mpass', 'username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['disable'] = True

    return staff_interface.edit_staff_proxy(**kwargs)

def task_enableuser(environ, start_response):
    request = environ['werkzeug.request']

    params = {'cookies': ['wakaadmin'], 'form': ['mpass', 'username']}

    kwargs = kwargs_from_params(request, params)
    kwargs['disable'] = False

    return staff_interface.edit_staff_proxy(**kwargs)

def task_edituser(environ, start_response):
    request = environ['werkzeug.request']

    params = {'form': ['mpass', 'usernametoedit', 'newpassword', 'newclass',
                       'originalpassword'], 
              'cookies': ['wakaadmin']}

    kwargs = kwargs_from_params(request, params)
    kwargs['username'] = kwargs.pop('usernametoedit')
    kwargs['reign'] = request.form.getlist('reign')

    return staff_interface.edit_staff_proxy(**kwargs)

def task_move(environ, start_response):
    request = environ['werkzeug.request']
    
    kwargs = {}
    kwargs['parent'] = request.values.get('num', '')
    try:
        kwargs['admin'] = get_cookie_from_request(request, 'wakaadmin')
    except KeyError:
        kwargs['admin'] = ''
    kwargs['src_brd_obj'] = environ['waka.board']
    kwargs['dest_brd_obj'] = Board(request.values.get('destboard', ''))

    return interboard.move_thread(**kwargs)

# Error-handling

def fffffff(environ, start_response, error):
    start_response('200 OK', [('Content-Type', 'text/html')])

    mini = '_mini' if environ['waka.fromwindow'] else ''
    return Template('error_template' + mini, error=error.message)

MAIN_SITE_URL = 'http://www.desuchan.net'
def not_found(environ, start_response):
    '''Not found handler that redirects to desuchan
    Meant for the development server'''

    start_response('302 Found',
        [('Location', MAIN_SITE_URL + environ['PATH_INFO'])])
    return []
