
class WakaPost(object):
    '''A post object that uses __slots__ for no good reason'''

    __slots__ = [
        # columns copied directly from model.board
        'num', 'parent', 'timestamp', 'lasthit', 'ip', 'date', 'name', 'trip',
        'email', 'subject', 'password', 'comment', 'image', 'size', 'md5',
        'width', 'height', 'thumbnail', 'tn_width', 'tn_height', 'lastedit',
        'lastedit_ip', 'admin_post', 'stickied', 'locked',
        # extensions
        'abbrev', 'req', 'req_file',
    ]

    def __init__(self, rowproxy=None, **kwargs):

        if rowproxy:
            self.update(items=rowproxy.items())
        else:
            self.update(**kwargs)

        self.abbrev = 0

    def update(self, items=None, **kwargs):
        for key, value in (items or kwargs.iteritems()):
            setattr(self, key, value)

    def __repr__(self):
        parent = ''
        if self.parent:
            parent = ' in thread %s' % self.parent
        return '<Post >>%s%s>' % (self.num, parent)
