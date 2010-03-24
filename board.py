import os
import model
from util import WakaError, import2

class Board(object):
    def __init__(self, board):
        if not os.path.exists(board):
            raise WakaError('Board not found.')
        if not os.path.exists(os.path.join(board, 'board_config.py')):
            raise WakaError('Board configuration not found.')
        
        module = import2('board_config', board)

        self.options = module.config
        
        self.ormclass = model.board(board)

        # TODO customize these
        self.path = os.path.abspath(board)
        self.url = '/%s/' % board

    def expand_url(self, filename, force_http=False, environ={}):
        '''When force_http is true, the environ parameter is required
        TODO: have a SERVER_NAME entry in config'''

        # TODO: is this the same as the intended in wakaba?
        if filename.startswith("/") or filename.startswith("http"):
            return filename

        self_path = self.url

        if force_http:
            self_path = 'http://' + environ['SERVER_NAME'] + self_path

        return self_path + filename



