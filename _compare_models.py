import json
import sqlite3
from pathlib import Path
import subprocess
import tempfile

root = Path(r'c:\Users\user\Development\vllm-openvino')
models_dir = root / 'models'
container = 'open-webui'

# local downloaded models from filesystem
local_models = []
if models_dir.exists():
    for org in models_dir.iterdir():
        if not org.is_dir():
            continue
        for model in org.iterdir():
            if not model.is_dir():
                continue
            try:
                has_content = any(model.iterdir())
            except Exception:
                has_content = False
            if has_content:
                local_models.append(f"{org.name}/{model.name}")
local_set = set(sorted(local_models))

# openwebui registered models from db (model table + user ui.models)
with tempfile.TemporaryDirectory() as td:
    db = Path(td) / 'webui.db'
    subprocess.run(['docker','cp',f'{container}:/app/backend/data/webui.db',str(db)], check=True)
    conn = sqlite3.connect(db)
    cur = conn.cursor()

    cur.execute('SELECT id FROM model')
    model_table = {r[0] for r in cur.fetchall() if r and r[0]}

    cur.execute('SELECT settings FROM user')
    ui_models = set()
    for (raw,) in cur.fetchall():
        if not raw:
            continue
        try:
            data = json.loads(raw)
            arr = data.get('ui',{}).get('models',[])
            if isinstance(arr, list):
                ui_models.update([x for x in arr if x])
        except Exception:
            pass
    conn.close()

openwebui_set = set(sorted(model_table | ui_models))

only_local = sorted(local_set - openwebui_set)
only_openwebui = sorted(openwebui_set - local_set)
both = sorted(local_set & openwebui_set)

print('LOCAL_COUNT', len(local_set))
print('OPENWEBUI_COUNT', len(openwebui_set))
print('MATCH_COUNT', len(both))
print('ONLY_LOCAL_COUNT', len(only_local))
print('ONLY_OPENWEBUI_COUNT', len(only_openwebui))
print('')
print('ONLY_LOCAL')
for m in only_local:
    print('-', m)
print('')
print('ONLY_OPENWEBUI')
for m in only_openwebui:
    print('-', m)
print('')
print('MATCHED')
for m in both:
    print('-', m)
