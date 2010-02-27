import os
import sys
import mimetypes
import functools

class WakaError(Exception):
    '''Error to be reported to the user'''
    def __init__(self, message, fromwindow=False):
        self.message = message
        self.fromwindow = fromwindow

    def __str__(self):
        return self.message

def wrap_static(application, *app_paths):
    '''Application used in the development server to serve static files
    (i.e. everything except the CGI filename). DO NOT USE IN PRODUCTION'''
    
    @functools.wraps(application)
    def wrapper(environ, start_response):
        filename = environ['PATH_INFO'].strip('/')

        if filename in app_paths or not filename:
            return application(environ, start_response)
        elif os.path.exists(filename):
            content, encoding = mimetypes.guess_type(filename)
            headers = [('Content-Type', content),
                       ('Content-Encoding', encoding)]
            start_response('200 OK', [x for x in headers if x[1]])
            return open(filename)
        else:
            start_response('404 Not found', [('Content-Type', 'text/plain')])
            return ['404 Not found: %s' % filename]
    
    return wrapper

def module_default(modulename, defaults):
    '''Set default values to modulename
    Keys which start with underscores are ignored'''

    module = __import__(modulename)
    for key in defaults:
        if not key.startswith('_') and not hasattr(module, key):
            setattr(module, key, defaults[key])
