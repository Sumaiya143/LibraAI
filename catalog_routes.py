"""Admin-only catalog CSV import and export routes."""
from flask import Blueprint, abort, flash, redirect, request, Response
from catalog_management import import_catalog, export_catalog, CatalogValidationError

catalog_bp = Blueprint('catalog_management', __name__)

def install_catalog(app, connect, get_user):
    def require_admin():
        user = get_user()
        if not user or user['role'] != 'admin': abort(403)

    @catalog_bp.get('/admin/catalog/export.csv')
    def download_catalog():
        require_admin()
        conn = connect()
        try: output = export_catalog(conn)
        finally: conn.close()
        return Response(output, mimetype='text/csv; charset=utf-8', headers={
            'Content-Disposition':'attachment; filename="libraai_catalog.csv"',
            'Cache-Control':'private, no-store',
        })

    @catalog_bp.post('/admin/catalog/import')
    def upload_catalog():
        require_admin()
        upload = request.files.get('catalog')
        if not upload: abort(400, 'Select a CSV file')
        content = upload.stream.read(512_001)
        if len(content) > 512_000:
            abort(413, 'Catalog CSV exceeds 500 KB')
        from upload_security import inspect_upload
        accepted, scan_status, scan_message = inspect_upload(upload.filename or 'catalog.csv', content)
        if not accepted:
            abort(503 if scan_status == 'unavailable' else 415 if scan_status == 'invalid' else 400, scan_message)
        conn = connect()
        try:
            count = import_catalog(conn, content)
            flash(f'Imported {count} books successfully.')
        except CatalogValidationError as exc:
            flash(f'Import rejected: {exc}')
        finally: conn.close()
        return redirect('/admin')

    app.register_blueprint(catalog_bp)
