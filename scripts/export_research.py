"""Export allowlisted benchmark fields and aggregates; never copy execution logs."""
import argparse,collections,datetime,hashlib,json,sqlite3
from pathlib import Path
from editorial_guard.dataset import dataset_summary,validate_dataset,write_json
from editorial_guard.protocol import ANNOTATION_VERSION
from editorial_guard.core import public_input
from editorial_guard.blinding import opaque_id

def reference(value):
    return 'evidence-'+hashlib.sha256(value.encode()).hexdigest()[:24]


def quality_index(rows):
    """Keep exclusions and unresolved judgments visible without manufacturing consensus."""
    output=[]
    for row in rows:
        annotations=[v['annotation'] for v in row['annotation_records']]
        reasons=[]
        if len(annotations)<2:reasons.append('insufficient_independent_annotations')
        if annotations and all(not a['valid_task'] for a in annotations):reasons.append('all_available_reviewers_reject_task')
        elif any(not a['valid_task'] for a in annotations):reasons.append('task_validity_disputed')
        if any(a['language_scope_status']!='supported' for a in annotations):reasons.append('language_scope_unvalidated')
        if any(a['source_fidelity']=='fail' for a in annotations):reasons.append('original_source_fidelity_contested')
        if any(a['source_fidelity']=='uncertain' or a['task_satisfied']=='uncertain' for a in annotations):reasons.append('semantic_uncertainty')
        missing=[value for value in row['constraints'].get('literal_required',[]) if value not in row['input_text']]
        if missing:reasons.append('required_literal_missing')
        states={(a['style_problem'],a['process_problem']) for a in annotations}
        confirmed_state=list(next(iter(states))) if len(annotations)>=2 and len(states)==1 else None
        no_edit=len(annotations)>=2 and all(a['valid_task'] and a['no_edit_needed'] and a['source_fidelity']=='pass' and a['task_satisfied']=='pass' and not a['style_problem'] and not a['process_problem'] for a in annotations)
        output.append({'id':row['id'],'source_group_id':row['source_group_id'],'route':row['provenance']['route'],
                       'annotation_count':len(annotations),'review_flags':reasons,
                       'task_validity':'insufficient_evidence' if len(annotations)<2 else 'invalid' if all(not a['valid_task'] for a in annotations) else 'disputed' if any(not a['valid_task'] for a in annotations) else 'model_agreement_valid',
                       'agreed_state_style_process':confirmed_state,'model_confirmed_no_edit':no_edit,
                       'designed_boundary':bool(row['provenance'].get('designed_boundary')),
                       'required_literal_count':len(row['constraints'].get('literal_required',[])),
                       'missing_required_literal_count':len(missing)})
    return output

def export(work,destination,release_locked=False,release_locked_families=None):
    if release_locked_families is not None and not release_locked:raise ValueError("Family release list requires explicit locked release")
    approved_locked=None if release_locked_families is None else set(release_locked_families)
    work=Path(work);out=Path(destination)
    if out.exists() and any(out.iterdir()):raise ValueError('Data export output must be empty')
    out.mkdir(parents=True,exist_ok=True)
    schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/sample-0.1.0.json').read_text(encoding='utf-8'))
    allowed=set(schema['properties']);all_rows=[];phase_counts={}
    with sqlite3.connect(work/'requests.sqlite3') as db:
        request_dates={rid:datetime.datetime.fromtimestamp(started,datetime.timezone.utc).isoformat() for rid,started in db.execute('select id,started from requests')}
    def observable(rid):
        p=work/'requests'/(rid+'.request.json')
        if not p.exists():return {'request_date':request_dates.get(rid),'transport':'unknown'}
        setting=json.loads(p.read_text(encoding='utf-8'))
        return {'request_date':request_dates.get(rid),'transport':setting.get('transport','unknown'),'provider_config_hash':setting.get('provider_config_hash','unknown'),'parameters':setting.get('parameters',{}),'endpoint':setting.get('endpoint'),'requested_max_tokens':setting.get('max_tokens'),'effective_max_tokens':setting.get('effective_max_tokens','unknown')}
    for phase,prefix in [('calibration','cal'),('main','main')]:
        directory=work/'data'/phase;rows=[]
        for path in sorted(directory.glob(prefix+'-*.json')):
            family=json.loads(path.read_text(encoding='utf-8'))
            for original in family['records']:
                row={k:v for k,v in original.items() if k in allowed}
                row=json.loads(json.dumps(row))
                rid=row['provenance'].get('request_id')
                row['generation_config'].update(observable(rid))
                row['provenance']['request_id']=reference(rid)
                votes=[]
                for p in sorted((directory/('labels-'+ANNOTATION_VERSION)).glob(row['id']+'--*.json')):
                    vote=json.loads(p.read_text(encoding='utf-8'))
                    vote={k:vote[k] for k in ('provider','requested_model','reported_model','request_id','annotation_version','annotation') if k in vote}
                    vote.update(observable(vote['request_id']))
                    vote['request_id']=reference(vote['request_id']);votes.append(vote)
                row['annotation_records']=votes
                signatures=[tuple(v['annotation'][k] for k in ('valid_task','style_problem','process_problem','source_fidelity','task_satisfied','no_edit_needed')) for v in votes]
                row['disagreement_status']='insufficient_evidence' if len(votes)<2 else 'agreement' if len(set(signatures))==1 else 'disputed'
                row['issues']=votes[0]['annotation']['issues'] if row['disagreement_status']=='agreement' else []
                rows.append(row)
        phase_counts[phase]=dataset_summary(rows);all_rows.extend(rows)
    locked_families={r["source_group_id"] for r in all_rows if r["split"]=="locked_test"}
    if approved_locked is not None and not approved_locked<=locked_families:raise ValueError("Unknown locked family in release list")
    released_locked=locked_families if release_locked and approved_locked is None else (approved_locked or set())
    validation=validate_dataset(all_rows)
    write_json(out/'validation.json',validation)
    suites={}
    for suite in ('StyleBench-ZH','DeliveryBench-ZH'):
        root=out/suite;root.mkdir(exist_ok=True)
        rows=[r for r in all_rows if r['suite']==suite]
        published=[r for r in rows if r['split']!='locked_test' or r['source_group_id'] in released_locked]
        with (root/'samples.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
            for row in published:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        # Alternate task views share their existing source families; they add zero independent families.
        view_index=[]
        with (root/'task-views.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
            for row in published:
                for track in ('detect','generate','workflow'):
                    view=public_input(row);view.update(id=opaque_id(row['id'],'solver-view-v1')+'-'+track,parent_id=opaque_id(row['id'],'solver-view-v1'),source_group_id=opaque_id(row['source_group_id'],'solver-family-v1'),track=track,view_status='task_view_not_independent_sample')
                    view_index.append({'view_id':view['id'],'parent_id':row['id'],'source_group_id':row['source_group_id'],'split':row['split']})
                    if track=='generate':view.pop('input_text',None)
                    stream.write(json.dumps(view,ensure_ascii=False)+'\n')
        write_json(root/'task-view-index.json',view_index)
        partition={kind:[r['id'] for r in published if r['split']==kind] for kind in ('calibration','development','validation','locked_test')}
        write_json(root/'partitions.json',partition)
        write_json(root/'disputed-index.json',[r['id'] for r in published if r['disagreement_status']=='disputed'])
        family_manifest=[]
        for group in sorted({r['source_group_id'] for r in published}):
            members=[r for r in published if r['source_group_id']==group]
            family_manifest.append({'source_group_id':group,'split':members[0]['split'],'suite':suite,'instance_ids':[r['id'] for r in members],'generator':members[0]['provenance']['generator'],'origin':'synthetic fictional task world'})
        write_json(root/'family-manifest.json',family_manifest)
        quality=quality_index(published)
        write_json(root/'quality-index.json',quality)
        summary=dataset_summary(published)
        summary['quality']={'task_validity':dict(collections.Counter(r['task_validity'] for r in quality)),'review_flags':dict(collections.Counter(flag for r in quality for flag in r['review_flags'])),'confirmed_no_edit_instances':sum(r['model_confirmed_no_edit'] for r in quality),'agreed_four_states':dict(collections.Counter(str(r['agreed_state_style_process']) for r in quality)),'required_literal_missing_instances':sum(bool(r['missing_required_literal_count']) for r in quality),'scope':'automated judgments; flags remain visible, no human validation or forced consensus'}
        summary.update(planned_main_families=250,main_families=len({r['source_group_id'] for r in rows if r['split']!='calibration'}),held_back_instances=len(rows)-len(published),generation_cohorts=dict(collections.Counter(r['provenance']['generator']+'|'+r['generation_config'].get('transport','unknown')+'|'+r['generation_config'].get('provider_config_hash','unknown') for r in published)),designed_boundary_instances=sum(bool(r['provenance'].get('designed_boundary')) for r in published),all_labels_automated=True,human_validation=False,independent_family_caveat='distinct fictional task worlds drawn from seven base templates; lexical deduplication does not prove semantic independence')
        suites[suite]=summary;write_json(root/'summary.json',summary)
    release={'version':'0.1.0','annotation_version':ANNOTATION_VERSION,'phases':phase_counts,'suites':suites,'validation_status':validation['status'],'locked_test_released':release_locked,'locked_test_release':{'scope':'explicit_family_allowlist' if approved_locked is not None else 'all_locked' if release_locked else 'none','family_ids':sorted(released_locked),'held_back_families':len(locked_families-released_locked)},'files':{str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'},'origin':'programmatic fictional facts and recorded model responses','license':'CC-BY-4.0'}
    write_json(out/'manifest.json',release)
    return release

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work-dir',required=True);p.add_argument('--output',required=True);p.add_argument('--release-locked',action='store_true');p.add_argument('--release-locked-family',action='append',help='Only release evaluated locked families; repeat for each source_group_id');a=p.parse_args()
    print(json.dumps(export(a.work_dir,a.output,a.release_locked,a.release_locked_family),ensure_ascii=False,indent=2))
