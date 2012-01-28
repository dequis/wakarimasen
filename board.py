import os
import re
import time
import random
import hashlib
from subprocess import Popen, PIPE
from urllib import quote, urlencode

import misc
import str_format
import oekaki
import util
import model
import staff
# NOTE: I'm not sure if interboard is a good module to have here.
import interboard
import config
import strings as strings
from util import WakaError, local
from template import Template

from sqlalchemy.sql import case, or_, and_, select, func, null

class Board(object):
    def __init__(self, board):
        board_path = os.path.abspath(os.path.join(\
                                        local.environ['DOCUMENT_ROOT'],
                                        config.BOARD_DIR,
                                        board))
        if not os.path.exists(board_path):
            raise BoardNotFound()
        if not os.path.exists(os.path.join(board_path, 'board_config.py')):
            raise BoardNotFound('Board configuration not found.')
        
        module = util.import2('board_config', board_path)

        self.options = module.config
        
        self.table = model.board(self.options['SQL_TABLE'])

        # TODO likely will still need customization
        self.path = board_path
        url_path = os.path.join('/', os.path.relpath(\
                                          board_path,
                                          local.environ['DOCUMENT_ROOT']), '')
        self.url = quote(('%s' % (url_path.encode('utf-8'))))
        self.name = board

    def make_path(self, file='', dir='', dirc=None, page=None, thread=None,
                  ext=config.PAGE_EXT, abbr=False, hash=None, url=False,
                  force_http=False):
        '''Builds an url or a path'''
        if url:
            base = self.url
            if force_http:
                # TODO: have a SERVER_NAME entry in config
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

    def check_access(self, admin):
        user = staff.check_password(admin)
        if user.account == staff.MODERATOR and self.name not in user.reign:
            raise WakaError('Access to this board (%s) denied.' % self.name)

        return user

    def make_url(self, **kwargs):
        '''Alias for make_path to build urls'''
        kwargs['url'] = True
        return self.make_path(**kwargs)

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

    def get_some_threads(self, page):
        '''Grab a partial list of threads for pre-emptive pagination.'''

        session = model.Session()
        table = self.table
        thread_dict = {}
        thread_nums = []

        # Query 1: Grab all thread (OP) entries.
        op_sql = table.select().where(table.c.parent == 0).order_by(
                    table.c.stickied.desc(),
                    table.c.lasthit.desc(),
                    table.c.num.asc()
                )
        op_query = session.execute(op_sql)

        for op in op_query:
            thread_dict[op.num] = [model.CompactPost(op)]
            thread_nums.append(op.num)

        # Query 2: Grab all reply entries and process.
        reply_sql = table.select().where(table.c.parent.in_(thread_nums))\
                    .order_by(table.c.stickied.desc(),
                        table.c.num.asc()
                    )
        reply_query = session.execute(reply_sql)

        for post in reply_query:
            thread_dict[post.parent].append(model.CompactPost(post))

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

    def parse_page_threads(self, pagethreads):
        threads = []
        for postlist in pagethreads:
            if len(postlist) == 0:
                continue
            elif len(postlist) > 1:
                parent, replies = postlist[0], postlist[1:]
            else:
                parent, replies = postlist[0], []

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
       
        return threads

    def get_board_page_data(self, page, total):
        if page >= total:
            if total:
                page = total - 1
            else:
                page = 0

        pages = []
        for i in xrange(total):
            p = {}
            p['page'] = i
            p['filename'] = self.make_url(page=i)
            p['current'] = page == i
            pages.append(p)
        prevpage = nextpage = None

        if page != 0:
            prevpage = pages[page - 1]['filename']
        if page != total - 1 and total:
            nextpage = pages[page + 1]['filename']

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
            thread.append(model.CompactPost(post))

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

            print_thread(thread, abbreviated_filename,
                omit=posts_to_trim - 1)
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
                os.makedirs(archive_base, 0755)
            except os.error:
                pass
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

    def _handle_post(self, name, email, subject, comment, file,
                      password, nofile, captcha, admin, no_captcha,
                      no_format, oekaki_post, srcinfo, pch, sticky, lock,
                      admin_post_mode, post_num=None, killtrip=False,
                      parent='0'):

        session = model.Session()

        # get a timestamp for future use
        timestamp = 0
        if not post_num:
            timestamp = time.time()

        # Other automatically determined variables.
        trip = ''
        date = lastedit = lasthit = ''
        post_ip = lastedit_ip = ''
        filename = thumbnail = md5 = ''
        size = width = height = tn_width = tn_height = 0

        # Initialize admin_post variable--tells whether or not this post has
        # fallen under the hand of a mod/admin
        admin_post = ''

        # check that the request came in as a POST, or from the command line
        if local.environ.get('REQUEST_METHOD', '') != 'POST':
            raise WakaError(strings.UNJUST)

        # Get parent post and original file if post_num is provided (editing).
        if post_num:
            original_row = session.execute(
                self.table.select(self.table.c.num == post_num))\
                .fetchone()

            if original_row == None:
                raise WakaError('Post not found') # TODO
                
            if not admin_post_mode and password != original_row['password']:
                raise WakaError('Wrong password for editing') # TODO

            parent = original_row['parent']
            filename = original_row['image']
            thumbnail = original_row['thumbnail']
            md5 = original_row['md5']
            height = original_row['height']
            width = original_row['width']
            tn_width = original_row['tn_width']
            tn_height = original_row['tn_height']
            timestamp = original_row['timestamp']
            date = original_row['date']
            post_ip = original_row['ip']
            size = original_row['size']
            lasthit = original_row['lasthit']
            if not killtrip:
                trip = original_row['trip']

        # check whether the parent thread is stickied
        if parent:
            sticky_check = session.execute(
                select([self.table.c.stickied, self.table.c.locked],
                    self.table.c.num == parent)).fetchone()

            if sticky_check is None:
                raise WakaError('Thread not found.')

            if sticky_check['stickied']:
                sticky = 1
            elif not admin_post_mode:
                sticky = 0

            if sticky_check['locked'] and not admin_post_mode:
                raise WakaError(strings.THREADLOCKEDERROR)

        username = accounttype = ''

        # check admin password - allow both encrypted and non-encrypted
        if admin_post_mode:
            user = self.check_access(admin)
            username = user.username
            accounttype = user.account
            admin_post = 'yes'
        else:
            if no_captcha or no_format or (sticky and not parent) or lock:
                raise WakaError(strings.WRONGPASS)

            if parent:
                if file and not self.options['ALLOW_IMAGE_REPLIES']:
                    raise WakaError(strings.NOTALLOWED)
                if not file and not self.options['ALLOW_TEXT_REPLIES']:
                    raise WakaError(strings.NOTALLOWED)
            else:
                if file and not self.options['ALLOW_IMAGES']:
                    raise WakaError(strings.NOTALLOWED)
                if not file and nofile and self.options['ALLOW_TEXTONLY']:
                    raise WakaError(strings.NOTALLOWED)


        threadupdate = self.table.update().where(
            or_(self.table.c.num == parent, self.table.c.parent == parent))
            
        if sticky and parent:
            threadupdate = threadupdate.values(stickied=1)

        if lock:
            if parent:
                threadupdate = threadupdate.values(locked='yes')
            lock = 'yes'
        else:
            lock = ''

        if (sticky or lock) and parent:
            session.execute(threadupdate)

        has_crlf = lambda x: '\n' in x or '\r' in x

        # check for weird characters
        if not post_num and ((len(parent) != 0 and not parent.isdigit())
           or len(parent) > 10 or has_crlf(name) or has_crlf(email)
           or has_crlf(subject)):
            raise WakaError(UNUSUAL)

        # convert parent to integer type
        if not post_num and len(parent) == 0:
            parent = 0
        else:
            parent = int(parent)

        # check for excessive amounts of text
        if (len(name) > self.options['MAX_FIELD_LENGTH'] or
           len(email) > self.options['MAX_FIELD_LENGTH'] or
           len(subject) > self.options['MAX_FIELD_LENGTH'] or
           len(comment) > self.options['MAX_COMMENT_LENGTH']):
            raise WakaError(strings.TOOLONG)

        # check to make sure the user selected a file, or clicked the checkbox
        if not post_num and not parent and not file and not nofile:
            raise WakaError(strings.NOPIC)

        # check for empty reply or empty text-only post
        if not comment.strip() and not file:
            raise WakaError(strings.NOTEXT)

        # get file size, and check for limitations.
        if file:
            size = misc.get_filestorage_size(file)
            if size > (self.options['MAX_KB'] * 1024):
                raise WakaError(strings.TOOBIG)
            if size == 0:
                raise WakaError(strings.TOOBIGORNONE)

        ip = local.environ['REMOTE_ADDR']
        numip = misc.dot_to_dec(ip)

        if post_num:
            lastedit_ip = numip
        else:
            post_ip = numip

        # set up cookies
        c_name = name
        c_email = email
        c_password = password

        # check if IP is whitelisted
        whitelisted = misc.is_whitelisted(numip)

        # process the tripcode - maybe the string should be decoded later
        name, temp = misc.process_tripcode(name, self.options['TRIPKEY'])
        trip = temp or trip

        if not whitelisted:
            # check for bans
            interboard.ban_check(numip, c_name, subject, comment)

            trap_fields = []
            if self.options['SPAM_TRAP']:
                trap_fields = ['name', 'link']

            misc.spam_engine(trap_fields, config.SPAM_FILES)

        if self.options['ENABLE_CAPTCHA'] and not no_captcha and \
           not misc.is_trusted(trip):
            misc.check_captcha(captcha, ip, parent)

        if not whitelisted and self.options['ENABLE_PROXY_CHECK']:
            misc.proxy_check(ip)

        # check if thread exists, and get lasthit value
        parent_res = ''
        if not post_num:
            if parent:
                parent_res = self.get_parent_post(parent)
                if not parent_res:
                    raise WakaError(strings.NOTHREADERR)
                lasthit = parent_res.lasthit
            else:
                lasthit = timestamp

        # kill the name if anonymous posting is being enforced
        if self.options['FORCED_ANON']:
            name = ''
            trip = ''
            if email.lower().count('sage'):
                email = 'sage'
            else:
                email = ''

        # clean up the inputs
        email = str_format.clean_string(str_format.decode_string(email))
        subject = str_format.clean_string(str_format.decode_string(subject))

        # fix up the email/link, if it is not a generic URI already.
        if email and not re.match("(?!^\w+:)|(?:\:\/\/)", email):
            email = "mailto:%s" % email

        # format comment
        if not no_format:
            comment = str_format.format_comment(str_format.clean_string(
                str_format.decode_string(comment)))

        # insert default values for empty fields
        if not parent:
            parent = 0

        if not (name or trip):
            name = self.make_anonymous(ip, timestamp)

        subject = subject or self.options['S_ANOTITLE']
        comment = comment or self.options['S_ANOTEXT']

        # flood protection - must happen after inputs have been cleaned up
        self.flood_check(numip, timestamp, comment, file, True, False)

        # Manager and deletion stuff - duuuuuh?

        # generate date
        if not post_num:
            date = misc.make_date(timestamp, self.options['DATE_STYLE'])
        else:
            lastedit = misc.make_date(timestamp, self.options['DATE_STYLE'])

        # generate ID code if enabled
        if self.options['DISPLAY_ID']:
            date += ' ID:' + self.make_id_code(ip, timestamp, email)


        # copy file, do checksums, make thumbnail, etc
        if file:
            if filename or thumbnail:
                self.delete_file(filename, thumbnail)

            filename, md5, width, height, thumbnail, tn_width, tn_height = \
                self.process_file(file, timestamp, parent)

            if oekaki_post and self.options['ENABLE_OEKAKI']:
                # TODO: oekaki not supported
                raise NotImplementedError()
                # i don't know what the hell is this pch stuff
                new_pch_filename = source_file = source_pch = ''

                # Check to see, if it is a modification of a source,
                # if the source has an animation file.
                srcinfo_array = srcinfo.split(",")
                if len(srcinfo_array) >= 3:
                    source_file = srcinfo_array[2].lstrip("/")
                    source_pch = misc.find_pch(source_file)

                # If applicable, copy PCH file with the same filename base
                # as the file we just copied.
                if pch and (not source_file or os.path.exists(source_pch)):
                    new_pch_filename = misc.copy_animation_file(pch, filename)
                    # TODO create postfix from OEKAKI_INFO_TEMPLATE
                    postfix = 'TODO'
                    #my $postfix = OEKAKI_INFO_TEMPLATE->(decode_srcinfo($srcinfo,$uploadname,$new_pch_filename));
                    comment += postfix

        # Make sure sticky is a numeric 0. TODO: do we need this in python?
        if not sticky:
            sticky = 0

        # choose whether we need an SQL UPDATE (editing) or INSERT (posting)
        db_update_function = None
        if post_num:
            db_update_function = self.table.update
        else:
            db_update_function = self.table.insert

        # TODO: Make a keyword dictionary for this?...
        db_update = db_update_function().values(parent=parent,
            timestamp=timestamp, ip=post_ip, date=date,
            name=name, trip=trip, email=email, subject=subject,
            password=password, comment=comment, image=filename, size=size,
            md5=md5, width=width, height=height, thumbnail=thumbnail,
            tn_width=tn_width, tn_height=tn_height, admin_post=admin_post,
            stickied=sticky, locked=lock, lastedit_ip=lastedit_ip,
            lasthit=lasthit, lastedit=lastedit)

        # finally, write to the database
        result = None
        if post_num:
            # We have to be selective if editing.
            result = session.execute(db_update\
                                     .where(self.table.c.num == post_num))
        else:
            result = session.execute(db_update)

        if parent and not post_num: # bumping
            # check for sage, or too many replies
            if not (email.lower().count("sage") or
                    self.sage_count(parent_res) > self.options['MAX_RES']):
                t = self.table
                session.execute(t.update()
                    .where(or_(t.c.num == parent, t.c.parent == parent))
                    .values(lasthit=timestamp))
        elif not post_num:
            post_num = result.last_inserted_ids()[0]

        # remove old threads from the database
        self.trim_database()

        # update the cached HTML pages
        self.build_cache()

        # update the individual thread cache
        if parent:
            self.build_thread_cache(parent)
        else: # new thread, id is in num
            if admin_post_mode:
                # TODO add_log_entry not implemented
                # add_log_entry(username, 'admin_post',
                #    '%s,%s' % (self.name, post_num),
                #    date, numip, 0, timestamp)
                pass
            if post_num == 1:
                # If this is the first post on a board recently cleared
                # of posts, the post count will reset; so should our
                # reports, then.
                report_table = model.report
                sql = report_table.delete()\
                    .where(report_table.c.board == self.name)
                session.execute(sql)

            self.build_thread_cache(post_num)

        # set the name, email and password cookies
        misc.make_cookies(name=c_name, email=c_email, password=c_password,
            autopath=self.options['COOKIE_PATH']) # yum !

        return post_num

    def post_stuff(self, parent, name, email, subject, comment, file,
                   password, nofile, captcha, admin, no_captcha,
                   no_format, oekaki_post, srcinfo, pch, sticky, lock,
                   admin_post_mode):
    
        post_num = self._handle_post(name, email, subject, comment,
                                      file, password, nofile, captcha, admin,
                                      no_captcha, no_format, oekaki_post,
                                      srcinfo, pch, sticky, lock,
                                      admin_post_mode, parent=parent)

        # For use with noko, below.
        if not parent:
            parent = post_num

        noko = False
        # check subject field for 'noko' (legacy)
        if subject.lower() == 'noko':
            subject = ''
            noko = True
        # and the link field (proper)
        elif email.lower() == 'noko':
            noko = True

        forward = ''
        if not admin_post_mode:
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
            if not noko:
                forward = '?'.join((misc.get_secure_script_name(),
                    urlencode({'task' : 'mpanel', 'board' : self.name})))
            else:
                forward = '?'.join((misc.get_secure_script_name(),
                    urlencode({'task' : 'mpanel',
                               'board' : self.name,
                               'page' : parent})))

        return util.make_http_forward(forward, config.ALTERNATE_REDIRECT)
        # end of this function. fuck yeah

    def edit_gateway_window(self, post_num, admin_post):
        return self._gateway_window(post_num, 'edit', admin_post=admin_post)

    def delete_gateway_window(self, post_num):
        return self._gateway_window(post_num, 'delete')

    def _gateway_window(self, post_num, task, admin_post=''):
        if not post_num.isdigit():
            raise WakaError('Please enter post number.') # TODO

        if task == 'edit': 
            return Template('password', admin_post=admin_post, num=post_num)
        else:
            return Template('delpassword', num=post_num)

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

    def delete_stuff(self, posts, password, file_only, archiving,
                     caller='user', admindelete=False,
                     from_window=False, admin=''):
        if admin and admindelete and caller == 'user':
            self.check_access(admin)
        elif caller == 'internal':
            # Internally called; force admin.
            admin = True

        for post in posts:
            self.delete_post(post, password, file_only, archiving,
                             from_window=False, admin=admindelete)

        self.build_cache()

        if admin and admindelete:
            forward = '?'.join((misc.get_secure_script_name(),
                urlencode({'task' : 'mpanel', 'board' : self.name})))
        else:
            forward = self.make_path(page=0, url=True)
        if caller == 'user':
            return util.make_http_forward(forward, config.ALTERNATE_REDIRECT)

    def delete_post(self, post, password, file_only, archiving,
                    from_window=False, admin=False):
        '''Delete a single post from the board. This method does not rebuild
        index cache automatically.'''
        thumb = self.options['THUMB_DIR']
        src = self.options['IMG_DIR']

        table = self.table

        sql = table.select().where(table.c.num == post)
        session = model.Session()
        query = session.execute(sql)

        row = query.fetchone()

        if row is None:
            raise WakaError(strings.POSTNOTFOUND % (int(post), self.name))

        if not admin: 
            archiving = False

            if row.admin_post:
                raise WakaError(strings.MODDELETEONLY)

            if password != row.password:
                raise WakaError(post + strings.BADDELPASS)

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
            select_thread_images = select([table.c.image, table.c.thumbnail],
                                          or_(table.c.num == post,
                                              table.c.parent == post))
            images_to_baleet = session.execute(select_thread_images)
            
            for i in images_to_baleet:
                if i.image and i.thumbnail:
                    self.delete_file(i.image, i.thumbnail,
                                     archiving=archiving)

            delete_query = table.delete(or_(
                table.c.num == post,
                table.c.parent == post))
            session.execute(delete_query)

        if not row.parent:
            if file_only:
                # removing parent (OP) image
                self.build_thread_cache(post)
            else:
                # removing an entire thread
                self.delete_thread_cache(post, archiving)
        else:
            # removing a reply, or a reply's image
            self.build_thread_cache(row.parent)

    def delete_file(self, relative_file_path, relative_thumb_path,
                    archiving=False):
        # pch = oekaki.find_pch(row.image)
        full_file_path = os.path.join(self.path, relative_file_path)
        full_thumb_path = os.path.join(self.path, relative_thumb_path)
        archive_base = os.path.join(self.path,
                                    self.options['ARCHIVE_DIR'], '')
        full_backup_path = os.path.join(archive_base,relative_file_path)
        full_tbackup_path = os.path.join(archive_base, relative_thumb_path)

        if os.path.exists(full_file_path):
            if archiving:
                os.renames(full_file_path, full_backup_path)
            else:
                os.unlink(full_file_path)
        if os.path.exists(full_thumb_path) and \
           re.match(self.options['THUMB_DIR'], relative_file_path):
            if archiving:
                os.renames(full_thumb_path, full_tbackup_path)
            else:
                os.unlink(full_thumb_path)

    def make_report_post_window(self, posts, from_window=False):
        if len(posts) == 0:
            raise WakaError('No posts selected.')
        if len(posts) > 10:
            raise WakaError('Too many posts. Try reporting the thread ' \
                            + 'or a single post in the case of floods.')

        num_parsed = ', '.join(posts)
        referer = ''
        if not from_window:
            referer = local.environ['HTTP_REFERER']

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

    def edit_window(self, post_num, admin, password, admin_edit_mode=False):

        session = model.Session()
        table = self.table
        sql = table.select().where(table.c.num == post_num)
        row = session.execute(sql).fetchone()

        if row is None:
            raise WakaError('Post not found') # TODO
        
        if admin_edit_mode:
            self.check_access(admin)
        elif password != row['password']:
            raise WakaError('Wrong pass for editing') # TODO

        return Template('post_edit_template', loop=[row],
                                              admin=admin_edit_mode)

    def edit_stuff(self, post_num, name, email, subject, comment, file,
                   password, nofile, captcha, admin, no_captcha,
                   no_format, oekaki_post, srcinfo, pch, sticky, lock,
                   admin_edit_mode, killtrip, postfix):

        self._handle_post(name, email, subject, comment, file,
                          password, nofile, captcha, admin, no_captcha,
                          no_format, oekaki_post, srcinfo, pch, sticky, lock,
                          admin_edit_mode, post_num=post_num,
                          killtrip=killtrip)

        return Template('edit_successful')

    def process_file(self, filestorage, timestamp, parent):
        filetypes = self.options['FILETYPES']

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
        thumbnail = self.make_path(filebase + "s", dirc='THUMB_DIR',
                                   ext='jpg')


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
        if ((parent and self.options['DUPLICATE_DETECTION'] == 'thread') or
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
                icon = os.path.join(self.path, filetypes[ext].lstrip("/"))

                tn_ext, tn_width, tn_height = \
                    analyze_image(open(icon, "rb"), icon)

                # was that icon file really there?
                if tn_width:
                    thumbnail = filetypes[ext]
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
                result = misc.make_thumbnail(filename, thumbnail, tn_width,
                   tn_height, self.options['THUMBNAIL_QUALITY'],
                   self.options['CONVERT_COMMAND'])
                if not result:
                    thumbnail = ''
        else:
            tn_width = width
            tn_height = height
            thumbnail = filename

        # externally defined filetype - restore the name
        if ext in filetypes and (ext not in ('gif', 'jpg', 'png') or
                                 filetypes[ext] == '.'):
            # cut off any directory in the original filename
            newfilename = self.make_path(filestorage.filename.split("/")[-1],
                dirc='IMG_DIR', ext=None)

            # verify no name clash
            if not os.path.exists(newfilename):
                os.rename(filename, newfilename)
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
        thumbnail = thumbnail.replace(self.path, '').lstrip('/')

        return (filename, md5, width, height, thumbnail, tn_width, tn_height)

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

        self_path = self.url

        if force_http:
            self_path = 'http://' + local.environ['SERVER_NAME'] + self_path

        return self_path + quote(filename.encode('utf-8'))

    def make_anonymous(self, ip, time):
        # TODO: SILLY_ANONYMOUS not supported
        return self.options['S_ANONAME']

    def make_id_code(self, ip, timestamp, link):
        # TODO not implemented
        raise NotImplementedError()

    def get_post(self, num):
        '''Returns None or CompactPost'''
        session = model.Session()
        sql = self.table.select(self.table.c.num == num)
        row = session.execute(sql).fetchone()
        if row:
            return model.CompactPost(row)

    def get_parent_post(self, parentid):
        session = model.Session()
        sql = self.table.select(and_(self.table.c.num == parentid,
            self.table.c.parent == 0))
        query = session.execute(sql)
        return model.CompactPost(query.fetchone())

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

    def toggle_thread_state(self, admin, num, operation, enable_state=True):
        self.check_access(admin)

        # Check thread
        session = model.Session()
        table = self.table
        sql = select([table.c.parent], table.c.num == num, table)
        row = session.execute(sql).fetchone()
        
        if not row:
            raise WakaError('Thread %s,%d not found.' % (self.name, num))
        if row['parent']:
            raise WakaError(strings.S_NOTATHREAD)

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

        # TODO: Log this.

        forward_url = '?'.join((misc.get_secure_script_name(),
            urlencode({'task' : 'mpanel', 'board' : self.name})))

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

# utility functions

def get_page_count(threads, per_page):
    return (len(threads) + per_page - 1) / per_page

def abbreviate_html(html, max_lines, approx_len):
    # TODO: implement abbreviate_html
    return

class BoardNotFound(WakaError):
    def __init__(self, message='Board not found'):
        WakaError.__init__(self, message)
