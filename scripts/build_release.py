"""Build version-consistent release archives from an accepted commit and data export."""
import argparse,hashlib,json,subprocess,sys,tomllib,zipfile
from pathlib import Path


DATA_FILES={'samples.jsonl','task-views.jsonl','task-view-index.json','partitions.json','disputed-index.json','summary.json','quality-index.json','family-manifest.json'}
SUITES=('StyleBench-ZH','DeliveryBench-ZH')

def checked_data_files(data,manifest):
    data=Path(data).resolve();approved=set(manifest['files'])
    actual={p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file() and p.relative_to(data).as_posix()!='manifest.json'}
    if actual!=approved:raise ValueError('Data directory differs from approved manifest')
    for name in sorted(approved):
        parts=Path(name).parts
        if name!='validation.json' and not (len(parts)==2 and parts[0] in SUITES and parts[1] in DATA_FILES):
            raise ValueError('Unapproved data artifact name')
        source=data/name
        if not source.resolve().is_relative_to(data) or source.is_symlink():raise ValueError('Unsafe data artifact path')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][name]:raise ValueError('Data export changed')
        if name.endswith('/samples.jsonl'):
            approved_locked=manifest.get('locked_test_release',{}).get('family_ids')
            for line in source.read_text(encoding='utf-8').splitlines():
                if not line:continue
                row=json.loads(line)
                if row.get('split')=='locked_test' and (not manifest.get('locked_test_released') or (approved_locked is not None and row.get('source_group_id') not in approved_locked)):
                    raise ValueError('Locked sample is outside the approved family release list')
    return approved

def tracked_skill_files(root,commit,skill):
    prefix='skills/'+skill+'/'
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'--',prefix],cwd=root,text=True).splitlines()
    if not names:raise ValueError('Skill is not part of accepted commit')
    items=[]
    for name in names:
        source=root/name
        if not source.resolve().is_relative_to(root) or source.is_symlink():raise ValueError('Unsafe Skill source path')
        items.append((source,skill+'/'+name[len(prefix):]))
    return items

def pack(root,destination,items):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for source,name in items:
            if '..' in Path(name).parts or name.startswith(('/','\\')):raise ValueError('Unsafe archive path')
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,Path(source).read_bytes())
    with zipfile.ZipFile(destination) as z:
        if z.testzip():raise ValueError('Archive CRC validation failed')

def build(root,data,output,acceptance,commit):
    root=Path(root).resolve();data=Path(data).resolve();out=Path(output).resolve()
    if out==root or root in out.parents:raise ValueError('Release output must be outside the repository')
    gate=json.loads(Path(acceptance).read_text(encoding='utf-8'))
    if not gate.get('local_release_ready') or gate.get('commit')!=commit:raise ValueError('Exact-commit local acceptance required')
    manifest=json.loads((data/'manifest.json').read_text(encoding='utf-8'))
    if manifest['phases']['main']['families']!=500 or manifest['phases']['calibration']['families']!=80:raise ValueError('Main/calibration family targets not met')
    if manifest['validation_status']!='pass' or not manifest['locked_test_released']:raise ValueError('Data validation and frozen evaluation release gate required')
    approved_data=checked_data_files(data,manifest)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
    if actual!=commit or dirty:raise ValueError('Build requires clean accepted HEAD')
    version=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if manifest['version']!=version:raise ValueError('Data and package versions differ')
    out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise ValueError('Refuse mixing with existing release assets')
    subprocess.run([sys.executable,'-m','build','--no-isolation','--outdir',str(out)],cwd=root,check=True)
    source=out/('editorial-guard-source-v'+version+'.zip')
    subprocess.run(['git','archive','--format=zip','--prefix=editorial-guard-'+version+'/','--output',str(source),commit],cwd=root,check=True)
    for skill in ('style-editor-zh','delivery-cleaner-zh'):
        folder=root/'skills'/skill
        items=tracked_skill_files(root,commit,skill)
        items.append((root/'LICENSE',skill+'/LICENSE'))
        pack(root,out/(skill+'-v'+version+'.zip'),items)
    for suite in ('StyleBench-ZH','DeliveryBench-ZH'):
        folder=data/suite
        items=[(data/name,name) for name in sorted(approved_data) if name.startswith(suite+'/')]
        items.extend([(root/'datasets'/suite/'DATASET_CARD.md',suite+'/DATASET_CARD.md'),(root/'datasets'/suite/'CITATION.cff',suite+'/CITATION.cff'),(root/'LICENSES/CC-BY-4.0.txt',suite+'/LICENSE'),(data/'manifest.json',suite+'/release-manifest.json')])
        pack(root,out/(suite+'-v'+version+'.zip'),items)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in hashes.items()),encoding='ascii')
    return {'version':version,'commit':commit,'artifacts':hashes,'checksum_file':'SHA256SUMS'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--output',required=True);p.add_argument('--acceptance',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],a.data,a.output,a.acceptance,a.commit),indent=2))
