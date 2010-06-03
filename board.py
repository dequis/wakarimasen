import os
import re
import time
import random
import hashlib
from subprocess import Popen, PIPE

import misc
import util
import model
import config, config_defaults
import strings_en as strings
from util import WakaError
from template import Template

from sqlalchemy.sql import case, or_, and_, select, func

class Board(object):
    def __init__(self, board):
        if not os.path.exists(board):
            raise WakaError('Board not found.')
        if not os.path.exists(os.path.join(board, 'board_config.py')):
            raise WakaError('Board configuration not found.')
        
        module = util.import2('board_config', board)

        self.options = module.config
        
        self.table = model.board(self.options['SQL_TABLE'])

        # TODO customize these
        self.path = os.path.abspath(board)
        self.url = '/%s/' % board
        self.name = board

    def make_path(self, file='', dir='', dirc=None, page=None, thread=None,
                  ext=config.PAGE_EXT, abbr=False, url=False):
        '''Builds an url or a path'''
        if url:
            base = self.url
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
        
        if file:
            if abbr:
                file += '_abbr'
            if ext is not None:
                file += '.' + ext.lstrip(".")
            return os.path.join(base, dir, file)
        else:
            return os.path.join(base, dir)

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

    def post_stuff(self, parent, name, email, subject, comment, file,
                   password, nofile, captcha, admin, no_captcha,
                   no_format, oekaki_post, srcinfo, pch, sticky, lock,
                   admin_post_mode, environ={}):
    
        session = model.Session()

        # get a timestamp for future use
        timestamp = time.time()

        # Initialize admin_post variable--tells whether or not this post has fallen under the hand of a mod/admin
        admin_post = ''

        # check that the request came in as a POST, or from the command line
        if environ.get('REQUEST_METHOD', '') != 'POST':
            raise WakaError(strings.UNJUST)

        # check whether the parent thread is stickied
        if parent:
            sticky_check = session.execute(
                select([self.table.c.stickied, self.table.c.locked],
                    self.table.c.num == parent)).fetchone()

            if sticky_check['stickied']:
                sticky = 1
            elif not admin_post_mode:
                sticky = 0

            # TODO use True/False instead of 'yes'?
            if sticky_check['locked'] == 'yes' and not admin_post_mode:
                raise WakaError(strings.THREADLOCKEDERROR)

        username = accounttype = ''

        # check admin password - allow both encrypted and non-encrypted
        if admin_post_mode:
            username, accounttype = misc.check_password(admin, 'mpost')
            admin_post = 'yes' # TODO use True/False?
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
            lock = 'yes' # TODO use True/False?

        if (sticky or lock) and parent:
            session.execute(threadupdate)

        has_crlf = lambda x: '\n' in x or '\r' in x

        # check for weird characters
        if (not parent.isdigit() or len(parent) > 10 or
           has_crlf(name) or has_crlf(email) or has_crlf(subject)):
            raise WakaError(strings.UNUSUAL)

        parent = int(parent)

        # check for excessive amounts of text
        if (len(name) > self.options['MAX_FIELD_LENGTH'] or
           len(email) > self.options['MAX_FIELD_LENGTH'] or
           len(subject) > self.options['MAX_FIELD_LENGTH'] or
           len(comment) > self.options['MAX_COMMENT_LENGTH']):
            raise WakaError(strings.TOOLONG)

        # check to make sure the user selected a file, or clicked the checkbox
        if not parent and not file and not nofile:
            raise WakaError(strings.NOPIC)

        # check for empty reply or empty text-only post
        if not comment.strip() and not file:
            raise WakaError(strings.NOTEXT)

        # get file size, and check for limitations.
        size = 0
        if file:
            size = misc.get_filestorage_size(file)
            if size > (self.options['MAX_KB'] * 1024):
                raise WakaError(strings.TOOBIG)
            if size == 0:
                raise WakaError(strings.TOOBIGORNONE)

        ip = environ['REMOTE_ADDR']
        numip = misc.dot_to_dec(ip)

        # set up cookies
        c_name = name
        c_email = email
        c_password = password

        # check if IP is whitelisted
        whitelisted = misc.is_whitelisted(numip)

        # process the tripcode - maybe the string should be decoded later
        name, trip = misc.process_tripcode(name, self.options['TRIPKEY'])

        if not whitelisted:
            # check for bans
            misc.ban_check(numip, c_name, subject, comment)

            trap_fields = []
            if self.options['SPAM_TRAP']:
                trap_fields = ['name', 'link']

            misc.spam_engine(environ, trap_fields, config.SPAM_FILES)

        if self.options['ENABLE_CAPTCHA'] and not no_captcha and \
           not misc.is_trusted(trip):
            misc.check_captcha(captcha, ip, parent)

        if not whitelisted and self.options['ENABLE_PROXY_CHECK']:
            misc.proxy_check(ip)

        # check if thread exists, and get lasthit value
        parent_res = lasthit = ''
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
        email = misc.clean_string(misc.decode_string(email))
        subject = misc.clean_string(misc.decode_string(subject))

        noko = False
        # check subject field for 'noko' (legacy)
        if subject.lower() == 'noko':
            subject = ''
            noko = True
        # and the link field (proper)
        elif email.lower() == 'noko':
            noko = True

        # fix up the email/link
        # TODO support URLs instead of emails too (wakaba uses a regexp here)
        if email:
            email = "mailto:%s" % email

        # format comment
        if not no_format:
            comment = misc.format_comment(misc.clean_string(
                misc.decode_string(comment)))

        # insert default values for empty fields
        if not parent:
            parent = 0

        if not (name or trip):
            name = self.make_anonymous(ip, timestamp)

        subject = subject or self.options['S_ANOTITLE']
        comment = comment or self.options['S_ANOTEXT']

        # flood protection - must happen after inputs have been cleaned up
        misc.flood_check(numip, timestamp, comment, file, 1, 0)

        # Manager and deletion stuff - duuuuuh?

        # generate date
        date = misc.make_date(timestamp + config.TIME_OFFSET, config.DATE_STYLE)

        # generate ID code if enabled
        if self.options['DISPLAY_ID']:
            date += ' ID:' + self.make_id_code(ip, timestamp, email)


        # copy file, do checksums, make thumbnail, etc
        if file:
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
        else:
            filename = md5 = thumbnail = ''
            width = height = tn_width = tn_height = 0

        # Make sure sticky is a numeric 0. TODO: do we need this in python?
        if not sticky:
            sticky = 0

        # finally, write to the database
        session = model.Session()
        result = session.execute(self.table.insert().values(parent=parent,
            timestamp=timestamp, lasthit=lasthit, ip=numip, date=date,
            name=name, trip=trip, email=email, subject=subject,
            password=password, comment=comment, image=filename, size=size,
            md5=md5, width=width, height=height, thumbnail=thumbnail,
            tn_width=tn_width, tn_height=tn_height, admin_post=admin_post,
            stickied=sticky, locked=lock))
        num = result.last_inserted_ids()[0]

        if parent: # bumping
            # check for sage, or too many replies
            if not (email.lower().count("sage") or
                    self.sage_count(parent_res) > self.options['MAX_RES']):
                t = self.table
                session.execute(t.update()
                    .where(or_(t.c.num == parent, t.c.parent == parent))
                    .values(lasthit=timestamp))

        # remove old threads from the database
        self.trim_database()

        # update the cached HTML pages
        self.build_cache(environ)

        # update the individual thread cache
        if parent:
            self.build_thread_cache(parent, environ)
        else: # new thread, id is in num
            if admin_post_mode:
                # TODO add_log_entry not implemented
                add_log_entry(username, 'admin_post',
                    '%s,%s' % (self.name, num),
                    date, numip, 0, timestamp)
            if num == 1:
                # If this is the first post on a board recently cleared
                # of posts, the post count will reset; so should our
                # reports, then.
                # TODO init_report_database not implemented
                # TODO maybe it shouldn't be implemented
                #init_report_database()
                pass

            self.build_thread_cache(num, environ)

            parent = num    # For use with "noko" below

        # set the name, email and password cookies
        misc.make_cookies(c_name, c_email, c_password, config.CHARSET,
            self.options['COOKIE_PATH'], environ) # yum !

        forward = ''
        if not admin_post_mode:
            if not noko:
                # forward back to the main page
                forward = self.make_path(page=0, url=True)
            else:
                # ...unless we have "noko" (a la 4chan)--then forward to thread
                # ("parent" contains current post number if a new thread was posted)
                if not os.path.exists(self.make_path(thread=parent, abbr=True)):
                    forward = self.make_url(thread=parent)
                else:
                    forward = self.make_url(thread=parent, abbr=True)
        else:
            # forward back to the mod panel
            if not noko:
                forward = '%s?task=mpanel&board=%s' % \
                    (misc.get_secure_script_name(), self.name)
            else:
                forward = '%s?task=mpanel&board=%s&page=t%s' % \
                    (misc.get_secure_script_name(), self.name, parent)

        return util.make_http_forward(environ, forward, config.ALTERNATE_REDIRECT)
        # end of this function. fuck yeah


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
        thumbnail = self.make_path(filebase + "s", dirc='THUMB_DIR', ext='jpg')

        print "*" * 30, filename, thumbnail

        if not known:
            filename += self.options['MUNGE_UNKNOWN']

        # copy file
        try:
            filestorage.save(filename)
        except IOError:
            raise WakaError(strings.NOTWRITE)

        # Check file type with UNIX utility file()
        file_response = Popen(["file", filename], stdout=PIPE).communicate()[0]
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
                if filetypes[ext].startswith("/"):
                    icon = filetypes[ext][1:] # FIXME: wtf is wakaba doing here
                else:
                    icon = os.path.join(self.path, filetypes[ext])

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
                print "hi there"
                result = misc.make_thumbnail(filename, thumbnail, tn_width,
                   tn_height, self.options['THUMBNAIL_QUALITY'],
                   self.options['CONVERT_COMMAND'])
                print "result is", result
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

        # Make file and thumbnailworld-readable
        os.chmod(filename, 0644)
        if thumbnail:
            os.chmod(thumbnail, 0644)

        # Clear out the board path name.
        filename = filename.replace(self.path, '').lstrip('/')
        thumbnail = thumbnail.replace(self.path, '').lstrip('/')

        return (filename, md5, width, height, thumbnail, tn_width, tn_height)

    def get_reply_link(self, reply, parent, abbreviated=False, force_http=False):
        raise NotImplementedError() # TODO
        #return expand_filename($board->option('RES_DIR').$parent.(($abbreviated) ? "_abbr" : "").$page_ext,$force_http).'#'.$reply if($parent);
        #return expand_filename($board->option('RES_DIR').$reply.(($abbreviated) ? "_abbr" : "").$page_ext,$force_http);

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

    def make_anonymous(self, ip, time):
        # TODO: SILLY_ANONYMOUS not supported
        return self.options['S_ANONAME']

    def make_id_code(self, ip, timestamp, link):
        # TODO not implemented
        raise NotImplementedError()

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
        pass

# utility functions

def get_page_count(threads, per_page):
    return (len(threads) + per_page - 1) / per_page

def abbreviate_html(html, max_lines, approx_len):
    # TODO: implement abbreviate_html
    return

