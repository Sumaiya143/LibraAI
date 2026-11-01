"""Pure input validation shared by request handlers; no Flask dependency."""
import math

class InputValidationError(ValueError):
    pass

def validate_progress(page, percent):
    try:
        page_num = int(page)
        progress = float(percent)
    except (TypeError, ValueError, OverflowError):
        raise InputValidationError('Invalid reading progress') from None
    if not 1 <= page_num <= 100000 or not math.isfinite(progress) or not 0 <= progress <= 100:
        raise InputValidationError('Reading progress is out of range')
    return page_num, progress

def validate_review(rating, body):
    try:
        score = int(rating)
    except (TypeError, ValueError, OverflowError):
        raise InputValidationError('Rating must be between 1 and 5') from None
    if not 1 <= score <= 5:
        raise InputValidationError('Rating must be between 1 and 5')
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 2000:
        raise InputValidationError('Review must contain 1–2000 characters')
    return score, body.strip()
