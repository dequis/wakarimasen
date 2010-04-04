import os

import model
import config, config_defaults
import strings_en as strings
from util import WakaError, import2
from template import Template

from sqlalchemy.sql import case, or_, select

class Board(object):
    def __init__(self, board):
        if not os.path.exists(board):
            raise WakaError('Board not found.')
        if not os.path.exists(os.path.join(board, 'board_config.py')):
            raise WakaError('Board configuration not found.')
        
        module = import2('board_config', board)

        self.options = module.config
        
        self.table = model.board(self.options['SQL_TABLE'])

        # TODO customize these
        self.path = os.path.abspath(board)
        self.url = '/%s/' % board

    def _get_all_threads(self):
        '''Build a list of threads from the database,
        where each thread is a list of CompactPost instances'''

        session = model.Session()
        table = self.table
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
        '''Build /board/$page.html'''
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

    def build_thread_cache(self, threadid, environ={}):
        '''Build /board/res/$threadid.html'''

        session = model.Session()
        sql = self.table.select(
            or_(
                self.table.c.num == threadid,
                self.table.c.parent == threadid
            )).order_by(self.table.c.num.asc())
        query = session.execute(sql)

        thread = []

        for post in query:
            thread.append(model.CompactPost(post))

        if thread[0].parent:
            raise WakaError(strings.NOTHREADERR)

        filename = os.path.join(self.path, self.options['RES_DIR'],
            "%s%s" % (threadid, config.PAGE_EXT))

        def print_thread(thread, filename, **kwargs):
            '''Function to avoid duplicating code with abbreviated pages'''
            Template('page_template',
                threads=[{'posts': thread}],
                thread=threadid,
                postform=self.options['ALLOW_TEXT_REPLIES'] or self.options['ALLOW_IMAGE_REPLIES'],
                image_inp=self.options['ALLOW_IMAGE_REPLIES'],
                textonly_inp=0,
                dummy=thread[-1].num,
                lockedthread=thread[0].locked,
                board=self,
                environ=environ,
                **kwargs
            ).render_to_file(filename)

        print_thread(thread, filename)

        # Determine how many posts need to be cut.
        posts_to_trim = len(thread) - config.POSTS_IN_ABBREVIATED_THREAD_PAGES

        # Filename for Last xx Posts Page.
        abbreviated_filename = os.path.join(self.path, self.options['RES_DIR'], 
            "%s_abbr%s" % (threadid, config.PAGE_EXT))

        if config.ENABLE_ABBREVIATED_THREAD_PAGES and posts_to_trim > 1:
            op = thread[0]
            thread = thread[posts_to_trim:]
            thread.insert(0, op)

            print_thread(thread, abbreviated_filename,
                omit=posts_to_trim - 1)
        else:
            if os.path.exists(abbreviated_filename):
                os.unlink(abbreviated_filename)

    def delete_thread_cache(self, parent):
        base = os.path.join(self.path, self.options['RES_DIR'], '')
        os.unlink(base + "%s%s" % (parent, config.PAGE_EXT))
        os.unlink(base + "%s_abbr%s" % (parent, config.PAGE_EXT))

    def build_thread_cache_all(self, environ={}):
        session = model.Session()
        sql = select([self.table.c.num], self.table.c.parent == 0)
        query = session.execute(sql)
        
        for row in query:
            self.build_thread_cache(row[0], environ)

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

