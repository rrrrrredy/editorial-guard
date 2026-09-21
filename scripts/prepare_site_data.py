"""Prepare minimal site data from actual exports and frozen experiment records.

This command performs no inference, publication or release acceptance.
"""
import argparse,collections,hashlib,json
from pathlib import Path
from build_release import checked_data_files,SUITES
from summarize_experiment import load_cells

def key(c):return tuple(c[k] for k in ('id','provider','method','mode','repeat'))
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def fraction(n,d):return f'{n}/{d} ({n/d:.1%})' if d else '未定义（分母为0）'

def prepare(data_export,experiment,output,models=None):
    data=Path(data_export);exp=Path(experiment);out=Path(output)
    if out.exists() and any(out.iterdir()):raise ValueError('Site data output must be empty')
    export=read(data/'manifest.json');checked_data_files(data,export)
    if export['validation_status']!='pass':raise ValueError('Invalid dataset export')
    samples=[]
    for suite in SUITES:
        for line in (data/suite/'samples.jsonl').read_text(encoding='utf-8').splitlines():
            if not line:continue
            row=json.loads(line)
            if row['suite']!=suite:raise ValueError('Wrong dataset suite')
            if row['split']=='locked_test' and not export['locked_test_released']:raise ValueError('Locked text lacks exposure approval')
            item={k:row[k] for k in ('id','source_group_id','suite','split','genre','stage','instruction','input_text','locale','disagreement_status')}
            item['provenance']={'route':row['provenance']['route']}
            if row['split']=='locked_test':item['test_exposure_approved']=True
            samples.append(item)
    if len({r['id'] for r in samples})!=len(samples):raise ValueError('Duplicate sample identifier')
    manifest=read(exp/'manifest.json');cells=load_cells(exp);observed={key(c):c for c in cells};expected={key(c) for c in manifest['cells']}
    if len(observed)!=len(cells) or len(expected)!=len(manifest['cells']) or not set(observed)<=expected:raise ValueError('Duplicate or unregistered experiment cells')
    strata={s['source_group_id']:s for s in manifest['strata']};meta={}
    for cell in cells:
        value=tuple(cell[k] for k in ('suite','profile','route'))
        if cell['id'] in meta and meta[cell['id']]!=value:raise ValueError('Conflicting experiment metadata')
        meta[cell['id']]=value
    groups=collections.defaultdict(list)
    for c in manifest['cells']:
        family=c['id'].rsplit('-',1)[0]
        route=c['id'].rsplit('-',1)[-1]
        suite,profile,route=meta.get(c['id'],(strata[family]['suite'],'源家族尚缺',route if route in ('natural','controlled') else 'unknown'))
        groups[(suite,c['provider'],c['method'],c['mode'],route,profile)].append(c)
    result_groups={suite:[] for suite in SUITES};models=models or {}
    for g,registered in sorted(groups.items()):
        suite,provider,method,mode,route,profile=g;rows=[observed[key(c)] for c in registered if key(c) in observed]
        completed=sum(c['status']=='completed' for c in rows);errors=sum(c['status']=='error' for c in rows);success=sum(bool(c.get('effective_success',False)) for c in rows);missing=len(registered)-len(rows)
        if not 0<=success<=completed<=len(rows)<=len(registered):raise ValueError('Inconsistent experiment counts')
        status=f'执行错误 {errors}；未运行 {missing}' if errors or missing else '已记录全部调用结果'
        result_groups[suite].append({'provider':provider,'model':provider+' / '+str(models.get(provider,'请求模型未知')),'method':method,'mode':mode,'route':route,'profile':profile,'n':len(registered),'recorded':len(rows),'completed':completed,'execution_errors':errors,'without_terminal_record':missing,'effective_success_count':success,'success':fraction(success,len(rows)),'success_given_completion':fraction(success,completed),'status':status})
    completed=sum(c['status']=='completed' for c in cells);errors=sum(c['status']=='error' for c in cells)
    main=export['phases']['main']['families'];cal=export['phases']['calibration']['families']
    summary={'summary':f'真实记录快照：校准{cal}个家族，主数据{main}个家族。正式实验登记{len(expected)}个单元，已记录{len(cells)}个，完成{completed}个，执行错误{errors}个，未取得终态{len(expected)-len(cells)}个。结果仅覆盖所列真实记录，缺失单元不插值。',
             'statuses':[{'label':'数据目标','value':f'校准{cal}/80；主数据{main}/500'},{'label':'版本范围','value':'当前仅接入三家模型；结果须与重新登记的矩阵和评分器版本绑定，不能继承旧综合实验结论。'},{'label':'推断限制','value':'简体中文合成任务、自动模型裁判，无人工验证；同源变体与重复运行不增加独立家族数。'}],
             'suite_results':[{'suite':suite,'note':'按模式、路线与风格配置分层。两个有效成功比例分别使用已记录和已完成单元作分母，缺失执行不插值。表格可横向滚动。','rows':result_groups[suite]} for suite in SUITES],
             'counts':{'registered':len(expected),'recorded':len(cells),'completed':completed,'execution_errors':errors,'without_terminal_record':len(expected)-len(cells)},
             'provenance':{'data_export_manifest_sha256':hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),'experiment_manifest_sha256':hashlib.sha256((exp/'manifest.json').read_bytes()).hexdigest(),'recorded_cell_set_sha256':hashlib.sha256(json.dumps(cells,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'scope':'Minimal real-data site view; full raw execution logs and private ledger are not included'}}
    write(out/'datasets/public_samples.json',samples);write(out/'reports/public_summary.json',summary)
    receipt={'samples':len(samples),'locked_samples':sum(r['split']=='locked_test' for r in samples),'result_rows':sum(len(g['rows']) for g in summary['suite_results']),'counts':summary['counts'],'release_acceptance_performed':False}
    write(out/'site-data-manifest.json',receipt)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-export',required=True);p.add_argument('--experiment',required=True);p.add_argument('--output',required=True);p.add_argument('--models',help='JSON mapping provider name to actual requested model ID; no credentials');a=p.parse_args()
    print(json.dumps(prepare(a.data_export,a.experiment,a.output,read(a.models) if a.models else None),ensure_ascii=False))
