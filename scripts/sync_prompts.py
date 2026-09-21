"""Generate MIT runtime prompt mirrors from the canonical Python protocol."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from editorial_guard import protocol
def synchronize(check=False):
    files={ROOT/'prompts'/(name.lower()+'.txt'):getattr(protocol,name)+'\n' for name in ['COMMON','GENERATE','ANNOTATE','EDIT','VERIFY']}
    for skill in ['style-editor-zh','delivery-cleaner-zh']:
        files[ROOT/'skills'/skill/'references/runtime-rules.md']=protocol.EDIT+'\n'
    files.update({ROOT/'schemas'/(name.lower()+'-0.1.0.json'):json.dumps(getattr(protocol,name),ensure_ascii=False,indent=2)+'\n' for name in ['ANNOTATIONS','GENERATION','VERDICT']})
    for path,body in files.items():
        if check:
            if not path.exists() or path.read_text(encoding='utf-8')!=body:raise ValueError('Prompt mirror differs: '+str(path.relative_to(ROOT)))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
if __name__=='__main__':synchronize('--check' in sys.argv)
