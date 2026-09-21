import concurrent.futures,json
import pytest
pytestmark=pytest.mark.unit
from editorial_guard.core import Context,lint_text,verify_edit,language_scope,public_input,content_hash
from editorial_guard.dataset import family_spec,locate_issues
from editorial_guard.finalize import ReceiptStore,finalize_artifact,PublicationBlocked
from editorial_guard.ledger import Ledger,Busy,LimitReached

@pytest.mark.parametrize('text,locale,expected',[
 ('本系统使用 API、JSON 和 Python 处理请求，失败时保留原始记录。','zh-Hans','supported'),
 ('This report explains all steps for publishing a software package.','zh-Hans','unsupported'),
 ('這個系統將資料寫入資料庫，並保留檢測紀錄。','zh-Hans','unvalidated'),
 ('本系统保留原始记录。','zh-Hant','unvalidated')])
def test_language(text,locale,expected):assert language_scope(text,locale)==expected

def test_stage_flip_and_modes():
    text='下面我先分析，再给出结论。项目仅支持本地读取。'
    assert any(i['suite']=='process' for i in lint_text(text,Context(mode='process'))['issues'])
    assert not lint_text(text,Context(mode='process',stage='plan'))['issues']
    assert not lint_text(text,Context(mode='style'))['issues']

def test_patterns_are_not_verdicts():
    r=lint_text('不是所有请求都会成功，而是仅满足条件的请求会成功。',Context())
    assert r['status']=='unchecked'
    assert all(x['severity'] is None for x in r['issues'])

def test_protection_and_unicode():
    tick=chr(96)
    text='---\ntitle: 测试\n---\n正文😀。\n'+tick*3+'python\nprint("下面我先分析")\n'+tick*3+'\n> 下面我先分析\n'+tick+'API'+tick+' https://example.org/path\n'
    assert not lint_text(text)['issues']
    pos=locate_issues(text,[{'text':'正文😀','occurrence':0,'category':'x'}])[0]
    assert text[pos['start']:pos['end']]=='正文😀'
    assert verify_edit(text,text.replace('API','RPC'))['status']=='fail'

def test_repeated_spans():
    got=locate_issues('重复😀。重复😀。',[{'text':'重复😀','occurrence':1,'category':'x'}])[0]
    assert got['start']==4
    with pytest.raises(ValueError):locate_issues('正文',[{'text':'不存在','occurrence':0}])

@pytest.mark.parametrize('candidate',['','项目成功。','项目有30万元预算且已全部支出。','项目只有300万元预算，条件不变。'])
def test_damage_does_not_pass(candidate):
    original='项目仅有30万元预算，尚未支出；只有测试通过后才允许采购。'
    assert verify_edit(original,candidate)['status']!='pass'

def test_noop_still_needs_semantic_review():
    text='项目仅有30万元预算，尚未支出；只有测试通过后才允许采购。'
    assert verify_edit(text,text)['status']=='unchecked'

def test_solver_export_drops_answers():
    got=public_input({'id':'x','input_text':'文本','issues':['SECRET'],'required_claims':['SECRET'],'annotation_records':['SECRET'],'acceptable_references':['SECRET'],'split':'locked_test'})
    assert set(got)=={'id','input_text'} and 'SECRET' not in json.dumps(got)

def test_families_and_assignments():
    specs=[family_spec(i,'main') for i in range(500)]
    assert len({s['source_group_id'] for s in specs})==500
    assert {x:sum(s['split']==x for s in specs) for x in ('development','validation','locked_test')}=={'development':300,'validation':100,'locked_test':100}
    assert sum(s['suite']=='StyleBench-ZH' for s in specs)==250
    for provider in ('codex','deepseek','glm'):
        assigned=[s for s in specs if s['generator']==provider]
        assert {s['controlled_state'] for s in assigned}=={0,1,2,3}
        assert len({s['suite'] for s in assigned})==2
    topics={}
    for s in specs:
        assert s['topic'] not in topics or topics[s['topic']]==s['split']
        topics[s['topic']]=s['split']

def test_ledger_persists_limits_and_cache(tmp_path):
    path=tmp_path/'ledger.db';ledger=Ledger(path,total_limit=2,codex_limit=1)
    rid=ledger.reserve('a','codex',{});ledger.finish(rid,result={'output':'x'})
    another=Ledger(path,total_limit=2,codex_limit=1)
    assert another.cached('a')=={'output':'x'}
    with pytest.raises(LimitReached):another.reserve('b','codex',{})
    rid=another.reserve('b','deepseek',{});another.finish(rid,error_type='timeout')
    with pytest.raises(LimitReached):another.reserve('c','glm',{})
    assert another.summary()['requests']==2
    assert another.summary()['groups'][0]['actual_cost'] is None
    with pytest.raises(ValueError):Ledger(path,total_limit=3,codex_limit=1)

def test_atomic_concurrency(tmp_path):
    path=tmp_path/'ledger.db';Ledger(path)
    def reserve(n):
        try:return Ledger(path).reserve(str(n),'deepseek',{})
        except Busy:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(8)))
    assert sum(x is not None for x in results)==1
    assert Ledger(path).summary()['requests']==1

def test_retry_limit_across_restarts(tmp_path):
    for i in range(3):
        ledger=Ledger(tmp_path/'ledger.db')
        rid=ledger.reserve('same','glm',{});ledger.finish(rid,error_type='timeout')
    with pytest.raises(LimitReached):Ledger(tmp_path/'ledger.db').reserve('same','glm',{})

def test_signed_publication_and_mutation(tmp_path):
    source=tmp_path/'candidate.md';source.write_text('项目仅在测试通过后开放。',encoding='utf-8')
    store=ReceiptStore(tmp_path/'state')
    receipt=store.issue({'status':'pass','candidate_hash':content_hash(source.read_text(encoding='utf-8'))},'run','turn','config')
    target=tmp_path/'published.md'
    r=finalize_artifact(source,receipt,target,allowed_root=tmp_path,receipt_store=store,config_hash='config')
    assert r['status']=='published' and source.read_bytes()==target.read_bytes()
    source.write_text('项目已开放。',encoding='utf-8')
    with pytest.raises(PublicationBlocked):finalize_artifact(source,receipt,target,allowed_root=tmp_path,receipt_store=store,config_hash='config')
    with pytest.raises(PublicationBlocked):store.verify(receipt,'changed')
    forged=json.loads(json.dumps(receipt));forged['validation']['candidate_hash']='fake'
    with pytest.raises(PublicationBlocked):store.verify(forged,'config')
    with pytest.raises(PublicationBlocked):finalize_artifact(source,receipt,tmp_path.parent/'escape.md',allowed_root=tmp_path,receipt_store=store,config_hash='config')

def test_symlink_blocked(tmp_path):
    target=tmp_path/'real.md';target.write_text('正文',encoding='utf-8')
    link=tmp_path/'link.md'
    try:link.symlink_to(target)
    except OSError:pytest.skip('Symlink creation unavailable')
    from editorial_guard.finalize import safe_path
    with pytest.raises(PublicationBlocked):safe_path(link,tmp_path)
