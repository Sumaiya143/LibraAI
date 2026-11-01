"""Creator reporting derived only from catalog, verified commerce, reading, and review data."""


def _has_format(value, terms):
    normalized = (value or '').lower().replace('ebook', 'e-book')
    return any(term in normalized for term in terms)


def creator_dashboard_data(conn, creator_id):
    """Return creator-owned catalog metrics and a small evidence-based next-book brief."""
    rows = conn.execute('''
        SELECT b.id,b.title,b.author,b.genre,b.format,b.reads,b.sales,b.rating,
               COALESCE(reading.sessions,0) AS sessions,
               COALESCE(reading.readers,0) AS readers,
               COALESCE(sales.units,0) AS paid_units,
               COALESCE(sales.gross_cents,0) AS gross_cents,
               COALESCE(reviews.review_count,0) AS review_count,
               reviews.average_rating
        FROM royalty_contracts rc
        JOIN books b ON b.id=rc.book_id
        LEFT JOIN (
            SELECT book_id,
                   COUNT(CASE WHEN event_type='session' THEN 1 END) AS sessions,
                   COUNT(DISTINCT CASE WHEN event_type='session' THEN user_id END) AS readers
            FROM qualified_reading_events GROUP BY book_id
        ) reading ON reading.book_id=b.id
        LEFT JOIN (
            SELECT oi.book_id,SUM(oi.quantity) AS units,
                   SUM(COALESCE(oi.line_total_cents,oi.unit_price_cents*oi.quantity)) AS gross_cents
            FROM order_items oi
            JOIN orders o ON o.id=oi.order_id
            JOIN payment_attempts pa ON pa.order_id=o.id AND pa.state='paid'
            WHERE o.status!='Refunded'
            GROUP BY oi.book_id
        ) sales ON sales.book_id=b.id
        LEFT JOIN (
            SELECT book_id,COUNT(*) AS review_count,AVG(rating) AS average_rating
            FROM reviews GROUP BY book_id
        ) reviews ON reviews.book_id=b.id
        WHERE rc.creator_user_id=? AND rc.active=1
        ORDER BY b.title COLLATE NOCASE
    ''', (creator_id,)).fetchall()

    books = []
    formats = {'Audio books': 0, 'eBooks': 0, 'PDFs': 0}
    genre_totals = {}
    for row in rows:
        item = dict(row)
        book_format = item['format'] or ''
        if _has_format(book_format, ('audio', 'audiobook', 'audio book')):
            formats['Audio books'] += 1
        if _has_format(book_format, ('ebook', 'e-book', 'epub')):
            formats['eBooks'] += 1
        if _has_format(book_format, ('pdf',)):
            formats['PDFs'] += 1
        item['display_rating'] = round(item['average_rating'], 1) if item['average_rating'] is not None else None
        item['session_rate'] = round(item['sessions'] / item['readers'], 1) if item['readers'] else 0
        books.append(item)
        genre = (item['genre'] or 'Uncategorized').strip()
        totals = genre_totals.setdefault(genre, {'views': 0, 'sales': 0, 'rating_total': 0.0, 'rated_books': 0})
        totals['views'] += item['sessions']
        totals['sales'] += item['paid_units']
        if item['display_rating'] is not None:
            totals['rating_total'] += item['display_rating']
            totals['rated_books'] += 1

    comments = conn.execute('''
        SELECT r.rating,r.text,r.created,u.name,b.title AS book_title
        FROM reviews r
        JOIN books b ON b.id=r.book_id
        JOIN royalty_contracts rc ON rc.book_id=b.id AND rc.creator_user_id=? AND rc.active=1
        JOIN users u ON u.id=r.user_id
        ORDER BY r.created DESC,r.id DESC LIMIT 8
    ''', (creator_id,)).fetchall()
    comments = [dict(comment) for comment in comments]

    max_sales = max((book['paid_units'] for book in books), default=0)
    max_views = max((book['sessions'] for book in books), default=0)
    for book in books:
        book['sales_width'] = round(book['paid_units'] * 100 / max_sales) if max_sales else 0
        book['views_width'] = round(book['sessions'] * 100 / max_views) if max_views else 0

    total_formats = sum(formats.values())
    pie_colors = ['#087f8c', '#d98936', '#547a54']
    chart_parts = []
    cursor = 0
    for (label, count), color in zip(formats.items(), pie_colors):
        end = cursor + (count * 100 / total_formats if total_formats else 0)
        chart_parts.append(f'{color} {cursor:.2f}% {end:.2f}%')
        cursor = end
    format_chart = 'conic-gradient(' + ','.join(chart_parts) + ')' if total_formats else 'conic-gradient(#dce4e4 0% 100%)'

    next_book = None
    if genre_totals:
        best_genre = max(
            genre_totals,
            key=lambda genre: (
                genre_totals[genre]['sales'],
                genre_totals[genre]['views'],
                genre_totals[genre]['rating_total'] / max(genre_totals[genre]['rated_books'], 1),
            ),
        )
        totals = genre_totals[best_genre]
        average_rating = round(totals['rating_total'] / totals['rated_books'], 1) if totals['rated_books'] else None
        signals = []
        if totals['sales']:
            signals.append(f'{totals["sales"]} paid copies')
        if totals['views']:
            signals.append(f'{totals["views"]} qualified reading sessions')
        if average_rating is not None:
            signals.append(f'{average_rating}/5 average reader rating')
        next_book = {
            'genre': best_genre,
            'signals': ', '.join(signals) if signals else 'No reader activity recorded yet',
            'recommendation': (
                f'Consider a new {best_genre} title. Use reader comments below to choose its topic, '
                'then compare its first 30 days of paid sales and qualified reads with this catalog.'
            ),
        }

    return {
        'books': books,
        'formats': formats,
        'format_count': total_formats,
        'total_titles': len(books),
        'total_sales': sum(book['paid_units'] for book in books),
        'total_gross_cents': sum(book['gross_cents'] for book in books),
        'total_views': sum(book['sessions'] for book in books),
        'unique_readers': sum(book['readers'] for book in books),
        'review_count': sum(book['review_count'] for book in books),
        'comments': comments,
        'format_chart': format_chart,
        'next_book': next_book,
        'notes_tracking': False,
        'lectures_tracking': False,
    }
