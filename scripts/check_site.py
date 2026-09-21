"""Verify prefixed local links, manifest hashes and data consistency."""
import argparse,hashlib,json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse,unquote
class Links(HTMLParser):
    def __init__(self):super().__init__();self.values=[]
    def handle_starttag(self,tag,attrs):
        self.values.extend(v for k,v in attrs if k in ('href','src') and v)
def check_result_counts(report):
    if 'counts' not in report:return False
    expected=report['counts'];totals={k:0 for k in ('registered','recorded','completed','execution_errors','without_terminal_record')}
    for group in report.get('suite_results',[]):
        if group['suite'] not in ('StyleBench-ZH','DeliveryBench-ZH'):raise ValueError('Unknown result suite')
        for row in group['rows']:
            values={k:row[k] for k in ('n','recorded','completed','execution_errors','without_terminal_record','effective_success_count')}
            if any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in values.values()):raise ValueError('Invalid result count')
            if row['mode'] not in ('style','process','both'):raise ValueError('Unknown result mode')
            if not (row['n']==row['recorded']+row['without_terminal_record'] and row['recorded']==row['completed']+row['execution_errors'] and row['effective_success_count']<=row['completed']):raise ValueError('Inconsistent result row')
            for column,denominator in [('success','recorded'),('success_given_completion','completed')]:
                n=row['effective_success_count'];d=row[denominator];display=f'{n}/{d} ({n/d:.1%})' if d else '未定义（分母为0）'
                if row[column]!=display:raise ValueError('Displayed success denominator differs')
            for name in totals:totals[name]+=row['n' if name=='registered' else name]
    if any(totals[k]!=expected[k] for k in totals):raise ValueError('Result totals differ from displayed strata')
    return True

def check(directory):
    root=Path(directory);manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'));base=manifest['base_path'];errors=[]
    actual={str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*') if p.is_file() and p.name!='manifest.json'}
    if actual!=set(manifest['files']):errors.append('manifest_file_set_mismatch')
    for name,digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:errors.append('unsafe_manifest_path');continue
        p=root/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append(name+':hash')
    for page in root.glob('*.html'):
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for value in parser.values:
            link=urlparse(value)
            if link.scheme or value.startswith('#'):continue
            path=unquote(link.path)
            if path.startswith(base):path=path[len(base):]
            elif path.startswith('/'):errors.append(page.name+':wrong_prefix:'+path);continue
            target=root/(path or 'index.html')
            if target.is_dir():target=target/'index.html'
            if not target.is_file():errors.append(page.name+':broken_link:'+path)
    samples=json.loads((root/'assets/samples.json').read_text(encoding='utf-8'))
    if len(samples)!=manifest['samples']:errors.append('sample_count')
    results=json.loads((root/'assets/results.json').read_text(encoding='utf-8'))
    result_counts_verified=check_result_counts(results)
    if errors:raise ValueError(json.dumps(errors))
    return {'status':'pass','pages':len(list(root.glob('*.html'))),'samples':len(samples),'build_commit':manifest['build_commit'],'result_counts_verified':result_counts_verified}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);a=p.parse_args();print(json.dumps(check(a.directory),indent=2))
