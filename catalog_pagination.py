"""Strict pagination and filter validation for public catalog responses."""
import math

ALLOWED_SORTS = frozenset({'trending', 'rated', 'new', 'bestseller'})


def parse_catalog_query(args):
    def positive_int(value, name, maximum):
        try:
            n = int(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f'{name} must be an integer')
        if n < 1 or n > maximum:
            raise ValueError(f'{name} must be between 1 and {maximum}')
        return n
    page = positive_int(args.get('page', '1'), 'page', 100000)
    size = positive_int(args.get('page_size', '12'), 'page_size', 48)
    sort = args.get('sort', 'trending')
    genre = args.get('genre', '')
    query = args.get('q', '').strip()
    if sort not in ALLOWED_SORTS:
        raise ValueError('Unsupported sort order')
    if not isinstance(genre, str) or len(genre) > 80:
        raise ValueError('Invalid genre')
    if not isinstance(query, str) or len(query) > 160:
        raise ValueError('Search query too long')
    return page, size, sort, genre, query


def paginate(items, page, size):
    total = len(items)
    start = (page - 1) * size
    return {'items': items[start:start + size], 'page': page,
            'page_size': size, 'total': total,
            'pages': math.ceil(total / size), 'has_more': start + size < total}
