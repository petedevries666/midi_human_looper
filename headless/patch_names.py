"""Patch slot labels are host metadata, separate from frozen musical schemas."""
import json,unicodedata
from project_sync import atomic_json

def read(directory):
    path=directory/'patch-names.json'
    if not path.exists():return {}
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or any(k not in ('1','2','3','4') or not isinstance(v,str) or len(v)>48 for k,v in data.items()):
        raise ValueError('Invalid patch names; original file preserved')
    return data

def rename(directory,slot,name,expected):
    if type(slot) is not int or slot not in (1,2,3,4) or not isinstance(name,str) or len(name)>48 or any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('Use a printable patch name of up to 48 characters')
    data=read(directory);key=str(slot)
    if data.get(key,'')!=expected:raise ValueError('Patch name changed; refresh before renaming')
    data[key]=name.strip();directory.mkdir(parents=True,exist_ok=True);atomic_json(directory/'patch-names.json',data)
    return data[key]
