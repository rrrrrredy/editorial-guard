"""Frozen secondary experiments and bounded blind dispute review."""
import concurrent.futures,hashlib,json
from pathlib import Path
from .core import public_input
from .dataset import PROVIDERS,write_json,locate_issues
from .protocol import EDIT,REWRITE,VERIFY,VERDICT,ANNOTATE,ANNOTATIONS
from .evals import context_for
from .providers import ModelFailure
from .blinding import blind_records
from .resumption import prepare_cell

def independent_judges(author):
    eligible=[p for p in PROVIDERS if p!=author]
    primary='glm' if author!='glm' else 'codex'
    return [primary,next(p for p in eligible if p!=primary)]

def checked_vote(client,judge,original,candidate,context,purpose):
    r=client.call(judge,VERIFY,{'input_text':original,'candidate_text':candidate,'context':context.public()},VERDICT,purpose=purpose)
    v=r['output']
    valid=all((not e['original_span'] or e['original_span'] in original) and (not e['candidate_span'] or e['candidate_span'] in candidate) for e in v['evidence'])
    valid=valid and all(x and x in original for x in v['original_process_spans']) and all(x and x in candidate for x in v['candidate_process_spans'])
    return {'provider':judge,'request_id':r['ledger_id'],'verdict':v,'evidence_valid':valid}

def run_tracks(client,source_row,output_dir,*,retry_errors=False):
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    tasks=[{'provider':p,'track':track} for p in PROVIDERS for track in ('detect','generate','style_then_process','process_then_style')]
    manifest={'version':'0.1.1','source_group_id':source_row['source_group_id'],'tasks':tasks,'denominator':'all registered tasks','judges':'two distinct author-excluded providers; GLM primary except for GLM authors','inference_limit':'single-family secondary experiment'}
    target=root/'manifest.json'
    if target.exists() and json.loads(target.read_text(encoding='utf-8'))!=manifest:raise ValueError('Frozen track manifest differs')
    write_json(target,manifest)
    def run(task):
        path=root/'cells'/(client.ledger.key(task)+'.json')
        cached,recovery=prepare_cell(path,retry_errors)
        if cached is not None:return cached
        p=task['provider'];track=task['track'];context=context_for(source_row,'both')
        result={**task,**recovery,'status':'error','requests':[],'judgments':[]}
        try:
            if track=='detect':
                blind,mapping=blind_records([public_input(source_row)])
                r=client.call(p,ANNOTATE,{'records':blind},ANNOTATIONS,purpose='track:detect:blind-v2')
                a=r['output']['records']
                if len(a)!=1 or a[0]['id'] not in mapping:raise ValueError('Detection id mismatch')
                a[0]['id']=mapping[a[0]['id']]
                a[0]['issues']=locate_issues(source_row['input_text'],a[0]['issues'])
                result.update(annotation=a[0]);result['requests'].append(r['ledger_id'])
            else:
                current=source_row['input_text']
                modes=('both',) if track=='generate' else ('style','process') if track=='style_then_process' else ('process','style')
                for mode in modes:
                    c=context_for(source_row,mode)
                    payload={'input_text':current,'context':c.public()}
                    system=EDIT
                    if track=='generate':
                        payload={'context':c.public(),'task':'根据资料直接生成可交付中文正文。没有待改写原稿。'}
                        system=EDIT+'\n本次为直接写作任务，从公开资料和要求生成正文。'
                    r=client.call(p,system,payload,REWRITE,purpose='track:'+track+':'+mode)
                    current=r['output']['candidate_text'];result['requests'].append(r['ledger_id'])
                # Generation uses the given facts as its fidelity reference, not a hidden answer.
                reference='\n'.join(source_row['source_bundle']['facts']) if track=='generate' else source_row['input_text']
                result['candidate_text']=current
                for judge in independent_judges(p):
                    result['judgments'].append(checked_vote(client,judge,reference,current,context,'track:blind_judge'))
            result['status']='completed'
        except (ModelFailure,ValueError) as exc:result['error']=str(exc)
        write_json(path,result);return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,tasks))
    report={'tasks':len(tasks),'completed':sum(r['status']=='completed' for r in results),'results':results,'inference_limit':manifest['inference_limit']}
    write_json(root/'report.json',report);return report

def review_disputes(client,rows,output_dir,limit=40,*,retry_errors=False):
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    disputed=[r for r in rows if r['disagreement_status']=='disputed']
    chosen=sorted(disputed,key=lambda r:hashlib.sha256(('dispute-v1:'+r['id']).encode()).hexdigest())[:limit]
    tasks=[]
    for row in chosen:
        used={a['provider'] for a in row['annotation_records']}|{row['provenance']['generator']}
        remaining=[p for p in ('glm','deepseek','codex') if p not in used]
        if remaining:tasks.append({'id':row['id'],'provider':remaining[0]})
    manifest={'version':'0.1.1','selection':'SHA256(dispute-v1:id), first N; no outcome-based reranking','limit':limit,'disputed_available':len(disputed),'tasks':tasks,'rounds':1,'original_votes_unchanged':True,'resolution':'additional blind counterevidence; disagreement not overwritten by majority'}
    path=root/'manifest.json'
    if path.exists():
        manifest=json.loads(path.read_text(encoding='utf-8'));tasks=manifest['tasks']
    else:write_json(path,manifest)
    by_id={r['id']:r for r in rows}
    def run(task):
        path=root/'cells'/(client.ledger.key(task)+'.json')
        cached,recovery=prepare_cell(path,retry_errors)
        if cached is not None:return cached
        row=by_id[task['id']];result={**task,**recovery,'status':'error'}
        try:
            blind,mapping=blind_records([public_input(row)])
            r=client.call(task['provider'],ANNOTATE,{'records':blind},ANNOTATIONS,purpose='dispute:blind_third_review:v2')
            a=r['output']['records']
            if len(a)!=1 or a[0]['id'] not in mapping:raise ValueError('Review id mismatch')
            a[0]['id']=mapping[a[0]['id']]
            a[0]['issues']=locate_issues(row['input_text'],a[0]['issues'])
            result.update(status='completed',annotation=a[0],request_id=r['ledger_id'])
        except (ModelFailure,ValueError) as exc:result['error']=str(exc)
        write_json(path,result);return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,tasks))
    report={'registered':len(tasks),'completed':sum(r['status']=='completed' for r in results),'results':results,'scope':'bounded counterreview; not arbitration or objective truth'}
    write_json(root/'report.json',report);return report

def run_reward_controls(client,source_row,output_dir,*,retry_errors=False):
    from .interventions import controlled_rows
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    clean=controlled_rows(source_row)[0];original=clean['input_text'];context=context_for(clean,'both')
    candidates={'drop_condition':source_row['source_bundle']['facts'][0],
                'invent_number':original+'\n项目收益已增加97%。',
                'invent_experience':original+'\n我亲自参加了项目，已确认效果显著。',
                'empty_vocabulary':'各项工作取得积极进展，相关举措具有重要意义，后续安排将继续稳步推进。'}
    tasks=[{'provider':p,'case':case} for p in PROVIDERS for case in candidates]
    manifest={'version':'0.1.1','source_group_id':source_row['source_group_id'],'tasks':tasks,'expected':'reject for fidelity or requirements; not merely low style score','programmatic_controls':True,'candidates':candidates}
    path=root/'manifest.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=manifest:raise ValueError('Reward-control manifest differs')
    write_json(path,manifest)
    def run(task):
        path=root/'cells'/(client.ledger.key(task)+'.json')
        cached,recovery=prepare_cell(path,retry_errors)
        if cached is not None:return cached
        result={**task,**recovery,'status':'error'}
        try:
            vote=checked_vote(client,task['provider'],original,candidates[task['case']],context,'H4:direct_reward_control')
            v=vote['verdict']
            result.update(status='completed',vote=vote,rejected=v['fidelity']=='fail' or v['requirements']=='fail',false_accept=vote['evidence_valid'] and v['fidelity']=='pass' and v['requirements']=='pass')
        except (ModelFailure,ValueError) as exc:result['error']=str(exc)
        write_json(path,result);return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,tasks))
    report={'tasks':len(tasks),'completed':sum(r['status']=='completed' for r in results),'results':results}
    write_json(root/'report.json',report);return report
