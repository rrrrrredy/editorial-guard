"""Independent semantic verification; bounded repair and honest abstention."""
from .core import Context,content_hash,language_scope,lint_text,verify_edit
from .protocol import EDIT,VERIFY,REWRITE,VERDICT

def semantic_verify(client,provider,original,candidate,context):
    deterministic=verify_edit(original,candidate,context)
    if deterministic['language_scope_status']!='supported':return deterministic
    hard={'empty_output','target_language_changed','protected_span_changed','required_literal_missing','length_constraint','document_structure_changed'}
    if hard.intersection(deterministic['reasons']):return deterministic
    response=client.call(provider,VERIFY,{'input_text':original,'candidate_text':candidate,'context':context.public(),'programmatic_signals':deterministic['reasons']},VERDICT,purpose='independent_verify')
    verdict=response['output']
    invalid=any((e['original_span'] and e['original_span'] not in original) or (e['candidate_span'] and e['candidate_span'] not in candidate) for e in verdict['evidence'])
    invalid=invalid or any(not span or span not in original for span in verdict.get('original_process_spans',[])) or any(not span or span not in candidate for span in verdict.get('candidate_process_spans',[]))
    if invalid:return {**deterministic,'status':'unchecked','semantic_review_required':True,'reasons':deterministic['reasons']+['judge_evidence_not_in_text'],'judge_request_id':response['ledger_id']}
    fidelity=verdict['fidelity']=='pass' and verdict['requirements']=='pass'
    improvement=verdict['target_improvement']=='better' or (verdict['target_improvement']=='tie' and verdict['original_no_edit_needed'])
    process=verdict['process_clean'] or context.mode=='style'
    status='pass' if fidelity and improvement and process and verdict['no_new_serious_issue'] else ('unchecked' if 'uncertain' in (verdict['fidelity'],verdict['requirements'],verdict['target_improvement']) else 'fail')
    return {**deterministic,'status':status,'semantic_review_required':False,'semantic_verdict':verdict,'judge_provider':provider,'judge_model':response['requested_model'],'judge_request_id':response['ledger_id']}

def rewrite_text(text,context,client,editor,judge,max_repairs=2):
    if editor==judge:raise ValueError('Primary fidelity judge must differ from candidate author')
    if max_repairs not in (0,1,2):raise ValueError('Repair rounds must be 0..2')
    if language_scope(text,context.locale)!='supported':return {'candidate_text':text,'validation':verify_edit(text,text,context),'attempts':[]}
    attempts=[];feedback=None
    for attempt in range(max_repairs+1):
        response=client.call(editor,EDIT,{'input_text':text,'context':context.public(),'repair_feedback':feedback,'repair_round':attempt},REWRITE,purpose='rewrite')
        candidate=response['output']['candidate_text']
        verdict=semantic_verify(client,judge,text,candidate,context)
        attempts.append({'candidate_text':candidate,'validation':verdict,'request_id':response['ledger_id']})
        if verdict['status']=='pass':return {'candidate_text':candidate,'validation':verdict,'attempts':attempts}
        feedback=verdict
    return {'candidate_text':candidate,'validation':verdict,'attempts':attempts,'original_retained':text}
