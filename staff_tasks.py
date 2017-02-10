import time

import model
import staff
import interboard
import misc
import config
from util import WakaError

# Dictionary of what action keywords mean. It's like a real dictionary!
# {name: {'name': title, 'content': content}}
ACTION_TRANSLATION  = {}

# {name: function}
ACTION_MAP = {}

def get_action_name(action_to_view, debug=0):
    try:
        name = ACTION_TRANSLATION[action_to_view]['name']
        content = ACTION_TRANSLATION[action_to_view]['content'] 
    except KeyError:
        raise WakaError('Missing action key or unknown action key.')

    if not debug:
        return name
    elif debug == 1:
        return (name, content)
    else:
        return content

def staff_action(action_name='', title='', content=''):
    def decorator(f):
        real_name = action_name or f.__name__
        real_title = title or real_name.title().replace("_", "")

        ACTION_TRANSLATION[real_name] = {'name': real_title,
            'content': content}
        ACTION_MAP[real_name] = f
        return f
    return decorator


@staff_action(title='Manager Post', content='Post')
def admin_post(task_data, **kwargs):
    return task_data.board.post_stuff(admin_data=task_data, **kwargs)

@staff_action(title='Administrative Edit', content='Post')
def admin_edit(task_data, **kwargs):
    return task_data.board.edit_stuff(admin_data=task_data, **kwargs)

@staff_action(title='Administrative Deletion', content='Post')
def admin_delete(task_data, **kwargs):
    return task_data.board.delete_stuff(admin_data=task_data, **kwargs)

@staff_action(title='Deletion From Trash Bin', content='Deleted Post')
def backup_remove(task_data, **kwargs):
    return task_data.board.remove_backup_stuff(admin_data=task_data,
                                               **kwargs)

@staff_action(content='Thread Parent')
def thread_lock(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'locked')

@staff_action(content='Thread Parent')
def thread_unlock(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'locked',
                                               enable_state=False)

@staff_action(content='Thread Parent')
def thread_sticky(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'sticky')

@staff_action(content='Thread Parent')
def thread_unsticky(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'sticky',
                                               enable_state=False)

@staff_action(title='Delete By IP (Board-Wide)', content='IP Address')
def delete_by_ip(task_data, **kwargs):
    return task_data.board.delete_by_ip(task_data=task_data, **kwargs)

@staff_action(title='Board Rebuild', content='Board Name')
def rebuild(task_data):
    return task_data.board.rebuild_cache_proxy(task_data)


# Interboard entries
# (these 'decorate' functions not in this module)

staff_action('admin_entry')(interboard.add_admin_entry)
staff_action('remove_admin_entry')(interboard.remove_admin_entry)
staff_action('edit_admin_entry')(interboard.edit_admin_entry)
staff_action('update_spam')(interboard.update_spam_file)

staff_action('report_resolve', title='Report Resolution',
    content='Resolved Post')(interboard.mark_resolved)

staff_action('thread_move',
    content='Source and Destination')(interboard.move_thread)

staff_action('delete_by_ip_global', title='Delete By IP (Global or Reign-Wide)',
    content='IP Address')(interboard.delete_by_ip)

staff_action('rebuild_global', title='Global Rebuild',
    content='Referer')(interboard.global_cache_rebuild_proxy)

staff_action('add_proxy_entry')(interboard.add_proxy_entry)
staff_action('remove_proxy_entry')(interboard.remove_proxy_entry)

# Unimplemented

staff_action('script_ban_forgive', title='Script Access Restoration',
    content='IP Address')(None)

staff_action('ipban_edit', title='IP Ban Revision',
    content='Revised Data')(None)

staff_action('whitelist', title='IP Whitelist',
    content='Whitelisted IP Address')(None)

staff_action('trust_edit', title='Revised Captcha Exemption',
    content='Revised Data')(None)

staff_action('trust_remove', title='Removed Captcha Exemption',
    content='Removed Tripcode')(None)

staff_action('backup_restore', title='Restoration From Trash Bin',
    content='Restored Post')(None)

staff_action('ipban', title='IP Ban',
     content='Affected IP Address')(None)

staff_action('ipban_remove', title='IP Ban Removal',
    content='Unbanned IP Address')(None)

staff_action('trust', title='Captcha Exemption',
    content='Exempted Tripcode')(None)

staff_action('wordban', title='Word Ban',
    content='Banned Phrase')(None)

staff_action('whitelist_remove', title='IP Whitelist Removal',
    content='Removed IP Address')(None)

staff_action('wordban_remove', title='Word Ban Removal',
    content='Unbanned Phrase')(None)

staff_action('wordban_edit', title='Word Ban Revision',
    content='Revised Data')(None)

staff_action('whitelist_edit', title='IP Whitelist Revision',
    content='Revised Data')(None)


class StaffAction(object):

    def __init__(self, cookie, action, **kwargs):
        self.action = action
        self.user = staff.StaffMember.get_from_cookie(cookie)
        self.board = None
        self.kwargs = kwargs
        try:
            self.board = kwargs.pop('board')
        except KeyError:
            pass
        self.timestamp = time.time()
        self.date = misc.make_date(self.timestamp, style=config.DATE_STYLE)
        self.contents = []
        self.action = action
        self.admin_id = None

    def execute(self):
        res = None
        try:
            # XXX there was an apparently pointless "if board" here
            res = ACTION_MAP[self.action](self, **self.kwargs)
            return res
        finally:
            # Execute after exceptions in the case of bulk deletions, etc.
            if res or self.contents:
                self._log_action()

    def _log_action(self):
        interboard.trim_activity()
        session = model.Session()
        table = model.activity
        ip = misc.dot_to_dec(self.user.login_data.addr)
        for content in self.contents:
            sql = table.insert().values(username=self.user.username,
                                        ip=ip,
                                        action=self.action,
                                        info=content,
                                        date=self.date,
                                        timestamp=self.timestamp,
                                        admin_id=self.admin_id)
            session.execute(sql)
