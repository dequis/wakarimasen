#!/usr/bin/python

import os
import sys

import fcgi
import werkzeug

import app
import util

def application(environ, start_response):
    '''Main routing application'''
    request = werkzeug.BaseRequest(environ)
    task = request.args.get('task', request.args.get('action', None))
    board = request.args.get('board', None)

    if task is None:
        return app.no_task(environ, start_response)
    elif task:
        funcname = 'task_' + task
        if hasattr(app, funcname):
            return getattr(app, funcname)(environ, start_response)
    
    return werkzeug.Response('task=%s board=%s' % (task, board)) \
        (environ, start_response)
    

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
