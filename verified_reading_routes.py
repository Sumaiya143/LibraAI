"""Authenticated reading event ingestion and transparent rankings API."""
from flask import Blueprint, request, jsonify, session, current_app
from verified_reading import setup, record, leaderboard

verified_reading_bp = Blueprint('verified_reading', __name__)

@verified_reading_bp.post('/api/reading-events')
def ingest():
    uid = session.get('uid')
    if not uid:
        return jsonify(error='Sign in required'), 401
    payload = request.get_json(silent=True) or {}
    try:
        book_id = int(payload.get('book_id', 0))
        event_type = payload.get('event_type', 'session')
        if book_id <= 0:
            raise ValueError('Invalid book')
        connection_factory = current_app.config['LIBRAAI_DB_FACTORY']
        with connection_factory() as conn:
            if not conn.execute('SELECT 1 FROM books WHERE id=?', (book_id,)).fetchone():
                return jsonify(error='Book not found'), 404
            accepted = record(conn, int(uid), book_id, event_type)
        return jsonify(accepted=accepted)
    except (ValueError, TypeError):
        return jsonify(error='Invalid reading event'), 400

@verified_reading_bp.get('/api/verified-rankings')
def rankings():
    try:
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 20))
        connection_factory = current_app.config['LIBRAAI_DB_FACTORY']
        with connection_factory() as conn:
            results = leaderboard(conn, days, limit)
        return jsonify(results=results, methodology='Unique authenticated readers ×3, capped sessions ×0.3, unique completions ×5; rolling time window')
    except (ValueError, TypeError):
        return jsonify(error='Invalid ranking filters'), 400

def install(app, connection_factory):
    app.config['LIBRAAI_DB_FACTORY'] = connection_factory
    with connection_factory() as conn:
        setup(conn)
    if 'verified_reading' not in app.blueprints:
        app.register_blueprint(verified_reading_bp)
