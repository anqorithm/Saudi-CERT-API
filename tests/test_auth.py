import json
import os
import time
import unittest
from unittest.mock import patch

import jwt

from functions.alerts import get_alert, get_alerts


class AuthTests(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(get_alerts, 'get_alerts', return_value=([], 0)),
                       patch.object(get_alert, 'get_alert_by_query', return_value=[{'title': 'x'}])):
            target.start()
            self.addCleanup(target.stop)

    def invoke(self, handler, headers=None):
        return handler.lambda_handler({'queryStringParameters': {'title': 'x'}, 'headers': headers}, None)

    def test_open_when_no_secret_is_set(self):
        with patch.dict(os.environ, {}, clear=True):
            for handler in (get_alerts, get_alert):
                self.assertEqual(self.invoke(handler)['statusCode'], 200)

    def test_requires_a_valid_token_when_secret_is_set(self):
        good = jwt.encode({'sub': 'client'}, 's3cret', algorithm='HS256')
        expired = jwt.encode({'exp': int(time.time()) - 60}, 's3cret', algorithm='HS256')
        wrong_key = jwt.encode({'sub': 'client'}, 'other', algorithm='HS256')
        with patch.dict(os.environ, {'JWT_SECRET': 's3cret'}):
            for handler in (get_alerts, get_alert):
                self.assertEqual(self.invoke(handler, {'Authorization': f'Bearer {good}'})['statusCode'], 200)
                self.assertEqual(self.invoke(handler, {'authorization': f'bearer {good}'})['statusCode'], 200)
                for headers in (None, {}, {'Authorization': good}, {'Authorization': f'Bearer {expired}'},
                                {'Authorization': f'Bearer {wrong_key}'}, {'Authorization': 'Bearer junk'}):
                    response = self.invoke(handler, headers)
                    self.assertEqual(response['statusCode'], 401, headers)
                    self.assertEqual(json.loads(response['body']), {'error': 'Unauthorized'})
                    self.assertEqual(response['headers']['WWW-Authenticate'], 'Bearer')


if __name__ == '__main__':
    unittest.main()
