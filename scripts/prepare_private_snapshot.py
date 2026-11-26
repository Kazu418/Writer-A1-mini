"""Prepare a sanitized, non-live publishing snapshot without changing printer files."""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

EXCLUDED_DIRS={'.git','.venv','venv','__pycache__','.pytest_cache','.ruff_cache','.playwright-cli','build','dist','graphify-out'}
TEXT_SUFFIXES={'.py','.json','.jsonl','.md','.txt','.html','.svg','.yml','.yaml','.toml','.sh','.log','.csv','.tsv','.ini','.conf','.mjs'}
SENSITIVE_KEYS=re.compile(r'("(?:api[_-]?key|access[_-]?code|password|secret|token|authorization|cookie|refresh_token|access_token)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
URL=re.compile(r'https?://[^\s"\'<>\\]+')
NETWORK_GUARD='''# Historical printer transport: enabled only on the owner machine.
import os as _writer_owner_os
if _writer_owner_os.environ.get("WRITER_A1_MINI_OWNER_CONTROL") != "1":
    raise RuntimeError("Owner-only hardware control. Friends use scripts/prepare_handoff.py; see docs/OWNER_OPERATIONS.md")
'''

def excluded(path):
    return any(p in EXCLUDED_DIRS or p.endswith('.egg-info') for p in path.parts) or path.name=='.DS_Store' or path.suffix in {'.pyc','.pyo','.pkl'} or path.name.startswith('.env') or path.suffix in {'.key','.pem'}

def known_secrets():
    values={v for k,v in os.environ.items() if re.search(r'(API_KEY|ACCESS_CODE|PASSWORD|SECRET|TOKEN)$',k) and len(v)>=8}
    config=Path.home()/'Library/Application Support/BambuStudio/BambuStudio.conf'
    if config.exists():
        data=json.loads(config.read_text())
        for key in ('access_code','user_access_code'):
            values.update(v for v in data.get(key,{}).values() if isinstance(v,str) and len(v)>=8)
    return values

def redact(text,secrets,json_fields=True):
    for value in secrets:
        text=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(value)+r'(?![A-Za-z0-9_])','<REDACTED>',text)
    if not json_fields:
        return text
    text=SENSITIVE_KEYS.sub(r'\1"<REDACTED>"',text)
    def clean_url(match):
        value=match.group()
        try:
            url=urlsplit(value)
            pairs=parse_qsl(url.query,keep_blank_values=True)
            changed=False;result=[]
            for key,val in pairs:
                if re.search(r'token|secret|signature|credential|authorization|api.?key|^sig$|^key$|^x-amz-',key,re.I):val='REDACTED';changed=True
                result.append((key,val))
            if changed:return urlunsplit((url.scheme,url.netloc,url.path,urlencode(result),url.fragment))
        except ValueError:pass
        return value
    return URL.sub(clean_url,text)

def clone(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():target.unlink()
    try:
        lib=ctypes.CDLL(None,use_errno=True)
        fn=lib.clonefile;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_int
        if fn(os.fsencode(source),os.fsencode(target),0)==0:return
    except (AttributeError,OSError):pass
    shutil.copyfile(source,target)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True,type=Path)
    parser.add_argument('--materials-root',type=Path)
    parser.add_argument('--source-only',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];dest=args.destination.resolve()
    if dest==root or root in dest.parents:raise SystemExit('Snapshot must be outside live project')
    if not args.source_only and args.materials_root is None:raise SystemExit('--materials-root required')
    dest.mkdir(parents=True,exist_ok=True);materials=args.materials_root.resolve() if args.materials_root else None
    if materials:materials.mkdir(parents=True,exist_ok=True)
    secrets=known_secrets();counts={'raw_files':0,'material_files':0,'redacted_files':0,'guarded_transport_files':0,'excluded_files':0};inventory=[]
    for directory,folders,files in os.walk(root):
        current=Path(directory);relative=current.relative_to(root)
        folders[:]=sorted(p for p in folders if not excluded(relative/p))
        for name in sorted(files):
            source=current/name;rel=source.relative_to(root)
            if source.is_symlink() or excluded(rel):counts['excluded_files']+=1;continue
            material=rel.parts[0] in {'output','tmp'}
            if material and args.source_only:continue
            payload=None;changed=False;guarded=False
            is_text=source.suffix.lower() in TEXT_SUFFIXES or source.name in {'plotnote','PlotNote.command','.gitignore','LICENSE','AGENTS.md'}
            if is_text:
                try:
                    original=source.read_text(encoding='utf-8');text=redact(original,secrets,json_fields=source.suffix.lower() in {'.json','.jsonl','.log','.html','.yaml','.yml','.conf','.ini'})
                    if source.suffix=='.py' and any((isinstance(node,ast.Import) and any(alias.name.startswith('paho.mqtt') for alias in node.names)) or (isinstance(node,ast.ImportFrom) and node.module=='send_air_only') for node in ast.walk(ast.parse(text))):
                        text=NETWORK_GUARD+'\n'+text;guarded=True
                    if text!=original:payload=text.encode();changed=True
                except UnicodeDecodeError:pass
            raw=not material or source.suffix in {'.py','.md'} or (source.suffix=='.json' and source.stat().st_size<2_000_000) or str(rel).startswith('output/exam-note/a4-v4-display-formula-blanks/') or str(rel)=='output/exam-note/a4-v4/a4-both-sides.pdf'
            targets=[]
            if raw:targets.append(dest/rel);counts['raw_files']+=1
            if material and materials:targets.append(materials/rel);counts['material_files']+=1
            for target in targets:
                if payload is not None:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                else:clone(source,target)
                target.chmod(source.stat().st_mode&0o777)
            if changed:counts['redacted_files']+=1
            if guarded:counts['guarded_transport_files']+=1
            if material:inventory.append({'path':rel.as_posix(),'bytes':len(payload) if payload is not None else source.stat().st_size,'sanitized':changed})
    share=dest/'share';share.mkdir(exist_ok=True)
    if not args.source_only:
        (share/'material-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    (share/('source-sync-report.json' if args.source_only else 'snapshot-report.json')).write_text(json.dumps(counts,indent=2)+'\n')
    print(json.dumps(counts),flush=True)
if __name__=='__main__':main()
