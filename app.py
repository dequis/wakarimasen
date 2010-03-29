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

def error(environ, start_response, error):
    start_response('200 OK', [('Content-Type', 'text/html')])
    return Template('error_template', error=error.message, environ=environ)

MAIN_SITE_URL = 'http://www.desuchan.net'
def not_found(environ, start_response):
    '''Not found handler that redirects to desuchan
    Meant for the development server'''

    start_response('302 Found',
        [('Location', MAIN_SITE_URL + environ['PATH_INFO'])])
    return []
