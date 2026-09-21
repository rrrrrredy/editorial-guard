import concurrent.futures,json,threading
from pathlib import Path
import pytest
from editorial_guard.dataset import write_json,write_jsonl
pytestmark=pytest.mark.unit

@pytest.mark.parametrize('line_format',[False,True])
def test_concurrent_snapshot_writers_publish_complete_records_without_temp_collisions(tmp_path,monkeypatch,line_format):
 target=tmp_path/('snapshot.jsonl' if line_format else 'snapshot.json')
 barrier=threading.Barrier(4);original_replace=Path.replace;entered=threading.local()
 def replace(path,destination):
  if Path(destination)==target and not getattr(entered,"ready",False):
   entered.ready=True;barrier.wait(timeout=5)
  return original_replace(path,destination)
 monkeypatch.setattr(Path,'replace',replace)
 values=[{'writer':i,'body':'正文'*200} for i in range(4)]
 def write(value):
  if line_format:write_jsonl(target,[value,value])
  else:write_json(target,value)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(write,values))
 if line_format:
  rows=[json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
  assert len(rows)==2 and rows[0]==rows[1] and rows[0] in values
 else:assert json.loads(target.read_text(encoding='utf-8')) in values
 assert sorted(p.name for p in tmp_path.iterdir())==[target.name]

def test_failed_snapshot_serialization_keeps_previous_file(tmp_path):
 path=tmp_path/'snapshot.jsonl';write_jsonl(path,[{'valid':True}])
 before=path.read_bytes()
 with pytest.raises(TypeError):write_jsonl(path,[{'valid':False},{'invalid':object()}])
 assert path.read_bytes()==before
 assert list(tmp_path.iterdir())==[path]

@pytest.mark.parametrize('line_format',[False,True])
@pytest.mark.parametrize('winerror',[5,32,33])
def test_transient_windows_lock_retries_atomic_replacement(tmp_path,monkeypatch,line_format,winerror):
 target=tmp_path/'snapshot';target.write_text('previous',encoding='utf-8')
 original_replace=Path.replace;attempts=[];delays=[]
 def replace(path,destination):
  attempts.append(path)
  assert target.read_text(encoding='utf-8')=='previous'
  if len(attempts)<3:
   error=PermissionError('transient lock');error.winerror=winerror;raise error
  return original_replace(path,destination)
 monkeypatch.setattr(Path,'replace',replace)
 monkeypatch.setattr('editorial_guard.dataset.time.sleep',delays.append)
 writer=write_jsonl if line_format else write_json
 writer(target,[{'complete':True}] if line_format else {'complete':True})
 assert json.loads(target.read_text(encoding='utf-8'))=={'complete':True}
 assert len(attempts)==3 and len(set(attempts))==1 and delays==[0.01,0.02]
 assert list(tmp_path.iterdir())==[target]

@pytest.mark.parametrize('winerror,expected_attempts',[(5,7),(32,7),(33,7),(None,1),(13,1)])
def test_unrecoverable_snapshot_permission_error_preserves_previous_file(tmp_path,monkeypatch,winerror,expected_attempts):
 target=tmp_path/'snapshot';target.write_bytes(b'previous');attempts=[];delays=[]
 error=PermissionError('unrecoverable')
 if winerror is not None:error.winerror=winerror
 def replace(path,destination):
  attempts.append(path);raise error
 monkeypatch.setattr(Path,'replace',replace)
 monkeypatch.setattr('editorial_guard.dataset.time.sleep',delays.append)
 with pytest.raises(PermissionError) as raised:write_json(target,{'next':True})
 assert raised.value is error and len(attempts)==expected_attempts
 assert len(delays)==expected_attempts-1 and sum(delays)<=0.631
 assert target.read_bytes()==b'previous' and list(tmp_path.iterdir())==[target]
