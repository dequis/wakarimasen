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
        session = model.Session()

        # TODO: check if the database exists?
        # if not, build cache and redirect

