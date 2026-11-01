import ast, pathlib, unittest
P=pathlib.Path(__file__).parent
class ExtensionChecks(unittest.TestCase):
    def test_module_parses(self):ast.parse((P/'commercial_extensions.py').read_text())
    def test_existing_modules_retained(self):
        s=(P/'app.py').read_text()
        for name in ('extended','research_tools','learning_engine','platform_plus','commercial_extensions'):
            self.assertIn('from '+name+' import',s)
    def test_operations_present(self):
        s=(P/'commercial_extensions.py').read_text()
        for path in ('/api/support','/api/lists','/api/admin/stock/','/api/admin/operations-summary','/api/security/csrf'):
            self.assertIn(path,s)
    def test_sql_parameterization(self):
        s=(P/'commercial_extensions.py').read_text()
        self.assertNotIn('executescript(request',s)
        self.assertIn('BEGIN IMMEDIATE',s)
if __name__=='__main__':unittest.main()
