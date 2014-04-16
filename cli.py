import os
import sys
import inspect
import werkzeug

import util
import fcgi
import config
import interboard
from board import Board
from util import local

COMMANDS = {}

# decorators

def command(f):
    COMMANDS[f.__name__] = f
    return f

def need_application(f):
    f.need_application = True
    return f

# commands

def set_env_vars(*args):
    (local.environ['DOCUMENT_ROOT'],
     local.environ['SCRIPT_NAME'],
     local.environ['SERVER_NAME']) = args[:3]

@command
def rebuild_cache(board_name, *env_vars):
    """
    $0 rebuild_cache board_name document_root script_name server_name
    """
    set_env_vars(*env_vars)

    board = Board(board_name)
    local.environ['waka.board'] = board
    board.rebuild_cache()

@command
def delete_by_ip(ip, boards, *env_vars):
    """
    $0 delete_by_ip ip boards document_root script_name server_name
    """
    boards = boards.split(",")
    set_env_vars(*env_vars)

    interboard.process_global_delete_by_ip(ip, boards)

@command
def rebuild_global_cache(*env_vars):
    """
    $0 document_root script_name server_name
    """
    set_env_vars(*env_vars)

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
def fcgi_tcp(application, host='', port=9000):
    """
    $0 fcgi_tcp [host [port]]

    Defaults to listening on all interfaces, port 9000
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

def handle_command(args, application):
    name = args.pop(0)
    f = COMMANDS.get(name, help)

    if getattr(f, 'need_application', False):
        args.insert(0, application)

    try:
        # attempt to call function with specified arguments
        inspect.getcallargs(f, *args)
    except TypeError:
        # it doesn't fit
        return help(name)

    f(*args)
