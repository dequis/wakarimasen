import model
from template import Template
from util import WakaError

def no_task(environ, start_response):
    board = environ['waka.board']
    board.build_cache(environ)
    start_response('302 Found', [('Location', board.url)])
    return []

def init_database():
    model.metadata.create_all()
    # TODO: cleanup backups table

def task_post(environ, start_response):
    request = environ['werkzeug.request']
    board = environ['waka.board']

    params = ['parent', 'field1', 'email', 'subject', 'comment',
        'password', 'nofile', 'captcha', 'wakaadmin', 'no_captcha',
        'no_format', 'sticky', 'lock', 'adminpost']
    kwargs = {}
    for param in params:
        kwargs[param] = request.form.get(param, '')

    kwargs['file'] = request.files['file']
    kwargs['name'] = kwargs.pop('field1')
    kwargs['admin'] = kwargs.pop('wakaadmin')
    kwargs['admin_post_mode'] = kwargs.pop('adminpost')
    kwargs['oekaki_post'] = kwargs['srcinfo'] = kwargs['pch'] = None
    kwargs['environ'] = environ
    
    return board.post_stuff(**kwargs)

def fffffff(environ, start_response, error):
    start_response('200 OK', [('Content-Type', 'text/html')])
    return Template('error_template', error=error.message, environ=environ)

MAIN_SITE_URL = 'http://www.desuchan.net'
def not_found(environ, start_response):
    '''Not found handler that redirects to desuchan
    Meant for the development server'''

    start_response('302 Found',
        [('Location', MAIN_SITE_URL + environ['PATH_INFO'])])
    return []
