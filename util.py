import os
import mimetypes
import functools

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
