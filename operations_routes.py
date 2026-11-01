"""Admin-only operations overview, intentionally read-only."""
from flask import Blueprint, abort, jsonify, render_template_string
from operations_dashboard import snapshot

operations_bp = Blueprint('operations', __name__)


def _admin_snapshot():
    from app import current_user, db
    user = current_user()
    if not user:
        abort(401)
    if user['role'] != 'admin':
        abort(403)
    with db() as conn:
        return snapshot(conn)


@operations_bp.get('/api/admin/operations')
def operations_json():
    return jsonify(_admin_snapshot())


@operations_bp.get('/admin/operations')
def operations_page():
    report = _admin_snapshot()
    return render_template_string('''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>LibraAI · Operations</title><style>
    body{font-family:system-ui,sans-serif;background:#f5f7fc;color:#182238;margin:0}
    main{max-width:1050px;margin:auto;padding:32px 20px}h1{margin-bottom:8px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:22px 0}
    .tile{background:white;border:1px solid #e2e7f0;border-radius:14px;padding:20px}
    .tile strong{display:block;font-size:30px;margin-top:8px}.muted{color:#667085}
    .warn{background:#fff4e5;padding:14px;border-radius:12px}li{margin:8px 0}
    a{color:#354ac8}small{color:#667085}
    </style></head><body><main>
    <p><a href="/admin">← Admin</a></p><h1>Operations overview</h1>
    <p class="muted">Read-only operational snapshot. This page never executes payments or refunds.</p>
    {% if not report.ready %}<p class="warn" role="alert">Attention required: schema or financial audit is not clean. Do not assume payments are reconciled.</p>{% endif %}
    {% if report.missing_tables %}<p class="warn">Missing tables: {{ report.missing_tables | join(', ') }}</p>{% endif %}
    <section class="grid">{% for key,value in report.counts.items() %}
    <div class="tile"><span>{{ key.replace('_',' ').title() }}</span><strong>{{ value }}</strong></div>
    {% endfor %}</section>
    <h2>Financial integrity</h2><p>Audit: {{ 'Passed' if report.financial_audit.ok else 'Needs review' }}</p>
    {% if report.financial_audit.total_findings %}<p>{{ report.financial_audit.total_findings }} findings (showing up to 25)</p>{% endif %}
    <ul>{% for finding in report.financial_audit.findings %}
    <li><strong>{{ finding.code }}</strong> — order {{ finding.get('order_id','—') }}: {{ finding.detail }}</li>
    {% endfor %}</ul><small>Generated {{ report.generated_at or 'unavailable' }} · Admin access only</small>
    </main></body></html>''', report=report)
