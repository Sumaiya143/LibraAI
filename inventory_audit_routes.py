"""Admin stock audit page; preserves the existing app and styling."""
from flask import Blueprint, request, redirect, url_for, abort, flash
from inventory_audit_engine import record_count

inventory_audits = Blueprint('inventory_audits', __name__)

@inventory_audits.route('/admin/stock-audits', methods=['GET', 'POST'])
def stock_audits():
    from app import current_user, db, page
    user = current_user()
    if user is None or user['role'] != 'admin':
        abort(403)
    conn = db()
    try:
        if request.method == 'POST':
            try:
                result = record_count(conn, book_id=int(request.form['book_id']),
                    counted=int(request.form['counted']), actor_id=user['id'],
                    note=request.form.get('note', ''), apply=request.form.get('apply') == 'on')
                conn.commit()
                flash('Stock audit recorded (difference: {}).'.format(result['difference']))
                return redirect(url_for('inventory_audits.stock_audits'))
            except (ValueError, KeyError) as exc:
                conn.rollback()
                flash('Invalid stock audit: {}'.format(exc))
        books = conn.execute('SELECT id,title,stock FROM books ORDER BY title').fetchall()
        audits = conn.execute('''SELECT a.*, b.title FROM stock_audits a
           JOIN books b ON b.id=a.book_id ORDER BY a.id DESC LIMIT 100''').fetchall()
        return page('Inventory audits', '''<h1>Physical inventory audits</h1>
        <div class="card"><form method="post">
        
        <label for="book_id">Book</label><select id="book_id" name="book_id" required>
        {% for b in books %}<option value="{{b.id}}">{{b.title}} (system: {{b.stock}})</option>{% endfor %}</select>
        <label for="counted">Physically counted copies</label>
        <input id="counted" name="counted" type="number" min="0" required>
        <label for="note">Audit note</label><input id="note" name="note" maxlength="1000">
        <label><input type="checkbox" name="apply"> Apply corrected stock to inventory</label>
        <button type="submit">Record count</button></form></div>
        <h2>Recent audits</h2><div class="card" style="overflow-x:auto"><table>
        <thead><tr><th>Book</th><th>Expected</th><th>Counted</th><th>Difference</th><th>Note</th><th>Date</th></tr></thead>
        <tbody>{% for a in audits %}<tr><td>{{a.title}}</td><td>{{a.expected}}</td>
        <td>{{a.counted}}</td><td>{{a.difference}}</td><td>{{a.note}}</td>
        <td>{{a.created_at}}</td></tr>{% endfor %}</tbody></table></div>''',books=books,audits=audits)
    finally:
        conn.close()
