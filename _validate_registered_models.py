import json, sqlite3, subprocess, tempfile
from pathlib import Path
root = Path(r'c:\Users\user\Development\vllm-openvino\models')
container='open-webui'
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/'webui.db'
    subprocess.run(['docker','cp',f'{container}:/app/backend/data/webui.db',str(db)], check=True)
    conn=sqlite3.connect(db)
    cur=conn.cursor()
    cur.execute('SELECT id FROM model ORDER BY id')
    mids=[r[0] for r in cur.fetchall() if r and r[0]]
    conn.close()

print('REGISTERED_COUNT', len(mids))
for m in mids:
    p = root / Path(m.replace('/','\\'))
    checks = {
        'exists': p.exists(),
        'graph.pbtxt': (p/'graph.pbtxt').exists(),
        'openvino_model.xml': (p/'openvino_model.xml').exists(),
        'openvino_model.bin': (p/'openvino_model.bin').exists(),
    }
    print(m, checks)
