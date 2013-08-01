#!/usr/bin/python

import os
import sys
import re

import fcgi
import werkzeug

import config, config_defaults
import app
import util
import model
import board
import interboard
from board import Board, NoBoard
from util import WakaError, local

@util.headers
def application(environ, start_response):
    '''Main routing application'''

    local.environ = environ
    request = werkzeug.BaseRequest(environ)

    task = request.values.get('task', request.values.get('action', ''))
    boardname = request.values.get('board', '')


    environ['waka.task'] = task
    environ['waka.boardname'] = boardname
    # Indicate "pop-up window" UI style.
    environ['waka.fromwindow'] = False
    environ['waka.rootpath'] = os.path.join('/', config.BOARD_DIR, '')

    if not task and not boardname:
        environ['waka.board'] = NoBoard()
        return app.check_setup(environ, start_response)

    environ['waka.board'] = NoBoard()
    try:
        if boardname:
            environ['waka.board'] = Board(boardname)
        elif task not in ('entersetup', 'setup', 'loginpanel'):
            raise WakaError("No board parameter set")
        elif task == 'loginpanel':
            raise WakaError("No board parameter set. "
                "If you haven't created boards yet, do it now.")
    except WakaError, e:
        return app.fffffff(environ, start_response, e)

    # the task function if it exists, otherwise no_task()
    function = getattr(app, 'task_%s' % task.lower(), app.no_task)

    try:
        interboard.remove_old_bans()
        interboard.remove_old_backups()
        return function(environ, start_response)
    except WakaError, e:
        return app.fffffff(environ, start_response, e)

def cleanup(*args, **kwargs):
    '''Destroy the thread-local session and environ'''
    session = model.Session()
    session.commit()
    session.transaction = None  # fix for a circular reference
    model.Session.remove()
    local.environ = {}

application = util.cleanup(application, cleanup)

def worker_commands(command, args):
    if command == 'rebuild_cache':
        board_name = args.pop(0)
    elif command == 'delete_by_ip':
        ip = args.pop(0)
        boards = args.pop(0).split(',')

    (local.environ['DOCUMENT_ROOT'], local.environ['SCRIPT_NAME'],
        local.environ['SERVER_NAME']) = args[:3]

    if command == 'rebuild_cache':
        board = Board(board_name)
        local.environ['waka.board'] = board
        board.rebuild_cache()

    elif command == 'rebuild_global_cache':
        interboard.global_cache_rebuild()

    elif command == 'delete_by_ip':
        interboard.process_global_delete_by_ip(ip, boards)

    cleanup()

def development_server():
    from werkzeug.serving import WSGIRequestHandler
    app_path = os.path.basename(__file__)

    werkzeug.run_simple('', 8000,
        util.wrap_static(application, app_path,
            index='wakaba.html',
            not_found_handler=app.not_found),
        use_reloader=True, use_debugger=config.DEBUG)

def main():
    # Set up tentative environment variables.
    local.environ['waka.rootpath'] \
        = os.path.join('/', config.BOARD_DIR, '')
    try:
        app.init_database()
    except model.OperationalError, e:
        # CGI-friendly error message
        print "Content-Type: text/plain\n"
        print "Error initializing database: %s" % e.args[0]
        return

    arg = sys.argv[1:] and sys.argv[1] or 'fcgi'
    if arg == 'fcgi':
        fcgi.WSGIServer(application).run()
    elif arg in ('rebuild_cache', 'rebuild_global_cache',
                         'delete_by_ip'):
        worker_commands(arg, sys.argv[2:])
    else:
        development_server()

if __name__ == '__main__':
    main()
