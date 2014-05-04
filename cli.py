import os
import sys
import inspect
import werkzeug

import util
import fcgi
import config
import board
import interboard
from util import local

COMMANDS = {}

# decorators

def command(f):
    COMMANDS[f.__name__] = f
    return f

def need_application(f):
    f.need_application = True
    return f

def need_environment(f):
    f.need_environment = True
    return f

# commands

@command
@need_environment
def rebuild_cache(board_name):
    """
    $0 rebuild_cache board_name
    """
    this_board = board.Board(board_name)
    local.environ['waka.board'] = this_board
    this_board.rebuild_cache()

@command
@need_environment
def delete_by_ip(ip, boards):
    """
    $0 delete_by_ip ip boards
    """
    boards = boards.split(",")

    interboard.process_global_delete_by_ip(ip, boards)

@command
@need_environment
def rebuild_global_cache():
    """
    $0
    """

    interboard.global_cache_rebuild()

def reset_password(username):
    """
    $0 reset_password username
    """
    import staff
    new_password = os.urandom(8).encode("base64").strip("=\n")

    try:
        staff.edit_staff(username, clear_pass=new_password)
    except staff.LoginError:
        print "No such user %r" % username
    else:
        print "Password of %r set to %r" % (username, new_password)

@command
@need_application
def http(application, host='', port=8000):
    """
    $0 http [host [port]]

    Defaults to listening on all interfaces, port 8000
    """

    app_path = os.path.basename(sys.argv[0])

    werkzeug.run_simple(host, int(port),
        util.wrap_static(application, app_path,
            index='wakaba.html'),
        use_reloader=True, use_debugger=config.DEBUG)

@command
@need_application
def fcgi_tcp(application, host='127.0.0.1', port=9000):
    """
    $0 fcgi_tcp [host [port]]

    Defaults to listening on 127.0.0.1, port 9000
    """
    fcgi.WSGIServer(application, bindAddress=(host, int(port))).run()

@command
@need_application
def fcgi_unix(application, path):
    """
    $0 fcgi_unix path
    """
    fcgi.WSGIServer(application, bindAddress=path).run()

@command
def help(command=None):
    """
    $0 help [command]
    """
    print "Wakarimasen CLI"

    f = COMMANDS.get(command, None)
    if f is None:
        print "Commands:", ', '.join(sorted(COMMANDS.keys()))
    else:
        docstring = str(f.__doc__).replace("$0", sys.argv[0])
        print "Usage:", docstring

def init_environ():
    """
    Initialize a wsgi-ish environment for commands.

    Tries to get variables from the OS env and checks for required ones.
    """

    ENV_VAR_HELP = """
    Environment variables explanation:
    - DOCUMENT_ROOT: full filesystem path to html files
      ex: /srv/http/imageboard.example.com/
    - SCRIPT_NAME: url to wakarimasen.py without host part
      ex: /wakarimasen.py
    - SERVER_NAME: hostname of the webserver
      ex: imageboard.example.com
    - SERVER_PORT: port of the webserver (optional)
      ex: 80
    """

    local.environ.update(os.environ)
    werkzeug.BaseRequest(local.environ)

    local.environ.setdefault('waka.rootpath',
        os.path.join('/', config.BOARD_DIR, ''))
    local.environ.setdefault('wsgi.url_scheme', 'http')
    local.environ.setdefault('SERVER_PORT', '80')

    required_vars = ['DOCUMENT_ROOT', 'SCRIPT_NAME', 'SERVER_NAME']

    for var in required_vars:
        if var not in local.environ:
            print "Error: %s not in environment" % (var,)
            print ENV_VAR_HELP
            sys.exit(1)

def handle_command(args, application):
    name = args.pop(0)
    f = COMMANDS.get(name, help)

    if hasattr(f, 'need_application'):
        args.insert(0, application)

    if hasattr(f, 'need_environment'):
        # Initialize environment
        init_environ()

    try:
        # attempt to call function with specified arguments
        inspect.getcallargs(f, *args)
    except TypeError:
        # it doesn't fit
        help(name)
        sys.exit(1)

    f(*args)
