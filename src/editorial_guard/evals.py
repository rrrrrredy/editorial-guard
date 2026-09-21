"""Pre-registered baseline execution with author-excluded judges and honest failures."""
from __future__ import annotations
import collections,concurrent.futures,json,random,hashlib
from pathlib import Path
from .core import Context,public_input
from .protocol import EDIT,REWRITE,VERIFY,VERDICT,ANNOTATE,ANNOTATIONS
from .pipeline import semantic_verify
from .dataset import PROVIDERS,write_json
from .providers import ModelFailure
from .ledger import LimitReached
from .stats import paired_cluster_bootstrap

METHODS=('B0','B1','B2','B3','B4','B5')
def make_manifest(rows,split='validation',families=12,repeats=3):
    eligible=[r for r in rows if r['split']==split]
    groups=sorted({r['source_group_id'] for r in eligible})
    rng=random.Random(1729);rng.shuffle(groups);groups=groups[:families]
    selected=[r['id'] for r in eligible if r['source_group_id'] in groups]
    cells=[{'id':rid,'provider':provider,'method':method,'repeat':rep,'mode':mode} for rid in selected for provider in PROVIDERS for method in METHODS for rep in range(repeats if method in ('B1','B4') else 1) for mode in ['both']]
    # Fixed matched ablation sample. These are secondary comparisons.
    cells += [{'id':rid,'provider':provider,'method':'B2','repeat':0,'mode':mode} for rid in selected[:8] for provider in PROVIDERS for mode in ('style','process')]
    return {'protocol_version':'0.1.0','split':split,'family_ids':groups,'instance_ids':selected,'cells':cells,'primary_comparison':['B1','B4'],'repeats':repeats,'selection_seed':1729,'B3_support':'prompt-equivalent; native Skill tested separately','author_exclusion':True,'denominator':'all registered cells, plus conditional-on-success results','bootstrap_unit':'source_group_id','multiple_comparisons':'secondary analyses descriptive; no uncorrected significance claims'}

def context_for(row,mode):
    return Context(instruction=row['instruction'],genre=row['genre'],audience=row['audience'],stage=row['stage'],delivery_channel=row['delivery_channel'],locale=row['locale'],mode=mode,profile=row['style_profile'],source_bundle=row['source_bundle'],protected_spans=tuple(row['protected_spans']),constraints=row['constraints'])


def provider_round_robin(cells):
    """Interleave registered cells without changing membership or within-provider order."""
    queues=collections.defaultdict(collections.deque)
    for cell in cells:queues[cell['provider']].append(cell)
    order=[p for p in PROVIDERS if p in queues]+sorted(set(queues)-set(PROVIDERS))
    output=[]
    while any(queues.values()):
        for provider in order:
            if queues[provider]:output.append(queues[provider].popleft())
    return output

def run_eval(client,rows,manifest,output_dir,*,retry_errors=False):
    folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
    frozen=folder/'manifest.json'
    if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=manifest:raise ValueError('Experiment manifest already frozen')
    write_json(frozen,manifest)
    by_id={r['id']:r for r in rows}
    def execute(cell):
        key=client.ledger.key(cell);target=folder/'cells'/(key+'.json')
        previous=None
        if target.exists():
            previous=json.loads(target.read_text(encoding='utf-8'))
            if previous['status']!='error' or not retry_errors or previous.get('execution_attempt',1)>=3:return previous
            if callable(retry_errors) and not retry_errors(previous):return previous
            write_json(folder/'execution_history'/(key+'-'+str(previous.get('execution_attempt',1))+'.json'),previous)
        row=by_id[cell['id']];context=context_for(row,cell['mode']);provider=cell['provider'];method=cell['method']
        result={**cell,'source_group_id':row['source_group_id'],'route':row['provenance']['route'],'suite':row['suite'],'profile':row['style_profile'],'status':'error','judgments':[],'attempts':[]}
        result['execution_attempt']=1 if previous is None else previous.get('execution_attempt',1)+1
        result['first_execution_status']=(previous.get('first_execution_status') or previous['status']) if previous else None
        excluded={row['provenance']['generator']} if method=='B0' else {provider}
        eligible=[p for p in PROVIDERS if p not in excluded]
        rotation=int(hashlib.sha256((row['source_group_id']+provider).encode()).hexdigest()[:8],16)%len(eligible)
        rotated=eligible[rotation:]+eligible[:rotation]
        primary=next(p for p in rotated if p in ('codex','glm'))
        judges=[primary,next(p for p in rotated if p!=primary)]
        if manifest.get('judge_policy')=='glm_primary_except_author':
            primary='glm' if 'glm' in eligible else 'codex'
            secondary=[p for p in eligible if p!=primary]
            judges=[primary,secondary[int(hashlib.sha256(row['id'].encode()).hexdigest()[:8],16)%len(secondary)]]
        try:
            if method=='B0':candidate=row['input_text']
            else:
                system='保留全部事实和必要信息，去掉机械表达与不合阶段的过程旁白。只输出JSON的candidate_text字段。' if method=='B1' else EDIT
                if method.startswith('R-'):
                    baseline=Path(__file__).resolve().parents[2]/'evals/third_party'/method[2:]
                    if method not in ('R-Humanizer','R-HumanizerZH','R-StopSlop') or not (baseline/'SKILL.md').is_file():raise ValueError('Pinned baseline unavailable')
                    system=(baseline/'SKILL.md').read_text(encoding='utf-8')
                    for ref in sorted((baseline/'references').glob('*.md')):system+='\n'+ref.read_text(encoding='utf-8')
                    system+='\n本次统一输出接口：只在JSON的candidate_text字段返回最终改写正文；任务、资料与原稿见输入。规则内容保持原版，不将本接口包装当作原版客户端行为。'
                    result['baseline_support']='pinned original rules with JSON output wrapper'
                payload={'input_text':row['input_text'],'context':context.public(),'replicate':cell['repeat']}
                candidates=[]
                for n in range(3 if method=='B5' else 1):
                    response=client.call(provider,system,{**payload,'candidate_index':n},REWRITE,purpose='baseline:'+method+':'+cell['mode'],native_skills=(method=='B3' and provider=='codex'))
                    candidates.append(response['output']['candidate_text']);result['attempts'].append(response['ledger_id'])
                    if method=='B3':result['skill_support']='native_load_observed' if response.get('native_skill_load_observed') else 'native_requested_not_observed' if provider=='codex' else 'prompt_equivalent'
                candidate=candidates[0]
                if method=='B5':
                    selection=[]
                    for cand in candidates:
                        check=semantic_verify(client,judges[0],row['input_text'],cand,context)
                        selection.append({'candidate_text':cand,'validation':check})
                    accepted=[x for x in selection if x['validation']['status']=='pass']
                    candidate=(accepted or selection)[0]['candidate_text'];result['selection']=selection
                if method=='B4':
                    for repair in range(3):
                        check=semantic_verify(client,judges[0],row['input_text'],candidate,context)
                        result.setdefault('repair_checks',[]).append(check)
                        if check['status']=='pass' or repair==2:break
                        response=client.call(provider,EDIT,{**payload,'candidate_text':candidate,'repair_feedback':check,'repair_round':repair+1},REWRITE,purpose='baseline:B4:repair')
                        candidate=response['output']['candidate_text'];result['attempts'].append(response['ledger_id'])
            result['candidate_text']=candidate
            # Final preference/fidelity votes are independent and blinded to method/model names.
            for judge in judges:
                response=client.call(judge,VERIFY,{'input_text':row['input_text'],'candidate_text':candidate,'context':context.public()},VERDICT,purpose='evaluation:blinded_judge')
                v=response['output']
                valid_evidence=all((not e['original_span'] or e['original_span'] in row['input_text']) and (not e['candidate_span'] or e['candidate_span'] in candidate) for e in v['evidence'])
                valid_evidence=valid_evidence and all(x and x in row['input_text'] for x in v.get('original_process_spans',[])) and all(x and x in candidate for x in v.get('candidate_process_spans',[]))
                result['judgments'].append({'provider':judge,'request_id':response['ledger_id'],'verdict':v,'evidence_valid':valid_evidence})
            votes=[]
            for judgment in result['judgments']:
                v=judgment['verdict']
                votes.append(judgment.get('evidence_valid',True) and v['fidelity']=='pass' and v['requirements']=='pass' and v['no_new_serious_issue'] and (v['target_improvement']=='better' or (v['target_improvement']=='tie' and v['original_no_edit_needed'])) and (v['process_clean'] or cell['mode']=='style'))
            result.update(status='completed',effective_success=bool(votes) and all(votes),judge_disagreement=len(set(votes))>1,candidate_fidelity_failure=any(x.get('evidence_valid',False) and x['verdict']['fidelity']=='fail' for x in result['judgments']),first_pass_success=(result.get('repair_checks',[{}])[0].get('status')=='pass') if method=='B4' else None)
        except (ModelFailure,ValueError,LimitReached) as exc:result.update(status='error',error_type=str(exc),effective_success=False)
        write_json(target,result);return result
    # Atomic provider reservations serialize shared judges across editor queues.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(execute,provider_round_robin(manifest['cells'])))
    report=eval_report(results);report['execution_order']='provider_round_robin';write_json(folder/'report.json',report)
    return report

def eval_report(rows):
    groups=collections.defaultdict(list)
    for row in rows:groups[(row['provider'],row['method'],row['mode'],row['suite'],row['profile'],row['route'])].append(row)
    summaries=[]
    for key,group in sorted(groups.items()):
        completed=[r for r in group if r['status']=='completed']
        summaries.append(dict(zip(('provider','method','mode','suite','profile','route'),key),n=len(group),completed=len(completed),failures=len(group)-len(completed),effective_success_end_to_end=sum(r.get('effective_success',False) for r in group)/len(group),effective_success_given_response=sum(r.get('effective_success',False) for r in completed)/len(completed) if completed else None,candidate_fidelity_failures=sum(any(v.get('evidence_valid',False) and v['verdict']['fidelity']=='fail' for v in r.get('judgments',[])) for r in completed),judge_disagreements=sum(r.get('judge_disagreement',False) for r in completed)))
    comparisons=[]
    for provider in PROVIDERS:
        matched={}
        for r in rows:
            if r['provider']==provider and r['mode']=='both' and r['method'] in ('B1','B4'):
                k=(r['id'],r['repeat']);matched.setdefault(k,{'source_group_id':r['source_group_id']})[r['method']]=int(r.get('effective_success',False))
        pairs=[{'source_group_id':r['source_group_id'],'a':r['B1'],'b':r['B4']} for r in matched.values() if 'B1'in r and 'B4'in r]
        comparisons.append({'provider':provider,**paired_cluster_bootstrap(pairs)})
    return {**detailed_metrics(rows),'fidelity_transitions':fidelity_transitions(rows),'B4_minus_B1_stratified':stratified_comparisons(rows),'resumed_cells':sum(r.get('execution_attempt',1)>1 for r in rows),'first_execution_errors':sum(r.get('first_execution_status')=='error' or (r.get('execution_attempt',1)==1 and r['status']=='error') for r in rows),'cells':len(rows),'completed':sum(r['status']=='completed' for r in rows),'summaries':summaries,'B4_minus_B1':comparisons,'support':'synthetic zh-Hans; LLM judgments, no human validation','denominator_scope':'Rates and matched comparisons cover terminal cell records supplied to this function; recorded operational errors count in end-to-end rates. Registered cells without terminal records are not model failures and require separate coverage reporting.','unrun':'The caller must list registered cells without terminal records; no interpolated scores'}

def detailed_metrics(rows):
    """Descriptive suite metrics and leave-one-judge sensitivity, without pseudo-replication."""
    by_method=collections.defaultdict(list)
    for row in rows:by_method[(row['provider'],row['method'],row['mode'],row['suite'],row['profile'],row['route'])].append(row)
    records=[]
    for key,group in sorted(by_method.items()):
        dimensions=collections.defaultdict(list);residuals=[];damaged=0;valid=0;first=[]
        for row in group:
            votes=[x for x in row.get('judgments',[]) if x.get('evidence_valid',True)]
            if row.get('first_pass_success') is not None:first.append(row['first_pass_success'])
            if not votes:continue
            valid+=1;damaged+=any(v['verdict']['fidelity']=='fail' for v in votes)
            per_dimension=collections.defaultdict(list)
            for vote in votes:
                v=vote['verdict']
                if 'original_style_scores' in v:
                    for dimension in v['original_style_scores']:
                        per_dimension[dimension].append(v['original_style_scores'][dimension]-v['candidate_style_scores'][dimension])
                residuals.append(len(v.get('candidate_process_spans',[])))
            for dimension,values in per_dimension.items():dimensions[dimension].append(sum(values)/len(values))
        records.append({'provider':key[0],'method':key[1],'mode':key[2],'suite':key[3],'profile':key[4],'route':key[5],'recorded_cells':len(group),'valid_review_cells':valid,'candidate_fidelity_failure_cells':damaged,'style_severity_reduction':{k:sum(v)/len(v) for k,v in dimensions.items()},'candidate_process_spans_mean_per_vote':sum(residuals)/len(residuals) if residuals else None,'first_pass_success':sum(first)/len(first) if first else None})
    sensitivity=[]
    for excluded in PROVIDERS:
        covered=success=0
        for row in rows:
            votes=[x for x in row.get('judgments',[]) if x['provider']!=excluded and x.get('evidence_valid',True)]
            if not votes:continue
            covered+=1
            def passes(x):
                v=x['verdict']
                return v['fidelity']=='pass' and v['requirements']=='pass' and v['no_new_serious_issue'] and (v['process_clean'] or row['mode']=='style') and (v['target_improvement']=='better' or (v['target_improvement']=='tie' and v['original_no_edit_needed']))
            success+=all(passes(x) for x in votes)
        sensitivity.append({'excluded_judge_provider':excluded,'covered_cells':covered,'success_rate':success/covered if covered else None,'scope':'recompute using available remaining votes; not a rerun or new independent sample'})
    return {'suite_metrics':records,'leave_one_judge_provider':sensitivity,'ordinal_score_caveat':'0–4 scores are ordered model judgments; mean differences are descriptive, not an interval-scale human quality measure'}

def stratified_comparisons(rows):
    output=[]
    groups=collections.defaultdict(list)
    for row in rows:
        if row['mode']=='both' and row['method'] in ('B1','B4'):
            groups[(row['provider'],row['suite'],row['profile'],row['route'])].append(row)
    for key,group in sorted(groups.items()):
        paired={}
        for row in group:
            unit=paired.setdefault((row['id'],row['repeat']),{'source_group_id':row['source_group_id']})
            unit[row['method']]=row
        complete=[];all_pairs=[]
        for unit in paired.values():
            if 'B1' not in unit or 'B4' not in unit:continue
            pair={'source_group_id':unit['source_group_id'],'a':int(unit['B1'].get('effective_success',False)),'b':int(unit['B4'].get('effective_success',False))}
            all_pairs.append(pair)
            if unit['B1']['status']=='completed' and unit['B4']['status']=='completed':complete.append(pair)
        output.append({**dict(zip(('provider','suite','profile','route'),key)),
                       'matched_pairs':len(all_pairs),'both_completed_pairs':len(complete),
                       'end_to_end':paired_cluster_bootstrap(all_pairs),
                       'both_completed':paired_cluster_bootstrap(complete),
                       'scope':'end-to-end includes recorded operational failures; complete-pair estimates are conditional and can have selection bias; no inference for unrun cells'})
    return output

def fidelity_transitions(rows):
    """Describe same-judge B0/candidate contrasts without treating inherited flaws as damage."""
    baselines=collections.defaultdict(dict)
    for row in rows:
        if row['method']!='B0':continue
        for vote in row.get('judgments',[]):
            if vote.get('evidence_valid',False):
                key=(row['id'],row['mode'],vote['provider'])
                baselines[key][vote['request_id']]=vote['verdict']['fidelity']
    comparisons=[];excluded_invalid=0
    for row in rows:
        if row['method']=='B0':continue
        for vote in row.get('judgments',[]):
            if not vote.get('evidence_valid',False):
                excluded_invalid+=1;continue
            baseline=baselines.get((row['id'],row['mode'],vote['provider']),{})
            states=set(baseline.values())
            before=next(iter(states)) if len(states)==1 else 'conflicting' if states else 'missing'
            after=vote['verdict']['fidelity']
            comparisons.append({**{k:row[k] for k in ('id','source_group_id','provider','method','mode','repeat','suite')},
                                'judge':vote['provider'],'baseline_fidelity':before,'candidate_fidelity':after,
                                'baseline_request_ids':sorted(baseline),'candidate_request_id':vote['request_id'],
                                'new_damage_signal':before=='pass' and after=='fail',
                                'original_already_failed':before=='fail',
                                'cell_status':row['status']})
    groups=collections.defaultdict(list)
    for c in comparisons:groups[(c['provider'],c['method'],c['mode'],c['suite'])].append(c)
    summaries=[]
    for key,group in sorted(groups.items()):
        eligible=[c for c in group if c['baseline_fidelity']=='pass']
        summaries.append({**dict(zip(('provider','method','mode','suite'),key)),
                          'candidate_judge_observations':len(group),'baseline_pass_observations':len(eligible),
                          'new_damage_signals':sum(c['new_damage_signal'] for c in eligible),
                          'new_damage_signal_rate':sum(c['new_damage_signal'] for c in eligible)/len(eligible) if eligible else None,
                          'original_already_failed_observations':sum(c['original_already_failed'] for c in group),
                          'missing_or_conflicting_baseline':sum(c['baseline_fidelity'] in ('missing','conflicting') for c in group)})
    return {'comparisons':comparisons,'summaries':summaries,'excluded_invalid_candidate_votes':excluded_invalid,
            'unique_request_pairs':len({(tuple(c['baseline_request_ids']),c['candidate_request_id']) for c in comparisons}),
            'scope':'Descriptive same-provider judge contrasts against evidence-valid B0 votes in the same mode. Baseline fail does not distinguish inherited from additional errors; missing/conflicting/uncertain baselines do not prove new damage. Reused requests, multiple judges and variants are not independent samples. Partial cells can supply a valid vote; this does not change primary acceptance.'}
