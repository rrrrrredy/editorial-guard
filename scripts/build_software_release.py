"""Build a software-only release; never relabel or re-export frozen datasets."""
import argparse, hashlib, json, subprocess, sys, tempfile, tomllib
from pathlib import Path
from build_release import pack, tracked_skill_files
from build_platform_packages import build as build_platforms

ROOT=Path(__file__).resolve().parents[1]

def build(output, acceptance, commit):
    out=Path(output).resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('Output must be outside source repository')
    gate=json.loads(Path(acceptance).read_text(encoding='utf-8'))
    if gate.get('commit')!=commit or gate.get('local_release_ready') is not True:raise ValueError('Exact-commit acceptance required')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Clean accepted HEAD required')
    if out.exists() and any(out.iterdir()):raise ValueError('Output must be empty')
    version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    build_platforms(out)
    subprocess.run([sys.executable,'-m','build','--no-isolation','--outdir',str(out)],cwd=ROOT,check=True)
    subprocess.run(['git','archive','--format=zip','--prefix=editorial-guard-'+version+'/', '--output',str(out/('editorial-guard-source-v'+version+'.zip')),commit],cwd=ROOT,check=True)
    for skill in ('style-editor-zh','delivery-cleaner-zh'):
        items=tracked_skill_files(ROOT,commit,skill)+[(ROOT/'LICENSE',skill+'/LICENSE')]
        pack(ROOT,out/(skill+'-v'+version+'.zip'),items)
    manifest={'software_version':version,'commit':commit,'data_version':'0.1.1','data_changed':False,
              'datasets':{name:'https://huggingface.co/datasets/RedinGhost/'+name+'/tree/v0.1.1' for name in ('StyleBench-ZH','DeliveryBench-ZH')}}
    (out/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'SHA256SUMS').write_text(''.join(v+'  '+n+'\n' for n,v in hashes.items()),encoding='ascii')
    return {'version':version,'commit':commit,'artifacts':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--acceptance',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
    print(json.dumps(build(a.output,a.acceptance,a.commit),indent=2))
