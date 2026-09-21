"""Bounded cell recovery, preserving the first failure and every previous execution."""
import json
from pathlib import Path
from .dataset import write_json

def prepare_cell(path,retry_errors=False):
    path=Path(path);previous=None
    if path.exists():
        previous=json.loads(path.read_text(encoding='utf-8'))
        if previous['status']!='error' or not retry_errors or previous.get('execution_attempt',1)>=3:
            return previous,None
        if callable(retry_errors) and not retry_errors(previous):return previous,None
        write_json(path.parent.parent/'execution_history'/(path.stem+'-'+str(previous.get('execution_attempt',1))+'.json'),previous)
    return None,{'execution_attempt':1 if previous is None else previous.get('execution_attempt',1)+1,
                 'first_execution_status':(previous.get('first_execution_status') or previous['status']) if previous else None}
