"""Version-bound local publication. This cannot control other publication tools."""
from __future__ import annotations
import hashlib,hmac,json,os,secrets,stat,tempfile
from pathlib import Path
from .core import content_hash,RULE_VERSION

class PublicationBlocked(RuntimeError): pass

def safe_path(path,root):
    root=Path(root).absolute();path=Path(path).absolute()
    if '..' in root.parts or '..' in path.parts:raise PublicationBlocked('Parent traversal forbidden')
    try:path.relative_to(root)
    except ValueError:raise PublicationBlocked('Path outside authorized root')
    current=path
    while True:
        if current.exists() or current.is_symlink():
            info=current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise PublicationBlocked('Symlink or reparse point forbidden')
        if current==root:break
        if current==current.parent:raise PublicationBlocked('Invalid root')
        current=current.parent
    if not root.exists():raise PublicationBlocked('Authorized root does not exist')
    return path

def acceptance_key(config,context):
    from .ledger import Ledger
    from .protocol import EDIT,VERIFY,VERDICT
    return Ledger.key({'provider_config':config,'context':context.public(),'rule_version':RULE_VERSION,'editor_prompt_hash':Ledger.key(EDIT),'verifier_prompt_hash':Ledger.key(VERIFY),'verdict_schema_hash':Ledger.key(VERDICT)})

def read_exact_utf8(path):
    return Path(path).read_bytes().decode('utf-8')

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()

class ReceiptStore:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.key_path=self.root/'receipt.key'
        try:
            fd=os.open(self.key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
        except FileExistsError:pass
        self.key=self.key_path.read_bytes()
        if len(self.key)!=32:raise PublicationBlocked('Receipt key incomplete or invalid; publication remains blocked')

    def issue(self,validation,run_id,turn_id,config_hash):
        if validation.get('status')!='pass':raise PublicationBlocked('Validation did not pass')
        receipt={'validation':validation,'run_id':run_id,'turn_id':turn_id,'config_hash':config_hash,'rule_version':RULE_VERSION}
        receipt['signature']=hmac.new(self.key,canonical(receipt),hashlib.sha256).hexdigest()
        return receipt

    def verify(self,receipt,config_hash):
        data=dict(receipt);sig=data.pop('signature','')
        if not hmac.compare_digest(sig,hmac.new(self.key,canonical(data),hashlib.sha256).hexdigest()):raise PublicationBlocked('Invalid receipt signature')
        if data['config_hash']!=config_hash or data['rule_version']!=RULE_VERSION:raise PublicationBlocked('Stale configuration or rules')
        if data['validation']['status']!='pass':raise PublicationBlocked('Non-passing receipt')
        return data['validation']

def finalize_artifact(candidate,validation,destination,*,allowed_root,receipt_store,config_hash):
    source=safe_path(candidate,allowed_root);target=safe_path(destination,allowed_root)
    if source.suffix.lower() not in ('.txt','.md') or target.suffix.lower() not in ('.txt','.md'):raise PublicationBlocked('Unsupported artifact extension')
    verdict=receipt_store.verify(validation,config_hash)
    data=source.read_bytes()
    if hashlib.sha256(data).hexdigest()!=verdict['candidate_hash']:raise PublicationBlocked('Candidate changed after validation')
    if not target.parent.exists():raise PublicationBlocked('Destination parent must already exist')
    fd,temp=tempfile.mkstemp(prefix='.eg-',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        safe_path(source,allowed_root);safe_path(target,allowed_root)
        if source.read_bytes()!=data:raise PublicationBlocked('Concurrent candidate modification')
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'status':'published','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'scope':'controlled_local_path_only'}
