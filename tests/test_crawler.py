import json
import unittest
from unittest.mock import patch

from functions.crewler import crawle_alerts_ar, crawle_alerts_en


class FakeCollection:
    def __init__(self, numbers=()):
        self.numbers = list(numbers)

    def find_one(self, query):
        return query['details.warning_number'] in self.numbers or None

    def insert_one(self, alert):
        self.numbers.append(alert['details']['warning_number'])


def alerts(*numbers):
    return [{'details': {'warning_number': n}} for n in numbers]


class CrawlNewAlertsTests(unittest.TestCase):
    # Site pages, newest first: 6 and 5 are new, 4 and below are already stored.
    SITE = {1: alerts(6, 5), 2: alerts(4, 3), 3: alerts(2, 1)}

    def crawl(self, module, collection, event, site=None):
        site = site or self.SITE
        with patch.object(module, 'get_collection', return_value=collection), \
                patch.object(module, 'scrape_page', side_effect=lambda p: site[p]) as scrape:
            response = module.lambda_handler(event, None)
        return response, [c.args[0] for c in scrape.call_args_list]

    def test_stops_at_stored_alerts_and_stores_oldest_first(self):
        for module in (crawle_alerts_en, crawle_alerts_ar):
            collection = FakeCollection([4, 3, 2, 1])
            response, pages = self.crawl(module, collection, {})
            self.assertEqual(pages, [1, 2])
            self.assertEqual(collection.numbers[4:], [5, 6])
            self.assertIn('Stored 2 new alerts', json.loads(response['body']))

    def test_failed_page_stores_nothing_so_retry_recovers(self):
        collection = FakeCollection([2, 1])
        broken = {**self.SITE, 2: 'Failed to retrieve data'}
        response, _ = self.crawl(crawle_alerts_en, collection, {}, broken)
        self.assertEqual(response['statusCode'], 500)
        self.assertEqual(collection.numbers, [2, 1])
        self.crawl(crawle_alerts_en, collection, {})
        self.assertEqual(collection.numbers, [2, 1, 3, 4, 5, 6])

    def test_page_cap_errors_without_leaving_a_gap(self):
        collection = FakeCollection([2, 1])
        response, pages = self.crawl(crawle_alerts_en, collection, {'max_pages': 1})
        self.assertEqual((response['statusCode'], pages), (500, [1]))
        self.assertEqual(collection.numbers, [2, 1])

    def test_explicit_page_range_is_unchanged(self):
        collection = FakeCollection()
        _, pages = self.crawl(crawle_alerts_en, collection, {'from_page': 2, 'to_page': 3})
        self.assertEqual(pages, [2, 3])
        self.assertEqual(collection.numbers, [4, 3, 2, 1])


if __name__ == '__main__':
    unittest.main()
