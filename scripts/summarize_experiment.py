"""Offline operational metrics from saved cells, public originals and request ledger.

No inference or credentials are required. Request reuse is deduplicated within each
stratum and in the study total; strata can share requests and their costs are not additive.
"""
from __future__ import annotations
import argparse,collections,json,sqlite3,statistics
from pathlib import Path

KEYS=('provider','method','mode','suite','profile','route')

def ratio(a,b):
    return a/b if b else None

def request_ids(cell):
    ids=set(cell.get('attempts',[]))
    ids.update(v['request_id'] for v in cell.get('judgments',[]) if v.get('request_id'))
    ids.update(v['judge_request_id'] for v in cell.get('repair_checks',[]) if v.get('judge_request_id'))
    ids.update(v['validation']['judge_request_id'] for v in cell.get('selection',[]) if v.get('validation',{}).get('judge_request_id'))
    return ids

def cost_summary(ids,requests):
    known=[requests[rid] for rid in ids if rid in requests]
    estimates=collections.defaultdict(float);actuals=collections.defaultdict(float);times=[]
    for r in known:
        if r.get('currency') and r.get('estimated_cost') is not None:estimates[r['currency']]+=r['estimated_cost']
        if r.get('currency') and r.get('actual_cost') is not None:actuals[r['currency']]+=r['actual_cost']
        if r.get('started') is not None and r.get('ended') is not None:times.append(r['ended']-r['started'])
    return {'referenced_or_retry_request_ids':len(ids),'ledger_requests_found':len(known),'missing_ledger_records':len(ids)-len(known),
            'succeeded_requests':sum(r.get('state')=='succeeded' for r in known),'failed_requests':sum(r.get('state')=='failed' for r in known),
            'known_estimated_cost_by_currency':dict(estimates),'known_actual_cost_by_currency':dict(actuals),
            'requests_with_unknown_cost':sum(not r.get('currency') or (r.get('estimated_cost') is None and r.get('actual_cost') is None) for r in known),
            'request_wall_seconds_total':sum(times) if times else None,'request_wall_seconds_median':statistics.median(times) if times else None,
            'timed_requests':len(times),'scope':'Unique linked requests and recorded retries of the same task key. Excludes unlinked all-failure requests; costs are a partial attribution, not a complete cell bill. Durations exclude pre-reservation queue wait and are not full cell latency.'}

def summarize(cells,originals,request_records=()):
    request_records=list(request_records)
    requests={r['id']:r for r in request_records};by_task=collections.defaultdict(set)
    for r in request_records:
        if r.get('task_key'):by_task[r['task_key']].add(r['id'])
    groups=collections.defaultdict(list)
    for c in cells:groups[tuple(c[k] for k in KEYS)].append(c)
    output=[];global_ids=set();membership=collections.Counter()
    for key,rows in sorted(groups.items()):
        result=dict(zip(KEYS,key));values=[];length_changes=[];linked=set();counts=collections.Counter()
        family_ids={r['source_group_id'] for r in rows}
        for c in rows:
            ids=request_ids(c);linked.update(ids)
            for rid in ids:
                if rid in requests:linked.update(by_task[requests[rid].get('task_key')])
            candidate=c.get('candidate_text');original=originals.get(c['id'])
            counts['recorded_cells']+=1;counts['completed_cells']+=c['status']=='completed';counts['operational_error_cells']+=c['status']=='error'
            counts['confirmed_effective_success_cells']+=bool(c.get('effective_success',False))
            counts['missing_candidate_cells']+=candidate is None;counts['missing_original_cells']+=original is None
            comparable=candidate is not None and original is not None
            if candidate is not None:
                counts['candidate_cells']+=1;counts['empty_candidate_cells']+=not candidate.strip()
            if comparable:
                counts['length_comparison_cells']+=1;length_changes.append(len(candidate)-len(original));counts['unchanged_text_cells']+=candidate==original
                if len(original):values.append(len(candidate)/len(original))
                else:counts['empty_original_cells']+=1
            valid=[v['verdict'] for v in c.get('judgments',[]) if v.get('evidence_valid',False)]
            counts['invalid_or_unverified_evidence_votes']+=sum(not v.get('evidence_valid',False) for v in c.get('judgments',[]))
            counts['valid_evidence_votes']+=len(valid)
            if not valid:continue
            counts['cells_with_valid_votes']+=1
            counts['model_new_serious_issue_cells']+=any(not v['no_new_serious_issue'] for v in valid)
            counts['model_uncertain_fidelity_or_requirements_cells']+=any(v['fidelity']=='uncertain' or v['requirements']=='uncertain' for v in valid)
            no_edit=all(v['original_no_edit_needed'] for v in valid)
            counts['available_votes_agree_original_no_edit_cells']+=no_edit
            counts['original_no_edit_disagreement_cells']+=len({v['original_no_edit_needed'] for v in valid})>1
            if no_edit and comparable:
                counts['comparable_model_no_edit_cells']+=1
                harm=any(v['target_improvement']=='worse' or v['fidelity']=='fail' or v['requirements']=='fail' or not v['no_new_serious_issue'] for v in valid)
                counts['harmful_change_on_model_no_edit_cells']+=candidate!=original and harm
                counts['unchanged_model_no_edit_pass_cells']+=candidate==original and all(v['fidelity']=='pass' and v['requirements']=='pass' and v['no_new_serious_issue'] and (v['process_clean'] or c['mode']=='style') for v in valid)
        fields=('recorded_cells','completed_cells','operational_error_cells','confirmed_effective_success_cells','candidate_cells','missing_candidate_cells','missing_original_cells','empty_candidate_cells','length_comparison_cells','empty_original_cells','unchanged_text_cells','valid_evidence_votes','invalid_or_unverified_evidence_votes','cells_with_valid_votes','model_new_serious_issue_cells','model_uncertain_fidelity_or_requirements_cells','available_votes_agree_original_no_edit_cells','original_no_edit_disagreement_cells','comparable_model_no_edit_cells','harmful_change_on_model_no_edit_cells','unchanged_model_no_edit_pass_cells')
        result.update({name:counts[name] for name in fields})
        result.update(source_family_clusters=len(family_ids),mean_length_ratio=statistics.mean(values) if values else None,median_length_ratio=statistics.median(values) if values else None,mean_codepoint_change=statistics.mean(length_changes) if length_changes else None,
                      harmful_change_on_model_no_edit_rate=ratio(counts['harmful_change_on_model_no_edit_cells'],counts['comparable_model_no_edit_cells']),
                      unchanged_model_no_edit_pass_rate=ratio(counts['unchanged_model_no_edit_pass_cells'],counts['comparable_model_no_edit_cells']),
                      model_new_serious_issue_rate=ratio(counts['model_new_serious_issue_cells'],counts['cells_with_valid_votes']),cost=cost_summary(linked,requests))
        output.append(result);global_ids.update(linked);membership.update(linked)
    return {'strata':output,'unique_attributed_requests_total':cost_summary(global_ids,requests),'request_ids_shared_between_strata':sum(n>1 for n in membership.values()),
            'scope':['Descriptive saved-cell operational metrics, not a new trial or a replacement for frozen effective-success criteria',
                     'Suites, profiles, routes, modes and providers remain separate; no pooled writing-quality score is produced',
                     'Variants, repeats and model votes are correlated; no extra independent families are inferred',
                     'No-edit and harmful-change signals use available evidence-valid model votes, sometimes only one on an incomplete cell; not human truth',
                     'New serious issue is a model signal distinct from source-fidelity failure; unchanged text alone is not editing success',
                     'Length is whole-string Unicode codepoints including whitespace and markup, not a new task word-count threshold',
                     'A referenced cached request is counted once within a stratum and once in the study total; costs across strata are not additive',
                     'All-failure calls with no saved cell reference can remain unattributed; global ledger totals must also be reported',
                     'Request timing excludes queue wait; full cell latency and actual vendor bills cannot be reconstructed from these fields']}

def load_cells(directory):
    directory=Path(directory);rows={}
    for p in sorted(list((directory/'cells').glob('*.json'))+list((directory/'batches').glob('*/cells/*.json'))):
        value=json.loads(p.read_text(encoding='utf-8'));old=rows.get(p.stem)
        if old and old.get('execution_attempt',1)==value.get('execution_attempt',1) and old!=value:raise ValueError('Conflicting same-attempt cell records')
        if old is None or value.get('execution_attempt',1)>old.get('execution_attempt',1):rows[p.stem]=value
    return list(rows.values())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',required=True);p.add_argument('--input',action='append',default=[]);p.add_argument('--family-directory');p.add_argument('--work-dir');p.add_argument('--output',required=True);args=p.parse_args()
    originals={}
    def add(row):
        if row['id'] in originals and originals[row['id']]!=row['input_text']:raise ValueError('Conflicting original text')
        originals[row['id']]=row['input_text']
    for name in args.input:
        for line in Path(name).read_text(encoding='utf-8').splitlines():
            if line:add(json.loads(line))
    if args.family_directory:
        for file in sorted(Path(args.family_directory).glob('main-*.json')):
            for row in json.loads(file.read_text(encoding='utf-8'))['records']:add(row)
    request_records=[]
    if args.work_dir:
        db_path=(Path(args.work_dir)/'requests.sqlite3').resolve()
        with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            request_records=[dict(r) for r in db.execute('select id,task_key,provider,state,started,ended,estimated_cost,actual_cost,currency from requests')]
    cells=load_cells(args.experiment)
    identity=lambda c:tuple(c[k] for k in ('id','provider','method','mode','repeat'))
    observed={identity(c) for c in cells}
    if len(observed)!=len(cells):raise ValueError('Duplicate logical cell records')
    result=summarize(cells,originals,request_records)
    manifest_path=Path(args.experiment)/'manifest.json'
    registered=json.loads(manifest_path.read_text(encoding='utf-8'))['cells'] if manifest_path.is_file() else None
    if registered is not None and not observed<={identity(c) for c in registered}:raise ValueError('Unregistered cell result')
    result['coverage']={'registered_cells':len(registered) if registered is not None else None,'recorded_cells':len(cells),'without_terminal_record':len({identity(c) for c in registered}-observed) if registered is not None else None,'recorded_source_families':len({c['source_group_id'] for c in cells}),'scope':'Unrun registered cells are missing coverage, not imputed model failures; rates use their explicitly reported observed denominators'}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'strata':len(result['strata']),'unique_attributed_requests':result['unique_attributed_requests_total']['referenced_or_retry_request_ids'],'output_written':True}))

if __name__=='__main__':main()
