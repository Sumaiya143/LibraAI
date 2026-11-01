"""Static contract checks; runtime tests require the project's Flask dependencies."""
from pathlib import Path
ROOT=Path(__file__).parent
routes=(ROOT/'ecosystem_routes.py').read_text()
app=(ROOT/'app.py').read_text()
page=(ROOT/'frontend/app/workspace/ecosystem-hub/page.tsx').read_text()
for route in ['/api/ecosystem/health','/api/ecosystem/recommendations','/api/ecosystem/preferences','/api/ecosystem/reading-sessions','/api/ecosystem/knowledge-notes','/api/ecosystem/creator/submissions','/api/ecosystem/analytics/me']:
    assert route in routes, f'missing route: {route}'
for table in ['reading_goals','reading_sessions','knowledge_notes','creator_submissions','user_preferences','user_notifications']:
    assert f'CREATE TABLE IF NOT EXISTS {table}' in routes, f'missing table: {table}'
assert 'install_ecosystem(app, db, current_user)' in app
assert '/backend/api/ecosystem/recommendations' in page
assert '/backend/api/ecosystem/knowledge-notes' in page
assert 'X-CSRF-Token' in page
print('ecosystem static contract: PASS')
