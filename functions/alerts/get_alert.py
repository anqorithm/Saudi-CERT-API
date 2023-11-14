import os
import json
from pymongo import MongoClient
from bson import json_util, ObjectId


def lambda_handler(event, context):
    try:
        alert_id = event['queryStringParameters']['id']
        alert = get_alert(alert_id)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'alert': alert}, default=json_util.default)
        }
    except KeyError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing alert ID'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def get_alert(alert_id):
    try:
        mongodb_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client['alerts_database']
        collection = db['alerts']

        object_id = ObjectId(alert_id)
        alert = collection.find_one({'_id': object_id})

        if alert:
            return alert
        else:
            raise ValueError(f"No alert found with ID: {alert_id}")
    except Exception as e:
        raise Exception(f"Failed to retrieve alert: {str(e)}")
