"""Dependency-free coverage for bounded authenticated CSV export wiring."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class FulfillmentCSVRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.functions = {n.name:n for n in cls.tree.body if isinstance(n, ast.FunctionDef)}

    def test_route_and_auth_decorators(self):
        node = self.functions['admin_fulfillment_export']
        self.assertEqual(len(node.decorator_list), 2)
        self.assertIn("'/admin/fulfillment/export.csv'", ast.unparse(node.decorator_list[0]))
        self.assertEqual(ast.unparse(node.decorator_list[1]), 'login_required')
        self.assertIn("current_user()['role'] != 'admin'", ast.get_source_segment(self.source, node))

    def test_csv_export_is_bounded_and_no_store(self):
        node = self.functions['admin_fulfillment_export']
        body = ast.get_source_segment(self.source, node)
        self.assertIn('_fulfillment_page_args(request.args)', body)
        self.assertIn('dashboard_data(c, limit, offset, exceptions_only)', body)
        self.assertIn('write_csv_report', body)
        self.assertIn('no-store, private', body)
        self.assertIn('nosniff', body)
        self.assertNotIn('address', body)

    def test_html_and_csv_share_validation(self):
        self.assertIn('_fulfillment_page_args(request.args)', ast.get_source_segment(self.source, self.functions['admin_fulfillment']))
        self.assertIn('admin_fulfillment_export', ast.get_source_segment(self.source, self.functions['admin_fulfillment']))

    def test_strict_pagination_parser(self):
        node = self.functions['_fulfillment_page_args']
        module = ast.Module(body=[node], type_ignores=[])
        node.decorator_list=[]
        scope={}
        exec(compile(module, '<pagination>', 'exec'), scope)
        parse=scope['_fulfillment_page_args']
        self.assertEqual(parse({}), (50,0,False))
        self.assertEqual(parse({'limit':'100','offset':'5','exceptions':'1'}), (100,5,True))
        for data in ({'limit':'101'}, {'limit':'0'}, {'offset':'-1'}, {'offset':'1000001'}, {'exceptions':'yes'}, {'limit':'abc'}):
            with self.subTest(data=data), self.assertRaises(ValueError): parse(data)

if __name__ == '__main__': unittest.main()
