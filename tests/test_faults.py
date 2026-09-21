import io,json,urllib.error
from pathlib import Path
import pytest
pytestmark=pytest.mark.integration_mock
from editorial_guard.providers import ModelClient,ModelFailure
from editorial_guard.protocol import REWRITE
from editorial_guard.hooks import install,uninstall,handle_event,register
from editorial_guard.finalize import ReceiptStore
from editorial_guard.core import content_hash
from editorial_guard.stats import classification_metrics,paired_cluster_bootstrap

class FakeResponse:
    def __init__(self,value):self.value=value
    def __enter__(self):return io.BytesIO(json.dumps(self.value).encode())
    def __exit__(self,*args):pass

class FakeOpener:
    def __init__(self,fn):self.fn=fn;self.calls=0
    def open(self,*args,**kwargs):self.calls+=1;return self.fn()

def client(tmp_path):
    return ModelClient({'providers':{'deepseek':{'model':'fixture','base_url':'https://api.deepseek.com'}}},tmp_path,lambda p:'fixture-credential')

@pytest.mark.parametrize('status',[401,403,400])
def test_http_errors_do_not_retry(tmp_path,status):
    c=client(tmp_path)
    def error():raise urllib.error.HTTPError('https://api.deepseek.com',status,'secret must not leak',{},io.BytesIO(b'{}'))
    c.opener=FakeOpener(error)
    with pytest.raises(ModelFailure) as exc:c.call('deepseek','system',{},REWRITE)
    assert str(status) in str(exc.value) and 'secret' not in str(exc.value)
    assert c.opener.calls==1 and c.ledger.summary()['requests']==1

def test_account_exhaustion_pauses_provider(tmp_path):
    c=client(tmp_path)
    def error():raise urllib.error.HTTPError('https://api.deepseek.com',429,'',{},io.BytesIO(b'{"error":{"code":"1113"}}'))
    c.opener=FakeOpener(error)
    with pytest.raises(ModelFailure,match='account_exhausted'):c.call('deepseek','system',{},REWRITE)
    with pytest.raises(ModelFailure,match='provider_paused'):c.call('deepseek','system',{'different':True},REWRITE)
    assert c.opener.calls==1

@pytest.mark.parametrize('status',[429,500,503])
def test_transient_retries_bounded(tmp_path,monkeypatch,status):
    monkeypatch.setattr('editorial_guard.providers.time.sleep',lambda n:None)
    c=client(tmp_path)
    def error():raise urllib.error.HTTPError('https://api.deepseek.com',status,'',{},io.BytesIO(b'{}'))
    c.opener=FakeOpener(error)
    with pytest.raises(ModelFailure):c.call('deepseek','system',{},REWRITE)
    assert c.opener.calls==3 and c.ledger.summary()['requests']==3
    from editorial_guard.ledger import LimitReached
    with pytest.raises(LimitReached):c.call('deepseek','system',{},REWRITE)
    assert c.opener.calls==3

@pytest.mark.parametrize('content,finish,kind',[
 ('not json','stop','invalid_response'),
 ('{"wrong":true}','stop','schema_error'),
 ('{"candidate_text":"正文"}','length','truncated_or_nonfinal')])
def test_invalid_responses_not_success(tmp_path,content,finish,kind):
    c=client(tmp_path);c.opener=FakeOpener(lambda:FakeResponse({'choices':[{'message':{'content':content},'finish_reason':finish}]}))
    with pytest.raises(ModelFailure,match=kind):c.call('deepseek','system',{},REWRITE)
    assert c.ledger.summary()['groups'][0]['state']=='failed'

def test_no_duplicate_paid_request(tmp_path):
    c=client(tmp_path);c.opener=FakeOpener(lambda:FakeResponse({'choices':[{'message':{'content':'{"candidate_text":"中文正文"}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':10}}))
    first=c.call('deepseek','system',{},REWRITE)
    other=client(tmp_path);other.opener=FakeOpener(lambda:pytest.fail('Cache should prevent network'))
    second=other.call('deepseek','system',{},REWRITE)
    assert second['replayed'] and first['output']==second['output']

def test_hook_install_merge_uninstall(tmp_path):
    folder=tmp_path/'.codex';folder.mkdir()
    original={'hooks':{'Stop':[{'hooks':[{'type':'command','command':'existing'}]}]},'description':'user'}
    config=folder/'hooks.json';config.write_text(json.dumps(original),encoding='utf-8')
    assert install(tmp_path)['status']=='installed'
    assert len(json.loads(config.read_text())['hooks']['Stop'])==2
    assert install(tmp_path)['status']=='already_installed'
    uninstall(tmp_path)
    assert json.loads(config.read_text())==original

def test_hook_stale_content_loop_and_guard(tmp_path):
    source=tmp_path/'a.md';source.write_text('项目尚未开放，仅供测试使用。',encoding='utf-8')
    store=ReceiptStore(tmp_path/'.eg'/'receipts')
    receipt=store.issue({'status':'pass','candidate_hash':content_hash(source.read_text(encoding='utf-8'))},'r','t','c')
    register(tmp_path,source,receipt)
    event={'hook_event_name':'Stop','session_id':'r','turn_id':'t','stop_hook_active':False}
    assert handle_event(tmp_path,event)=={}
    source.write_text('项目已经开放。',encoding='utf-8')
    assert handle_event(tmp_path,event)['decision']=='block'
    assert 'decision' not in handle_event(tmp_path,{**event,'stop_hook_active':True})
    guard=tmp_path/'.eg'/'hook-active.lock';guard.write_text('')
    assert 'unchecked' in handle_event(tmp_path,event)['systemMessage']

def test_metrics_empty_and_clustered():
    assert classification_metrics([],[])['f1'] is None
    assert classification_metrics([False],[False])['precision'] is None
    assert classification_metrics([True],[False])['recall']==0
    a=[{'source_group_id':'a','a':0,'b':1}]*100+[{'source_group_id':'b','a':1,'b':0}]
    report=paired_cluster_bootstrap(a,iterations=100)
    assert report['families']==2 and report['difference']==0


def test_typed_quota_error_pauses_and_redacts(tmp_path):
    c=client(tmp_path)
    def error():
        body=json.dumps({'error':{'type':'exceeded_current_quota_error','message':'Insufficient balance fixture-credential'}}).encode()
        raise urllib.error.HTTPError('https://api.deepseek.com',429,'',{},io.BytesIO(body))
    c.opener=FakeOpener(error)
    with pytest.raises(ModelFailure,match='account_exhausted'):c.call('deepseek','system',{},REWRITE)
    with pytest.raises(ModelFailure,match='provider_paused'):c.call('deepseek','system',{'new':1},REWRITE)
    assert c.opener.calls==1
    diagnostic=json.loads(next((tmp_path/'requests').glob('*.error.json')).read_text(encoding='utf-8'))
    assert diagnostic['type']=='exceeded_current_quota_error'
    assert 'fixture-credential' not in diagnostic['message'] and '[REDACTED]' in diagnostic['message']

@pytest.mark.parametrize('reviewed',[False,True])
def test_native_cli_permissions_and_credential_isolation(tmp_path,monkeypatch,reviewed):
    import types,sys,os
    root=tmp_path/'skills'
    for name in ('style-editor-zh','delivery-cleaner-zh'):
        folder=root/name;folder.mkdir(parents=True);(folder/'SKILL.md').write_text('fixture',encoding='utf-8')
    monkeypatch.setenv('DEEPSEEK_API_KEY','must-not-inherit-fixture')
    def run(args,**kwargs):
        assert '--dangerously-bypass-approvals-and-sandbox' not in args
        assert '--dangerously-bypass-hook-trust' not in args and '--ignore-rules' not in args
        assert 'DEEPSEEK_API_KEY' not in kwargs['env']
        if reviewed:assert '--approve-for-me' in args and '-s' not in args
        else:assert args[args.index('-s')+1]=='read-only' and '--approve-for-me' not in args
        Path(args[args.index('-o')+1]).write_text('{"candidate_text":"中文候选。"}',encoding='utf-8')
        return types.SimpleNamespace(returncode=0,stdout='{"type":"turn.completed","usage":{}}',stderr='')
    monkeypatch.setattr('editorial_guard.providers.subprocess.run',run)
    c=ModelClient({'providers':{'codex':{'model':'fixture','executable':sys.executable,'native_skill_root':str(root),'native_approval_review':reviewed}}},tmp_path/'work')
    result=c.call('codex','system',{},REWRITE,native_skills=True)
    assert result['native_skill_load_observed'] is False
    assert result['native_approval_review']==reviewed

def test_paused_provider_can_replay_completed_request(tmp_path):
    c=client(tmp_path)
    c.opener=FakeOpener(lambda:FakeResponse({'choices':[{'message':{'content':'{"candidate_text":"已完成中文正文。"}'},'finish_reason':'stop'}]}))
    first=c.call('deepseek','system',{},REWRITE)
    (tmp_path/'blocked_providers.json').write_text('{"deepseek":{"reason":"account_exhausted"}}',encoding='utf-8')
    replay=c.call('deepseek','system',{},REWRITE)
    assert replay['replayed'] and replay['ledger_id']==first['ledger_id'] and c.opener.calls==1
    with pytest.raises(ModelFailure,match='provider_paused'):c.call('deepseek','system',{'new':True},REWRITE)
    assert c.ledger.summary()['requests']==1

def test_native_load_requires_successful_complete_rule_reads(tmp_path):
    from editorial_guard.providers import observed_skill_loading
    events=[]
    for name in ('style-editor-zh','delivery-cleaner-zh'):
        for rel in ('SKILL.md','references/runtime-rules.md'):
            p=tmp_path/'.agents/skills'/name/rel;p.parent.mkdir(parents=True,exist_ok=True)
            body=name+rel+' complete rules';p.write_text(body,encoding='utf-8')
            events.append({'type':'item.completed','item':{'type':'command_execution','command':str(p),'exit_code':0,'aggregated_output':body}})
    assert observed_skill_loading(events,tmp_path)['complete']
    events[0]['item']['exit_code']=1
    assert not observed_skill_loading(events,tmp_path)['complete']
    events[0]['item']['exit_code']=0;events[0]['item']['aggregated_output']='partial'
    assert not observed_skill_loading(events,tmp_path)['complete']

def test_missing_key_never_sends_network_request(tmp_path):
    c=client(tmp_path);c.credentials=lambda provider:''
    c.opener=FakeOpener(lambda:pytest.fail('No network without credential'))
    with pytest.raises(ModelFailure,match='missing_key'):c.call('deepseek','system',{},REWRITE)
    assert c.opener.calls==0 and c.ledger.summary()['groups'][0]['state']=='failed'

def test_timeout_has_bounded_persisted_attempts(tmp_path,monkeypatch):
    monkeypatch.setattr('editorial_guard.providers.time.sleep',lambda n:None)
    c=client(tmp_path)
    def timeout():raise TimeoutError('private transport detail')
    c.opener=FakeOpener(timeout)
    with pytest.raises(ModelFailure,match='timeout') as error:c.call('deepseek','system',{},REWRITE)
    assert 'private' not in str(error.value)
    assert c.opener.calls==3 and c.ledger.summary()['requests']==3

def test_unknown_model_error_is_not_success_or_retried(tmp_path):
    c=client(tmp_path)
    def error():
        raise urllib.error.HTTPError('https://api.deepseek.com',400,'',{},io.BytesIO(b'{"error":{"code":"model_not_found","message":"Unknown requested model"}}'))
    c.opener=FakeOpener(error)
    with pytest.raises(ModelFailure,match='http_400'):c.call('deepseek','system',{},REWRITE)
    assert c.opener.calls==1
