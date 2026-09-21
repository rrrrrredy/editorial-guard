"""Build only allowlisted, approved public material into the static site."""
import argparse,hashlib,html,json,re
from pathlib import Path

def build(root,destination,base_path,commit,release_url=None):
    root=Path(root);out=Path(destination)
    if not re.fullmatch(r'/[A-Za-z0-9/_-]*/',base_path) and base_path!='/':raise ValueError('Invalid base path')
    if not re.fullmatch(r'[0-9a-f]{40}|unpublished',commit):raise ValueError('Invalid build commit')
    if out.exists() and any(out.iterdir()):raise ValueError('Site output must be empty; refusing to mix stale or unrelated files')
    out.mkdir(parents=True,exist_ok=True);(out/'assets').mkdir(exist_ok=True)
    template=(root/'site/template.html').read_text(encoding='utf-8')
    titles={'index':'首页','standards':'任务与标准','datasets':'数据样本','results':'真实结果','install':'安装与复现','license':'许可与引用','404':'页面不存在'}
    downloads='<a href="'+html.escape(release_url,quote=True)+'">下载此版本 Release</a>' if release_url else '此本地构建尚未绑定已发布下载包；正式下载链接在发布验收后提供。'
    for path in (root/'site/pages').glob('*.html'):
        text=template.replace('{{TITLE}}',titles[path.stem]).replace('{{CONTENT}}',path.read_text(encoding='utf-8')).replace('{{BASE}}',base_path).replace('{{VERSION}}','0.1.1').replace('{{DOWNLOADS}}',downloads)
        (out/path.name).write_text(text,encoding='utf-8',newline='\n')
    for name in ('style.css','app.js'):
        (out/'assets'/name).write_text((root/'site/assets'/name).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    source=root/'datasets/public_samples.json'
    samples=json.loads(source.read_text(encoding='utf-8')) if source.exists() else []
    if any(x.get('split')=='locked_test' and not x.get('test_exposure_approved') for x in samples):raise ValueError('Locked data not approved for publication')
    (out/'assets/samples.json').write_text(json.dumps(samples,ensure_ascii=False),encoding='utf-8',newline='\n')
    source=root/'reports/public_summary.json';results=json.loads(source.read_text(encoding='utf-8')) if source.exists() else {'summary':'正式实验尚未运行。'}
    (out/'assets/results.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8',newline='\n')
    (out/'.nojekyll').write_text('',encoding='utf-8',newline='\n')
    manifest={'version':'0.1.1','data_version':'0.1.1','build_commit':commit,'base_path':base_path,'samples':len(samples),'files':{str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8',newline='\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--base-path',default='/editorial-guard/');p.add_argument('--commit',required=True);p.add_argument('--release-url');args=p.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],args.output,args.base_path,args.commit,args.release_url),indent=2))
