"""Build portable skills and WorkBuddy packages from one canonical skill."""
import argparse, hashlib, json, re, struct, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.2.0'
SKILL = 'editorial-guard-zh'

def skill_files(workbuddy=False):
    files = {p.relative_to(ROOT/'skills'/SKILL).as_posix(): p.read_bytes()
             for p in sorted((ROOT/'skills'/SKILL).rglob('*')) if p.is_file()}
    files['LICENSE'] = (ROOT/'LICENSE').read_bytes()
    if workbuddy:
        files = {n: v for n,v in files.items() if not n.startswith('agents/')}
        text = files['SKILL.md'].decode('utf-8')
        _, front, body = text.split('---', 2)
        front += ('display_name: 中文改稿与交付检查\ndisplay_name_en: Chinese Editing and Delivery Review\n'
                  'description_zh: 润色已有中文草稿并保护原意与结构，宿主自查不等于独立验收。\n'
                  'description_en: Polish Chinese drafts and preserve source meaning; host review is not independent validation.\n'
                  'category: writing\nversion: "'+VERSION+'"\nauthor: Song Luo\n')
        body = re.sub(r'\[([^\]]+)\]\((references/[^)]+)\)', r'\1：@\2', body)
        files['SKILL.md'] = ('---'+front+'---'+body).encode('utf-8')
    return files

def write_zip(destination, files):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name: raise ValueError('Unsafe ZIP entry')
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() or len(archive.namelist())!=len(set(archive.namelist())): raise ValueError('Invalid archive')

def check_avatar(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or struct.unpack('>II',data[16:24])!=(512,512) or len(data)>500_000:
        raise ValueError('Expected 512 x 512 PNG under 500 KB')

def plugin_files(kind):
    folder=ROOT/'platforms/workbuddy'/('editorial-guard-'+kind)
    files={p.relative_to(folder).as_posix():p.read_bytes() for p in sorted(folder.rglob('*')) if p.is_file()}
    meta=json.loads(files['.codebuddy-plugin/plugin.json'])
    ids=[PurePosixPath(a).stem for a in meta['agents']]
    if meta['agentName'] not in ids or meta['defaultInitPrompt']!=meta['quickPrompts'][0]:raise ValueError('Invalid entrypoint')
    if len(meta['tags'])!=3 or len(meta['quickPrompts'])!=3:raise ValueError('Expected three tags and prompts')
    if not 40<=len(re.findall('[\u4e00-\u9fff]',meta['displayDescription']['zh']))<=50:raise ValueError('Description length')
    for agent in meta['agents']:
        text=files[agent.removeprefix('./')].decode('utf-8')
        if '\ntools:' in text or '\nname: '+PurePosixPath(agent).stem+'\n' not in text:raise ValueError('Invalid agent')
    avatar_names=[PurePosixPath(meta['avatar']).name]
    if kind=='team':
        members=meta['members'];team=meta['teamInfo']
        if {x['id'] for x in members}!=set(ids) or set(team['memberAgents'])!=set(ids)-{team['leadAgent']}:raise ValueError('Team roles differ')
        if sum(x['role']=='lead' for x in members)!=1 or meta['agentName']!=team['leadAgent']:raise ValueError('Invalid team lead')
        if files['settings.json']!=files['setting.json'] or json.loads(files['settings.json'])['agent']!=team['leadAgent']:raise ValueError('Settings differ')
        avatar_names += [PurePosixPath(x['avatar']).name for x in members]
    for name in avatar_names:
        data=(ROOT/'platforms/workbuddy/avatars'/name).read_bytes();check_avatar(data);files['avatars/'+name]=data
    files.update({'skills/'+SKILL+'/'+name:data for name,data in skill_files(True).items()})
    files['LICENSE']=(ROOT/'LICENSE').read_bytes()
    for path in meta['skills']:
        if path.removeprefix('./')+'/SKILL.md' not in files:raise ValueError('Missing embedded skill')
    return {folder.name+'/'+name:data for name,data in files.items()}

def build(output):
    out=Path(output).resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('Use output outside source repository')
    if out.exists() and any(out.iterdir()):raise ValueError('Output must be empty')
    out.mkdir(parents=True,exist_ok=True)
    for suffix,files in [
        ('editorial-guard-zh', {SKILL+'/'+n:v for n,v in skill_files().items()}),
        ('editorial-guard-zh-portable-flat',skill_files()),
        ('editorial-guard-workbuddy-skill',skill_files(True)),
        ('editorial-guard-workbuddy-expert',plugin_files('expert')),
        ('editorial-guard-workbuddy-team',plugin_files('team'))]:
        write_zip(out/(suffix+'-v'+VERSION+'.zip'),files)
    avatar=(ROOT/'platforms/workbuddy/avatars/skill.png').read_bytes();check_avatar(avatar)
    (out/'editorial-guard-skill-avatar.png').write_bytes(avatar)
    report={'version':VERSION,'local_package_checks':'pass','platform_import_tested':False,
            'portable_flat_contract':'SKILL.md at ZIP root; no platform-specific manifest asserted',
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'platform-package-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(build(parser.parse_args().output),indent=2))
