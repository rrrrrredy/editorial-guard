"""Recompute released result tables without credentials or model calls.

A successful replay establishes record and calculation consistency, not semantic truth.
"""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from editorial_guard.evals import eval_report

def replay(directory):
 root=Path(directory).resolve()
 manifest=json.loads((root/'results-manifest.json').read_text(encoding='utf-8'))
 for name,digest in manifest['files'].items():
  path=(root/name).resolve()
  if not path.is_relative_to(root) or not path.is_file():raise ValueError('Unsafe or missing result file')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Result file differs from manifest: '+name)
 counts={}
 for name in ('core','H2'):
  protocol=json.loads((root/(name+'-manifest.json')).read_text(encoding='utf-8'))
  cells=[json.loads(line) for line in (root/(name+'-cells.jsonl')).read_text(encoding='utf-8').splitlines() if line]
  def key(c):return tuple(c[k] for k in ('id','provider','method','mode','repeat'))
  expected={key(c) for c in protocol['cells']};observed={key(c) for c in cells}
  if len(observed)!=len(cells) or observed!=expected:raise ValueError('Missing, duplicate or unregistered result cells')
  saved=json.loads((root/(name+'-results.json')).read_text(encoding='utf-8'))
  if eval_report(cells)!=saved:raise ValueError('Saved metrics do not reproduce: '+name)
  counts[name]={'registered':len(expected),'recorded':len(cells),'completed':sum(c['status']=='completed' for c in cells)}
 return {'status':'pass','experiments':counts,'model_calls':0,'scope':'Saved records and metric calculations only; does not validate model judgments'}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',default='reports');args=parser.parse_args()
 print(json.dumps(replay(args.directory),ensure_ascii=False,indent=2))
