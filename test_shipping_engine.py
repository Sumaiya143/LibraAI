import sqlite3
import unittest
from shipping_engine import setup, update_shipment, ShippingError

class ShippingTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT,address TEXT);
          CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,state TEXT);
          CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,format TEXT);
          INSERT INTO orders VALUES(1,'Paid — fulfillment pending','Dhaka');
          INSERT INTO orders VALUES(2,'Awaiting payment — sandbox only','Dhaka');
          INSERT INTO orders VALUES(3,'Refunded','Dhaka');
          INSERT INTO orders VALUES(4,'Paid — fulfillment pending','Dhaka');
          INSERT INTO orders VALUES(5,'Paid — fulfillment pending',NULL);
          INSERT INTO payment_attempts VALUES(1,1,'paid');
          INSERT INTO payment_attempts VALUES(2,3,'paid');
          INSERT INTO payment_attempts VALUES(3,4,'paid');
          INSERT INTO payment_attempts VALUES(4,5,'paid');
          INSERT INTO order_items VALUES(1,1,'Print');
          INSERT INTO order_items VALUES(2,2,'Print');
          INSERT INTO order_items VALUES(3,3,'Print');
          INSERT INTO order_items VALUES(4,4,'eBook');
          INSERT INTO order_items VALUES(5,5,'Print');''')
        setup(self.c)
    def tearDown(self): self.c.close()
    def test_happy_path(self):
        self.assertTrue(update_shipment(self.c,1,9,'packing'))
        self.assertTrue(update_shipment(self.c,1,9,'dispatched','Courier','TRACK-1'))
        self.assertTrue(update_shipment(self.c,1,9,'delivered'))
        row=self.c.execute('SELECT * FROM print_shipments WHERE order_id=1').fetchone()
        self.assertEqual((row['state'],row['tracking_number']),('delivered','TRACK-1'))
    def test_idempotent(self):
        update_shipment(self.c,1,9,'packing')
        self.assertFalse(update_shipment(self.c,1,9,'packing'))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM print_shipment_events').fetchone()[0],1)
    def test_dispatch_retry_with_changed_tracking_rejected(self):
        update_shipment(self.c,1,9,'packing')
        update_shipment(self.c,1,9,'dispatched','Courier','TRACK-1')
        with self.assertRaises(ShippingError):
            update_shipment(self.c,1,9,'dispatched','Courier','TRACK-2')
        row=self.c.execute('SELECT tracking_number FROM print_shipments WHERE order_id=1').fetchone()
        self.assertEqual(row['tracking_number'],'TRACK-1')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM print_shipment_events').fetchone()[0],2)

    def test_exact_dispatch_retry_is_idempotent(self):
        update_shipment(self.c,1,9,'packing')
        update_shipment(self.c,1,9,'dispatched','Courier','TRACK-1')
        self.assertFalse(update_shipment(self.c,1,9,'dispatched','Courier','TRACK-1'))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM print_shipment_events').fetchone()[0],2)

    def test_no_unpaid(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,2,9,'packing')
    def test_no_refunded(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,3,9,'packing')
    def test_no_ebook(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,4,9,'packing')
    def test_no_address(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,5,9,'packing')
    def test_no_skip(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,1,9,'delivered')
    def test_no_dispatch_without_tracking(self):
        update_shipment(self.c,1,9,'packing')
        with self.assertRaises(ShippingError): update_shipment(self.c,1,9,'dispatched')
    def test_no_reverse(self):
        update_shipment(self.c,1,9,'packing')
        update_shipment(self.c,1,9,'dispatched','Courier','ABC')
        with self.assertRaises(ShippingError): update_shipment(self.c,1,9,'packing')
    def test_audit_events_in_order(self):
        update_shipment(self.c,1,9,'packing')
        update_shipment(self.c,1,9,'dispatched','Courier','T123')
        update_shipment(self.c,1,9,'delivered')
        states=[r['state'] for r in self.c.execute(
            'SELECT state FROM print_shipment_events WHERE order_id=? ORDER BY id',(1,))]
        self.assertEqual(states,['packing','dispatched','delivered'])

    def test_dispatch_history_keeps_tracking_snapshot(self):
        update_shipment(self.c,1,9,'packing')
        update_shipment(self.c,1,9,'dispatched','Courier','T123')
        update_shipment(self.c,1,9,'delivered')
        rows=self.c.execute('SELECT state,carrier,tracking_number FROM print_shipment_events ORDER BY id').fetchall()
        self.assertEqual((rows[1]['carrier'],rows[1]['tracking_number']),('Courier','T123'))
        self.assertEqual((rows[2]['carrier'],rows[2]['tracking_number']),('Courier','T123'))

    def test_existing_event_table_is_migrated(self):
        self.c.execute('DROP TABLE print_shipment_events')
        self.c.execute('CREATE TABLE print_shipment_events (id INTEGER PRIMARY KEY,order_id INTEGER,actor_id INTEGER,state TEXT,created TEXT)')
        self.c.execute("INSERT INTO print_shipment_events(order_id,actor_id,state,created) VALUES(1,9,'packing','old')")
        setup(self.c)
        columns={row[1] for row in self.c.execute('PRAGMA table_info(print_shipment_events)')}
        self.assertTrue({'carrier','tracking_number'}.issubset(columns))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM print_shipment_events').fetchone()[0],1)

    def test_failed_transition_does_not_create_audit_event(self):
        with self.assertRaises(ShippingError):
            update_shipment(self.c,1,9,'delivered')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM print_shipment_events').fetchone()[0],0)

    def test_invalid_actor(self):
        with self.assertRaises(ShippingError): update_shipment(self.c,1,0,'packing')

if __name__=='__main__': unittest.main()
