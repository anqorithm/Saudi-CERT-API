import os
import json
from pymongo import MongoClient
from bson import json_util, ObjectId


def lambda_handler(event, context):
    try:
        query_params = event.get('queryStringParameters', {})

        if 'id' in query_params:
            alert_id = query_params['id']
            alert = get_alert_by_id(alert_id)
        else:
            alert = get_alert_by_query(query_params)

        if alert:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'alert': alert}, default=json_util.default)
            }
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Alert not found'})
            }
    except KeyError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing search parameters'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def get_alert_by_id(alert_id):
    try:
        mongodb_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client['alerts_database']
        collection = db['alerts']

        object_id = ObjectId(alert_id)
        return collection.find_one({'_id': object_id})
    except Exception as e:
        raise Exception(f"Failed to retrieve alert by ID: {str(e)}")


def get_alert_by_query(query_params):
    try:
        mongodb_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client['alerts_database']
        collection = db['alerts']
        query = {k: v for k, v in query_params.items() if v}
        alerts = collection.find(query)
        return list(alerts)
    except Exception as e:
        raise Exception(f"Failed to retrieve alerts by query: {str(e)}")
