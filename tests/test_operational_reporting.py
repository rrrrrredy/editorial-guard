import importlib.util,json
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
spec=importlib.util.spec_from_file_location('operational_summary',Path(__file__).resolve().parents[1]/'scripts/summarize_experiment.py')
summary=importlib.util.module_from_spec(spec);spec.loader.exec_module(summary)

def cell(**kwargs):
    return {'id':'sample','source_group_id':'family','provider':'codex','method':'B2','mode':'both','suite':'StyleBench-ZH','profile':'general-zh','route':'natural','repeat':0,'status':'completed','effective_success':False,'candidate_text':'正文','attempts':[],'judgments':[],**kwargs}

def vote(valid=True,**kwargs):
    return {'provider':'glm','request_id':'judge','evidence_valid':valid,'verdict':{'no_new_serious_issue':True,'fidelity':'pass','requirements':'pass','original_no_edit_needed':True,'target_improvement':'tie','process_clean':True,**kwargs}}

def test_shared_cached_requests_and_failed_retries_are_deduplicated_with_currency_separation():
    cells=[cell(attempts=['good']),cell(route='controlled',attempts=['good','unknown'])]
    requests=[{'id':'bad','task_key':'task','state':'failed','estimated_cost':1,'actual_cost':None,'currency':'CNY','started':0,'ended':2},
              {'id':'good','task_key':'task','state':'succeeded','estimated_cost':2,'actual_cost':None,'currency':'USD','started':3,'ended':6},
              {'id':'unknown','task_key':'second','state':'succeeded','estimated_cost':None,'actual_cost':None,'currency':None}]
    r=summary.summarize(cells,{'sample':'正文'},iter(requests));total=r['unique_attributed_requests_total']
    assert total['ledger_requests_found']==3 and total['failed_requests']==1
    assert total['known_estimated_cost_by_currency']=={'CNY':1,'USD':2}
    assert total['requests_with_unknown_cost']==1 and total['known_actual_cost_by_currency']=={}
    assert total['request_wall_seconds_total']==5 and r['request_ids_shared_between_strata']==2
    assert sum(x['cost']['ledger_requests_found'] for x in r['strata'])==5

def test_empty_output_is_not_missing_output_and_empty_denominators_stay_unknown():
    rows=[cell(candidate_text=''),cell(id='missing',candidate_text=None,status='error')]
    r=summary.summarize(rows,{'sample':'中😀文'})['strata'][0]
    assert r['empty_candidate_cells']==1 and r['missing_candidate_cells']==1
    assert r['length_comparison_cells']==1 and r['mean_length_ratio']==0 and r['mean_codepoint_change']==-3
    assert r['harmful_change_on_model_no_edit_rate'] is None and r['model_new_serious_issue_rate'] is None
    assert r['cost']['request_wall_seconds_total'] is None

def test_invalid_evidence_cannot_create_harm_and_unchanged_text_requires_model_support():
    rows=[cell(id='a',candidate_text='改写',judgments=[vote(False,no_new_serious_issue=False,target_improvement='worse')]),
          cell(id='b',judgments=[vote()]),cell(id='c',judgments=[vote(original_no_edit_needed=False)]),
          cell(id='d',candidate_text='改写',judgments=[vote(target_improvement='worse')])]
    r=summary.summarize(rows,{k:'正文' for k in 'abcd'})['strata'][0]
    assert r['invalid_or_unverified_evidence_votes']==1 and r['cells_with_valid_votes']==3
    assert r['comparable_model_no_edit_cells']==2 and r['harmful_change_on_model_no_edit_cells']==1
    assert r['unchanged_text_cells']==2 and r['unchanged_model_no_edit_pass_cells']==1
    assert r['model_new_serious_issue_cells']==0

def test_suites_profiles_routes_are_separate_and_repeats_do_not_inflate_families():
    rows=[cell(),cell(repeat=1),cell(suite='DeliveryBench-ZH'),cell(profile='editorial-zh'),cell(route='controlled')]
    r=summary.summarize(rows,{'sample':'正文'})
    assert len(r['strata'])==4
    assert all(x['source_family_clusters']==1 for x in r['strata'])
    assert max(x['recorded_cells'] for x in r['strata'])==2

def test_same_attempt_conflicts_are_rejected_and_newer_execution_is_selected(tmp_path):
    root=tmp_path/'cells';root.mkdir();batch=tmp_path/'batches'/'b'/'cells';batch.mkdir(parents=True)
    first=cell(execution_attempt=1);(root/'same.json').write_text(json.dumps(first),encoding='utf-8')
    changed={**first,'candidate_text':'changed'};(batch/'same.json').write_text(json.dumps(changed),encoding='utf-8')
    with pytest.raises(ValueError,match='Conflicting'):summary.load_cells(tmp_path)
    changed['execution_attempt']=2;(batch/'same.json').write_text(json.dumps(changed),encoding='utf-8')
    assert summary.load_cells(tmp_path)==[changed]
