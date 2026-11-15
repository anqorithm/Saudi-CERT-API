import json
import unittest
from unittest.mock import patch

from functions.crewler import crawle_alerts_ar, crawle_alerts_en


class CrawlNewAlertsTests(unittest.TestCase):
    def run_crawler(self, module, event, inserted):
        with patch.object(module, 'scrape_page', return_value=[{}]) as scrape, \
                patch.object(module, 'store_in_mongodb', side_effect=inserted):
            response = module.lambda_handler(event, None)
        return response, [c.args[0] for c in scrape.call_args_list]

    def test_stops_at_first_page_without_new_alerts(self):
        for module in (crawle_alerts_en, crawle_alerts_ar):
            response, pages = self.run_crawler(module, {}, [10, 3, 0, 5])
            self.assertEqual(pages, [1, 2, 3])
            self.assertEqual(response['statusCode'], 200)
            self.assertIn('Stored 13 new alerts from pages 1 to 3', json.loads(response['body']))

    def test_respects_max_pages(self):
        _, pages = self.run_crawler(crawle_alerts_en, {'max_pages': 2}, [10, 10, 10])
        self.assertEqual(pages, [1, 2])

    def test_explicit_page_range_is_unchanged(self):
        _, pages = self.run_crawler(crawle_alerts_en, {'from_page': 2, 'to_page': 4}, [0])
        self.assertEqual(pages, [2, 3, 4])

    def test_failed_page_returns_error(self):
        with patch.object(crawle_alerts_en, 'scrape_page', return_value='Failed to retrieve data'):
            response = crawle_alerts_en.lambda_handler({}, None)
        self.assertEqual(response['statusCode'], 500)


if __name__ == '__main__':
    unittest.main()
