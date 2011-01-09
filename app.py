import model
from template import Template
from util import WakaError

def no_task(environ, start_response):
    board = environ['waka.board']
    board.build_cache()
    start_response('302 Found', [('Location', board.url)])
    return []

def init_database():
    model.metadata.create_all()
    # TODO: cleanup backups table

# Posting
def task_post(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = ['parent', 'field1', 'email', 'subject', 'comment',
        'password', 'nofile', 'captcha', 'wakaadmin', 'no_captcha',
        'no_format', 'sticky', 'lock', 'adminpost']
    kwargs = {}
    for param in params:
        kwargs[param] = request.values.get(param, '')

    kwargs['file'] = request.files['file']
    kwargs['name'] = kwargs.pop('field1')
    kwargs['admin'] = kwargs.pop('wakaadmin')
    kwargs['admin_post_mode'] = kwargs.pop('adminpost')
    kwargs['oekaki_post'] = kwargs['srcinfo'] = kwargs['pch'] = None
    # kwargs['environ'] = environ
    
    return board.post_stuff(**kwargs)

# Post Deletion
def task_delete(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    kwargs = {}
    params = ['password', 'file_only', 'archiving', 'from_window']
    for param in params:
        kwargs[param] = request.form.get(param, '')

    # Parse posts string into array.
    kwargs['posts'] = request.form.getlist('num')

    return board.delete_stuff(**kwargs)

def task_delpostwindow(environ, start_response):
    pass

# Post Editing
def edit_param_parse(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = ['num', 'field1', 'email', 'subject', 'comment',
        'password', 'nofile', 'captcha', 'wakaadmin', 'no_captcha',
        'no_format', 'sticky', 'lock', 'adminedit', 'killtrip',
        'postfix']
    kwargs = {}
    for param in params:
        kwargs[param] = request.values.get(param, '')
 
    kwargs['file'] = request.files['file']
    kwargs['name'] = kwargs.pop('field1')
    kwargs['post_num'] = kwargs.pop('num')
    kwargs['admin'] = kwargs.pop('wakaadmin')
    kwargs['admin_post_mode'] = kwargs.pop('adminedit')
    kwargs['oekaki_post'] = kwargs['srcinfo'] = kwargs['pch'] = None
    # kwargs['environ'] = environ

    return kwargs

# TODO: Really, this should be called task_editwindow.
def task_edit(environ, start_response):
    kwargs = edit_param_parse(environ, start_response)
    pass

# TODO: Really, this should be called task_edit.
def task_editpost(environ, start_response):
    kwargs = edit_param_parse(environ, start_response)
    return board.edit_stuff(**kwargs)

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
