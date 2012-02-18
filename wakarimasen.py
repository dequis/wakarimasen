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
from board import Board
from util import WakaError, local

@util.headers
def application(environ, start_response):
    '''Main routing application'''
    local.environ = environ
    request = werkzeug.BaseRequest(environ)

    task = request.values.get('task', request.values.get('action', ''))
    boardname = request.values.get('board', '9001') # temp. default value

    environ['waka.task'] = task
    environ['waka.boardname'] = boardname
    # Indicate "pop-up window" UI style.
    environ['waka.fromwindow'] = False
    environ['waka.rootpath'] = os.path.join('/', config.BOARD_DIR, '')
    environ['waka.board'] = Board(boardname)

    # the task function if it exists, otherwise no_task()
    function = getattr(app, 'task_%s' % task.lower(), app.no_task)

    try:
        interboard.remove_old_bans()
        return function(environ, start_response)
    except WakaError, e:
        return app.fffffff(environ, start_response, e)

def cleanup(environ, start_response):
    '''Destroy the thread-local session and environ'''
    session = model.Session()
    session.commit()
    session.transaction = None  # fix for a circular reference
    model.Session.remove()
    local.environ = {}

application = util.cleanup(application, cleanup)

def main():
    # Set up tentative environment variables.
    local.environ['waka.rootpath'] \
        = os.path.join('/', config.BOARD_DIR, '')
    local.environ['SCRIPT_NAME'] = sys.argv[0]
    local.environ['SERVER_NAME'] = config.SERVER_NAME

    app.init_database()
    arg = sys.argv[1:] and sys.argv[1] or 'fcgi'
    if arg == 'fcgi':
        fcgi.WSGIServer(application).run()
    elif sys.argv[1] == 'rebuild_cache':
        local.environ['DOCUMENT_ROOT'] = sys.argv[3]
        board = Board(sys.argv[2])
        local.environ['waka.board'] = board
        board.rebuild_cache()
    elif sys.argv[1] == 'rebuild_global_cache':
        local.environ['DOCUMENT_ROOT'] = sys.argv[2]
        interboard.global_cache_rebuild()
    else:
        werkzeug.run_simple('', 8000,
            util.wrap_static(application, __file__,
                index='wakaba.html',
                not_found_handler=app.not_found),
            use_reloader=True, use_debugger=config.DEBUG)

if __name__ == '__main__':
    main()
