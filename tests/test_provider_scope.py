import pytest
from editorial_guard.dataset import PROVIDERS
from editorial_guard.supplemental import independent_judges
from editorial_guard.ledger import Ledger,LimitReached
from editorial_guard.providers import ModelClient
pytestmark=pytest.mark.unit

@pytest.mark.parametrize('author',PROVIDERS)
def test_three_provider_independent_review(author):
 judges=independent_judges(author)
 assert len(judges)==2 and len(set(judges))==2
 assert set(judges)==set(PROVIDERS)-{author}

def test_deleted_history_does_not_restore_request_allowance(tmp_path):
 ledger=Ledger(tmp_path/'requests.sqlite3',total_limit=3,codex_limit=1)
 with ledger.connection() as db:
  db.executemany('INSERT INTO settings VALUES (?,?)',[('retired_requests','2'),('retired_codex_requests','1')])
 assert ledger.summary()['requests']==2 and ledger.summary()['remaining_codex']==0
 with pytest.raises(LimitReached):ledger.reserve('client','codex',{})
 rid=ledger.reserve('last','glm',{});ledger.finish(rid,error_type='fixture')
 with pytest.raises(LimitReached):ledger.reserve('over','deepseek',{})
 assert ledger.summary()['requests']==3 and ledger.summary()['retained_requests']==1

def test_unknown_provider_cannot_use_injected_config(tmp_path):
 client=ModelClient({'providers':{'unsupported':{'model':'fixture'}}},tmp_path)
 with pytest.raises(ValueError,match='Unsupported provider'):
  client.call('unsupported','',{}, {})


def test_calibration_accepts_all_supported_providers_and_rejects_missing(tmp_path):
 import json
 from editorial_guard.calibration import calibrate_judges,control_cases
 root=tmp_path/'calibration/judge-controls-blind-v2';root.mkdir(parents=True)
 for provider in PROVIDERS:
  (root/(provider+'-controls.json')).write_text(json.dumps({'provider':provider,'correct':12,'total':12,'cases':[]}))
 class NoCalls:
  def call(self,*args,**kwargs):raise AssertionError('Cached controls should not call a model')
 assert calibrate_judges(NoCalls(),tmp_path)['status']=='pass'
 (root/(PROVIDERS[0]+'-controls.json')).write_text(json.dumps({'provider':PROVIDERS[0],'correct':10,'total':12,'cases':[]}))
 assert calibrate_judges(NoCalls(),tmp_path)['status']=='fail'

def test_explicit_generation_plan_rejects_duplicate_ids_before_call(tmp_path):
 from editorial_guard.dataset import build_dataset,family_spec
 spec=family_spec(0,'main')
 with pytest.raises(ValueError,match='Invalid generation plan'):
  build_dataset(None,tmp_path,'main',count=2,family_specs=[spec,spec])
