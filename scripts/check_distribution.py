"""Inspect final archive contents, not just ignore rules."""
import argparse,json,tarfile,zipfile
from pathlib import Path
BAD=('calibration.py','bias_checks.py','claim_controls.py','interventions.py','supplemental.py','requests.sqlite3','auth.json')
def check(directory):
    reports=[]
    for path in sorted(Path(directory).iterdir()):
        if path.suffix=='.whl':
            with zipfile.ZipFile(path) as z:
                names=z.namelist()
                if z.testzip():raise ValueError('Corrupt wheel')
        elif path.name.endswith('.tar.gz'):
            with tarfile.open(path) as t:names=t.getnames()
        else:continue
        if any(any(b in n for b in BAD) or '/datasets/' in n or '/evals/' in n or '/.eg/' in n or '..' in Path(n).parts for n in names):raise ValueError('Private or answer-bearing material in '+path.name)
        if not any(n.endswith('/LICENSE') for n in names):raise ValueError('Missing MIT text')
        if not any(n.endswith('/schemas/sample-0.1.0.json') for n in names):raise ValueError('Missing runtime schema')
        reports.append({'file':path.name,'entries':len(names),'status':'pass'})
    if len(reports)!=2:raise ValueError('Expected one wheel and one sdist')
    return reports
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);a=p.parse_args();print(json.dumps(check(a.directory),indent=2))
