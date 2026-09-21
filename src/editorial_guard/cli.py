"""Command-line interface; body output and diagnostics are separate."""
from __future__ import annotations
import argparse,json,sys,uuid
from pathlib import Path
from . import __version__
from .core import Context,lint_text,verify_edit
from .ledger import Ledger,LimitReached
from .providers import ModelClient,ModelFailure
from .pipeline import rewrite_text,semantic_verify
from .finalize import ReceiptStore,finalize_artifact,PublicationBlocked,acceptance_key,read_exact_utf8

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def emit(value,stream=sys.stdout):print(json.dumps(value,ensure_ascii=False,indent=2),file=stream)
def verdict_exit(status):return {'pass':0,'published':0,'fail':1,'blocked':1,'unchecked':2}.get(status,3)

def main(argv=None):
    p=argparse.ArgumentParser(prog='editorial-guard')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    for name in ('lint','rewrite','verify','pipeline'):
        cmd=sub.add_parser(name);cmd.add_argument('input');cmd.add_argument('--context');cmd.add_argument('--mode',choices=('style','process','both'),default='both');cmd.add_argument('--config');cmd.add_argument('--work-dir',default='.eg');cmd.add_argument('--editor',default='deepseek');cmd.add_argument('--judge',default='glm');cmd.add_argument('--output');cmd.add_argument('--sidecar');cmd.add_argument('--candidate');cmd.add_argument('--receipt');cmd.add_argument('--max-repairs',type=int,default=2)
    cmd=sub.add_parser('finalize');cmd.add_argument('candidate');cmd.add_argument('destination');cmd.add_argument('--receipt',required=True);cmd.add_argument('--root',required=True);cmd.add_argument('--work-dir',default='.eg');cmd.add_argument('--config',required=True);cmd.add_argument('--context');cmd.add_argument('--mode',choices=('style','process','both'),default='both')
    cmd=sub.add_parser('dataset');cmd.add_argument('action',choices=('build','annotate','validate'));cmd.add_argument('--config');cmd.add_argument('--work-dir',required=True);cmd.add_argument('--phase',choices=('calibration','main'),default='calibration');cmd.add_argument('--input')
    cmd=sub.add_parser('eval');cmd.add_argument('action',choices=('run','report'));cmd.add_argument('--config');cmd.add_argument('--work-dir',required=True);cmd.add_argument('--input');cmd.add_argument('--manifest');cmd.add_argument('--output',required=True);cmd.add_argument('--retry-errors',action='store_true')
    cmd=sub.add_parser('resume');cmd.add_argument('--work-dir',required=True);cmd.add_argument('--config');cmd.add_argument('--status-only',action='store_true')
    cmd=sub.add_parser('hook');cmd.add_argument('action',choices=('install','disable','uninstall','register'));cmd.add_argument('--root',required=True);cmd.add_argument('--candidate');cmd.add_argument('--receipt');cmd.add_argument('--config');cmd.add_argument('--context');cmd.add_argument('--mode',choices=('style','process','both'),default='both')
    args=p.parse_args(argv)
    try:
        if args.command=='doctor':
            emit({'version':__version__,'python':sys.version.split()[0],'language':'zh-Hans','modes':['style','process','both'],'semantic_status':'requires_configured_models','native_hook':'project adapter; host trust and live event verification required','strict_publication':'controlled local finalize only'});return 0
        if args.command=='hook':
            from .hooks import install,uninstall,register
            if args.action=='register':
                if not args.candidate or not args.receipt or not args.config:raise ValueError('--candidate, --receipt and --config required')
                emit(register(args.root,args.candidate,load(args.receipt),args.config,args.context,args.mode));return 0
            emit(install(args.root) if args.action=='install' else uninstall(args.root));return 0
        if args.command=='resume':
            job_path=Path(args.work_dir)/'active-job.json'
            if args.status_only:
                emit(Ledger(Path(args.work_dir)/'requests.sqlite3').summary());return 0
            if not job_path.exists():
                emit({'status':'unchecked','reason':'no_saved_job','ledger':Ledger(Path(args.work_dir)/'requests.sqlite3').summary()});return 2
            job=load(job_path);command=list(job['argv'])
            if command[:2] not in (['dataset','build'],['dataset','annotate'],['eval','run']):raise ValueError('Unsupported saved job; resume accepts data and evaluation jobs only')
            if args.config:
                pos=command.index('--config');command[pos+1]=args.config
            if command[:2]==['eval','run'] and '--retry-errors' not in command:command.append('--retry-errors')
            return main(command)
        if args.command=='dataset':
            from .dataset import build_dataset,annotate_dataset,validate_dataset
            if args.action=='validate':
                if not args.input:raise ValueError('--input required')
                report=validate_dataset([json.loads(l) for l in Path(args.input).read_text(encoding='utf-8').splitlines() if l]);emit(report);return 0 if report['status']=='pass' else 1
            if not args.config:raise ValueError('--config required')
            from .dataset import write_json
            job_args=['dataset',args.action,'--config',str(Path(args.config).absolute()),'--work-dir',str(Path(args.work_dir).absolute()),'--phase',args.phase]
            write_json(Path(args.work_dir)/'active-job.json',{'argv':job_args,'status':'running'})
            client=ModelClient(load(args.config),args.work_dir)
            report=(build_dataset if args.action=='build' else annotate_dataset)(client,args.work_dir,args.phase)
            complete=report.get('generated',0)==report.get('target',-1) if args.action=='build' else not report.get('disagreements',{}).get('insufficient_evidence',0)
            write_json(Path(args.work_dir)/'active-job.json',{'argv':job_args,'status':'completed' if complete else 'partial'})
            emit(report);return 0 if complete else 2
        if args.command=='eval':
            from .evals import run_eval,eval_report
            if args.action=='report':
                rows=[load(f) for f in (Path(args.output)/'cells').glob('*.json')];emit(eval_report(rows));return 0
            if not args.config or not args.input or not args.manifest:raise ValueError('--config, --input and frozen --manifest required')
            rows=[json.loads(l) for l in Path(args.input).read_text(encoding='utf-8').splitlines() if l]
            from .dataset import write_json
            job_args=['eval','run','--config',str(Path(args.config).absolute()),'--work-dir',str(Path(args.work_dir).absolute()),'--input',str(Path(args.input).absolute()),'--manifest',str(Path(args.manifest).absolute()),'--output',str(Path(args.output).absolute())]
            write_json(Path(args.work_dir)/'active-job.json',{'argv':job_args,'status':'running'})
            report=run_eval(ModelClient(load(args.config),args.work_dir),rows,load(args.manifest),args.output,retry_errors=args.retry_errors)
            write_json(Path(args.work_dir)/'active-job.json',{'argv':job_args,'status':'completed' if report['cells']==report['completed'] else 'partial'})
            emit(report);return 0 if report['cells']==report['completed'] else 2
        if args.command=='finalize':
            config=load(args.config);store=ReceiptStore(Path(args.work_dir)/'receipts')
            ctx=load(args.context) if args.context else {};ctx['mode']=args.mode;context=Context.from_dict(ctx)
            emit(finalize_artifact(args.candidate,load(args.receipt),args.destination,allowed_root=args.root,receipt_store=store,config_hash=acceptance_key(config,context)));return 0
        text=read_exact_utf8(args.input)
        ctx=load(args.context) if args.context else {};ctx['mode']=args.mode;context=Context.from_dict(ctx)
        if args.command=='lint':result=lint_text(text,context);emit(result);return verdict_exit(result['status'])
        if not args.config:raise ValueError('--config required for semantic operations')
        config=load(args.config);client=ModelClient(config,args.work_dir)
        if args.command=='verify':
            if not args.candidate:raise ValueError('--candidate required')
            candidate=read_exact_utf8(args.candidate)
            result=semantic_verify(client,args.judge,text,candidate,context);validation=result
        else:
            result=rewrite_text(text,context,client,args.editor,args.judge,args.max_repairs);validation=result['validation']
            # Out-of-scope input is preserved; failed semantic candidates never masquerade as final output.
            body=result['candidate_text'] if validation['status']=='pass' else text
            if args.output:Path(args.output).write_bytes(body.encode('utf-8'))
            else:print(body,end='')
        if args.receipt and validation['status']=='pass':
            receipt=ReceiptStore(Path(args.work_dir)/'receipts').issue(validation,str(uuid.uuid4()),'cli',acceptance_key(config,context))
            Path(args.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        if args.sidecar:Path(args.sidecar).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        emit(result,sys.stdout if args.command=='verify' else sys.stderr)
        return verdict_exit(validation['status'])
    except (ValueError,OSError,ModelFailure,PublicationBlocked,LimitReached) as exc:
        emit({'status':'error','error_type':type(exc).__name__,'detail':str(exc) if isinstance(exc,(ValueError,ModelFailure,PublicationBlocked,LimitReached)) else 'Filesystem operation failed'},sys.stderr);return 3
if __name__=='__main__':raise SystemExit(main())
