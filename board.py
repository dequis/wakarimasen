import os

import model
import config, config_defaults
from util import WakaError, import2
from template import Template

from sqlalchemy.sql import case

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

    def _get_all_threads(self):
        '''Build a list of threads from the database,
        where each thread is a list of CompactPost instances'''

        session = model.Session()
        table = self.ormclass.__table__
        sql = table.select().order_by(table.c.stickied.desc(),
            table.c.lasthit.desc(),
            case({0: table.c.num}, table.c.parent, table.c.parent).asc(),
            table.c.num.asc()
        )
        query = session.execute(sql)

        threads = []
        thread = []
        for post in query:
            if thread and not post.parent:
                threads.append(thread)
                thread = []
            thread.append(model.CompactPost(post))
        threads.append(thread)

        return threads

    def build_cache(self, environ={}):
        threads = self._get_all_threads()
        
        per_page = self.options['IMAGES_PER_PAGE']
        total = get_page_count(threads, per_page)

        for page in xrange(total):
            pagethreads = threads[page * per_page:(page + 1) * per_page]
            self.build_cache_page(page, total, pagethreads, environ)

        # check for and remove old pages
        page += 1
        while os.path.exists(self.get_page_filename(page)):
            os.unlink(self.get_page_filename(page))
            page += 1

    def build_cache_page(self, page, total, pagethreads, environ={}):
        filename = self.get_page_filename(page)
        
        threads = []
        for postlist in pagethreads:
            parent, replies = postlist[0], postlist[1:]
            images = [x for x in replies if x.image]

            if parent.stickied:
                max_replies = config.REPLIES_PER_STICKY
            else:
                max_replies = self.options['REPLIES_PER_THREAD']

            max_images = self.options['IMAGE_REPLIES_PER_THREAD'] \
                or len(images)

            thread = {}
            thread['omit'] = 0
            thread['omitimages'] = 0
            while len(replies) > max_replies or len(images) > max_images:
                post = replies.pop(0)
                thread['omit'] += 1
                if post.image:
                    thread['omitimages'] += 1

            thread['posts'] = [parent] + replies
            
            for post in thread['posts']:
                abbreviation = abbreviate_html(post.comment,
                    self.options['MAX_LINES_SHOWN'],
                    self.options['APPROX_LINE_LENGTH'])

                if abbreviation:
                    post.abbrev = 1
                    post.comment = abbreviation

            threads.append(thread)
        
        pages = []
        for i in xrange(total):
            p = {}
            p['page'] = i
            p['filename'] = self.get_page_url(page)
            p['current'] = page == i
            pages.append(p)
	
        prevpage = nextpage = None
        if page != 0:
            prevpage = pages[page - 1]['filename']
        if page != total - 1:
            nextpage = pages[page + 1]['filename']

        Template('page_template',
            pages=pages,
            postform=self.options['ALLOW_TEXTONLY'] or self.options['ALLOW_IMAGES'],
            image_inp=self.options['ALLOW_IMAGES'],
            textonly_inp=(self.options['ALLOW_IMAGES'] and self.options['ALLOW_TEXTONLY']),
            prevpage=prevpage,
            nextpage=nextpage,
            threads=threads,
            board=self,
            environ=environ
        ).render_to_file(filename)

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

