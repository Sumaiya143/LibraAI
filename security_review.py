"""Best-effort local static security checks; not an independent security audit."""
from pathlib import Path
import re, subprocess, sys, json, importlib.util
ROOT = Path(__file__).resolve().parent
SKIP = {'.git', 'node_modules', '.next', '__pycache__', 'venv', '.venv', 'tests'}
SECRET_PATTERNS = [
    (re.compile(r'(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), 'private-key material'),
    (re.compile(r'(?i)(?:api[_-]?key|secret[_-]?key|client[_-]?secret|password)\s*[:=]\s*[\'\"][^\'\"]{12,}[\'\"]'), 'possible hard-coded credential'),
]

def main():
    findings=[]; scanned=0
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.name.startswith('test_') or any(part in SKIP for part in p.parts): continue
        if p.name in {'.env', '.env.production'}:
            findings.append({'file':str(p.relative_to(ROOT)), 'issue':'real environment file present in working tree'}); continue
        if p.suffix.lower() not in {'.py','.js','.mjs','.ts','.tsx','.json','.yml','.yaml','.sh','.bat','.html'}: continue
        try: data=p.read_text(encoding='utf-8', errors='ignore')
        except OSError: continue
        scanned+=1
        for regex, label in SECRET_PATTERNS:
            if regex.search(data): findings.append({'file':str(p.relative_to(ROOT)), 'issue':label})
    scanners={}
    for tool, module, args in [('bandit','bandit',[sys.executable,'-m','bandit','-q','-r',str(ROOT),'-x','tests,node_modules,.next,venv,.venv']), ('pip-audit','pip_audit',[sys.executable,'-m','pip_audit','-r',str(ROOT/'requirements.txt')])]:
        if importlib.util.find_spec(module) is None:
            scanners[tool]={'available':False,'note':'Install the scanner and rerun for dependency/code analysis.'}
            continue
        try:
            proc=subprocess.run(args, capture_output=True, text=True, timeout=90)
            scanners[tool]={'available':True,'exit_code':proc.returncode,'output_excerpt':(proc.stdout+proc.stderr)[-2500:]}
        except subprocess.TimeoutExpired: scanners[tool]={'available':True,'timed_out':True,'note':'Scanner timed out; rerun in CI.'}
    result={'files_scanned':scanned,'findings':findings,'scanners':scanners,'scope_note':'Heuristic scan only; false positives/negatives possible. Not a penetration test or independent audit.'}
    print(json.dumps(result,indent=2))
    # Hard-coded-secret heuristic findings are review gates; optional scanners unavailable are not reported as passes.
    return 1 if findings else 0
if __name__=='__main__': raise SystemExit(main())
