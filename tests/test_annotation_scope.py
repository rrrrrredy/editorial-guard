import json
import pytest
pytestmark=pytest.mark.unit
from editorial_guard.dataset import annotate_dataset,family_spec,instances,write_json

def test_scoped_annotation_only_calls_selected_families_but_keeps_full_snapshot(tmp_path):
 root=tmp_path/'data/main';seen=[]
 for index in (0,4):
  spec=family_spec(index,'main')
  records=instances(spec,{'input_text':'测试正文','style_variant':'测试正文'},{'ledger_id':'generation','requested_model':'fixture','reported_model':'fixture'})
  write_json(root/(spec['source_group_id']+'.json'),{'spec':spec,'records':records})
 class Client:
  def call(self,provider,system,payload,schema,**kwargs):
   seen.extend(payload['records'])
   annotations=[{'id':r['id'],'issues':[],'valid_task':True,'style_problem':False,'process_problem':False,
    'source_fidelity':'pass','task_satisfied':'pass','no_edit_needed':True} for r in payload['records']]
   return {'output':{'records':annotations},'requested_model':'fixture','reported_model':'fixture','ledger_id':'review'}
 result=annotate_dataset(Client(),tmp_path,'main',providers=('glm',),source_group_ids={'main-0004'})
 assert len(seen)==2
 assert all('虚构设备巡检项目5号' in json.dumps(r,ensure_ascii=False) for r in seen)
 assert all(r['source_group_id'].startswith('r') and not r['id'].startswith('main-') for r in seen)
 assert all('main-0004' not in json.dumps(r,ensure_ascii=False) and 'parent_id' not in r for r in seen)
 labels=list((root/'labels-0.1.2').glob('*.json'))
 assert len(labels)==2 and all(p.name.startswith('main-0004-') for p in labels)
 assert result['families']==2 and result['instances']==4
 assert len((root/'annotated.jsonl').read_text(encoding='utf-8').splitlines())==4


def test_exhausted_label_is_not_retried_and_routes_are_separate(tmp_path):
 root=tmp_path/'data/main';seen=[]
 for index in (0,3):
  spec=family_spec(index,'main')
  records=instances(spec,{'input_text':'测试正文','style_variant':'测试变体'},{'ledger_id':'generation','requested_model':'fixture','reported_model':'fixture'})
  write_json(root/(spec['source_group_id']+'.json'),{'spec':spec,'records':records})
 class Client:
  def call(self,provider,system,payload,schema,**kwargs):
   seen.append(payload['records'])
   return {'output':{'records':[{'id':r['id'],'issues':[],'valid_task':True,'style_problem':False,'process_problem':False,'source_fidelity':'pass','task_satisfied':'pass','no_edit_needed':True} for r in payload['records']]},'requested_model':'fixture','reported_model':'fixture','ledger_id':'review'}
 result=annotate_dataset(Client(),tmp_path,'main',batch_size=8,providers=('glm',),exclude_annotations={'glm':['main-0000-natural']})
 assert sorted(map(len,seen))==[1,2]
 assert not (root/'labels-0.1.2/main-0000-natural--glm.json').exists()
 assert result['instances']==4 and len(result['excluded_exhausted_annotations'])==1
 assert result['independent_judgments']==3
