#!/usr/bin/python

import os
import sys

import fcgi
import werkzeug

import app
import util
import model
from board import Board
from util import WakaError

@util.headers
def application(environ, start_response):
    '''Main routing application'''
    request = werkzeug.BaseRequest(environ)
    task = request.args.get('task', request.args.get('action', None))
    boardname = request.args.get('board', None)
    environ['waka.task'] = task
    environ['waka.boardname'] = boardname
    if boardname:
        environ['waka.board'] = Board(boardname)
    else:
        # temporary
        environ['waka.board'] = Board('9001')

    # the task function if it exists, otherwise no_task()
    function = getattr(app, 'task_%s' % task, app.no_task)

    try:
        return function(environ, start_response)
    except WakaError, e:
        return app.error(environ, start_response, e)

def cleanup(environ, start_response):
    '''Destroy the thread-local session'''
    session = model.Session()
    session.commit()
    session.transaction = None  # fix for a circular reference
    model.Session.remove()

application = util.cleanup(application, cleanup)

def main():
    server = sys.argv[1:] and sys.argv[1] or 'fcgi'
    if server == 'fcgi':
        fcgi.WSGIServer(application).run()
    else:
        werkzeug.run_simple('', 8000,
            util.wrap_static(application, __file__),
            use_reloader=True, use_debugger=True)

if __name__ == '__main__':
    main()
