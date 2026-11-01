from pathlib import Path
s=Path(__file__).with_name('ecosystem_routes.py').read_text(encoding='utf-8')
for route in [
    "/api/ecosystem/reading-goals",
    "/api/ecosystem/notifications",
    "/api/ecosystem/notifications/<int:notification_id>/read",
    "/api/admin/ecosystem/creator-submissions",
    "/api/admin/ecosystem/creator-submissions/<int:submission_id>/review",
]:
    assert route in s, f"Missing ecosystem route: {route}"
assert "target_minutes" in s and "target_books" in s
assert "u.get('role')!='admin'" in s
print('extended ecosystem static contract: PASS')
