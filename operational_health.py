"""Read-only operational health checks; no credentials or customer data exposed."""
import os
import sqlite3
from health_core import inspect_database
from flask import Blueprint, jsonify, current_app

health_bp = Blueprint('operational_health', __name__)




@health_bp.get('/health/live')
def live():
    return jsonify(status='alive'), 200


@health_bp.get('/health/ready')
def ready():
    result = inspect_database(current_app.config['LIBRAAI_HEALTH_DB'])
    # Only operational flags, no secrets, usernames, or infrastructure paths.
    return jsonify(status='ready' if result['ok'] else 'not_ready', database=result), (200 if result['ok'] else 503)
