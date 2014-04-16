import os
import sys
import time
import errno
import imp
import Cookie
import threading
import mimetypes
import functools
import strings

class DefaultLocal(threading.local):
    environ = {}

    # shortcuts
    board = property(lambda self: self.environ['waka.board'])
    request = property(lambda self: self.environ['werkzeug.request'])

local = DefaultLocal()

class WakaError(Exception):
    '''Error to be reported to the user'''
    def __init__(self, message, fromwindow=False, plain=False):
        self.message = message
        self.fromwindow = fromwindow
        self.plain = plain

    def __str__(self):
        return self.message

class SpamError(WakaError):
    '''Specialized spam-catch error for potential catching.'''
    def __init__(self, message=None, fromwindow=False):
        message = message or strings.SPAM
        super(SpamError, self).__init__(message, fromwindow)

def wrap_static(application, *app_paths, **kwds):
    '''Application used in the development server to serve static files
    (i.e. everything except the CGI filename). DO NOT USE IN PRODUCTION'''
    
    @functools.wraps(application)
    def wrapper(environ, start_response):
        filename = environ['PATH_INFO'].strip('/')
        environ['DOCUMENT_ROOT'] = os.getcwd()

        if filename in app_paths or not filename:
            environ['SCRIPT_NAME'] = '/' + filename
            return application(environ, start_response)

        if os.path.isdir(filename):
            index = kwds.get('index', 'index.html')
            filename = os.path.join(filename, index)

        if os.path.exists(filename):
            content, encoding = mimetypes.guess_type(filename)
            headers = [('Content-Type', content),
                       ('Content-Encoding', encoding)]
            start_response('200 OK', [x for x in headers if x[1]])
            return open(filename)
        else:
            handler = kwds.get('not_found_handler', None)
            if handler:
                return handler(environ, start_response)
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

def import2(name, path):
    '''Imports a module from path without requiring a __init__.py file'''

    fullname = '%s.%s' % (path, name)

    if fullname in sys.modules:
        return sys.modules[fullname]
    else:
        modinfo = imp.find_module(name, [path])
        module = imp.load_module(fullname, *modinfo)
        modinfo[0].close() # the docs say i must close this :(
        return module

def headers(f):
    '''Decorator that allows sending output without calling start_response
    It replaces start_response with a backwards-compatible version that
    doesn't do anything if called more than once.'''

    @functools.wraps(f)
    def wrapper(environ, start_response):
        environ['waka.status'] = '200 OK'
        environ['waka.headers'] = {'Content-Type': 'text/html'}
        environ['waka.response_sent'] = False
        environ['waka.cookies'] = Cookie.BaseCookie()

        def new_start_response(status, headers):
            if environ['waka.response_sent']:
                return
            environ['waka.response_sent'] = True

            # merge parameter headers with the environ ones
            environ['waka.headers'].update(dict(headers))

            # Set-cookie can be repeated, so it's handled separately
            headerlist = environ['waka.headers'].items()
            for cookie in environ['waka.cookies'].itervalues():
                headerlist.append(tuple(cookie.output().split(": ", 1)))

            start_response(status, headerlist)
            
        appiter = f(environ, new_start_response)
        new_start_response(environ['waka.status'], environ['waka.headers'])
        return appiter
    return wrapper

def cleanup(application, cleanup_function):
    '''Pseudo-decorator that calls a cleanup function always after an app
    is run. This is needed because the apps may return the iterator before
    execution is done'''

    @functools.wraps(application)
    def wrapper(environ, start_response):
        try:
            appiter = application(environ, start_response)
            for item in appiter:
                yield item
        finally:
            cleanup_function(environ, start_response)
    return wrapper

def make_http_forward(location, alternate_method=False):
    '''Pseudo-application to redirect to another location. The location
    parameter is assumed to be properly decoded and escaped.'''

    if alternate_method:
        return [str('<html><head>'
                '<meta http-equiv="refresh" content="0; url=%s" />'
                '<script type="text/javascript">document.location="%s";'
                '</script></head><body><a href="%s">%s</a></body></html>' %\
                ((location, ) * 4))]
    else:
        local.environ['waka.status'] = '303 Go West'
        local.environ['waka.headers']['Location'] = location
        return [str('<html><body><a href="%s">%s</a></body></html>' %\
                ((location, ) * 2))]

# The following code was ripped from
# http://www.evanfosmark.com/2009/01/
#   cross-platform-file-locking-support-in-python/
# I can't really improve on this to my knowledge.
 
class FileLockException(Exception):
    pass

class FileLock(object):
    """ A file locking mechanism that has context-manager support so 
        you can use it in a with statement. This should be relatively cross
        compatible as it doesn't rely on msvcrt or fcntl for the locking.
    """
 
    def __init__(self, file_name, timeout=10, delay=.05):
        """ Prepare the file locker. Specify the file to lock and optionally
            the maximum timeout and the delay between each attempt to lock.
        """
        self.is_locked = False
        self.lockfile = os.path.join(os.getcwd(), "%s.lock" % file_name)
        self.file_name = file_name
        self.timeout = timeout
        self.delay = delay
 
 
    def acquire(self):
        """ Acquire the lock, if possible. If the lock is in use, it check again
            every `wait` seconds. It does this until it either gets the lock or
            exceeds `timeout` number of seconds, in which case it throws 
            an exception.
        """
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lockfile, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                break;
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise 
                if (time.time() - start_time) >= self.timeout:
                    raise FileLockException("Timeout occured.")
                time.sleep(self.delay)
        self.is_locked = True
 
 
    def release(self):
        """ Get rid of the lock by deleting the lockfile. 
            When working in a `with` statement, this gets automatically 
            called at the end.
        """
        if self.is_locked:
            os.close(self.fd)
            os.unlink(self.lockfile)
            self.is_locked = False
 
 
    def __enter__(self):
        """ Activated when used in the with statement. 
            Should automatically acquire a lock to be used in the with block.
        """
        if not self.is_locked:
            self.acquire()
        return self
 
 
    def __exit__(self, type, value, traceback):
        """ Activated at the end of the with statement.
            It automatically releases the lock if it isn't locked.
        """
        if self.is_locked:
            self.release()
 
 
    def __del__(self):
        """ Make sure that the FileLock instance doesn't leave a lockfile
            lying around.
        """
        self.release()
