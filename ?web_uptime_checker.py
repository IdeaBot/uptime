from libs import plugin, dataloader
import requests
import time

DB_FILE = 'data/uptime.db'

CREATE_UPTIMES_TABLE_SQL = '''CREATE TABLE IF NOT EXISTS uptimes (
id INTEGER PRIMARY KEY,
parameter TEXT,
owner TEXT NOT NULL,
uptime INTEGER NOT NULL DEFAULT 1,
downtime INTEGER NOT NULL DEFAULT 0,
max INTEGER NOT NULL DEFAULT 4194304,
period INTEGER NOT NULL DEFAULT 60,
type TEXT NOT NULL DEFAULT "web",
lastupdated INTEGER NOT NULL DEFAULT 0,
notify INTEGER NOT NULL DEFAULT 0,
isup INTEGER NOT NULL DEFAULT 1
); '''

COLUMNS = {
            'parameter':'TEXT',
            'uptime':'INTEGER NOT NULL DEFAULT 1',
            'downtime':'INTEGER NOT NULL DEFAULT 0',
            'max':'INTEGER NOT NULL DEFAULT 4194304',
            'period':'INTEGER NOT NULL DEFAULT 60',
            'type':'TEXT NOT NULL DEFAULT "web"',
            'lastupdated':'INTEGER NOT NULL DEFAULT 0',
            'notify':'INTEGER NOT NULL DEFAULT 0',
            'isup':'INTEGER NOT NULL DEFAULT 1'
            }

TIMEOUT = 1 # GET request timeout, in seconds

class Plugin(plugin.ThreadedPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, should_spawn_thread=False, **kwargs)
        self.public_namespace.db = dataloader.datafile(DB_FILE, load_as='db')
        self.public_namespace.db.execute(CREATE_UPTIMES_TABLE_SQL)
        self.public_namespace.db.patch('uptimes', COLUMNS, commit=True)
        self.run = 0
        self.spawn_process()

    def threaded_action(self, q):
        self.public_namespace.db.execute('SELECT * FROM uptimes WHERE type=\"web\"')
        rows = self.public_namespace.db.cursor.fetchall()
        for row in rows:
            if (self.run * self.threaded_period) % row['period'] < self.threaded_period:
                try:
                    requests.get(row['parameter'], timeout=TIMEOUT)
                except requests.exceptions.RequestException as e:
                    up, down = next_values(row['uptime'], row['downtime'], max=row['max'], mode='down')
                    if row['notify'] == 1 and row['isup'] == 1:
                        pass
                        # q.put({self.SEND_MESSAGE:{plugin.ARGS = [row['owner'], row['parameter'] + ' has gone offline']}})
                    self.public_namespace.db.execute('UPDATE uptimes SET uptime=?, downtime=?, lastupdated=?, isup=0 WHERE id=?', (up, down, int(time.time()), row['id']))
                else:
                    up, down = next_values(row['uptime'], row['downtime'], max=row['max'], mode='up')
                    self.public_namespace.db.execute('UPDATE uptimes SET uptime=?, downtime=?, lastupdated=?, isup=1 WHERE id=?', (up, down, int(time.time()), row['id']))
        self.public_namespace.db.save()
        self.run += 1

def next_values(up, down, max, mode):
    if mode == 'up':
        if up+1 == max:
            if down == 0:
                return up, down
            else:
                return up, down-1
        else:
            return up+1, down

    elif mode == 'down':
        if down+1 == max:
            if up == 0:
                return up, down
            else:
                return up-1, down
        else:
            return up, down+1

    else:
        return up, down
