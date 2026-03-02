import sqlite3
conn=sqlite3.connect('_tmp_webui.db')
cur=conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print('TABLES:')
for r in cur.fetchall():
    print(r[0])

for t in ['config','models','users','functions','pipelines','settings','tools','memories','tags','folders']:
    cur.execute(f'PRAGMA table_info({t})')
    cols=[r[1] for r in cur.fetchall()]
    if cols:
        print(f'\n[{t}] cols={cols}')
        cur.execute(f'SELECT * FROM {t} LIMIT 50')
        for row in cur.fetchall():
            print(row)
