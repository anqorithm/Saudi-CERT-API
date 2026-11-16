import base64
import csv
import io
import json
import unittest
from unittest.mock import patch

from bson import ObjectId
from openpyxl import load_workbook

from functions.alerts import get_alerts


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.alerts = [
            {'_id': ObjectId(), 'title': 'تنبيه', 'details': {'warning_number': '001'}},
            {'title': '=1+1', 'details': {'description': 'comma, newline\nand "quote"'}},
        ]
        self.database = patch.object(get_alerts, 'get_alerts', return_value=(self.alerts, 21))
        self.fetch = self.database.start()
        self.addCleanup(self.database.stop)

    def invoke(self, params):
        return get_alerts.lambda_handler({'queryStringParameters': params}, None)

    def test_default_response_and_pagination_are_preserved(self):
        response = self.invoke(None)
        body = json.loads(response['body'])
        self.assertEqual(body['total_alerts'], 21)
        self.assertIn('page=2', body['next_page'])
        self.assertNotIn('Content-Disposition', response['headers'])

    def test_next_page_uses_the_request_host(self):
        event = {'queryStringParameters': None,
                 'requestContext': {'domainName': 'api.example.com', 'path': '/default/get_alerts'}}
        body = json.loads(get_alerts.lambda_handler(event, None)['body'])
        self.assertTrue(body['next_page'].startswith('https://api.example.com/default/get_alerts?page=2'))

    def test_json_exports_requested_page_and_language(self):
        response = self.invoke({'format': 'json', 'lang': 'ar', 'page': '2', 'limit': '5'})
        self.fetch.assert_called_once_with(2, 5, 'ar', None)
        body = json.loads(response['body'])
        self.assertEqual(body[0]['_id']['$oid'], str(self.alerts[0]['_id']))
        self.assertEqual(body[0]['title'], 'تنبيه')
        self.assertIn('alerts.json', response['headers']['Content-Disposition'])

    def test_csv_preserves_fields_unicode_and_escapes_formulas(self):
        response = self.invoke({'format': 'csv'})
        self.assertTrue(response['body'].startswith('\ufeff'))
        rows = list(csv.DictReader(io.StringIO(response['body'].lstrip('\ufeff'))))
        self.assertEqual(rows[0]['title'], 'تنبيه')
        self.assertEqual(rows[0]['details.warning_number'], '001')
        self.assertEqual(rows[1]['title'], "'=1+1")
        self.assertEqual(rows[1]['details.description'], self.alerts[1]['details']['description'])

    def test_excel_is_readable_and_formula_values_are_text(self):
        response = self.invoke({'format': 'xlsx'})
        self.assertTrue(response['isBase64Encoded'])
        workbook = load_workbook(io.BytesIO(base64.b64decode(response['body'])))
        sheet = workbook['Alerts']
        columns = [cell.value for cell in sheet[1]]
        title_column = columns.index('title') + 1
        self.assertEqual(sheet.cell(2, title_column).value, 'تنبيه')
        self.assertEqual(sheet.cell(3, title_column).value, '=1+1')
        self.assertEqual(sheet.cell(3, title_column).data_type, 's')
        self.assertEqual(sheet.cell(2, columns.index('details.warning_number') + 1).value, '001')

    def test_empty_exports(self):
        self.fetch.return_value = ([], 0)
        for export_format in ('json', 'csv', 'xlsx'):
            with self.subTest(format=export_format):
                self.assertEqual(self.invoke({'format': export_format})['statusCode'], 200)

    def test_invalid_format_and_pagination_do_not_query_database(self):
        for params in ({'format': 'pdf'}, {'page': 'abc'}, {'limit': '0'}):
            self.assertEqual(self.invoke(params)['statusCode'], 400)
        self.fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class SortTests(unittest.TestCase):
    def setUp(self):
        self.database = patch.object(get_alerts, 'get_alerts', return_value=([], 21))
        self.fetch = self.database.start()
        self.addCleanup(self.database.stop)

    def test_sort_is_passed_through_and_kept_in_next_page(self):
        response = get_alerts.lambda_handler({'queryStringParameters': {'sort': 'warning_date'}}, None)
        self.fetch.assert_called_once_with(1, 10, 'en', 'warning_date')
        self.assertIn('sort=warning_date', json.loads(response['body'])['next_page'])

    def test_unknown_sort_is_rejected(self):
        response = get_alerts.lambda_handler({'queryStringParameters': {'sort': 'title'}}, None)
        self.assertEqual(response['statusCode'], 400)
        self.fetch.assert_not_called()
