import sqlite3
import unittest
from support_engine import setup,create_ticket,get_ticket,add_message,change_status

class SupportTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)')
        self.conn.executemany('INSERT INTO users(id,name) VALUES(?,?)',[(1,'Alice'),(2,'Bob'),(3,'Admin')])
        setup(self.conn)
    def tearDown(self):self.conn.close()
    def make(self):return create_ticket(self.conn,1,'Payment question','payment','Where is my receipt?')
    def test_create(self):
        ticket=self.make(); self.assertEqual(get_ticket(self.conn,ticket,1)['status'],'open')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM support_messages').fetchone()[0],1)
    def test_private(self):self.assertIsNone(get_ticket(self.conn,self.make(),2))
    def test_admin_access(self):self.assertIsNotNone(get_ticket(self.conn,self.make(),3,True))
    def test_replies_restricted(self):
        with self.assertRaises(PermissionError):add_message(self.conn,self.make(),2,'Intruder')
    def test_owner_reply(self):
        ticket=self.make();add_message(self.conn,ticket,1,'Additional information')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM support_messages').fetchone()[0],2)
    def test_status_admin_only(self):
        with self.assertRaises(PermissionError):change_status(self.conn,self.make(),'closed',False)
    def test_close(self):
        ticket=self.make();change_status(self.conn,ticket,'closed',True)
        with self.assertRaises(ValueError):add_message(self.conn,ticket,1,'Hello')
    def test_invalid_category(self):
        with self.assertRaises(ValueError):create_ticket(self.conn,1,'Valid subject','nonsense','Long enough message')
    def test_invalid_subject(self):
        with self.assertRaises(ValueError):create_ticket(self.conn,1,'Hi','payment','Long enough message')
    def test_invalid_status(self):
        with self.assertRaises(ValueError):change_status(self.conn,self.make(),'deleted',True)
    def test_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):create_ticket(self.conn,99,'Valid subject','payment','Long enough message')

if __name__=='__main__':unittest.main()
