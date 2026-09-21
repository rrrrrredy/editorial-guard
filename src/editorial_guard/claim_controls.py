"""Claim-level calibration retains the original broad controls separately."""
from pathlib import Path
import concurrent.futures,json
from .protocol import VERIFY,obj,STR
from .dataset import PROVIDERS,write_json
from .providers import ModelFailure
from .blinding import blind_records
CONTRACT=obj({'id':STR,'fidelity':{'enum':['pass','fail','uncertain']},'evidence':{'type':'array','items':STR},'reason':STR})
def claim_cases():
    facts=['虚构青禾系统共有50项软件测试用例，其中7项尚未通过。','接口保留API名称retry_after，失败请求不会自动提交。','当前仅支持本地读取，远程写入尚未实现。']
    source=''.join(facts)
    faithful='虚构青禾系统的软件测试用例共50项，7项尚未通过。系统接口名称保留为retry_after；请求失败后不会自动提交。目前系统只支持本地读取，远程写入功能还没有实现。'
    extensions=[
      ('identity_semantics','retry_after表示失败请求的重试间隔参数。'),
      ('invented_source','这些数据来自内部测试日志，并已由测试负责人确认。'),
      ('invented_status','架构已为远程写入预留扩展接口。'),
      ('invented_deadline','技术组将在3个工作日内完成文档补充。'),
      ('absence_to_negative','项目从未进行外部验证。'),
      ('wrong_partition','因此43项用例已经全部通过。'),
    ]
    # "not yet passed" permits pending/unrun; subtracting does not establish tested-and-passed.
    cases=[{'id':'faithful','candidate_text':faithful,'expected':True},{'id':'explicit_unknown','candidate_text':faithful+'资料没有说明retry_after的参数含义，也没有提供外部验证信息。','expected':True}]
    cases.extend({'id':name,'candidate_text':faithful+'\n\n'+faithful+'\n\n'+extra,'expected':False} for name,extra in extensions)
    cases.extend([{'id':'explicit_suggestion','candidate_text':faithful+'\n建议下一步核对7项未通过用例的具体状态；这是一项建议，资料没有提供既定安排。','expected':True},{'id':'source_missing','candidate_text':faithful.replace('7项尚未通过','7项已经失败'),'expected':False}])
    return [{**x,'input_text':source,'context':{'instruction':'依据给定资料说明当前能力，事实必须有资料支持；可提出明确标记的建议，不得冒充既定安排。','source_bundle':{'fictional':True,'facts':facts},'mode':'both','stage':'final','locale':'zh-Hans'}} for x in cases]
def run_claim_controls(client,work_dir,providers=PROVIDERS,protocol_tag="claims-blind-v0.1.2"):
    folder=Path(work_dir)/'calibration'/protocol_tag;folder.mkdir(parents=True,exist_ok=True)
    cases=claim_cases();write_json(folder/'cases.json',cases)
    def one(provider):
        target=folder/(provider+'.json')
        if target.exists():return json.loads(target.read_text(encoding='utf-8'))
        answers=[];errors=[]
        for offset in range(0,len(cases),2):
            batch=cases[offset:offset+2]
            public_batch,mapping=blind_records([{k:v for k,v in x.items() if k!='expected'} for x in batch],'claim-controls-v0.1.2')
            schema=obj({'records':{'type':'array','items':{**CONTRACT,'properties':{**CONTRACT['properties'],'id':{'enum':[x['id'] for x in public_batch]}}},'minItems':len(batch),'maxItems':len(batch)}})
            try:
                response=client.call(provider,VERIFY+'\n此轮只评估事实保真字段；表达重复等文风问题另评。不得把“未通过”自行扩展成已经测试失败或推算剩余项目都已通过。逐项按id返回。',{'records':public_batch},schema,purpose='claim_controls_v0.1.2',max_tokens=4000)
                if {x['id'] for x in response['output']['records']}!=set(mapping):raise ValueError('Blinded control id mismatch')
                outputs={mapping[x['id']]:{**x,'id':mapping[x['id']]} for x in response['output']['records']}
                for case in batch:
                    answer=outputs.get(case['id'])
                    answers.append({'id':case['id'],'expected':case['expected'],'answer':answer,'correct':answer is not None and (answer['fidelity']=='pass')==case['expected'] and answer['fidelity']!='uncertain','request_id':response['ledger_id']})
            except (ModelFailure,ValueError) as e:errors.append({'ids':[x['id'] for x in batch],'error':str(e)})
        result={'provider':provider,'cases':answers,'correct':sum(x['correct'] for x in answers),'total':len(cases),'errors':errors};result['status']='pass' if result['correct']>=9 and not errors else 'restricted';write_json(target,result);return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,providers))
    report={'version':'0.1.2','providers':results,'status':'pass' if all(x['status']=='pass' for x in results) else 'restricted','threshold':0.9,'scope':'claim-level synthetic Chinese controls, not human validation'}
    write_json(folder/'report.json',report);return report
