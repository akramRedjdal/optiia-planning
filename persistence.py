"""Local persistent scenario storage; no credentials or publication approval saved."""
import json, os, tempfile
from pathlib import Path
PATH=Path(__file__).resolve().parent/'.local'/'scenario.json'
def load():
    if not PATH.exists(): return {}
    data=json.loads(PATH.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('team'),list): raise ValueError('Scénario invalide')
    return data

def save(data):
    payload=json.dumps(data,ensure_ascii=False,indent=2)
    if PATH.exists() and PATH.read_text(encoding='utf-8')==payload:return
    PATH.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=PATH.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(payload)
        os.replace(tmp,PATH)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def reset():
    PATH.unlink(missing_ok=True)
