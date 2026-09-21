"""Chinese-native, family-split synthesis and blinded cross-provider annotation."""
from __future__ import annotations
import collections,concurrent.futures,hashlib,json,random,re,sqlite3,time,uuid
from pathlib import Path
import jsonschema
from .core import public_input,content_hash
from .protocol import GENERATE,GENERATION,ANNOTATE,ANNOTATIONS,ANNOTATION_VERSION,obj
from .providers import ModelFailure
from .ledger import LimitReached
from .blinding import blind_records

PROVIDERS=('codex','deepseek','glm')
GENRES=('行业分析','技术解释','项目文档','工作报告','教程','邮件沟通','社交媒体短文')
TOPICS=('设备巡检','仓储温控','社区图书','园区公交','远程教学','档案修复','农业灌溉','海岸监测','实验室排班','公共照明','博物馆导览','雨水回收','餐厅预订','工厂质检','机器人分拣','电池回收','城市绿化','水务巡查','校园配送','车间通风','气象观测','文化活动','机房散热','港口装卸','食品冷链','林地巡护','运动场预约','出版校对','工地扬尘','无障碍导航','声学测试','桥梁维护','渔业记录','文物数字化','河道清淤','消防演练','助听设备','光伏巡检','湿地保护','种子储存','地下管网','船舶排期','家具维修','缆车运行','道路融雪','陶瓷烧制','废水采样','制衣裁剪','隧道通风','轨道润滑','山地救援','陶片归档','纸张防潮','声场校准','候鸟计数','茶叶分级','灯塔巡查','菌种运输')

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_jsonl(path,rows):
    """Publish one complete snapshot even when independent workers finish together."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    try:
        with temporary.open('w',encoding='utf-8',newline='\n') as stream:
            for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

def family_spec(index,phase):
    calibration=phase=='calibration'
    topic_index=(50+index//10) if calibration else index//10
    topic=TOPICS[topic_index]
    split='calibration' if calibration else ('development' if topic_index<30 else 'validation' if topic_index<40 else 'locked_test')
    rng=random.Random(f'editorial-guard-v1:{phase}:{index}')
    group=f'{"cal" if calibration else "main"}-{index:04d}'
    entity=f'虚构{topic}项目{index+1}号'
    a=rng.randint(31,94);b=rng.randint(5,24);days=rng.randint(8,27)
    kind=index%7
    facts_by_kind=[
      [f'{entity}在{days}天内检查了{a}台设备，其中{b}台需要复检。',f'只有温度低于{rng.randint(28,36)}摄氏度时才安排复检。',f'记录来自项目值班表，尚未证明复检能延长设备寿命。'],
      [f'{entity}本期预算为{a}万元，其中试验费用为{b}万元。',f'采购只有在两组试验都合格后才获准开展。',f'预算尚未实际支出，不能据此计算真实收益。'],
      [f'{entity}的软件测试包含{a}项用例，其中{b}项尚未通过。',f'接口保留API名称retry_after，失败请求不会自动提交。',f'当前仅支持本地读取，计划中的远程写入尚未实现。'],
      [f'{entity}收到{a}份有效问卷，其中{b}份要求延长开放时间。',f'问卷仅来自自愿参加的现有使用者，不能代表所有居民。',f'团队预计在{days}天后复核意见，尚未决定调整时间。'],
      [f'{entity}安排{a}个名额，已有{b}人报名。',f'只有完成预约者才能入场，报名不等于实际参加。',f'活动持续{days}天，尚未公布后续场次。'],
      [f'{entity}本期运输{a}箱物资，其中{b}箱需要温控。',f'只有到货核验通过后才登记为交付，发运不等于签收。',f'运输记录覆盖{days}天，不能推算全年损耗。'],
      [f'{entity}试验组用电{a}千瓦时，对照组用电{a+b}千瓦时。',f'两组运行时长均为{days}小时，但负荷不同。',f'记录显示用电量有差异，尚不足以认定节能效率提高。']
    ]
    facts=facts_by_kind[kind]
    length=('short','medium','long')[index%3]
    requested={'short':'180—280字','medium':'450—650字','long':'900—1300字'}[length]
    if not calibration and length!='short':
        supplements=[
            f'{entity}的资料由记录员甲整理、记录员乙复核，两人的分工不代表独立外部审计。',
            f'本期有{rng.randint(2,4)}份附件尚待核对，未核对的附件不得用于扩大现有结论。',
            f'资料版本号为V{index+1}，后续修订须保留原记录及修改原因。',
            f'本期记录分{rng.randint(2,5)}批录入，批次顺序不表示效果优劣。',
            f'项目只在每周{rng.choice(["一","二","三","四","五"])}更新一次记录，未更新不等于相关工作没有发生。',
            f'本期共有{rng.randint(3,8)}个字段属于可选备注，缺少备注不能解释为结果为零。',
            '异常项应保留原始描述，不能在复核前直接改为正常。',
            '对外使用资料前必须重新核对版本号，内部流转不等于已获准公开。',
            '不同观察条件的记录分别存放，不直接合并为总体效果。',
            '下一步安排是核对附件和记录范围，未提供确定的完成日期或收益承诺。'
        ]
        rng.shuffle(supplements)
        facts=facts+supplements[:3 if length=='medium' else 7]
    stage='plan' if (index//16)%4==0 else ('progress' if (index//16)%8==1 else 'final')
    instruction=f'依据给定虚构资料，为项目参与者撰写{GENRES[index%7]}，交付阶段为{stage}，正文约{requested}。完整保留三项事实及其条件、范围、来源和未知事项。不要当作真实新闻。'
    if not calibration:instruction=instruction.replace('三项事实','全部资料事实')
    if stage=='plan':instruction+='任务明确要求说明下一步核对计划。'
    if stage=='progress':instruction+='任务明确要求报告已完成、尚未完成及下一步。'
    constraints={}
    if not calibration and index%5<2:
        protected_quote='“'+facts[1]+'”'
        instruction+='正文须原样引用以下资料句并保留引号：'+protected_quote
        constraints={'literal_required':[protected_quote],'boundary_kind':'source_quote'}
    return {'source_group_id':group,'index':index,'controlled_state':(index//4)%4,'split':split,'suite':'StyleBench-ZH' if (index//4+index)%2==0 else 'DeliveryBench-ZH','topic':topic,'genre':GENRES[index%7],'length_band':length,'audience':'项目参与者','stage':stage,'delivery_channel':'document','instruction':instruction,'source_bundle':{'fictional':True,'source_language':'zh','facts':facts,'unknowns':['没有提供因果验证或外部普遍性证据']},'constraints':constraints,'generator':PROVIDERS[index%len(PROVIDERS)],'rubric_before_generation':{'required_source_facts':facts,'no_unsupported_claims':True,'stage':stage},'designed_boundary':stage!='final' or bool(constraints)}

def instances(spec,generation,request):
    natural=generation['input_text'];controlled=generation['style_variant'] if spec['controlled_state'] in (1,3) else natural
    if spec['controlled_state'] in (2,3):controlled='下面我先分析，再给出一个深入且可落地的版本。\n\n'+controlled+'\n\n我已为你去除AI味。'
    elif spec['stage']=='plan':controlled='我先核对资料，再给出结论。\n\n'+controlled
    base={'source_group_id':spec['source_group_id'],'parent_id':None,'suite':spec['suite'],'track':'rewrite','split':spec['split'],'language':'zh','locale':'zh-Hans','source_language':'zh','is_translation':False,'language_scope_status':'supported','genre':spec['genre'],'audience':spec['audience'],'stage':spec['stage'],'delivery_channel':spec['delivery_channel'],'instruction':spec['instruction'],'style_profile':'editorial-zh' if spec['index']%5==0 else 'general-zh','source_bundle':spec['source_bundle'],'protected_spans':[],'required_claims':spec['source_bundle']['facts'],'constraints':spec['constraints'],'issues':[],'acceptable_references':[],'provenance':{'origin':'synthetic','generator':spec['generator'],'request_id':request['ledger_id'],'topic':spec['topic'],'length_band':spec['length_band'],'designed_boundary':spec['designed_boundary']},'generation_config':{'requested_model':request['requested_model'],'reported_model':request['reported_model'],'weight_version_locked':False,'transport':request.get('transport','unknown'),'provider_config_hash':request.get('provider_config_hash','unknown')},'annotation_records':[],'disagreement_status':'unannotated','oracle_type':'model_inferred','schema_version':'0.1.0','rubric_version':'0.1.0'}
    out=[]
    for route,text in [('natural',natural),('controlled',controlled)]:
        row={**base,'id':spec['source_group_id']+'-'+route,'variant_id':route,'input_text':text,'content_hash':content_hash(text)}
        row['provenance']={**base['provenance'],'route':route}
        if route=='controlled':row['parent_id']=spec['source_group_id']+'-natural';row['oracle_type']='mixed'
        out.append(row)
    return out

def locate_issues(text,issues):
    result=[]
    for issue in issues:
        quote=issue['text']
        if not quote:raise ValueError('Empty evidence span')
        matches=list(re.finditer(re.escape(quote),text))
        occurrence=issue['occurrence']
        if occurrence>=len(matches):raise ValueError('Evidence span not in original text')
        match=matches[occurrence]
        result.append({**issue,'start':match.start(),'end':match.end(),'rule':issue['category']})
    return result

def reserve_generation(work_dir, phase, family_ids):
    """Conservative persistent cap, independent of prompt changes and transport retries."""
    with sqlite3.connect(Path(work_dir)/'generation_attempts.sqlite3',timeout=30) as db:
        db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT,phase TEXT,family TEXT,created REAL,PRIMARY KEY(id,family))')
        db.execute('BEGIN IMMEDIATE')
        for family in family_ids:
            used=db.execute('SELECT count(*) FROM attempts WHERE phase=? AND family=?',(phase,family)).fetchone()[0]
            if used>=3:raise ValueError('family_attempt_limit:'+family)
        attempt=str(uuid.uuid4())
        db.executemany('INSERT INTO attempts VALUES(?,?,?,?)',[(attempt,phase,f,time.time()) for f in family_ids])
    return attempt

def archive_failures(target,kind,failures):
    write_json(target/(kind+'_failures.json'),failures)
    history=target/'failure_history';history.mkdir(exist_ok=True)
    write_json(history/(kind+'-'+str(time.time_ns())+'.json'),failures)


def build_dataset(client,work_dir,phase='calibration',count=None,batch_size=2,providers=PROVIDERS,family_specs=None):
    if phase not in ('calibration','main'):raise ValueError('Unknown phase')
    count=count if count is not None else (80 if phase=='calibration' else 500)
    target=Path(work_dir)/'data'/phase;target.mkdir(parents=True,exist_ok=True)
    specs=[family_spec(i,phase) for i in range(count)] if family_specs is None else family_specs
    if len(specs)!=count or len({s['source_group_id'] for s in specs})!=count or any(s['generator'] not in PROVIDERS for s in specs):raise ValueError('Invalid generation plan')
    manifest=target/'family_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))!=specs:raise ValueError('Frozen family manifest differs')
    write_json(manifest,specs)
    schema=obj({'families':{'type':'array','items':obj({'source_group_id':{'type':'string'},**GENERATION['properties']})}})
    failures=[]
    def generate(provider):
        local=[]
        assigned=[s for s in specs if s['generator']==provider and not (target/(s['source_group_id']+'.json')).exists()]
        for pos in range(0,len(assigned),batch_size):
            batch=assigned[pos:pos+batch_size]
            public_specs=[{k:v for k,v in s.items() if k not in ('generator','split','designed_boundary','index','controlled_state')} for s in batch]
            try:
                batch_schema=json.loads(json.dumps(schema))
                batch_schema['properties']['families']['items']['properties']['source_group_id']={'enum':[s['source_group_id'] for s in batch]}
                batch_schema['properties']['families'].update(minItems=len(batch),maxItems=len(batch))
                reserve_generation(work_dir,phase,[s['source_group_id'] for s in batch])
                r=client.call(provider,GENERATE+'\n逐字保留每个source_group_id，不改编号，每个家族恰好返回一次。',{'families':public_specs},batch_schema,purpose='family_generation:'+phase,max_tokens=12000)
                by_id={x['source_group_id']:x for x in r['output']['families']}
                if set(by_id)!={s['source_group_id'] for s in batch}:raise ValueError('Wrong family identifiers')
                for s in batch:
                    gen=by_id[s['source_group_id']]
                    if not gen['input_text'].strip() or not gen['style_variant'].strip():raise ValueError('Empty generated text')
                    write_json(target/(s['source_group_id']+'.json'),{'spec':s,'records':instances(s,gen,r),'generation_request':r['ledger_id'],'generated_instruction':gen['instruction'],'generation_output':gen})
            except (ModelFailure,ValueError,LimitReached) as exc:
                local.append({'provider':provider,'families':[s['source_group_id'] for s in batch],'error':str(exc)})
                if isinstance(exc,LimitReached):break
                if isinstance(exc,ModelFailure) and exc.kind in ('http_401','http_403','http_402','account_exhausted','provider_paused','http_429'):break
        return local
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(generate,providers):failures.extend(result)
    archive_failures(target,'generation',failures)
    return {'target':count,'generated':sum((target/(s['source_group_id']+'.json')).exists() for s in specs),'failures':failures}

def annotate_dataset(client,work_dir,phase='calibration',batch_size=2,providers=PROVIDERS,source_group_ids=None,exclude_annotations=None):
    target=Path(work_dir)/'data'/phase
    families=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(target.glob(('cal' if phase=='calibration' else 'main')+'-*.json'))]
    label_dir=target/('labels-'+ANNOTATION_VERSION);label_dir.mkdir(exist_ok=True)
    tasks={p:[] for p in PROVIDERS}
    excluded=exclude_annotations or {}
    skipped=[]
    for family in families:
        if source_group_ids is not None and family['spec']['source_group_id'] not in source_group_ids:continue
        generator=family['spec']['generator'];index=family['spec']['index']
        eligible=[p for p in PROVIDERS if p!=generator]
        judges=eligible
        if len(judges)!=2:raise ValueError('Exactly two independent annotation providers required')
        for judge in judges:
            for row in family['records']:
                if row['id'] in excluded.get(judge,()):
                    skipped.append({'provider':judge,'id':row['id']});continue
                if not (label_dir/(row['id']+'--'+judge+'.json')).exists():tasks[judge].append(row)
    def annotate(provider):
        failures=[]
        rows=sorted(tasks[provider],key=lambda row:(row['variant_id'],row['source_group_id']))
        batches=[]
        for route in ('controlled','natural'):
            route_rows=[row for row in rows if row['variant_id']==route]
            batches.extend(route_rows[pos:pos+batch_size] for pos in range(0,len(route_rows),batch_size))
        for batch in batches:
            try:
                public_batch,mapping=blind_records([public_input(x) for x in batch])
                batch_schema=json.loads(json.dumps(ANNOTATIONS))
                batch_schema['properties']['records']['items']['properties']['id']={'enum':[x['id'] for x in public_batch]}
                batch_schema['properties']['records'].update(minItems=len(batch),maxItems=len(batch))
                r=client.call(provider,ANNOTATE+'\n逐字保留每个id，不改编号，每个实例恰好返回一次。',{'records':public_batch},batch_schema,purpose='blind_annotation:'+phase+':'+ANNOTATION_VERSION,max_tokens=12000)
                if {x['id'] for x in r['output']['records']}!=set(mapping):raise ValueError('Wrong blinded annotation identifiers')
                outputs={mapping[x['id']]:{**x,'id':mapping[x['id']]} for x in r['output']['records']}
                if set(outputs)!={x['id'] for x in batch}:raise ValueError('Wrong annotation identifiers')
                for row in batch:
                    annotation=outputs[row['id']]
                    annotation['issues']=locate_issues(row['input_text'],annotation['issues'])
                    write_json(label_dir/(row['id']+'--'+provider+'.json'),{'provider':provider,'requested_model':r['requested_model'],'reported_model':r['reported_model'],'request_id':r['ledger_id'],'annotation_version':ANNOTATION_VERSION,'transport':r.get('transport','unknown'),'provider_config_hash':r.get('provider_config_hash','unknown'),'annotation':annotation})
            except (ModelFailure,ValueError,LimitReached) as exc:
                failures.append({'provider':provider,'ids':[r['id'] for r in batch],'error':str(exc)})
                if isinstance(exc,LimitReached):break
                if isinstance(exc,ModelFailure) and exc.kind in ('http_401','http_403','http_402','account_exhausted','provider_paused','http_429'):break
        return failures
    failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(annotate,providers):failures.extend(result)
    archive_failures(target,'annotation',failures)
    rows=[]
    for family in families:
        for row in family['records']:
            annotations=[json.loads(p.read_text(encoding='utf-8')) for p in label_dir.glob(row['id']+'--*.json')]
            row['annotation_records']=annotations
            if len(annotations)>=2:
                signatures=[tuple(a['annotation'][k] for k in ('valid_task','style_problem','process_problem','source_fidelity','task_satisfied','no_edit_needed')) for a in annotations]
                row['disagreement_status']='agreement' if len(set(signatures))==1 else 'disputed'
                row['issues']=annotations[0]['annotation']['issues'] if row['disagreement_status']=='agreement' else []
            else:row['disagreement_status']='insufficient_evidence'
            rows.append(row)
    write_jsonl(target/'annotated.jsonl',rows)
    return {**dataset_summary(rows),'excluded_exhausted_annotations':skipped,'failures':failures}

def dataset_summary(rows):
    return {'families':len({r['source_group_id'] for r in rows}),'instances':len(rows),'splits':dict(collections.Counter(r['split'] for r in rows)),'suites':dict(collections.Counter(r['suite'] for r in rows)),'disagreements':dict(collections.Counter(r['disagreement_status'] for r in rows)),'languages':dict(collections.Counter(r['locale'] for r in rows)),'annotation_sources':dict(collections.Counter(r['oracle_type'] for r in rows)),'independent_judgments':sum(len(r['annotation_records']) for r in rows),'confirmed_no_edit':sum(r['disagreement_status']=='agreement' and r['annotation_records'][0]['annotation']['no_edit_needed'] for r in rows)}

def validate_dataset(rows):
    errors=[];splits={};seen={};near=[];schema_valid_rows=[]
    schema=json.loads((Path(__file__).parent/'schemas/sample-0.1.0.json').read_text(encoding='utf-8'))
    validator=jsonschema.Draft202012Validator(schema)
    for r in rows:
        schema_errors=list(validator.iter_errors(r))
        if schema_errors:
            identifier=r.get('id','unknown') if isinstance(r,dict) else 'non_object'
            errors.extend(str(identifier)+':schema:'+str(e.json_path) for e in schema_errors)
            continue
        schema_valid_rows.append(r)
        if content_hash(r['input_text'])!=r['content_hash']:errors.append(r['id']+':content_hash')
        group=r['source_group_id']
        if group in splits and splits[group]!=r['split']:errors.append(group+':family_leak')
        splits[group]=r['split']
        if r['content_hash'] in seen and seen[r['content_hash']]!=r['split']:errors.append(r['id']+':exact_cross_split_duplicate')
        seen[r['content_hash']]=r['split']
        providers=[a['provider'] for a in r['annotation_records']]
        if len(set(providers))!=len(providers):errors.append(r['id']+':duplicate_annotation_provider')
        for a in r['annotation_records']:
            if a['annotation']['id']!=r['id']:errors.append(r['id']+':annotation_id')
            if a['provider']==r['provenance']['generator']:errors.append(r['id']+':self_annotation')
            for issue in a['annotation']['issues']:
                if r['input_text'][issue['start']:issue['end']]!=issue['text']:errors.append(r['id']+':span')
    # Character 5-gram overlap ignores numbers to detect superficial template clones.
    representatives={r['source_group_id']:r for r in schema_valid_rows if r['variant_id']=='natural'}
    fingerprints=[]
    for r in representatives.values():
        text=re.sub(r'\d+','N',r['input_text'])
        grams={text[i:i+5] for i in range(max(0,len(text)-4))}
        for old,other in fingerprints:
            if old['split']==r['split']:continue
            union=len(grams|other)
            similarity=len(grams&other)/union if union else 1
            if similarity>0.72:near.append({'a':old['id'],'b':r['id'],'jaccard':similarity})
        fingerprints.append((r,grams))
    return {'status':'pass' if not errors and not near else 'fail','errors':errors,'cross_split_near_duplicates':near,'schema_invalid_rows':len(rows)-len(schema_valid_rows),'summary':dataset_summary(schema_valid_rows),'near_duplicate_scope':'lexical 5-grams; does not establish semantic independence'}
