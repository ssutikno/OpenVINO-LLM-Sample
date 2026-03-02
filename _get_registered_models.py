import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path

container='open-webui'
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/'webui.db'
    subprocess.run(['docker','cp',f'{container}:/app/backend/data/webui.db',str(db)], check=True)
    conn=sqlite3.connect(db)
    cur=conn.cursor()
    cur.execute('SELECT id FROM model ORDER BY id')
    model_ids=[r[0] for r in cur.fetchall() if r and r[0]]
    conn.close()
print(','.join(model_ids))
