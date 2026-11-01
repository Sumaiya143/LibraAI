from datetime import date, timedelta

def schedule(interval, grade, today=None):
    """Deterministic Leitner-style scheduling; grade 0-2 again, 3-5 success."""
    if grade not in range(6): raise ValueError('Grade must be 0 through 5')
    interval = max(1, int(interval))
    next_interval = 1 if grade < 3 else min(365, max(2, round(interval * (1.5 + (grade - 3) * .5))))
    return next_interval, (today or date.today()) + timedelta(days=next_interval)

