import ast, pathlib, re, unittest
P=pathlib.Path(__file__).parent
class DeploymentChecks(unittest.TestCase):
    def test_source_syntax(self):
        for f in P.glob('*.py'): ast.parse(f.read_text(),filename=str(f))
    def test_no_csrf_bypass_for_ai(self):
        s=(P/'app.py').read_text()
        self.assertNotIn("request.endpoint != 'api_ai'",s)
    def test_production_secret_required(self):
        s=(P/'app.py').read_text()
        self.assertIn('Production SECRET_KEY must be at least 32 characters',s)
        self.assertIn('SESSION_COOKIE_SECURE=',s)

    def test_container_runs_as_non_root_and_has_healthcheck(self):
        dockerfile=(P/'Dockerfile').read_text()
        self.assertRegex(dockerfile, r'(?m)^USER\s+libra\s*$')
        self.assertIn('HEALTHCHECK', dockerfile)
        self.assertIn('requirements-production.txt', dockerfile)

    def test_compose_restricts_host_binding_and_container_privileges(self):
        compose=(P/'compose.yaml').read_text()
        self.assertIn('127.0.0.1:8000:8000', compose)
        self.assertIn('read_only: true', compose)
        self.assertIn('no-new-privileges:true', compose)
        self.assertIn('cap_drop:', compose)
        self.assertIn('      - ALL', compose)
        self.assertIn('pids_limit:', compose)
        self.assertIn('mem_limit:', compose)
        self.assertIn('libraai_data:/data', compose)
        self.assertNotRegex(compose, r'(?m)^\s*-\s*["\']?8000:8000')

    def test_production_dependency_file_includes_wsgi_server(self):
        requirements=(P/'requirements-production.txt').read_text()
        self.assertIn('-r requirements.txt', requirements)
        self.assertRegex(requirements, r'(?m)^gunicorn[<=>]')

    def test_ci_fails_closed_if_payment_route_tests_skip(self):
        verifier=(P/'verify_payment_route_tests.py').read_text()
        workflow=(P/'.github/workflows/buyer-verification.yml').read_text()
        self.assertIn('FLASK_IMPORT_ERROR', verifier)
        self.assertIn('result.skipped', verifier)
        self.assertIn('EXPECTED_TESTS = 5', verifier)
        self.assertIn('python -B verify_payment_route_tests.py', workflow)

    def test_deployment_artifacts(self):
        for name in ('Dockerfile','compose.yaml','backup_db.py','requirements-production.txt'):
            self.assertTrue((P/name).is_file())
if __name__=='__main__': unittest.main()
