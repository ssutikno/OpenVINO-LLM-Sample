import sqlite3, json
conn=sqlite3.connect('_tmp_webui.db')
cur=conn.cursor()
cur.execute("PRAGMA table_info(user)")
print('USER COLS:', [r[1] for r in cur.fetchall()])
cur.execute("SELECT id,email,role,settings,info FROM user")
rows=cur.fetchall()
print('USER ROW COUNT:', len(rows))
for r in rows:
    print('USER:', r[0], r[1], r[2])
    print(' settings=', r[3])
    print(' info=', r[4])
