import concurrent.futures,json,threading
from pathlib import Path
import pytest
from editorial_guard.dataset import write_json,write_jsonl
pytestmark=pytest.mark.unit

@pytest.mark.parametrize('line_format',[False,True])
def test_concurrent_snapshot_writers_publish_complete_records_without_temp_collisions(tmp_path,monkeypatch,line_format):
 target=tmp_path/('snapshot.jsonl' if line_format else 'snapshot.json')
 barrier=threading.Barrier(4);original_replace=Path.replace
 def replace(path,destination):
  if Path(destination)==target:barrier.wait(timeout=5)
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
