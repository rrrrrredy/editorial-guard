"""Project-scoped Stop advisory adapter and reversible installation."""
from __future__ import annotations
import argparse,hashlib,json,os,shlex,subprocess,sys
from pathlib import Path
from .core import content_hash,RULE_VERSION
from .finalize import safe_path,PublicationBlocked

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.new');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def install(root):
    root=Path(root).resolve();safe_path(root,root)
    config=root/'.codex'/'hooks.json';safe_path(config,root)
    state=root/'.eg';state.mkdir(exist_ok=True)
    marker=state/'hook-install.json'
    if marker.exists():return {'status':'already_installed','scope':'project'}
    original=config.read_text(encoding='utf-8') if config.exists() else None
    data=json.loads(original) if original else {}
    handlers=data.setdefault('hooks',{}).setdefault('Stop',[])
    argv=[sys.executable,'-m','editorial_guard.hooks','--root',str(root)]
    entry={'hooks':[{'type':'command','command':shlex.join(argv),'commandWindows':subprocess.list2cmdline(argv),'timeout':10,'statusMessage':'Checking registered deliverable versions'}]}
    handlers.append(entry)
    atomic_json(config,data)
    atomic_json(marker,{'entry':entry,'version':RULE_VERSION,'created_config':original is None,'original':original})
    return {'status':'installed','scope':'project','native_status':'requires_host_hook_trust','trust_instruction':'Review this hook in the host /hooks interface. Installation does not imply it has run.'}

def uninstall(root):
    root=Path(root).resolve();config=root/'.codex'/'hooks.json';marker=root/'.eg'/'hook-install.json'
    safe_path(config,root);safe_path(marker,root)
    if not marker.exists():return {'status':'not_installed'}
    record=json.loads(marker.read_text(encoding='utf-8'))
    if config.exists():
        data=json.loads(config.read_text(encoding='utf-8'))
        entries=data.get('hooks',{}).get('Stop',[])
        if record['entry'] not in entries:raise PublicationBlocked('Installed entry changed; preserve user configuration')
        entries.remove(record['entry'])
        if not entries:data['hooks'].pop('Stop',None)
        if not data.get('hooks'):data.pop('hooks',None)
        if not data and record['created_config']:config.unlink()
        else:atomic_json(config,data)
    marker.unlink()
    return {'status':'uninstalled','scope':'only_owned_entry'}

def register(root,path,receipt,config_path=None,context_path=None,mode="both"):
    root=Path(root).resolve();path=safe_path(path,root)
    if path.suffix.lower() not in ('.md','.txt'):raise PublicationBlocked('Unsupported artifact')
    state=root/'.eg';state.mkdir(exist_ok=True)
    file=state/'registered.json';registered=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    registered[str(path.relative_to(root))]={'receipt':receipt,'registered_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'config_path':str(Path(config_path).absolute()) if config_path else None,'context_path':str(Path(context_path).absolute()) if context_path else None,'mode':mode}
    atomic_json(file,registered)
    return {'status':'registered','artifact':str(path.relative_to(root))}

def handle_event(root,event):
    root=Path(root).resolve()
    if event.get('hook_event_name') not in (None,'Stop'):return {}
    if os.environ.get('EDITORIAL_GUARD_WORKER')=='1':return {}
    state=root/'.eg';state.mkdir(exist_ok=True);guard=state/'hook-active.lock'
    try:fd=os.open(guard,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:return {'systemMessage':'Editorial Guard unchecked: concurrent or interrupted hook.'}
    os.close(fd)
    try:
        registry=state/'registered.json'
        if not registry.exists():return {}
        turn=str(event.get('turn_id','unknown'));run=str(event.get('session_id','unknown'))
        count_file=state/'hook-counts.json'
        counts=json.loads(count_file.read_text(encoding='utf-8')) if count_file.exists() else {}
        key=content_hash(run+':'+turn)
        problems=[]
        from .finalize import ReceiptStore
        store=ReceiptStore(state/'receipts')
        for relative,item in json.loads(registry.read_text(encoding='utf-8')).items():
            try:
                path=safe_path(root/relative,root)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                receipt=item['receipt']
                expected=receipt['config_hash']
                if item.get('config_path'):
                    from .finalize import acceptance_key
                    from .core import Context
                    cfg=json.loads(Path(item['config_path']).read_text(encoding='utf-8-sig'))
                    ctx=json.loads(Path(item['context_path']).read_text(encoding='utf-8-sig')) if item.get('context_path') else {}
                    ctx['mode']=item.get('mode','both')
                    expected=acceptance_key(cfg,Context.from_dict(ctx))
                verdict=store.verify(receipt,expected)
                if digest!=verdict['candidate_hash']:problems.append(relative+':changed')
            except (OSError,KeyError,ValueError,PublicationBlocked):problems.append(relative+':unchecked')
        record={'run_id':run,'turn_id':turn,'rule_version':RULE_VERSION,'status':'blocked' if problems else 'pass','problems':problems,'scope':'registered_local_artifacts'}
        atomic_json(state/'last-hook-check.json',record)
        if not problems:return {}
        if event.get('stop_hook_active') or counts.get(key,0)>=2:
            return {'systemMessage':'Editorial Guard blocked: registered artifacts remain unchecked. Continuation limit reached; controlled finalize will refuse publication.'}
        counts[key]=counts.get(key,0)+1;atomic_json(count_file,counts)
        return {'decision':'block','reason':'Registered deliverables changed or lack valid acceptance. Run the controlled verification/finalize workflow. Do not publish unchecked candidates.'}
    finally:guard.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);args=p.parse_args()
    try:print(json.dumps(handle_event(args.root,json.load(sys.stdin)),ensure_ascii=False));return 0
    except Exception:print(json.dumps({'systemMessage':'Editorial Guard unchecked: hook error; controlled finalize still requires validation.'}));return 0
if __name__=='__main__':raise SystemExit(main())
