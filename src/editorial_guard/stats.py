"""Family-level descriptive metrics; zero denominators are undefined."""
import random,statistics,collections

def safe_ratio(a,b):return a/b if b else None
def classification_metrics(expected,predicted):
    if len(expected)!=len(predicted):raise ValueError('Mismatched observations')
    tp=sum(a and b for a,b in zip(expected,predicted));fp=sum(not a and b for a,b in zip(expected,predicted));fn=sum(a and not b for a,b in zip(expected,predicted))
    precision=safe_ratio(tp,tp+fp);recall=safe_ratio(tp,tp+fn)
    return {'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,'f1':safe_ratio(2*tp,2*tp+fp+fn),'denominator':len(expected)}

def paired_cluster_bootstrap(rows,a='a',b='b',iterations=2000,seed=4201):
    families=collections.defaultdict(list)
    for row in rows:families[row['source_group_id']].append(row[b]-row[a])
    values=[statistics.mean(families[key]) for key in sorted(families)]
    if len(values)<2:return {'difference':statistics.mean(values) if values else None,'ci95':None,'families':len(values),'reason':'insufficient_families'}
    rng=random.Random(seed);means=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(iterations))
    return {'difference':statistics.mean(values),'ci95':[means[int(iterations*.025)],means[min(iterations-1,int(iterations*.975))]],'families':len(values),'unit':'source_group_id','scope':'conditional on synthetic distribution and model judges; not human preference'}

def span_metrics(expected,predicted):
    """Compare located issue spans; duplicates and overlaps do not add character credit.

    Inputs contain document_id, start/end (Unicode code points, end exclusive), and task.
    Exact spans require identical boundaries and task; character scores use a union per task.
    Empty denominators return None rather than a perfect score.
    """
    def normalize(items):
        exact=set();characters=set()
        for item in items:
            start,end=item['start'],item['end']
            if isinstance(start,bool) or isinstance(end,bool) or not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end:
                raise ValueError('Invalid nonempty Unicode span')
            document=item['document_id'];task=item['task']
            exact.add((document,task,start,end))
            characters.update((document,task,pos) for pos in range(start,end))
        return exact,characters
    gold,gold_chars=normalize(expected);pred,pred_chars=normalize(predicted)
    def score(a,b):
        tp=len(a&b);fp=len(b-a);fn=len(a-b)
        return {'tp':tp,'fp':fp,'fn':fn,'precision':safe_ratio(tp,tp+fp),'recall':safe_ratio(tp,tp+fn),'f1':safe_ratio(2*tp,2*tp+fp+fn)}
    return {'exact_span':score(gold,pred),'character_union':score(gold_chars,pred_chars),'offsets':'Unicode code point; end exclusive','reference_status':'comparison against supplied annotations, not an assertion of objective truth'}
