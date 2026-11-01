"""Fail-closed buyer release gate. Offline checks never certify live production."""
import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(command, timeout=180):
    try:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
        return {'passed':p.returncode == 0, 'exit_code':p.returncode,
                'output':(p.stdout+'\n'+p.stderr)[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'passed':False,'error':str(exc)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',default='commercial_release_evidence.json')
    parser.add_argument('--payment-evidence',help='Path to independent payment sandbox evidence JSON')
    parser.add_argument('--deployment-evidence',help='Path to HTTPS/staging deployment evidence JSON')
    parser.add_argument('--security-evidence',help='Path to independent security review evidence JSON')
    args=parser.parse_args()
    checks={
        'unit_tests':run([sys.executable,'-m','unittest','discover','-q']),
        'source_compilation':run([sys.executable,'-B','-c',
            "import ast,pathlib; [ast.parse(p.read_text(encoding='utf-8'),filename=str(p)) for p in pathlib.Path('.').glob('*.py')]" ]),
        'buyer_package_preflight':run([sys.executable,'-B','buyer_preflight.py']),
        'flask_runtime_acceptance':run([sys.executable,'-B','buyer_acceptance.py']),
    }
    for name,path in [('payment_sandbox',args.payment_evidence),('https_deployment',args.deployment_evidence),('independent_security_review',args.security_evidence)]:
        # User-provided evidence is flagged for human review; its mere existence cannot pass a certification gate.
        checks[name]={'passed':False,'status':'requires independent human validation',
                      'evidence_supplied':bool(path and Path(path).is_file())}
    outcome={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'release_certified':all(x['passed'] for x in checks.values()),
             'checks':checks,
             'note':'Automated evidence alone cannot establish 100% production verification. External checks require validated merchant, deployed site and independent audit.'}
    dest=Path(args.evidence)
    dest.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'release_certified':outcome['release_certified'],
                      'checks':{k:v['passed'] for k,v in checks.items()},'evidence':str(dest)},indent=2))
    return 0 if outcome['release_certified'] else 1

if __name__=='__main__':
    raise SystemExit(main())
