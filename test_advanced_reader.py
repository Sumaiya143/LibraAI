import unittest, ast
from pathlib import Path

# Tests pure policy without requiring Flask to be installed.
module = ast.parse(Path(__file__).with_name('advanced_reader.py').read_text())
fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name=='may_read')
ns={}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'<policy>','exec'),ns)

class PolicyTests(unittest.TestCase):
    def test_public_sample(self): self.assertTrue(ns['may_read']('sample',False))
    def test_licensed_denied_anonymous(self): self.assertFalse(ns['may_read']('licensed',False))
    def test_licensed_denied_unentitled(self): self.assertFalse(ns['may_read']('licensed',True))
    def test_licensed_purchased(self): self.assertTrue(ns['may_read']('licensed',True,purchased=True))
    def test_licensed_borrowed(self): self.assertTrue(ns['may_read']('licensed',True,borrowed=True))
    def test_licensed_admin(self): self.assertTrue(ns['may_read']('licensed',True,is_admin=True))
    def test_unknown_policy_denied(self): self.assertFalse(ns['may_read']('other',True,purchased=True))
if __name__=='__main__':unittest.main()
