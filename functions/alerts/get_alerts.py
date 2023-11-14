import os
import json
from pymongo import MongoClient
from bson import json_util
from urllib.parse import urlencode


def lambda_handler(event, context):
    page = 1
    limit = 10

    query_params = event.get('queryStringParameters', {})
    if query_params:
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 10))

    if page < 1 or limit < 1:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'error', 'message': 'Page and limit must be positive integers'})
        }

    try:
        alerts, total_alerts = get_alerts(page, limit)
        next_page_url = None

        total_pages = (total_alerts + limit - 1) // limit

        if page < total_pages:
            next_page_params = urlencode({'page': page + 1, 'limit': limit})
            next_page_url = "https://1tozt5y6hl.execute-api.us-east-1.amazonaws.com/default/get_alerts?" + next_page_params

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'success',
                'message': 'Alerts retrieved successfully',
                'total_alerts': total_alerts,
                'alerts': alerts,
                'next_page': next_page_url
            }, default=json_util.default)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'error', 'message': str(e)})
        }


def get_alerts(page, limit):
    try:
        mongodb_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()

        db = client['alerts_database']
        collection = db['alerts']

        skip = (page - 1) * limit

        total_alerts = collection.count_documents({})

        alerts = list(collection.find({}).skip(skip).limit(limit))
        return alerts, total_alerts
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")
