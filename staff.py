'''Staff management.'''

import time
from sqlalchemy.sql import case, or_, and_, select, func, null

import strings
import model
import misc
import staff_interface
import config, config_defaults
from util import WakaError, local
from template import Template

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

    def ___init___(self, user, addr):
        self.addr = addr
        self.crypt = misc.hide_critical_data\
                       (','.join((user.password, remote)), config.SECRET)
        self.username = user.username
        self.cookie_str = ','.join((self.username, self.crypt))

    def make_cookie(self, save_login=False):
        misc.make_cookies(admin=self._cstring)

        if save_login:
            misc.make_cookies(wakaadminsave='1', wakaadmin=self.crypt,
                              expires=time.time()+SAVED_LOGIN_EXPIRE)
        else:
            misc.make_cookies(wakaadminsave='0', wakaadmin=self.crypt,
                              expires=time.time()+UNSAVED_LOGIN_EXPIRE)

# Class for representing staff
class StaffMember(object):
    '''A staff object for acquiring and updating personnel account
    information. Use the class factory method to initialize:
    
    >> StaffMember.get('SirDerpDeeDoo')
    
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
        # TODO: Sanity checks

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
        self._disabled = disable
        self._update_db(disabled=int(disable))

    def login_host(self, ip):
        login_data = LoginData(self.username, ip)
        self._login_data = login_data
        return login_data

    def logout_user(self):
        self._login_data = None

    def flush_db(self):
        session = model.Session()
        table = self._table

        if len(self._update_dict) > 0:
            db_update = table.update().where(self.username == username)\
                             .values(**self._update_dict)
            session.execute(db_update)

    @classmethod
    def get(cls, username):
#        if username in _staff:
#            return _staff[username]

        staff_obj = cls(username)
#       _staff[username] = staff_obj
        return staff_obj

def add_staff(username, pt_password, account, reign):
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

def edit_staff(mpass, username, clear_pass=None, new_class=None,
               reign=None):

    staff_obj = StaffMember.get(username)
    
    if clear_pass:
        staff_obj.password = misc.hide_critical_data(clear_pass,
                                                     config.SECRET)

    if new_class and new_class in CLASSES:
        staff_obj.account = new_class

    if reign:
        staff_obj.reign = reign

    staff_obj.flush_db()

def staff_exist():
    session = model.Session()
    table = model.account
    sql = select([func.count()], table)
    row = session.execute(sql).fetchone()

    return row != 0

def clear_login_cookies():
    misc.make_cookies(wakaadmin='', wakaadminsave='0', expires=0)

def do_login(username=None, password=None, save_login=False,
             admin_cookie=None, nexttask='mpanel'):

    bad_pass = False
    staff_entry = None

    if not staff_exist():
        return staff_interface.make_first_time_setup_gateway()
    elif username and password:
        # Login via login form entry.
        try:
            staff_entry = StaffMember.get(username)
        except LoginError:
            # Bad username.
            bad_pass = True
        else:
            crypt_pass = misc.hide_critical_data(staff_entry.password,
                                                 config.SECRET)
            if crypt_pass == staff_entry.password:
                staff_entry.login_host(remote)
            else:
                bad_pass = True
    elif admin_cookie:
        # Attempt automatic login.
        try:
            staff_entry = check_password(admin_cookie)
        except LoginError:
            clear_login_cookies()
            bad_pass = True
    else:
        # No login credentials given.
        bad_pass = True

    if bad_pass:
        return staff_interface.make_login_panel()
    else:
        login = staff_entry.login_data
        login.make_cookie(save_login=save_login)
        return staff_interface.make_admin_panel(login.cookie, nexttask)

def do_logout(admin):
    # Clear login cache.
    try:
        user = check_password(admin)
        user.logout_user()
    except LoginError:
        pass

    clear_login_cookies()

def check_password(cookie_str, editing=None):
    (username, crypt) = cookie_str.split(',')
    staff_entry = StaffMember.get(username)
    cache = staff_entry.login_data

    if cache and cache.addr == remote:
        # The host is already logged in.
        pass
    elif crypt != misc.hide_critical_data(','.join([staff_entry.password,
                                                    remote]), config.SECRET):
        raise LoginError(S_WRONGPASS)
    else:
        # NOTE: This will overwrite the current network address login.
        staff_entry.login_host(remote)

    return staff_entry

def crypt_pass(cleartext):
    remote = local.environ['REMOTE_ADDR']
    return misc.hide_critical_data(','.join((cleartext, remote)),
                                            config.SECRET)

class LoginError(WakaError):
    '''WakaError subclass to discriminate login-related exceptions (bad
    password/username combinations).'''
    pass
