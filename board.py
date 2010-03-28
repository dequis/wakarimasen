import os

import model
import config, config_defaults
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

    def _get_page_filename(self, page):
        '''Returns either wakaba.html or (page).html'''
        if page == 0:
            return self.options['HTML_SELF']
        else:
            return "%s%s" % (page, config.PAGE_EXT)

    def get_page_filename(self, page):
        '''Returns the local path to a file in the board'''
        return os.path.join(self.path, self._get_page_filename(page))

    def get_page_url(self, page):
        return self.expand_url(self._get_page_filename(page))
        
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

# utility functions

def get_page_count(threads, per_page):
    return (len(threads) + per_page - 1) / per_page

def abbreviate_html(html, max_lines, approx_len):
    # TODO: implement abbreviate_html
    return

