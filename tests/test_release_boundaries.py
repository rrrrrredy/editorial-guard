import importlib.util,json,subprocess,sys
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from editorial_guard.core import Context,content_hash
from editorial_guard.finalize import acceptance_key,ReceiptStore
from editorial_guard.hooks import register,handle_event
from editorial_guard.ledger import Ledger

def test_real_cross_process_reservation(tmp_path):
    path=tmp_path/'ledger.db';Ledger(path)
    code="import sys;from editorial_guard.ledger import Ledger,Busy\ntry: Ledger(sys.argv[1]).reserve(sys.argv[2],'deepseek',{});print('reserved')\nexcept Busy: print('busy')"
    processes=[subprocess.Popen([sys.executable,'-c',code,str(path),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(6)]
    outputs=[p.communicate(timeout=30) for p in processes]
    assert all(p.returncode==0 for p in processes),outputs
    assert sum(out.strip()=='reserved' for out,err in outputs)==1
    assert Ledger(path).summary()['requests']==1

def test_hook_config_change_invalidates(tmp_path):
    config=tmp_path/'config.json';config.write_text('{"providers":{}}',encoding='utf-8')
    candidate=tmp_path/'candidate.md';candidate.write_text('这个项目目前仅支持本地读取。',encoding='utf-8')
    store=ReceiptStore(tmp_path/'.eg/receipts')
    receipt=store.issue({'status':'pass','candidate_hash':content_hash(candidate.read_text(encoding='utf-8'))},'run','turn',acceptance_key({'providers':{}},Context()))
    register(tmp_path,candidate,receipt,config)
    assert handle_event(tmp_path,{'hook_event_name':'Stop','session_id':'r','turn_id':'t'})=={}
    config.write_text('{"providers":{"glm":{"model":"changed"}}}',encoding='utf-8')
    result=handle_event(tmp_path,{'hook_event_name':'Stop','session_id':'r','turn_id':'t'})
    assert result['decision']=='block'

def test_public_scanner_redacts_actual_match(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('public_check',root/'scripts/check_public.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    value='only-for-the-secret-scanner-fixture'
    (tmp_path/'README.md').write_text(value,encoding='utf-8')
    result=module.scan(tmp_path,['README.md'],[value])
    assert result['status']=='fail'
    assert value not in json.dumps(result)
    assert module.inspect_names(['../escape.txt','.eg/requests.sqlite3'])

def test_site_rejects_unreleased_locked_test(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('site_build',root/'scripts/build_site.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import shutil
    shutil.copytree(root/'site',tmp_path/'site')
    shutil.copyfile(root/'pyproject.toml',tmp_path/'pyproject.toml')
    (tmp_path/'datasets').mkdir()
    (tmp_path/'datasets/public_samples.json').write_text('[{"split":"locked_test"}]',encoding='utf-8')
    with pytest.raises(ValueError,match='Locked data'):module.build(tmp_path,tmp_path/'out','/editorial-guard/','unpublished')


def test_site_refuses_stale_or_unrelated_output(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('site_build',root/'scripts/build_site.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    out=tmp_path/'out';out.mkdir();(out/'private.txt').write_text('private fixture',encoding='utf-8')
    with pytest.raises(ValueError,match='empty'):module.build(root,out,'/editorial-guard/','unpublished')
    assert (out/'private.txt').read_text(encoding='utf-8')=='private fixture'

def test_release_manifest_rejects_added_or_changed_data(tmp_path):
    import hashlib
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('release_build',root/'scripts/build_release.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    folder=tmp_path/'StyleBench-ZH';folder.mkdir()
    source=folder/'samples.jsonl';source.write_text('{}\n',encoding='utf-8')
    manifest={'files':{'StyleBench-ZH/samples.jsonl':hashlib.sha256(source.read_bytes()).hexdigest()}}
    assert module.checked_data_files(tmp_path,manifest)==set(manifest['files'])
    extra=folder/'private-notes.txt';extra.write_text('must not be packed',encoding='utf-8')
    with pytest.raises(ValueError,match='differs'):module.checked_data_files(tmp_path,manifest)
    extra.unlink();source.write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='changed'):module.checked_data_files(tmp_path,manifest)

def test_data_export_refuses_mixed_output(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('research_export',root/'scripts/export_research.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    destination=tmp_path/'output';destination.mkdir()
    (destination/'private.txt').write_text('preserve',encoding='utf-8')
    with pytest.raises(ValueError,match='empty'):module.export(tmp_path/'work',destination)
    assert (destination/'private.txt').read_text()=='preserve'


@pytest.mark.parametrize('json_layers',[0,1,2])
@pytest.mark.parametrize('parts',[('D:','Codex','private','file.json'),('D:','Documents','private.txt'),('C:','Users','example','file.json')])
def test_public_scanner_rejects_escaped_personal_path(tmp_path,json_layers,parts):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('public_check',root/'scripts/check_public.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text=chr(92).join(parts)
    for _ in range(json_layers):text=json.dumps({'path':text})
    (tmp_path/'README.md').write_text(text,encoding='utf-8')
    result=module.scan(tmp_path,['README.md'])
    assert result['status']=='fail'
    assert result['errors']==[{'path':'README.md','kind':'personal_absolute_path'}]


def test_site_build_normalizes_checkout_line_endings(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('site_build',root/'scripts/build_site.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    builds=[]
    for label,newline in [('lf',chr(10)),('crlf',chr(13)+chr(10))]:
        source=tmp_path/label
        for original in (root/'site').rglob('*'):
            if original.is_file():
                target=source/'site'/original.relative_to(root/'site');target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(original.read_text(encoding='utf-8').replace(chr(10),newline).encode('utf-8'))
        (source/'pyproject.toml').write_bytes((root/'pyproject.toml').read_bytes())
        out=tmp_path/(label+'-build')
        module.build(source,out,'/editorial-guard/','unpublished')
        builds.append({p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()})
    assert builds[0]==builds[1]
    assert all(bytes([13,10]) not in content for content in builds[0].values())


def test_export_and_pack_keep_unevaluated_locked_family_private(tmp_path):
    from editorial_guard.dataset import family_spec,instances,write_json
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('scoped_export',root/'scripts/export_research.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    work=tmp_path/'work';Ledger(work/'requests.sqlite3')
    for index in (0,1,400,401):
        family=family_spec(index,'main')
        text='未公开锁定内容标记' if index==401 else '公开测试内容'+str(index)
        records=instances(family,{'input_text':text,'style_variant':text},{'ledger_id':'fixture','requested_model':'fixture','reported_model':'fixture'})
        write_json(work/'data/main'/(family['source_group_id']+'.json'),{'spec':family,'records':records})
    out=tmp_path/'out';manifest=module.export(work,out,True,{'main-0400'})
    assert manifest['phases']['main']['families']==4
    assert manifest['locked_test_release']['family_ids']==['main-0400']
    assert manifest['locked_test_release']['held_back_families']==1
    assert sum(v['families'] for v in manifest['suites'].values())==3
    for path in out.rglob('*'):
        if path.is_file():assert '未公开锁定内容标记' not in path.read_text(encoding='utf-8')
    spec=importlib.util.spec_from_file_location('scoped_release',root/'scripts/build_release.py')
    release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    release.checked_data_files(out,manifest)
    manifest['locked_test_release']['family_ids']=[]
    with pytest.raises(ValueError,match='outside the approved'):release.checked_data_files(out,manifest)


@pytest.mark.parametrize('autocrlf',['true','false'])
def test_hash_bound_reports_survive_git_index_normalization(tmp_path,autocrlf):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'.gitattributes').write_bytes((root/'.gitattributes').read_bytes())
    (tmp_path/'reports').mkdir()
    records={'reports/result.json':b'{"status":"fixture"}\r\n','reports/result.md':b'# Result\r\n','reports/cells.jsonl':b'{"cell":1}\n'}
    for name,data in records.items():(tmp_path/name).write_bytes(data)
    subprocess.run(['git','init','--quiet',str(tmp_path)],check=True,capture_output=True)
    subprocess.run(['git','-c','core.autocrlf='+autocrlf,'add','.gitattributes',*records],cwd=tmp_path,check=True,capture_output=True)
    for name,data in records.items():
        assert subprocess.check_output(['git','show',':'+name],cwd=tmp_path)==data
