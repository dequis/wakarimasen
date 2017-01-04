import os
import re
import time
import sys
import hashlib
import mimetypes
from subprocess import Popen, PIPE

import misc
import str_format
import util
import model
import staff
import staff_interface
# NOTE: I'm not sure if interboard is a good module to have here.
import interboard
import config
import strings as strings
from util import WakaError, local
from template import Template
from wakapost import WakaPost

try:
    import board_config_defaults
except ImportError:
    board_config_defaults = None

from sqlalchemy.sql import case, or_, and_, select, func, null

class Board(object):
    def __init__(self, board):
        # Correct for missing key when running under WSGI
        if 'DOCUMENT_ROOT' not in local.environ:
            local.environ['DOCUMENT_ROOT'] = os.getcwd()

        # For WSGI mode (which does not initialize this for whatever reason).
        board_path = os.path.abspath(os.path.join(\
                                        local.environ['DOCUMENT_ROOT'],
                                        config.BOARD_DIR,
                                        board))
        if not os.path.exists(board_path):
            raise BoardNotFound()
        if not os.path.exists(os.path.join(board_path, 'board_config.py')):
            raise BoardNotFound('Board configuration not found.')

        module = util.import2('board_config', board_path)

        if board_config_defaults:
            self.options = board_config_defaults.config.copy()
            self.options.update(module.config)
        else:
            self.options = module.config

        self.table = model.board(self.options['SQL_TABLE'])

        # TODO likely will still need customization
        self.path = board_path
        url_path = os.path.join('/', os.path.relpath(\
                                          board_path,
                                          local.environ['DOCUMENT_ROOT']), '')
        self.url = str_format.percent_encode(url_path)
        self.name = board

    def make_path(self, file='', dir='', dirc=None, page=None, thread=None,
                  ext=config.PAGE_EXT, abbr=False, hash=None, url=False,
                  force_http=False):
        '''Builds an url or a path'''
        if url:
            base = self.url
            if force_http:
                base = 'http://' + local.environ['SERVER_NAME'] + base
        else:
            base = self.path

        if page is not None:
            if page == 0:
                file = self.options['HTML_SELF']
                ext = None
            else:
                file = str(page)

        if dirc:
            dir = self.options[dirc]

        if thread is not None:
            dir = self.options['RES_DIR']
            file = str(thread)

        if hash is not None:
            hash = '#%s' % hash
        else:
            hash = ''

        if file:
            if abbr:
                file += '_abbr'
            if ext is not None:
                file += '.' + ext.lstrip(".")
            return os.path.join(base, dir, file) + hash
        else:
            return os.path.join(base, dir) + hash

    def check_access(self, user):
        user.check_access(self.name)
        return user

    def make_url(self, **kwargs):
        '''Alias for make_path to build urls'''
        kwargs['url'] = True
        return self.make_path(**kwargs)

    def _get_all_threads(self):
        '''Build a list of threads from the database,
        where each thread is a list of WakaPost instances'''

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
            thread.append(WakaPost(post))
        threads.append(thread)

        return threads

    def get_some_threads(self, page):
        '''Grab a partial list of threads for pre-emptive pagination.'''

        session = model.Session()
        table = self.table
        thread_dict = {}
        thread_nums = []

        per_page = self.options['IMAGES_PER_PAGE']
        # Page is zero-indexed, so offset formula must differ.
        offset = page * per_page

        # Query 1: Grab all thread (OP) entries.
        op_sql = table.select().where(table.c.parent == 0).order_by(
                    table.c.stickied.desc(),
                    table.c.lasthit.desc(),
                    table.c.num.asc()
                ).limit(per_page).offset(offset)
        op_query = session.execute(op_sql)

        for op in op_query:
            thread_dict[op.num] = [WakaPost(op)]
            thread_nums.append(op.num)

        # Query 2: Grab all reply entries and process.
        reply_sql = table.select().where(table.c.parent.in_(thread_nums))\
                    .order_by(table.c.stickied.desc(),
                        table.c.num.asc()
                    )
        reply_query = session.execute(reply_sql)

        for post in reply_query:
            thread_dict[post.parent].append(WakaPost(post))

        return [thread_dict[num] for num in thread_nums]

    def build_cache(self):
        threads = self._get_all_threads()

        per_page = self.options['IMAGES_PER_PAGE']
        total = get_page_count(threads, per_page)

        for page in xrange(total):
            pagethreads = threads[page * per_page:\
                          min(len(threads), (page + 1) * per_page)]
            self.build_cache_page(page, total, pagethreads)

        # check for and remove old pages
        page = total
        while os.path.exists(self.make_path(page=page)):
            os.unlink(self.make_path(page=page))
            page += 1

        if config.ENABLE_RSS:
            self.update_rss()

    def rebuild_cache(self):
        self.build_thread_cache_all()
        self.build_cache()

    def rebuild_cache_proxy(self, task_data):
        task_data.user.check_access(self.name)

        task_data.contents.append(self.name)

        Popen([sys.executable, sys.argv[0], 'rebuild_cache', self.name],
            env=util.proxy_environ())

        return util.make_http_forward(
            misc.make_script_url(task='mpanel', board=self.name),
            config.ALTERNATE_REDIRECT)

    def parse_page_threads(self, pagethreads):
        threads = []
        for postlist in pagethreads:
            if len(postlist) == 0:
                continue
            elif len(postlist) > 1:
                parent, replies = postlist[0], postlist[1:]
            else:
                parent, replies = postlist[0], []

            images = [x for x in replies if x.filename]

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
                if post.filename:
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

        return threads

    def get_board_page_data(self, page, total, admin_page=''):
        if page >= total:
            if total:
                page = total - 1
            else:
                page = 0

        pages = []
        for i in xrange(total):
            p = {}
            p['page'] = i
            if admin_page:
                # Admin mode: direct to staff interface, not board pages.
                p['filename'] = misc.make_script_url(task=admin_page,
                    board=self.name, page=i, _amp=True)
            else:
                p['filename'] = self.make_url(page=i)
            p['current'] = page == i
            pages.append(p)
        prevpage = nextpage = 'none'

        key_select = 'page' if admin_page else 'filename'
        if page != 0:
            prevpage = pages[page - 1][key_select]
        if page != total - 1 and total:
            nextpage = pages[page + 1][key_select]

        return (pages, prevpage, nextpage)

    def build_cache_page(self, page, total, pagethreads):
        '''Build $rootpath/$board/$page.html'''

        # Receive contents.
        threads = self.parse_page_threads(pagethreads)

        # Calculate page link data.
        (pages, prevpage, nextpage) = self.get_board_page_data(page, total)

        # Generate filename and links to other pages.
        filename = self.make_path(page=page)

        Template('page_template',
            pages=pages,
            postform=self.options['ALLOW_TEXTONLY'] \
              or self.options['ALLOW_IMAGES'],
            image_inp=self.options['ALLOW_IMAGES'],
            textonly_inp=(self.options['ALLOW_IMAGES'] \
              and self.options['ALLOW_TEXTONLY']),
            prevpage=prevpage,
            nextpage=nextpage,
            threads=threads,
        ).render_to_file(filename)

    def get_thread_posts(self, threadid):
        session = model.Session()
        sql = self.table.select(
            or_(
                self.table.c.num == threadid,
                self.table.c.parent == threadid
            )).order_by(self.table.c.num.asc())
        query = session.execute(sql)

        thread = []

        for post in query:
            thread.append(WakaPost(post))

        if not len(thread):
            raise WakaError('Thread not found.')

        if thread[0].parent:
            raise WakaError(strings.NOTHREADERR)

        return thread

    def build_thread_cache(self, threadid):
        '''Build $rootpath/$board/$res/$threadid.html'''

        thread = self.get_thread_posts(threadid)

        filename = os.path.join(self.path, self.options['RES_DIR'],
            "%s%s" % (threadid, config.PAGE_EXT))

        def print_thread(thread, filename, **kwargs):
            '''Function to avoid duplicating code with abbreviated pages'''
            Template('page_template',
                threads=[{'posts': thread}],
                thread=threadid,
                postform=self.options['ALLOW_TEXT_REPLIES'] \
                         or self.options['ALLOW_IMAGE_REPLIES'],
                image_inp=self.options['ALLOW_IMAGE_REPLIES'],
                textonly_inp=0,
                dummy=thread[-1].num,
                lockedthread=thread[0].locked,
                **kwargs
            ).render_to_file(filename)

        print_thread(thread, filename)

        # Determine how many posts need to be cut.
        posts_to_trim = len(thread) - config.POSTS_IN_ABBREVIATED_THREAD_PAGES

        # Filename for Last xx Posts Page.
        abbreviated_filename = os.path.join(self.path,
            self.options['RES_DIR'], 
            "%s_abbr%s" % (threadid, config.PAGE_EXT))

        if config.ENABLE_ABBREVIATED_THREAD_PAGES and posts_to_trim > 1:
            op = thread[0]
            thread = thread[posts_to_trim:]
            thread.insert(0, op)

            if len(thread) > 1:
                min_res = thread[1].num
            else:
                min_res = op.num

            print_thread(thread, abbreviated_filename,
                omit=posts_to_trim - 1, min_res=min_res)
        else:
            if os.path.exists(abbreviated_filename):
                os.unlink(abbreviated_filename)

    def delete_thread_cache(self, parent, archiving):
        archive_dir = self.options['ARCHIVE_DIR']

        base = os.path.join(self.path, self.options['RES_DIR'], '')
        full_filename = "%s%s" % (parent, config.PAGE_EXT)
        full_thread_page = base + full_filename
        abbrev_thread_page = base + "%s_abbr%s" % (parent, config.PAGE_EXT)
        if archiving:
            archive_base = os.path.join(self.path,
                                        self.options['ARCHIVE_DIR'],
                                        self.options['RES_DIR'], '')
            try:
                os.makedirs(archive_base, 0o755)
            except os.error:
                pass
            # umask a shit
            if os.path.isdir(archive_base): os.chmod(archive_base, 0o755)

            archive_thread_page = archive_base + full_filename

            with open(full_thread_page, 'r') as res_in:
                with open(archive_thread_page, 'w') as res_out:
                    for line in res_in:
                        # Update thumbnail links.
                        line = re.sub(r'img src="(.*?)'
                                          + self.options['THUMB_DIR'],
                                      r'img src="\1'
                                          + os.path.join(archive_dir,
                                              self.options['THUMB_DIR'], ''),
                                      line)
                        # Update image links.
                        line = re.sub(r'a href="(.*?)'
                                          + self.options['IMG_DIR'],
                                      r'a href="\1'
                                          + os.path.join(archive_dir,
                                              self.options['IMG_DIR'], ''),
                                      line)
                        # Update reply links.
                        line = re.sub(r'a href="(.*?)'
                            + os.path.join(self.path,
                                           self.options['RES_DIR'], ''),
                            r'a href="\1' + os.path.join(\
                                           self.path,
                                           self.options['RES_DIR'], ''),
                            line)

                        res_out.write(line)

        if os.path.exists(full_thread_page):
            os.unlink(full_thread_page)
        if os.path.exists(abbrev_thread_page):
            os.unlink(abbrev_thread_page)

    def build_thread_cache_all(self):
        session = model.Session()
        sql = select([self.table.c.num], self.table.c.parent == 0)
        query = session.execute(sql)

        for row in query:
            self.build_thread_cache(row[0])

    def _handle_post(self, wakapost, editing=None, admin_data=None):
        """Worst function ever"""

        session = model.Session()

        # get a timestamp for future use
        timestamp = time.time()

        if admin_data:
            admin_data.user.check_access(self.name)
            wakapost.admin_post = True

        # run several post validations - raises exceptions
        wakapost.validate(editing, admin_data, self.options)

        # check whether the parent thread is stickied
        if wakapost.parent:
            self.sticky_lock_check(wakapost, admin_data)
            self.sticky_lock_update(wakapost.parent, wakapost.stickied,
                wakapost.locked)

        ip = local.environ['REMOTE_ADDR']
        numip = misc.dot_to_dec(ip)

        wakapost.set_ip(numip, editing)

        # set up cookies
        wakapost.make_post_cookies(self.options, self.url)

        # check if IP is whitelisted
        whitelisted = misc.is_whitelisted(numip)

        if not whitelisted and not admin_data:
            # check for bans
            interboard.ban_check(numip, wakapost.name,
                wakapost.subject, wakapost.comment)

            # check for spam matches
            trap_fields = []
            if self.options['SPAM_TRAP']:
                trap_fields = ['name', 'link']

            misc.spam_engine(trap_fields, config.SPAM_FILES)

            # check for open proxies
            if self.options['ENABLE_PROXY_CHECK']:
                self.proxy_check(ip)

        # check if thread exists, and get lasthit value
        parent_res = None
        if not editing:
            wakapost.timestamp = timestamp
            if wakapost.parent:
                parent_res = self.get_parent_post(wakapost.parent)
                if not parent_res:
                    raise WakaError(strings.NOTHREADERR)
                wakapost.lasthit = parent_res.lasthit
            else:
                wakapost.lasthit = timestamp

        # split tripcode and name
        wakapost.set_tripcode(self.options['TRIPKEY'])

        # clean fields
        wakapost.clean_fields(editing, admin_data, self.options)

        # flood protection - must happen after inputs have been cleaned up
        self.flood_check(numip, timestamp, wakapost.comment,
            wakapost.req_file, editing is None, False)

        # generate date
        wakapost.set_date(editing, self.options['DATE_STYLE'])

        # generate ID code if enabled
        if self.options['DISPLAY_ID']:
            wakapost.date += ' ID:' + \
                self.make_id_code(ip, timestamp, wakapost.email)

        # copy file, do checksums, make thumbnail, etc
        if wakapost.req_file:
            if editing and (editing.filename or editing.thumbnail):
                self.delete_file(editing.filename, editing.thumbnail)

            # TODO: this process_file is just a thin wrapper around awful code
            wakapost.process_file(self, editing is not None)

        # choose whether we need an SQL UPDATE (editing) or INSERT (posting)
        if editing:
            db_update = self.table.update().where(
                self.table.c.num == wakapost.num)
        else:
            db_update = self.table.insert()

        db_update = db_update.values(**wakapost.db_values)

        # finally, write to the database
        result = session.execute(db_update)

        if not editing:
            if wakapost.parent:
                self.update_bump(wakapost, parent_res)

            wakapost.num = result.inserted_primary_key[0]

        # remove old threads from the database
        self.trim_database()

        # update the cached HTML pages
        self.build_cache()

        # update the individual thread cache
        self.build_thread_cache(wakapost.parent or wakapost.num)

        return wakapost.num

    def post_stuff(self, wakapost, admin_data=None):

        # For use with noko, below.
        parent = wakapost.parent or wakapost.num
        noko = wakapost.noko

        try:
            post_num = self._handle_post(wakapost, admin_data=admin_data)
        except util.SpamError:
            forward = self.make_path(page=0, url=True)
            return util.make_http_forward(forward, config.ALTERNATE_REDIRECT)

        forward = ''
        if not admin_data:
            if not noko:
                # forward back to the main page
                forward = self.make_path(page=0, url=True)
            else:
                # ...unless we have "noko" (a la 4chan)--then forward to
                # thread ("parent" contains current post number if a new
                # thread was posted)
                if not os.path.exists(self.make_path(thread=parent,
                                      abbr=True)):
                    forward = self.make_url(thread=parent)
                else:
                    forward = self.make_url(thread=parent, abbr=True)
        else:
            # forward back to the mod panel
            kwargs = dict(task='mpanel', board=self.name)

            if noko:
                kwargs['page'] = "t%s" % parent

            forward = misc.make_script_url(**kwargs)

            admin_data.contents.append('/%s/%d' % (self.name, post_num))

        return util.make_http_forward(forward, config.ALTERNATE_REDIRECT)
        # end of this function. fuck yeah

    def edit_gateway_window(self, post_num):
        return self._gateway_window(post_num, 'edit')

    def delete_gateway_window(self, post_num):
        return self._gateway_window(post_num, 'delete')

    def _gateway_window(self, post_num, task):
        if not post_num.isdigit():
            raise WakaError('Please enter post number.')

        wakapost = self.get_post(post_num)
        if not wakapost:
            raise WakaError(strings.POSTNOTFOUND)

        template_name = 'password' if task == 'edit' else 'delpassword'
        return Template(template_name, admin_post=wakapost.admin_post, num=post_num)

    def get_local_reports(self):
        session = model.Session()
        table = model.report
        sql = table.select().where(and_(table.c.board == self.name,
                                        table.c.resolved == 0))
        query = session.execute(sql).fetchall()
        reported_posts = [dict(row.items()) for row in query]

        rowtype = 1
        for row in reported_posts:
            # Alternate between rowtypes 1 and 2.
            rowtype ^= 0x3
            row['rowtype'] = rowtype

        return reported_posts

    def delete_by_ip(self, task_data, ip, mask='255.255.255.255'):
        if task_data and not task_data.contents:
            task_data.contents.append(ip + ' (' + mask + ')' + ' @ ' \
                                      + self.name)

        try:
            ip = int(ip)
        except ValueError:
            ip = misc.dot_to_dec(ip)

        try:
            mask = int(mask)
        except ValueError:
            mask = misc.dot_to_dec(mask or '255.255.255.255')

        session = model.Session()
        table = self.table

        sql = table.select().where(and_(
            table.c.ip.op('&')(mask) == ip & mask,
            table.c.timestamp > (time.time() - config.NUKE_TIME_THRESHOLD)
        ))
        rows = session.execute(sql)

        if not rows.rowcount:
            return

        timestamp = None
        if config.POST_BACKUP:
            timestamp = time.time()

        for row in rows:
            try:
                self.delete_post(row.num, '', False, False, admin=True,
                                 timestampofarchival=timestamp)
            except WakaError:
                pass

        self.build_cache()

    def delete_stuff(self, posts, password, file_only, archiving,
                     caller='user', admindelete=False,
                     admin_data=None, from_window=False):
        if caller == 'internal':
            # Internally called; force admin.
            admindelete = True

        timestamp = None
        if config.POST_BACKUP:
            timestamp = time.time()

        for post in posts:
            self.delete_post(post, password, file_only, archiving,
                             from_window=False, admin=admindelete,
                             timestampofarchival=timestamp,
                             admin_data=admin_data)

        self.build_cache()

        if admindelete:
            forward = misc.make_script_url(task='mpanel', board=self.name)
        else:
            forward = self.make_path(page=0, url=True)
        if caller == 'user':
            return util.make_http_forward(forward, config.ALTERNATE_REDIRECT)

    def delete_post(self, post, password, file_only, archiving,
                    admin_data=None, from_window=False, admin=False,
                    timestampofarchival=None, recur=False):
        '''Delete a single post from the board. This method does not rebuild
        index cache automatically.'''

        session = model.Session()
        table = self.table

        row = self.get_post(post)

        if row is None:
            raise WakaError(strings.POSTNOTFOUND % (int(post), self.name))

        if not admin:
            archiving = False

            if row.admin_post:
                raise WakaError(strings.MODDELETEONLY)

            if password != row.password:
                raise WakaError("Post #%s: %s" % (post, strings.BADDELPASS))

        if config.POST_BACKUP and not archiving:
            if not timestampofarchival:
                timestampofarchival = time.time()
            sql = model.backup.insert().values(board_name=self.name,
                                               postnum=row.num,
                                               parent=row.parent,
                                               timestamp=row.timestamp,
                                               lasthit=row.lasthit,
                                               ip=row.ip,
                                               date=row.date,
                                               name=row.name,
                                               trip=row.trip,
                                               email=row.email,
                                               subject=row.subject,
                                               password=row.password,
                                               comment=row.comment,
                                               image=row.filename,
                                               size=row.size,
                                               md5=row.md5,
                                               width=row.width,
                                               height=row.height,
                                               thumbnail=row.thumbnail,
                                               tn_width=row.tn_width,
                                               tn_height=row.tn_height,
                                               lastedit=row.lastedit,
                                               lastedit_ip=row.lastedit_ip,
                                               admin_post=row.admin_post,
                                               stickied=row.stickied,
                                               locked=row.locked,
                                               timestampofarchival=\
                                                  timestampofarchival)
            session.execute(sql)

        if file_only:
            # remove just the image and update the database
            select_post_image = select([table.c.image, table.c.thumbnail],
                                       or_(table.c.num == post))
            baleet_me = session.execute(select_post_image).fetchone()

            if baleet_me.image and baleet_me.thumbnail:
                self.delete_file(baleet_me.image, baleet_me.thumbnail,
                                 archiving=archiving)

            postupdate = table.update().where(table.c.num == post).values(
                size=0, md5=null(), thumbnail=null())
            session.execute(postupdate)

        else:
            if config.POST_BACKUP and not archiving:
                select_thread_images \
                    = select([table.c.image, table.c.thumbnail],
                             table.c.num == post)
            else:
                select_thread_images \
                    = select([table.c.image, table.c.thumbnail],
                             or_(table.c.num == post, table.c.parent == post))
            images_to_baleet = session.execute(select_thread_images)

            for i in images_to_baleet:
                if i.image and i.thumbnail:
                    self.delete_file(i.image, i.thumbnail, archiving=archiving)

            if config.POST_BACKUP and not archiving:
                delete_query = table.delete(table.c.num == post)
            else:
                delete_query = table.delete(or_(
                    table.c.num == post, table.c.parent == post))
            session.execute(delete_query)

            # Also back-up child posts.
            if config.POST_BACKUP and not archiving:
                sql = select([table.c.num], table.c.parent == post)
                sel_posts = session.execute(sql).fetchall()
                for i in [p[0] for p in sel_posts]:
                    self.delete_post(i, '', False, False,
                                     from_window=from_window, admin=True,
                                     recur=True)

        # Cache building
        if not row.parent:
            if file_only:
                # removing parent (OP) image
                self.build_thread_cache(post)
            else:
                # removing an entire thread
                self.delete_thread_cache(post, archiving)
        elif not recur:
            # removing a reply, or a reply's image
            self.build_thread_cache(row.parent)

        if admin_data:
            admin_data.contents.append('/%s/%d' % (self.name, int(post)))

    def delete_file(self, relative_file_path, relative_thumb_path,
                    archiving=False):
        full_file_path = os.path.join(self.path, relative_file_path)
        full_thumb_path = os.path.join(self.path, relative_thumb_path)
        archive_base = os.path.join(self.path,
                                    self.options['ARCHIVE_DIR'], '')
        backup_base = os.path.join(archive_base, self.options['BACKUP_DIR'])

        if config.POST_BACKUP:
            for path in (archive_base, backup_base,
                        os.path.join(archive_base,self.options['IMG_DIR']),
                        os.path.join(archive_base,self.options['THUMB_DIR'])):
                try:
                    os.makedirs(path, 0o755)
                except os.error:
                    pass
                # umask a shit
                if os.path.isdir(path): os.chmod(path, 0o755)

        full_archive_path = os.path.join(archive_base,
                                         relative_file_path)
        full_tarchive_path = os.path.join(archive_base,
                                          relative_thumb_path)
        full_backup_path = os.path.join(backup_base,
                                        os.path.basename(relative_file_path))
        full_tbackup_path = os.path.join(backup_base, 
                                         os.path.basename(relative_thumb_path))

        if os.path.isfile(full_file_path):
            if archiving:
                os.renames(full_file_path, full_archive_path)
                os.chmod(full_archive_path, 0644)
            elif config.POST_BACKUP:
                os.renames(full_file_path, full_backup_path)
                os.chmod(full_backup_path, 0644)
            else:
                os.unlink(full_file_path)
        if os.path.isfile(full_thumb_path):
            if archiving:
                os.renames(full_thumb_path, full_tarchive_path)
                os.chmod(full_tarchive_path, 0644)
            elif config.POST_BACKUP:
                os.renames(full_thumb_path, full_tbackup_path)
                os.chmod(full_tbackup_path, 0644)
            else:
                os.unlink(full_thumb_path)

    def remove_backup_stuff(self, admin_data, posts, restore=False):
        user = admin_data.user
        user.check_access(self.name)

        if restore:
            admin_data.action = 'backup_restore'

        for post in posts:
            self.remove_backup_post(admin_data, post, restore=restore)
            # Log.
            admin_data.contents.append('/%s/%d' % (self.name, int(post)))

        # Board pages need refereshing.
        self.build_cache()

        return staff_interface.StaffInterface(user.login_data.cookie,
                                              board=self,
                                              dest=staff_interface.TRASH_PANEL)

    def remove_backup_post(self, task_data, post, restore=False, child=False):
        session = model.Session()
        table = model.backup
        sql = table.select().where(and_(table.c.postnum == post,
                                        table.c.board_name == self.name))
        row = session.execute(sql).fetchone()

        if not row:
            raise WakaError('Backup record not found for post %s.' % (post))

        arch_dir = os.path.join(self.path,
                                self.options['ARCHIVE_DIR'],
                                self.options['BACKUP_DIR'], '')
        if row.image:
            arch_image = os.path.join(arch_dir, os.path.basename(row.image))
        else:
            arch_image = None
        if row.thumbnail:
            arch_thumb = os.path.join(arch_dir, os.path.basename(row.thumbnail))
        else:
            arch_thumb = None

        if restore:
            my_table = self.table
            if row.parent and not child:
                sql = my_table.select().where(my_table.c.num == row.parent)
                parent = session.execute(sql).fetchone()
                if not parent:
                    raise WakaError('Cannot restore post %s: '
                                    'Parent thread deleted.' % (post))
                stickied = parent.stickied
                locked = parent.locked
                lasthit = parent.lasthit
            else:
                stickied = row.stickied
                locked = row.locked
                lasthit = row.lasthit

            # Perform insertion.
            sql = my_table.insert().values(num=row.postnum,
                                           parent=row.parent,
                                           timestamp=row.timestamp,
                                           lasthit=lasthit,
                                           ip=row.ip,
                                           date=row.date,
                                           name=row.name,
                                           trip=row.trip,
                                           email=row.email,
                                           subject=row.subject,
                                           password=row.password,
                                           comment=row.comment,
                                           image=row.image,
                                           size=row.size,
                                           md5=row.md5,
                                           width=row.width,
                                           height=row.height,
                                           thumbnail=row.thumbnail,
                                           tn_width=row.tn_width,
                                           tn_height=row.tn_height,
                                           lastedit=row.lastedit,
                                           lastedit_ip=row.lastedit_ip,
                                           admin_post=row.admin_post,
                                           stickied=stickied,
                                           locked=locked)
            session.execute(sql)

            # Move file/thumb.
            if arch_image and os.path.exists(arch_image):
                os.renames(arch_image, os.path.join(self.path, row.image))
                os.chmod(os.path.join(self.path, row.image), 0o644)
            if arch_thumb and os.path.exists(arch_thumb):
                os.renames(arch_thumb, os.path.join(self.path, row.thumbnail))
                os.chmod(os.path.join(self.path, row.thumbnail), 0o644)

            if not child:
                if row.parent:
                    self.build_thread_cache(row.parent)
                else:
                    self.build_thread_cache(row.postnum)
        else:
            # Delete file/thumb.
            if arch_image and os.path.exists(arch_image):
                os.unlink(arch_image)
            if arch_thumb and os.path.exists(arch_thumb):
                os.unlink(arch_thumb)

        # Remove (and restore if appropriate) all thread backups made at the
        # point of archival.
        if not row.parent:
            sql = table.select(and_(table.c.parent == row.postnum,
                                    table.c.board_name == self.name,
                                    table.c.timestampofarchival\
                                        == row.timestampofarchival))\
                       .order_by(table.c.num.asc())
            for row in session.execute(sql):
                self.remove_backup_post(None, row.postnum, restore=restore,
                                        child=True)

        sql = table.delete().where(and_(table.c.postnum == post,
                                        table.c.board_name == self.name))
        session.execute(sql)

    def make_report_post_window(self, posts, from_window=False):
        if len(posts) == 0:
            raise WakaError('No posts selected.')
        if len(posts) > 10:
            raise WakaError('Too many posts. Try reporting the thread ' \
                            + 'or a single post in the case of floods.')

        num_parsed = ', '.join(posts)
        referer = ''
        if not from_window:
            referer = self.url

        return Template('post_report_window', num=num_parsed, referer=referer)

    def report_posts(self, comment, referer, posts):
        numip = misc.dot_to_dec(local.environ['REMOTE_ADDR'])

        # Sanity checks.
        if not comment:
            raise WakaError('Please input a comment.')
        if len(comment) > config.REPORT_COMMENT_MAX_LENGTH:
            raise WakaError('Comment is too long.')
        if len(comment) < 3:
            raise WakaError('Comment is too short.')
        if len(posts) > 10:
            raise WakaError('Too many posts. Try reporting the thread or a '\
                            + 'single post in the case of floods.')

        # Access checks.
        whitelisted = misc.is_whitelisted(numip)
        if not whitelisted:
            interboard.ban_check(numip, '', '', '')
        self.flood_check(numip, time.time(), comment, '', False, True)

        # Clear up the backlog.
        interboard.trim_reported_posts()

        comment = str_format.format_comment(str_format.clean_string(
                str_format.decode_string(comment)))

        session = model.Session()
        reports_table = model.report

        # Handle errors individually rather than cancelling operation.
        errors = []

        for post in posts:
            if not post.isdigit():
                errors.append({'error' : '%s: Invalid post number.' % (post)})
                continue

            sql = select([self.table.c.ip], self.table.c.num == post,
                         self.table)
            post_row = session.execute(sql).fetchone()

            if not post_row:
                errors.append({'error' \
                    : '%s: Post not found (likely deleted).' % (post) })
                continue

            # Store offender IP in case this post is deleted later.
            offender_ip = post_row.ip

            sql = reports_table.select()\
                .where(and_(reports_table.c.postnum == post,
                            reports_table.c.board == self.name))
            report_row = session.execute(sql).fetchone()

            if report_row:
                if report_row['resolved']:
                    errors.append({'error' : '%s: Already resolved.' \
                                             % (post)})
                else:
                    errors.append({'error' : '%s: Already reported.' \
                                             % (post)})
                continue

            timestamp = time.time()
            date = misc.make_date(timestamp, self.options['DATE_STYLE'])

            # File report.
            sql = reports_table.insert().values(reporter=numip,
                                                board=self.name,
                                                offender=offender_ip,
                                                postnum=post,
                                                comment=comment,
                                                timestamp=timestamp,
                                                date=date,
                                                resolved=0)
            session.execute(sql)

        return Template('report_submitted', errors=errors,
                        error_occurred=len(errors)>0,
                        referer=referer)

    def edit_window(self, post_num, cookie, password, admin_mode=False):
        wakapost = self.get_post(post_num)

        if wakapost is None:
            raise WakaError('Post not found')

        if admin_mode:
            staff.StaffMember.get_from_cookie(cookie).check_access(self)
        elif password != wakapost.password:
            raise WakaError('Wrong pass for editing') # TODO

        return Template('post_edit_template', loop=[wakapost],
                                              admin=admin_mode)

    def edit_stuff(self, request_post, admin_data=None):

        original_post = self.get_post(request_post.num)

        if not original_post:
            raise WakaError('Post not found')

        if not admin_data and request_post.password != original_post.password:
            raise WakaError('Wrong password for editing')

        edited_post = WakaPost.copy(original_post)
        edited_post.merge(request_post, which='request')

        if edited_post.killtrip:
            edited_post.trip = ''

        try:
            self._handle_post(edited_post, original_post, admin_data)
        except util.SpamError:
            return Template('edit_successful')

        if admin_data:
            admin_data.contents.append(
                '/%s/%d' % (self.name, int(request_post.num)))

        return Template('edit_successful')

    def process_file(self, filestorage, timestamp, parent, editing):
        filetypes = self.options.get('EXTRA_FILETYPES', [])

        # analyze file and check that it's in a supported format
        ext, width, height = misc.analyze_image(filestorage.stream,
            filestorage.filename)

        known = (width != 0 or ext in filetypes)
        if not (self.options['ALLOW_UNKNOWN'] or known) or \
               ext in self.options['FORBIDDEN_EXTENSIONS']:
            raise WakaError(strings.BADFORMAT)

        maxw, maxh, maxp = self.options['MAX_IMAGE_WIDTH'], \
            self.options['MAX_IMAGE_HEIGHT'], self.options['MAX_IMAGE_PIXELS']
        if (maxw and width > maxw) or (maxh and height > maxh) or \
               (maxp and (width * height) > maxp):
            raise WakaError(strings.BADFORMAT)

        # generate "random" filename
        filebase = ("%.3f" % timestamp).replace(".", "")
        filename = self.make_path(filebase, dirc='IMG_DIR', ext=ext)


        if not known:
            filename += self.options['MUNGE_UNKNOWN']

        # copy file
        try:
            filestorage.save(filename)
        except IOError:
            raise WakaError(strings.NOTWRITE)

        # Check file type with UNIX utility file()
        file_response = Popen(["file", filename], stdout=PIPE)\
                        .communicate()[0]
        if re.match("\:.*(?:script|text|executable)", file_response):
            os.unlink(filename)
            raise WakaError(strings.BADFORMAT + " Potential Exploit")

        # Generate thumbnail based on file
        if file_response.find('JPEG') != -1:
            thumb_ext = 'jpg'
        elif file_response.find('GIF') != -1:
            thumb_ext = 'gif'
        elif file_response.find('PNG') != -1:
            thumb_ext = 'png'
        else:
            thumb_ext = os.path.splitext(filename)[1]
        thumbnail = self.make_path(filebase + "s", dirc='THUMB_DIR',
                                   ext=thumb_ext)

        # get the checksum
        md5h = hashlib.md5()
        filestorage.stream.seek(0)
        while True:
            buffer = filestorage.stream.read(16 * 1024)
            if not buffer:
                break
            md5h.update(buffer)
        md5 = md5h.hexdigest()

        # check for duplicate files
        if (not editing  and \
            (parent and self.options['DUPLICATE_DETECTION'] == 'thread') or
             self.options['DUPLICATE_DETECTION'] == 'board'):
            session = model.Session()

            # Check dupes in same thread
            if self.options['DUPLICATE_DETECTION'] == 'thread':
                sql = self.table.select("md5=:md5 AND (parent=:parent OR "
                    "num=:num)").params(md5=md5, parent=parent, num=parent)
                result = session.execute(sql)
            else: # Check dupes throughout board
                sql = self.table.select("md5=:md5").params(md5=md5)
                result = session.execute(sql)

            match = result.fetchone()
            if match:
                os.unlink(filename) # make sure to remove the file
                raise WakaError(strings.DUPE %
                    self.get_reply_link(match['num'], parent))

        # do thumbnail
        tn_width = tn_height = 0
        tn_ext = ''

        if not width:  # unsupported file
            if ext in filetypes: # externally defined filetype
                # Compensate for absolute paths, if given.
                icon = config.ICONS.get(ext, None)
                if icon:
                    if icon.startswith('/'):
                        icon = os.path.join(local.environ['DOCUMENT_ROOT'],
                                            icon.lstrip("/"))
                    else:
                        icon = os.path.join(self.path, icon)

                if icon and os.path.exists(icon):
                    tn_ext, tn_width, tn_height = \
                        misc.analyze_image(open(icon, "rb"), icon)
                else:
                    tn_ext, tn_width, tn_height = ('', 0, 0)

                # was that icon file really there?
                if tn_width:
                    thumbnail = icon
                else:
                    thumbnail = ''
            else:
                thumbnail = ''

        elif width > self.options['MAX_W'] or \
             height > self.options['MAX_H'] or \
             self.options['THUMBNAIL_SMALL']:

            if width <= self.options['MAX_W'] and \
               height <= self.options['MAX_H']:
                tn_width = width
                tn_height = height
            else:
                tn_width = self.options['MAX_W']
                tn_height = height * self.options['MAX_W'] / width
                if tn_height > self.options['MAX_H']:
                    tn_width = width * self.options['MAX_H'] / height
                    tn_height = self.options['MAX_H']

            if self.options['STUPID_THUMBNAILING']:
                thumbnail = filename
            else:
                tn_width, tn_height \
                    = misc.make_thumbnail(filename, thumbnail, tn_width,
                        tn_height, self.options['THUMBNAIL_QUALITY'],
                        self.options['CONVERT_COMMAND'])
                if not tn_width and tn_height:
                    thumbnail = ''
        else:
            tn_width = width
            tn_height = height
            thumbnail = filename

        # restore the name for extensions in KEEP_NAME_FILETYPES
        # or, if it doesn't exist, for all the ones in filetypes
        if ext in self.options.get('KEEP_NAME_FILETYPES', filetypes):

            # cut off any directory in the original filename
            newfilename = self.make_path(filestorage.filename.split("/")[-1],
                                         dirc='IMG_DIR', ext=None)


            # verify no name clash
            if not os.path.exists(newfilename):
                os.rename(filename,
                          newfilename.encode(sys.getfilesystemencoding()))
                if thumbnail == filename:
                    thumbnail = newfilename 
                filename = newfilename
            else:
                os.unlink(filename)
                raise WakaError(strings.DUPENAME)

        if self.options['ENABLE_LOAD']:
            # TODO, some day
            raise NotImplementedError('ENABLE_LOAD not implemented')

        # Make file and thumbnail world-readable
        os.chmod(filename, 0644)
        if thumbnail:
            os.chmod(thumbnail, 0644)

        # Clear out the board path name.
        filename = filename.replace(self.path, '').lstrip('/')
        if thumbnail.startswith(self.path):
            thumbnail = thumbnail.replace(self.path, '').lstrip('/')
        else:
            thumbnail = thumbnail.replace(local.environ['DOCUMENT_ROOT'], '')

        return (filename.encode(sys.getfilesystemencoding()), md5, width,
                height, thumbnail, tn_width, tn_height)

    def get_reply_link(self, reply, parent='', abbreviated=False,
                       force_http=False):
        if parent:
            return self.make_url(thread=parent, hash=reply, abbr=abbreviated,
                force_http=force_http)
        else:
            return self.make_url(thread=reply, abbr=abbreviated,
                force_http=force_http)

    def expand_url(self, filename, force_http=False):
        # TODO: mark this as deprecated?

        # Is the filename already expanded?
        # The generic regex tests for http://, https://, ftp://, etc.
        if filename.startswith("/") or re.match('\w+:', filename):
            return filename

        if force_http:
            host_url = local.environ['werkzeug.request'].host_url.strip('/')
            self_path = host_url + self.url
        else:
            self_path = self.url

        return os.path.join(self_path, str_format.percent_encode(filename))

    def make_anonymous(self, ip, time):
        # TODO: SILLY_ANONYMOUS not supported
        return self.options['S_ANONAME']

    def make_id_code(self, ip, timestamp, link):
        # TODO not implemented
        raise NotImplementedError()

    def get_post(self, num):
        '''Returns None or WakaPost'''
        session = model.Session()
        sql = self.table.select(self.table.c.num == num)
        row = session.execute(sql).fetchone()
        if row:
            return WakaPost(row)

    def get_parent_post(self, parentid):
        session = model.Session()
        sql = self.table.select(and_(self.table.c.num == parentid,
            self.table.c.parent == 0))
        query = session.execute(sql)
        return WakaPost(query.fetchone())

    def sage_count(self, parent):
        session = model.Session()
        sql = select([func.count()], 'parent=:parent AND '
            'NOT (timestamp<:timestamp AND ip=:ip)', self.table).params(
                parent=parent.num,
                timestamp=parent.timestamp + self.options['NOSAGE_WINDOW'],
                ip=parent.ip)
        row = session.execute(sql).fetchone()
        return row[0]

    def trim_database(self):
        session = model.Session()
        table = self.table
        max_age = self.options['MAX_AGE']

        # Clear expired posts due to age.
        if max_age:
            mintime = time.time() - max_age * 3600

            sql = table.select().where(and_(table.c.parent == 0,
                                            table.c.timestamp <= mintime,
                                            table.c.stickied == 0))
            query = session.execute(sql)

            for row in query:
                self.delete_post(row.num, '', False,
                                 self.options['ARCHIVE_MODE'], admin=True)

        # TODO: Implement other maxes (even though no one freakin' uses
        #       them). :3c

    def toggle_thread_state(self, task_data, num, operation,
                            enable_state=True):

        task_data.user.check_access(self.name)

        # Check thread
        session = model.Session()
        table = self.table
        sql = select([table.c.parent], table.c.num == num, table)
        row = session.execute(sql).fetchone()

        if not row:
            raise WakaError('Thread %s,%s not found.' % (self.name, num))
        if row['parent']:
            raise WakaError(strings.NOTATHREAD)

        update = {}
        if operation == 'sticky':
            update = {'stickied' : 1 if enable_state else 0}
        else:
            update = {'locked' : 'yes' if enable_state else ''}

        sql = table.update().where(or_(table.c.num == num,
                                       table.c.parent == num))\
                            .values(**update)
        session.execute(sql)

        self.build_cache()

        task_data.contents.append('/%s/%s' % (self.name, num))

        forward_url = misc.make_script_url(task='mpanel', board=self.name)

        return util.make_http_forward(forward_url, config.ALTERNATE_REDIRECT)

    def flood_check(self, ip, timestamp, comment, file, no_repeat,
                    report_check):
        session = model.Session()

        flood_param = self.options['RENZOKU']
        table = self.table
        ip_column = table.c.ip
        err_str = strings.RENZOKU

        if report_check:
            flood_param = config.REPORT_RENZOKU
            table = model.report
            ip_column = table.c.reporter
        elif file:
            # File posts get different flooding rules.
            err_str = strings.RENZOKU2
            flood_param = self.options['RENZOKU2']

        maxtime = time.time() - flood_param

        sql = select([func.count()],
                     and_(ip_column == ip, table.c.timestamp > maxtime))
        row = session.execute(sql).fetchone()

        if row[0] != 0:
            raise WakaError(err_str)

        if no_repeat and not report_check and not file:
            # Check for repeated text-only messsages.
            maxtime = time.time() - self.options['RENZOKU3']
            sql = select([func.count()],
                         and_(ip_column == ip, table.c.comment == comment,
                              timestamp > maxtime))
            row = session.execute(sql).fetchone()
            if row[0] != 0:
                raise WakaError(strings.RENZOKU3)

    def update_rss(self):
        rss_file = os.path.join(self.path, 'board.rss')

        session = model.Session()
        table = self.table
        sql = table.select().order_by(table.c.num.desc())\
                   .limit(config.RSS_LENGTH)

        posts = [dict(post.items()) for post in session.execute(sql)]
        for post in posts:
            filename = post['image']
            if filename:
                post['mime_type'] = mimetypes.guess_type(filename)[0]

        Template('rss_template', items=posts,
                 pub_date=misc.make_date(time.time(), 'http'))\
                 .render_to_file(rss_file)

    def proxy_check(self, ip):
        session = model.Session()

        # TODO proxy_clean

        sql = select([func.count()], 'type="black" AND ip=:ip',
            model.proxy).params(ip=ip)
        row = session.execute(sql).fetchone()
        if row and row[0]:
            raise WakaError(strings.PROXY, plain=True)

        sql = select([func.count()], 'type="white" AND ip=:ip',
            model.proxy).params(ip=ip)
        row = session.execute(sql).fetchone()
        is_white = (row and row[0])

        timestamp = time.time()
        date = misc.make_date(timestamp, self.options['DATE_STYLE'])

        if is_white:
            # known good IP, refresh entry
            sql = model.proxy.update().where(model.proxy.c.ip == ip)\
                .values(timestamp=timestamp, date=date)
            session.execute(sql)
        else:
            # unknown IP, check for proxy

            # enterprise command launching system
            # may send crap to stderr on failure
            retval = os.system(self.options['PROXY_COMMAND'] + " %s" % ip)

            sql = model.proxy.insert().values(ip=ip,
                timestamp=timestamp, date=date)

            retval_blacklist = self.options.get('PROXY_RETVAL_BLACKLIST', 100)
            if retval == retval_blacklist:
                session.execute(sql.values(type='black'))
                raise WakaError(strings.PROXY, plain=True)
            else:
                session.execute(sql.values(type='white'))

    def sticky_lock_check(self, wakapost, admin_mode):
        '''Checks for sticky status (or locked) and updates the whole thread
        if it's possible to post there. Raises exception on locked thread.
        Modifies wakapost if needed.'''

        sticky_check = model.Session().execute(
            select([self.table.c.stickied, self.table.c.locked],
                self.table.c.num == wakapost.parent)).fetchone()

        if sticky_check is None:
            raise WakaError('Thread not found.')

        if sticky_check['stickied']:
            wakapost.stickied = True
        elif not admin_mode:
            wakapost.stickied = False

        if sticky_check['locked'] == 'yes':
            if not admin_mode:
                raise WakaError(strings.THREADLOCKEDERROR)
            else:
                wakapost.locked = True

        return (wakapost.stickied, wakapost.locked)

    def sticky_lock_update(self, parent, stickied, locked):
        '''Update the whole thread to make it all sticky or locked'''

        threadupdate = self.table.update().where(
            or_(self.table.c.num == parent,
                self.table.c.parent == parent))
        do_thread_update = False

        if stickied:
            threadupdate = threadupdate.values(stickied=1)
            do_thread_update = True

        if locked:
            threadupdate = threadupdate.values(locked='yes')
            do_thread_update = True

        if do_thread_update:
            model.Session().execute(threadupdate)

    def update_bump(self, wakapost, parent_res):
        '''Bumping - check for sage, or too many replies'''

        if (wakapost.email.lower() == "mailto:sage" or
             self.sage_count(parent_res) > self.options['MAX_RES']):
            return

        model.Session().execute(self.table.update()
            .where(or_(self.table.c.num == wakapost.parent,
                       self.table.c.parent == wakapost.parent))
            .values(lasthit=wakapost.timestamp))

class NoBoard(object):
    '''Object that provides the minimal attributes to use a few templates
    when no board is defined.'''
    name = ''
    path = ''
    options = {
        'FAVICON': '',
        'DEFAULT_STYLE': 'futaba',
    }

    def expand_url(self, url, force_http=False):
        return url

# utility functions

def get_page_count(threads, per_page):
    return (len(threads) + per_page - 1) / per_page

def abbreviate_html(html, max_lines, approx_len):
    lines = chars = 0
    stack = []

    if not max_lines:
        return

    for match in re.finditer("(?:([^<]+)|<(/?)(\w+).*?(/?)>)", html):
        text, closing, tag, implicit = match.groups()
        tag = tag.lower() if tag else ''

        if text:
            chars += len(text)
        else:
            if not closing and not implicit:
                stack.append(tag)
            if closing:
                try:
                    stack.pop()
                except IndexError:
                    pass

            if (closing or implicit) and (tag in ('p', 'blockquote',
                'pre', 'li', 'ol', 'ul', 'br')):
                lines += (chars / approx_len) + 1
                if tag in ('p', 'blockquote'):
                    lines += 1
                chars = 0

            if lines > max_lines:
                # check if there's anything left other than end-tags
                if re.match("^(?:\s*</\w+>)*\s*$", html[match.end():]):
                    return

                abbrev =  html[:match.end()]
                while stack:
                    tag = stack.pop()
                    abbrev += "</%s>" % tag
                return abbrev

class BoardNotFound(WakaError):
    def __init__(self, message='Board not found'):
        WakaError.__init__(self, message)
