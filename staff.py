'''Staff management.'''

import time
from sqlalchemy.sql import select, func

import strings
import model
import misc
import config, config_defaults
from util import WakaError, local

# TODO: Synchronized cache of staff personnel objects.
# _staff = {}

# Staff class types.
ADMIN = 'admin'
GLOBAL_MOD = 'globmod'
MODERATOR = 'mod'
CLASSES = (ADMIN, GLOBAL_MOD, MODERATOR)

# Login cookie expire times (in seconds).
SAVED_LOGIN_EXPIRE = 365 * 24 * 3600
UNSAVED_LOGIN_EXPIRE = 3600

# Staff Accounts and Logins
class LoginData(object):
    '''Class for interfacing with prefetched login data.'''

    def __init__(self, user, addr):
        self.addr = addr
        self.crypt = crypt_pass(user.password, addr)
        self.username = user.username
        self.cookie = ','.join((self.username, self.crypt))

    def make_cookie(self, save_login=False):
        expires = time.time() + (SAVED_LOGIN_EXPIRE if save_login
            else UNSAVED_LOGIN_EXPIRE)

        misc.make_cookies(wakaadmin=self.cookie, httponly=1, expires=expires)

        # the following isn't http only
        wakaadminsave = '1' if save_login else ''
        misc.make_cookies(wakaadminsave=wakaadminsave, expires=expires)

# Class for representing staff
class StaffMember(object):
    '''A staff object for acquiring and updating personnel account
    information. Use the class factory method to initialize:
    
    >>> StaffMember.get('SirDerpDeeDoo')
    
    To create new staff accounts, use the add_staff() function instead.'''

    def __init__(self, username):
        session = model.Session()
        table = model.account
        sql = table.select().where(table.c.username == username)
        row = session.execute(sql).fetchone()
        self._table = table

        if row is None:
            raise LoginError('Staff not found.')

        # Grab parameters from database. Password is pre-encrypted.
        self.username = username
        self._password = row.password
        self._class = row.account
        self._reign = row.reign.split(',')
        self._disabled = row.disabled
        self._update_dict = {}

        # Not logged in yet.
        self._login_data = None

    def _update_db(self, **kwargs):
        self._update_dict.update(kwargs)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, new):
        table = self._table
        if len(new) < 8:
            raise WakaError('Passwords should be at least eight characters!')

        new = misc.hide_critical_data(new, config.SECRET)

        self._update_db(password=new)
        self._password = new

    @property
    def reign(self):
        return self._reign

    @reign.setter
    def reign(self, board_list):
        reign_str = ','.join(board_list)
        self._update_db(reign=reign_str)

        self._reign = board_list

    @property
    def account(self):
        return self._class

    @account.setter
    def account(self, new):
        if new in CLASSES:
            self._update_db(account=new)
            self._class = new
        else:
            raise WakaError('Invalid class name %s' % new)

    @property
    def login_data(self):
        return self._login_data

    @property
    def disabled(self):
        return self._disabled

    @disabled.setter
    def disabled(self, disable):
        self._disabled = bool(disable)
        if disable:
            disable = 1
        else:
            disable = 0

        self._update_db(disabled=disable)

    def login_host(self, ip):
        login_data = LoginData(self, ip)
        self._login_data = login_data
        return login_data

    def logout_user(self):
        self._login_data = None

    def flush_db(self):
        session = model.Session()
        table = self._table

        if len(self._update_dict) > 0:
            db_update = table.update()\
                             .where(table.c.username == self.username)\
                             .values(**self._update_dict)
            session.execute(db_update)

    @classmethod
    def get(cls, username):
#        if username in _staff:
#            return _staff[username]

        staff_obj = cls(username)
#       _staff[username] = staff_obj
        return staff_obj

    @classmethod
    def get_from_cookie(cls, cookie_str):
        if not cookie_str or not cookie_str.count(','):
            raise LoginError('Cookie data missing.')

        remote = local.environ['REMOTE_ADDR']
        (username, crypt) = cookie_str.split(',')
        staff_entry = cls.get(username)
        cache = staff_entry.login_data

        if cache and cache.addr == remote:
            # The host is already logged in.
            pass
        elif crypt != crypt_pass(staff_entry.password, remote):
            raise LoginError(strings.WRONGPASS)
        elif staff_entry.disabled:
            raise LoginError('You have been disabled.')
        else:
            # NOTE: This will overwrite the current network address login.
            staff_entry.login_host(remote)
            # Needs save_login parameter. Only useful once sessions and
            # user caches are implemented.
            # staff_entry.login_data.make_cookie()

        return staff_entry

    def check_access(self, board_name):
        if self.account == MODERATOR and board_name not in self.reign:
            raise WakaError('Access to this board (%s) denied.' % board_name)

def add_staff(username, pt_password, account, reign):
    if not username:
        raise WakaError('A username is necessary.')
    if not pt_password:
        raise WakaError('A password is necessary.')
    if len(pt_password) < 8:
        raise WakaError('Passwords should be eight characters minimum.')
    if len(reign) == 0 and account == MODERATOR:
        raise WakaError('Board reign not specified for moderator account.')

    # Check whether the user exists already.
    try:
        StaffMember.get(username)
    except LoginError:
        # User not found. Good.
        pass
    else:
        raise WakaError('Username exists.')

    session = model.Session()
    table = model.account
    password = misc.hide_critical_data(pt_password, config.SECRET)
    reign_str = ','.join(reign)

    sql = table.insert().values(username=username, password=password,
                                account=account, reign=reign_str,
                                disabled=0)
    session.execute(sql)

def del_staff(username):
    session = model.Session()
    table = model.account
    sql = table.delete(table.c.username == username)
    session.execute(sql)

#    try:
#        del _staff[username]
#    except AttributeError:
#        pass

def edit_staff(username, clear_pass=None, new_class=None, reign=None,
               disable=None):

    staff_obj = StaffMember.get(username)
    
    if clear_pass:
        staff_obj.password = clear_pass

    if new_class and new_class in CLASSES:
        staff_obj.account = new_class

    if reign:
        staff_obj.reign = reign

    if disable is not None:
        staff_obj.disabled = disable

    staff_obj.flush_db()

def staff_exists():
    session = model.Session()
    table = model.account
    sql = select([func.count()], table)
    row = session.execute(sql).fetchone()

    return row[0] != 0

def check_password(cookie_str):
    return StaffMember.get_from_cookie(cookie_str)

def crypt_pass(cleartext, remote):
    return misc.hide_critical_data(','.join((cleartext, remote)),
                                            config.SECRET)

class LoginError(WakaError):
    '''WakaError subclass to discriminate login-related exceptions (bad
    password/username combinations).'''
    pass
