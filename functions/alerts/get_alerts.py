import os
import json
import base64
import csv
from io import BytesIO, StringIO
from pymongo import MongoClient
from bson import json_util
from urllib.parse import urlencode


def lambda_handler(event, context):
    page = 1
    limit = 10
    lang = 'en'

    query_params = event.get('queryStringParameters') or {}
    export_format = query_params.get('format')
    if export_format not in (None, 'json', 'csv', 'xlsx'):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'error', 'message': 'Format must be json, csv or xlsx'})
        }
    if query_params:
        try:
            page = int(query_params.get('page', 1))
            limit = int(query_params.get('limit', 10))
        except (TypeError, ValueError):
            page = limit = 0
        lang = query_params.get('lang', 'en')

    if page < 1 or limit < 1:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'error', 'message': 'Page and limit must be positive integers'})
        }

    try:
        alerts, total_alerts = get_alerts(
            page, limit, lang)
        if export_format:
            return export_alerts(alerts, export_format)
        next_page_url = None

        total_pages = (total_alerts + limit - 1) // limit

        if page < total_pages:
            next_page_params = urlencode(
                {'page': page + 1, 'limit': limit, 'lang': lang})
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


def export_alerts(alerts, export_format):
    headers = {'Content-Disposition': f'attachment; filename="alerts.{export_format}"'}
    if export_format == 'json':
        headers['Content-Type'] = 'application/json'
        return {'statusCode': 200, 'headers': headers,
                'body': json.dumps(alerts, default=json_util.default, ensure_ascii=False)}

    def flatten(document, prefix=''):
        row = {}
        for key, value in document.items():
            name = f'{prefix}.{key}' if prefix else key
            if isinstance(value, dict):
                row.update(flatten(value, name))
            elif isinstance(value, (list, tuple)):
                row[name] = json.dumps(value, default=json_util.default, ensure_ascii=False)
            else:
                row[name] = '' if value is None else str(value)
        return row

    rows = [flatten(alert) for alert in alerts]
    columns = list(dict.fromkeys(key for row in rows for key in row))
    if export_format == 'csv':
        output = StringIO(newline='')
        output.write('\ufeff')  # Excel recognizes UTF-8 Arabic with a BOM.
        writer = csv.writer(output)
        for values in [columns] + [[row.get(column, '') for column in columns] for row in rows]:
            writer.writerow(["'" + value if value.lstrip().startswith(('=', '+', '-', '@'))
                             or value.startswith(('\t', '\r', '\n')) else value for value in values])
        headers['Content-Type'] = 'text/csv; charset=utf-8'
        return {'statusCode': 200, 'headers': headers, 'body': output.getvalue()}

    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Alerts')
    for values in [columns] + [[row.get(column, '') for column in columns] for row in rows]:
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=value)
            cell.data_type = 's'
            cells.append(cell)
        sheet.append(cells)
    output = BytesIO()
    workbook.save(output)
    headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return {'statusCode': 200, 'headers': headers, 'isBase64Encoded': True,
            'body': base64.b64encode(output.getvalue()).decode('ascii')}


def get_alerts(page, limit, lang):
    try:
        mongodb_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()

        db = client['alerts_database']
        collection_name = 'alerts_ar' if lang == 'ar' else 'alerts'
        collection = db[collection_name]

        skip = (page - 1) * limit

        total_alerts = collection.count_documents({})

        alerts = list(collection.find({}).skip(skip).limit(limit))
        return alerts, total_alerts
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")
