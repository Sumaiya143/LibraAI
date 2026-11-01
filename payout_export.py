"""Admin-only export formatting for a bounded, read-only payout audit snapshot."""
import csv
import io

FIELDS = ('record_type','id','payout_id','merchant_id','reviewer_id','amount','currency','previous_status','status','reference','created')

def safe_cell(value):
    """Prevent spreadsheet formula interpretation of untrusted ledger fields."""
    if value is None:
        return ''
    text = str(value)
    if text.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
        return "'" + text
    return text

def render_payout_csv(snapshot):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS, extrasaction='ignore', lineterminator='\r\n')
    writer.writeheader()
    for payout in snapshot['payouts']:
        writer.writerow({key: safe_cell(value) for key, value in dict(payout, record_type='payout').items()})
    for event in snapshot['review_events']:
        item = dict(event, record_type='review_event', status=event.get('new_status', ''))
        writer.writerow({key: safe_cell(value) for key, value in item.items()})
    return ('\ufeff' + output.getvalue()).encode('utf-8')
