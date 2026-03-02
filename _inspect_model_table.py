import sqlite3, json
conn=sqlite3.connect('_tmp_webui.db')
cur=conn.cursor()
cur.execute("PRAGMA table_info(model)")
print('MODEL COLS:', [r[1] for r in cur.fetchall()])
cur.execute("SELECT * FROM model")
rows=cur.fetchall()
print('MODEL ROW COUNT:', len(rows))
for i,row in enumerate(rows,1):
    print(f'ROW {i}:', row)
