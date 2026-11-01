from flask import Blueprint, request, abort, redirect, flash, render_template_string
from catalog_editor import clean_book, save_book, CatalogEditError

catalog_editor_bp=Blueprint('catalog_editor',__name__)

def install_catalog_editor(app, db, current_user, page):
    def authorized():
        user=current_user()
        if not user:
            abort(401)
        if user['role']!='admin':
            abort(403)
        return user

    @catalog_editor_bp.route('/admin/catalog/new',methods=['GET','POST'])
    @catalog_editor_bp.route('/admin/catalog/<int:book_id>/edit',methods=['GET','POST'])
    def edit_catalog(book_id=None):
        user=authorized()
        with db() as conn:
            book=conn.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone() if book_id else None
            if book_id and book is None: abort(404)
            if request.method=='POST':
                try:
                    values=clean_book(request.form)
                    with conn:
                        book_id=save_book(conn,values,user['id'],book_id)
                except CatalogEditError as exc:
                    abort(400,str(exc))
                flash('Catalog metadata saved. No digital content rights were granted.')
                return redirect('/admin/catalog/'+str(book_id)+'/edit')
            data=dict(book) if book else {}
        template='''<h1>{{'Edit' if existing else 'Add'}} catalog book</h1><p class="muted">Metadata only. Uploading metadata does not authorize distribution of copyrighted content.</p><p><a href="/admin">← Back to administration</a></p><form method="post" class="card" style="max-width:720px">{% for name,label in labels %}<label for="field-{{name}}">{{label}}</label>{% if name=='description' %}<textarea id="field-{{name}}" name="{{name}}" maxlength="2000">{{data.get(name,'')}}</textarea>{% else %}<input class="input" id="field-{{name}}" name="{{name}}" value="{{data.get(name,defaults.get(name,''))}}" {% if name in ('title','author','genre','format','stock','year','price') %}required{% endif %} {% if name in ('stock','year') %}type="number" min="{{0 if name=='stock' else 1450}}" max="{{1000000 if name=='stock' else 2200}}"{% endif %} {% if name=='price' %}type="number" min="0" max="100000" step="0.01"{% endif %}>{% endif %}{% endfor %}<button class="btn" type="submit">Save metadata</button></form>'''
        labels=[('title','Title'),('author','Author'),('genre','Genre'),('format','Formats'),('price','Price (catalog display currency)'),('stock','Available stock'),('year','Publication year'),('language','Language'),('isbn','ISBN'),('branch','Library branch'),('shelf','Shelf'),('description','Description')]
        return page('Catalog editor',template,data=data,labels=labels,defaults={'stock':0,'year':2026,'price':'0.00','format':'Print'})
    app.register_blueprint(catalog_editor_bp)
