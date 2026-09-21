import pytest
pytestmark=pytest.mark.unit
from editorial_guard.evals import fidelity_transitions,eval_report

def cell(method,fidelity,*,rid='source',judge='glm',valid=True,mode='both',request=None):
 return {'id':rid,'source_group_id':'family','provider':'codex','method':method,'mode':mode,'repeat':0,
         'suite':'StyleBench-ZH','profile':'general-zh','route':'natural','status':'completed','effective_success':False,
         'judgments':[{'provider':judge,'request_id':request or method+rid+fidelity,'evidence_valid':valid,'verdict':{
          'fidelity':fidelity,'requirements':'pass','no_new_serious_issue':True,'process_clean':True,
          'target_improvement':'tie','original_no_edit_needed':False,'candidate_process_spans':[]}}]}

def test_original_failure_is_not_new_damage_and_duplicate_b0_is_not_extra_evidence():
 baseline=cell('B0','fail');candidate=cell('B2','fail')
 report=fidelity_transitions([baseline,dict(baseline),candidate])
 assert len(report['comparisons'])==1
 assert report['comparisons'][0]['original_already_failed']
 assert not report['comparisons'][0]['new_damage_signal']
 assert len(report['comparisons'][0]['baseline_request_ids'])==1
 assert report['summaries'][0]['new_damage_signal_rate'] is None
 raw=eval_report([baseline,candidate])
 assert all('content_damage' not in x for x in raw['summaries'])
 assert raw['summaries'][0]['candidate_fidelity_failures']==1

def test_new_damage_requires_same_judge_mode_and_valid_evidence():
 base=cell('B0','pass')
 cases=[cell('B2','fail'),cell('B1','fail',judge='deepseek'),cell('B4','fail',mode='style'),cell('B5','fail',valid=False)]
 report=fidelity_transitions([base]+cases)
 assert sum(c['new_damage_signal'] for c in report['comparisons'])==1
 assert sum(c['baseline_fidelity']=='missing' for c in report['comparisons'])==2
 assert report['excluded_invalid_candidate_votes']==1

def test_conflicting_or_uncertain_baseline_does_not_prove_new_damage():
 rows=[cell('B0','pass',request='one'),cell('B0','fail',request='two'),cell('B2','fail'),
       cell('B0','uncertain',rid='other'),cell('B2','fail',rid='other')]
 report=fidelity_transitions(rows)
 assert {c['baseline_fidelity'] for c in report['comparisons']}=={'conflicting','uncertain'}
 assert not any(c['new_damage_signal'] for c in report['comparisons'])

def test_intervention_invalid_spans_are_not_counted_as_valid_fidelity_failures(tmp_path):
 from editorial_guard.interventions import run_interventions
 from editorial_guard.dataset import family_spec,instances
 from editorial_guard.ledger import Ledger
 from editorial_guard.protocol import VERIFY
 spec=family_spec(425,'main')
 row=instances(spec,{'input_text':'fixture','style_variant':'fixture'},{'ledger_id':'fixture','requested_model':'fixture','reported_model':'fixture'})[0]
 class FakeClient:
  ledger=Ledger
  def call(self,provider,system,payload,schema,**kwargs):
   if system!=VERIFY:return {'ledger_id':'fixture-edit','output':{'candidate_text':payload['input_text']}}
   verdict={'fidelity':'fail','evidence':[{'original_span':'ABSENT_EVIDENCE','candidate_span':'','reason':'fixture'}],
            'original_process_spans':[],'candidate_process_spans':[]}
   return {'ledger_id':'fixture-judge','output':verdict}
 report=run_interventions(FakeClient(),row,tmp_path)
 assert report['completed']==27
 rounds=[rnd for result in report['results'] for rnd in result['rounds']]
 assert rounds and all(not rnd['candidate_fidelity_failure'] for rnd in rounds)
 assert all(not vote['evidence_valid'] for rnd in rounds for vote in rnd['judgments'])
