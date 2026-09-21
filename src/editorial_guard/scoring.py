"""Offline detection comparisons against independent automated annotations."""
import collections
from .stats import classification_metrics,span_metrics

def detection_report(samples,predictions):
    by_id={row['id']:row for row in samples}
    groups=collections.defaultdict(list);coverage=collections.Counter();seen=set()
    for prediction in predictions:
        identity=(prediction['provider'],prediction['id'])
        if identity in seen:raise ValueError('Duplicate detector instance; keep repeats in separate cohorts')
        seen.add(identity);provider,rid=identity;coverage[(provider,'registered')]+=1
        if prediction.get('status')!='completed':
            coverage[(provider,'execution_error')]+=1;continue
        coverage[(provider,'completed')]+=1
        row=by_id[rid];references=[r for r in row['annotation_records'] if r['provider']!=provider]
        if not references:coverage[(provider,'no_independent_reference')]+=1
        for reference in references:
            gold=reference['annotation'];pred=prediction['annotation']
            if not gold['valid_task'] or gold['language_scope_status']!='supported':
                coverage[(provider,'ineligible_reference_votes')]+=1;continue
            for task in ('style','process'):
                def spans(annotation):
                    return [{'document_id':rid,'task':task,'start':x['start'],'end':x['end']} for x in annotation['issues'] if x['suite']==task and x['action'] in ('rewrite','remove')]
                groups[(provider,reference['provider'],row['suite'],task)].append({
                    'source_group_id':row['source_group_id'],'expected':gold[task+'_problem'],'predicted':pred[task+'_problem'],
                    'expected_spans':spans(gold),'predicted_spans':spans(pred)})
    comparisons=[]
    for key,items in sorted(groups.items()):
        comparisons.append({**dict(zip(('detector','reference_provider','suite','task'),key)),
                            'instances':len(items),'families':len({x['source_group_id'] for x in items}),
                            'document':classification_metrics([x['expected'] for x in items],[x['predicted'] for x in items]),
                            'localization':span_metrics([s for x in items for s in x['expected_spans']],[s for x in items for s in x['predicted_spans']])})
    return {'coverage':[{'provider':p,**{name:n for (q,name),n in coverage.items() if q==p}} for p in sorted({p for p,name in coverage})],
            'comparisons':comparisons,
            'reference_status':'independent model-relative agreement; references remain separate, not human or objective truth',
            'positive_span_policy':'rewrite/remove issue actions only; preserve/review are not positive corrections',
            'uncertainty':'No score for missing independent reference; no interpolation for failed detector calls; repeated families are not independent votes'}

def mask_exact_process_spans(text,spans):
    """Literal secondary-analysis masking; reject missing or protected spans."""
    import re
    from .core import protected_ranges,overlaps
    protected=protected_ranges(text);ranges=[]
    for span in spans:
        if not span:raise ValueError('Empty process span')
        matches=list(re.finditer(re.escape(span),text))
        if not matches:raise ValueError('Process span absent from text')
        for match in matches:
            if overlaps(match.start(),match.end(),protected):raise ValueError('Process span overlaps protected content')
            ranges.append((match.start(),match.end()))
    pieces=[];cursor=0
    for start,end in sorted(set(ranges)):
        if end<=cursor:continue
        if start>cursor:pieces.append(text[cursor:start])
        cursor=max(cursor,end)
    pieces.append(text[cursor:])
    return ''.join(pieces)
