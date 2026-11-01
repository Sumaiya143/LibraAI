"""Normalize catalog format availability for a physical/eBook mixed cart."""

class FormatUnavailable(ValueError):
    pass


def available_formats(catalog_value):
    text = str(catalog_value or '').lower().replace('-', '').replace(' ', '')
    result = []
    if 'ebook' in text or 'epub' in text or 'pdf' in text or 'digital' in text:
        result.append('eBook')
    if 'print' in text or 'paperback' in text or 'hardcover' in text:
        result.append('Print')
    return tuple(result)


def select_format(catalog_value, requested):
    options = available_formats(catalog_value)
    if requested not in ('eBook', 'Print') or requested not in options:
        raise FormatUnavailable('This book is not offered in the selected format')
    return requested
