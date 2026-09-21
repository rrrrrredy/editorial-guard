import json
import pytest
pytestmark=pytest.mark.unit
from editorial_guard.finalize import safe_path,PublicationBlocked,acceptance_key,read_exact_utf8,ReceiptStore,finalize_artifact
from editorial_guard.core import Context,content_hash,language_scope
from editorial_guard.dataset import reserve_generation
from editorial_guard.ledger import Ledger

def test_context_changes_invalidate_receipt(tmp_path):
    config={'providers':{}};a=Context(stage='final');b=Context(stage='plan')
    store=ReceiptStore(tmp_path/'receipts');receipt=store.issue({'status':'pass'},'r','t',acceptance_key(config,a))
    with pytest.raises(PublicationBlocked):store.verify(receipt,acceptance_key(config,b))
    with pytest.raises(PublicationBlocked):store.verify(receipt,acceptance_key(config,Context(profile='editorial-zh')))

def test_crlf_bytes_survive_verified_publication(tmp_path):
    source=tmp_path/'input.md';source.write_bytes('中文第一行。\r\n中文第二行。\r\n'.encode())
    body=read_exact_utf8(source);assert '\r\n' in body
    store=ReceiptStore(tmp_path/'receipts');receipt=store.issue({'status':'pass','candidate_hash':content_hash(body)},'r','t','cfg')
    target=tmp_path/'out.md';finalize_artifact(source,receipt,target,allowed_root=tmp_path,receipt_store=store,config_hash='cfg')
    assert target.read_bytes()==source.read_bytes()

def test_parent_traversal_denied(tmp_path):
    with pytest.raises(PublicationBlocked):safe_path(tmp_path/'..'/'escape.md',tmp_path)

def test_family_attempt_cap_survives_restart_and_prompt_change(tmp_path):
    for i in range(3):reserve_generation(tmp_path,'main',['family'])
    with pytest.raises(ValueError,match='family_attempt_limit'):reserve_generation(tmp_path,'main',['family'])
    reserve_generation(tmp_path,'main',['other'])

def test_mixed_currencies_never_summed(tmp_path):
    ledger=Ledger(tmp_path/'l.db')
    for i,currency in enumerate(['USD','CNY']):
        rid=ledger.reserve(str(i),'glm',{});ledger.finish(rid,result={},estimated_cost=1,currency=currency)
    groups=ledger.summary()['groups'];assert len(groups)==2
    assert {g['currency'] for g in groups}=={'USD','CNY'}

def test_shared_han_character_is_not_traditional():
    assert language_scope('请依据资料核对材料，材料记录完整，所有资料均需保留。')=='supported'

def test_evaluation_resume_preserves_failure_and_reuses_success(tmp_path):
    from editorial_guard.evals import run_eval
    from editorial_guard.providers import ModelFailure
    from editorial_guard.dataset import family_spec,instances
    class Client:
        ledger=Ledger
        calls=0
        def call(self,*args,**kwargs):
            self.calls+=1
            if self.calls==1:raise ModelFailure('account_exhausted','glm')
            scores=dict.fromkeys(('template_dependence','expression_efficiency','coherence','scene_fit'),0)
            verdict={'fidelity':'pass','requirements':'pass','target_improvement':'tie','no_new_serious_issue':True,'process_clean':True,'original_no_edit_needed':True,'evidence':[],'reason':'fixture','original_style_scores':scores,'candidate_style_scores':scores,'original_process_spans':[],'candidate_process_spans':[]}
            return {'output':verdict,'ledger_id':str(self.calls)}
    spec=family_spec(400,'main')
    row=instances(spec,{'input_text':'项目资料尚待复核。','style_variant':'项目资料尚待复核。'},{'ledger_id':'fixture','requested_model':'fixture','reported_model':'fixture'})[0]
    manifest={'cells':[{'id':row['id'],'provider':'codex','method':'B0','mode':'both','repeat':0}],'judge_policy':'glm_primary_except_author'}
    client=Client()
    assert run_eval(client,[row],manifest,tmp_path)['completed']==0
    assert run_eval(client,[row],manifest,tmp_path)['completed']==0 and client.calls==1
    assert run_eval(client,[row],manifest,tmp_path,retry_errors=lambda previous:False)['completed']==0 and client.calls==1
    report=run_eval(client,[row],manifest,tmp_path,retry_errors=True)
    assert report['completed']==1 and report['first_execution_errors']==1 and report['resumed_cells']==1
    assert len(list((tmp_path/'execution_history').glob('*.json')))==1
    calls=client.calls
    assert run_eval(client,[row],manifest,tmp_path,retry_errors=True)['completed']==1 and client.calls==calls

def test_concurrent_candidate_change_blocks_publication(tmp_path,monkeypatch):
    import os
    source=tmp_path/'candidate.md';source.write_text('项目尚未开放。',encoding='utf-8')
    store=ReceiptStore(tmp_path/'receipts')
    receipt=store.issue({'status':'pass','candidate_hash':content_hash(source.read_text(encoding='utf-8'))},'r','t','c')
    real_fsync=os.fsync
    def mutate(fd):
        real_fsync(fd)
        source.write_text('项目已经开放。',encoding='utf-8')
    monkeypatch.setattr('editorial_guard.finalize.os.fsync',mutate)
    target=tmp_path/'published.md'
    with pytest.raises(PublicationBlocked,match='Concurrent'):
        finalize_artifact(source,receipt,target,allowed_root=tmp_path,receipt_store=store,config_hash='c')
    assert not target.exists()

def test_windows_junction_rejected(tmp_path):
    import os
    if os.name!='nt':pytest.skip('Windows reparse-point check')
    import _winapi
    target=tmp_path/'real';target.mkdir()
    junction=tmp_path/'junction'
    try:_winapi.CreateJunction(str(target),str(junction))
    except OSError:pytest.skip('Junction creation unavailable')
    with pytest.raises(PublicationBlocked,match='reparse'):
        safe_path(junction/'candidate.md',tmp_path)


def test_resume_rejects_recursive_or_unrelated_saved_command(tmp_path,capsys):
    from editorial_guard.cli import main
    for command in [['resume','--work-dir',str(tmp_path)],['hook','uninstall','--root',str(tmp_path)]]:
        (tmp_path/'active-job.json').write_text(json.dumps({'argv':command}),encoding='utf-8')
        assert main(['resume','--work-dir',str(tmp_path)])==3
        assert 'Unsupported saved job' in capsys.readouterr().err


def test_blinding_removes_route_and_error_name_hints():
    from editorial_guard.blinding import blind_records
    records=[{'id':'main-0123-controlled','source_group_id':'main-0123','input_text':'中文事实。'},{'id':'invented_source','input_text':'中文候选。'}]
    blinded,mapping=blind_records(records)
    assert 'controlled' not in json.dumps(blinded) and 'invented_source' not in json.dumps(blinded)
    assert 'main-0123' not in json.dumps(blinded)
    assert set(mapping.values())=={r['id'] for r in records}
    assert [r['input_text'] for r in blinded]==[r['input_text'] for r in records]
    assert records[0]['id']=='main-0123-controlled'
    assert blind_records(records)==(blinded,mapping)


def test_persistent_provider_queue_is_fifo(tmp_path):
    from editorial_guard.ledger import Busy
    ledger=Ledger(tmp_path/'queue.db')
    first=ledger.enqueue('a','codex');second=ledger.enqueue('b','codex')
    with pytest.raises(Busy):ledger.reserve('b','codex',{},queue_ticket=second)
    rid=ledger.reserve('a','codex',{},queue_ticket=first);ledger.finish(rid,result={})
    with pytest.raises(Busy):Ledger(tmp_path/'queue.db').reserve('late','codex',{})
    rid=Ledger(tmp_path/'queue.db').reserve('b','codex',{},queue_ticket=second);ledger.finish(rid,result={})
    ledger.enqueue('abandoned','codex',ttl=-1)
    third=ledger.enqueue('c','codex')
    rid=ledger.reserve('c','codex',{},queue_ticket=third);ledger.finish(rid,result={})
    assert ledger.summary()['requests']==3

def test_span_metrics_separates_documents_tasks_and_overlaps():
    from editorial_guard.stats import span_metrics
    gold=[{'document_id':'a','task':'style','start':1,'end':4}]
    pred=[{'document_id':'a','task':'style','start':1,'end':3},{'document_id':'a','task':'style','start':2,'end':4}]
    result=span_metrics(gold,pred)
    assert result['character_union']['tp']==3 and result['character_union']['f1']==1
    assert result['exact_span']['tp']==0 and result['exact_span']['fp']==2
    wrong=[{'document_id':'b','task':'style','start':1,'end':4},{'document_id':'a','task':'process','start':1,'end':4}]
    assert span_metrics(gold,wrong)['character_union']['tp']==0

def test_span_metrics_empty_duplicate_and_invalid_boundaries():
    from editorial_guard.stats import span_metrics
    assert span_metrics([],[])['exact_span']['f1'] is None
    # Emoji occupies one Python/Unicode code point.
    text='中😀文';issue={'document_id':'a','task':'style','start':1,'end':2}
    assert text[issue['start']:issue['end']]=='😀'
    assert span_metrics([issue],[issue,issue])['character_union']['tp']==1
    with pytest.raises(ValueError):span_metrics([], [{**issue,'end':1}])

def test_secondary_recovery_preserves_history_and_stops_after_three(tmp_path):
    from editorial_guard.resumption import prepare_cell
    from editorial_guard.dataset import write_json
    path=tmp_path/'cells'/'fixture.json'
    for attempt in range(1,4):
        cached,metadata=prepare_cell(path,retry_errors=True)
        assert cached is None and metadata['execution_attempt']==attempt
        write_json(path,{'status':'error','error':'fixture',**metadata})
        if attempt==1:
            cached,denied=prepare_cell(path,retry_errors=lambda previous:False)
            assert cached['execution_attempt']==1 and denied is None
            assert not list((tmp_path/'execution_history').glob('*.json'))
    cached,metadata=prepare_cell(path,retry_errors=lambda previous:False)
    assert cached['execution_attempt']==3 and metadata is None
    cached,metadata=prepare_cell(path,retry_errors=True)
    assert cached['execution_attempt']==3 and metadata is None
    assert len(list((tmp_path/'execution_history').glob('*.json')))==2
    other=tmp_path/'cells'/'done.json';write_json(other,{'status':'completed','execution_attempt':1})
    assert prepare_cell(other,True)[0]['status']=='completed'

def test_unicode_offsets_preserve_original_normalization():
    from editorial_guard.dataset import locate_issues
    text='甲e\u0301乙é'
    item=locate_issues(text,[{'text':'e\u0301','occurrence':0,'category':'fixture'}])[0]
    assert item['start']==1 and item['end']==3 and text[1:3]=='e\u0301'
    with pytest.raises(ValueError):locate_issues('甲e\u0301乙',[{'text':'é','occurrence':0,'category':'fixture'}])

def test_external_local_write_can_bypass_wrapper(tmp_path):
    import subprocess,sys
    # A controlled publisher is not a global file-write interceptor.
    destination=tmp_path/'external.md'
    command='from pathlib import Path;import sys;Path(sys.argv[1]).write_text("unverified external write",encoding="utf-8")'
    result=subprocess.run([sys.executable,'-c',command,str(destination)],capture_output=True)
    assert result.returncode==0 and destination.read_text()=='unverified external write'
    store=ReceiptStore(tmp_path/'receipts')
    with pytest.raises(PublicationBlocked):store.verify({},'config')

def test_dataset_validation_reports_malformed_nested_annotation():
    from editorial_guard.dataset import family_spec,instances,validate_dataset
    row=instances(family_spec(0,'main'),{'input_text':'测试项目。','style_variant':'测试项目。'},{'ledger_id':'fixture','requested_model':'fixture','reported_model':'fixture'})[0]
    row['annotation_records']=[{'provider':'glm','request_id':'fixture','annotation_version':'0.1.2','annotation':{'issues':[{'text':'测试'}]}}]
    result=validate_dataset([row,{'id':'missing-fields'},'not-an-object'])
    assert result['status']=='fail' and result['schema_invalid_rows']==3
    assert result['summary']['instances']==0 and result['errors']


def test_incomplete_concurrent_receipt_key_fails_closed(tmp_path):
    root=tmp_path/"receipts";root.mkdir();(root/"receipt.key").write_bytes(b"")
    with pytest.raises(PublicationBlocked,match="key incomplete"):ReceiptStore(root)

def test_provider_round_robin_preserves_registered_cells_and_local_order():
    from editorial_guard.evals import provider_round_robin
    cells=[{'provider':p,'id':str(i)} for p,count in [('codex',4),('deepseek',2),('glm',3)] for i in range(count)]
    ordered=provider_round_robin(cells)
    assert [c['provider'] for c in ordered[:3]]==['codex','deepseek','glm']
    assert len(ordered)==len(cells)
    assert sorted((c['provider'],c['id']) for c in ordered)==sorted((c['provider'],c['id']) for c in cells)
    for provider in ('codex','deepseek','glm'):
        assert [c['id'] for c in ordered if c['provider']==provider]==[c['id'] for c in cells if c['provider']==provider]

def test_family_bootstrap_is_invariant_to_file_enumeration_order():
    from editorial_guard.stats import paired_cluster_bootstrap
    rows=[{'source_group_id':str(i),'a':0,'b':value} for i,value in enumerate([.11,.24,-.71,.6,.9,-.3,.42])]
    assert paired_cluster_bootstrap(rows,iterations=100)==paired_cluster_bootstrap(list(reversed(rows)),iterations=100)
