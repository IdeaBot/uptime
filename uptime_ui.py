from addons.UIdea.libs import ui as ui_class
from libs import dataloader
import re
import time

CURSOR = ' **<**'
BACK = '*<<Back*'
UPTIMES = '`%d` up | `%d` down'
UPTIME_P = '`%.4f%%` uptime'

TITLE = 'Uptime'

class UI(ui_class.UI):
    def shouldCreate(msg):
        return collect_args(msg) is not None

    def onCreate(self, msg):
        args = collect_args(msg)
        self.adding = False
        self.removing = False
        self.selected = -1 # list of checkers
        self.confirming = False
        self.owner = msg.author.id
        self._load_db_data()
        self.cursor_index = 0
        self._update_em()

    def down(self, reaction, user):
        self.confirming = False
        if self.cursor_index+1 < len(self.checkers):
            self.cursor_index += 1
        self._update_em()

    def up(self, reaction, user):
        self.confirming = False
        if self.cursor_index > 0:
            self.cursor_index -= 1
        self._update_em()

    def select(self, reaction, user):
        if not self.confirming:
            if len(self.checkers) > 0:
                if self.selected == -1:
                    self.selected, self.cursor_index = self.cursor_index, 0
                else:
                    self._interact_with(self.selected, self.cursor_index)
        else:
            self._remove(self.selected)
            self.selected = -1
        self._update_em()
        self.confirming = False

    def add(self, reaction, user):
        if self.selected == -1:
            self.adding = not self.adding
            self.removing = False
        if self.confirming:
            self.confirming = False
        self._update_em()

    def remove(self, reaction, user):
        if self.selected == -1:
            self.removing = not self.removing
            self.adding = False
        elif not self.confirming:
            self.confirming = True
            self.embed.description = '**Delete `%s`?**\nClick ☑ to confirm (any other buttom will dismiss).' % self._build_name(self.rows[self.selected])
            self.update()
            return
        self._update_em()
        self.confirming = False

    def onMessage(self, message):
        self.confirming = False
        if self.adding:
            self._add_from_msg(message)
            self.adding = False
        elif self.removing:
            self._remove_from_msg(message)
            self.removing = False
        self._update_em()

    def _build_description(self):
        desc = ''
        if self.selected == -1:
            desc = self._draw_cursor_in_lines(self.checkers)
        else:
            s_row = self.rows[self.selected]  # selected row
            lines = [
                    BACK,
                    UPTIMES % (s_row['uptime'], s_row['downtime']),
                    UPTIME_P % (100*s_row['uptime'] / (s_row['uptime'] + s_row['downtime']))
                    ]
            if s_row['type'] == 'web':
                # append custom stuff to lines
                pass
            if s_row['type'] == 'user':
                # append custom stuff to lines
                pass
            # cursor is disabled for now since there's nothing to select!
            desc = self._draw_cursor_in_lines(lines, cursor='')
        return desc

    def _draw_cursor_in_lines(self, lines, cursor=CURSOR):
        desc = ''
        for i in range(len(lines)):
            desc += lines[i]
            if i == self.cursor_index:
                desc += cursor
            desc += '\n'
        if desc != '':
            return desc
        else:
            return '-- No entries --'

    def _update_em(self):
        if self.adding:
            self.embed.title = TITLE + ' +++'
        elif self.removing:
            self.embed.title = TITLE + ' ---'
        else:
            self.embed.title = TITLE
        self.embed.description = self._build_description()
        self.update()

    def _interact_with(self, row_index, cursor_index):
        if cursor_index == 0:  # back
            self.selected = -1
            return
        if cursor_index in [1, 2]:
            # ignore; data lines
            return
        s_row = self.rows[row_index]
        # handle by uptime checker type and cursor index
        if s_row['type'] == 'web':
            return
        elif s_row['type'] == 'user':
            return

    def _remove(self, index):
        selected_row = self.rows[index]
        del(self.rows[index])
        del(self.checkers[index])
        self.public_namespace.db.execute('DELETE FROM uptimes WHERE id=?', (selected_row['id'],))
        self.public_namespace.db.save()

    def _add_from_msg(self, msg):
        # determine uptime type
        param, type = extract_uptime(msg.content)
        if param is None:
            return
        period = 60
        # add db entry
        self.public_namespace.db.execute('INSERT INTO uptimes (owner, parameter, type, period, lastupdated) VALUES (?,?,?,?,?)', (self.owner, param, type, period, int(time.time())))
        # generate necessary stuff to add to uptime checker list
        self.public_namespace.db.execute('SELECT * FROM uptimes WHERE owner=? and parameter=?', (self.owner, param))
        new_row = list(self.public_namespace.db.cursor.fetchall())[-1]
        self.rows.append(new_row)
        self.checkers.append(self._make_checker_line(new_row))
        self.public_namespace.db.save()

    def _remove_from_msg(self, msg):
        # verify uptime entry exists & owned by msg.author
        param, type = extract_uptime(msg.content)
        if param is None:
            return
        for i in range(len(self.rows)):
            if self.rows[i]['parameter'] == param:
                self._remove(i)
                return

    def _load_db_data(self):
        # get uptime entries owned by self.owner
        self.public_namespace.db.execute('SELECT * FROM uptimes WHERE owner=? ORDER BY id ASC', (self.owner,))
        self.checkers = list()
        self.rows = list(self.public_namespace.db.cursor.fetchall())
        # generate lines to display
        for row in self.rows:
            self.checkers.append(self._make_checker_line(row))

    def _make_checker_line(self, row):
        uptime = 100*row['uptime'] / (row['uptime'] + row['downtime'])
        if uptime >= 100:
            filler = ''
        elif uptime >= 10:
            filler = '.'
        else:
            filler = '..'
        result = ('`%s%.2f%%`| ' % (filler, uptime)) + self._build_name(row)
        return result

    def _build_name(self, row):
        if row['type'] == 'user':
            return '<@!%s>' % row['parameter']
        elif row['type'] == 'web':
            return '<%s>' % row['parameter']

def collect_args(msg):
    return re.search(r'\bview\s+uptimes?\b', msg.content, re.I)

def extract_uptime(string):
    web_match = re.match(r'\s*<?(https?:\/\/(?:\S+))>?\b', string)
    if web_match is not None:
        # print(web_match.group(1), 'web')
        return web_match.group(1), 'web'
    # user_match = re.match(r'\s*(?:\<\@\!?)?(\d{18})>?', string)
    # if user_match is not None:
    #     print(user_match.group(1), 'user')
    #     return user_match.group(1), 'user'
    # print('no match')
    return None, None
