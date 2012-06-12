import time

import model
import staff
import interboard
import misc
import config
from util import WakaError

# Dictionary of what action keywords mean. It's like a real dictionary!
ACTION_TRANSLATION  = {
    'ipban' : {'name' : 'IP Ban', 'content' : 'Affected IP Address'},
    'ipban_edit'
        : {'name' : 'IP Ban Revision', 'content' : 'Revised Data'},
    'ipban_remove'
        : {'name' : 'IP Ban Removal',
           'content' : 'Unbanned IP Address'},
    'wordban' : {'name' : 'Word Ban', 'content' : 'Banned Phrase'},
    'wordban_edit' : {'name' : 'Word Ban Revision',
                     'content' : 'Revised Data'},
    'wordban_remove' : {'name' : 'Word Ban Removal',
                       'content' : 'Unbanned Phrase'},
    'whitelist' : {'name' : 'IP Whitelist',
                  'content' : 'Whitelisted IP Address'},
    'whitelist_edit' : {'name' : 'IP Whitelist Revision',
                       'content' : 'Revised Data'},
    'whitelist_remove' : {'name' : 'IP Whitelist Removal',
                                  'content' : 'Removed IP Address'},
    'trust' : {'name' : 'Captcha Exemption',
              'content' : 'Exempted Tripcode'},
    'trust_edit' : {'name' : 'Revised Captcha Exemption',
                   'content' : 'Revised Data'},
    'trust_remove' : {'name' : 'Removed Captcha Exemption',
                     'content' : 'Removed Tripcode'},
    'admin_post' : {'name' : 'Manager Post', 'content' : 'Post'},
    'admin_edit' : {'name' : 'Administrative Edit',
                   'content' : 'Post'},
    'admin_delete' : {'name' : 'Administrative Deletion',
                     'content' : 'Post'},
    'thread_sticky' : {'name' : 'Thread Sticky',
                      'content' : 'Thread Parent'},
    'thread_unsticky' : {'name' : 'Thread Unsticky',
                        'content': 'Thread Parent'},
    'thread_lock' : {'name' : 'Thread Lock',
                    'content' : 'Thread Parent'},
    'thread_unlock' : {'name' : 'Thread Unlock',
                      'content' : 'Thread Parent'},
    'report_resolve' : {'name' : 'Report Resolution',
                       'content' : 'Resolved Post'},
    'backup_restore' : {'name' : 'Restoration From Trash Bin',
                       'content' : 'Restored Post'},
    'backup_remove' : {'name' : 'Deletion From Trash Bin',
                      'content' : 'Deleted Post'},
    'thread_move' : {'name' : 'Thread Move',
                    'content' : 'Source and Destination'},
    'script_ban_forgive' : {'name' : 'Script Access Restoration',
                           'content' : 'IP Address'},
    'delete_by_ip': {'name': 'Delete By IP (Board-Wide)',
                    'content': 'IP Address'},
    'delete_by_ip_global': {'name': 'Delete By IP (Global or Reign-Wide)',
                            'content': 'IP Address'},
    'rebuild': {'name': 'Board Rebuild',
                'content': 'Board Name'},
    'rebuild_global': {'name': 'Global Rebuild', 'content': 'Referer'},
}

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

def make_admin_post(task_data, **kwargs):
    return task_data.board.post_stuff(admin_task_data=task_data, **kwargs)

def edit_admin_post(task_data, **kwargs):
    return task_data.board.edit_stuff(admin_task_data=task_data, **kwargs)

def delete_admin_post(task_data, **kwargs):
    return task_data.board.delete_stuff(admin_task_data=task_data, **kwargs)

def delete_backup_post(task_data, **kwargs):
    return task_data.board.remove_backup_stuff(admin_task_data=task_data,
                                               **kwargs)

def lock_thread(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'locked')

def unlock_thread(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'locked',
                                               enable_state=False)

def sticky_thread(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'sticky')

def unsticky_thread(task_data, num):
    return task_data.board.toggle_thread_state(task_data, num, 'sticky',
                                               enable_state=False)

def delete_by_board_ip(task_data, **kwargs):
    return task_data.board.delete_by_ip(task_data=task_data, **kwargs)

def rebuild_board(task_data):
    return task_data.board.rebuild_cache_proxy(task_data)

class StaffAction(object):
    ACTION_MAP = {
        'admin_entry' : interboard.add_admin_entry,
        'remove_admin_entry': interboard.remove_admin_entry,
        'edit_admin_entry': interboard.edit_admin_entry,
        'admin_post' : make_admin_post,
        'admin_edit' : edit_admin_post,
        'admin_delete' : delete_admin_post,
        'thread_sticky' : sticky_thread,
        'thread_unsticky' : unsticky_thread,
        'thread_lock' : lock_thread,
        'thread_unlock' : unlock_thread,
        'report_resolve' : interboard.mark_resolved,
        'backup_remove' : delete_backup_post,
        'thread_move' : interboard.move_thread,
        'delete_by_ip_global': interboard.delete_by_ip,
        'delete_by_ip': delete_by_board_ip,
        'rebuild': rebuild_board,
        'rebuild_global': interboard.global_cache_rebuild_proxy,
        'update_spam': interboard.update_spam_file,
        # Unimplemented :B
        'script_ban_forgive' : None,
    }

    def __init__(self, admin, action, **kwargs):
        self.action = action
        self.user = staff.check_password(admin)
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

    def execute(self):
        res = None
        try:
            if self.board:
                res = self.ACTION_MAP[self.action](self, **self.kwargs)
            else:
                res = self.ACTION_MAP[self.action](self, **self.kwargs)

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
                                        timestamp=self.timestamp)
            session.execute(sql)
