import os
import json
import requests
from pymongo import MongoClient
from bs4 import BeautifulSoup


def lambda_handler(event, context):
    try:
        from_page = int(event.get("from_page", 1))
        to_page = int(event.get("to_page", 1)) + 1

        all_alerts = []
        for i in range(from_page, to_page):
            data = scrape_page(i)
            all_alerts.extend(data)
        store_in_mongodb(all_alerts)
        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully processed pages {from_page} to {to_page - 1}')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }


def store_in_mongodb(data):
    mongodb_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongodb_uri)
    db = client['alerts_database']
    collection = db['alerts']

    for alert in data:
        warning_number = alert['details'].get('warning_number')
        if not collection.find_one({'details.warning_number': warning_number}):
            collection.insert_one(alert)
        else:
            print(
                f"Alert with warning number {warning_number} already exists, skipping.")


def scrape_alert_details(alert_url):
    response = requests.get(alert_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        alert_details_div = soup.find(
            'div', class_='cert-body cert-gray-70 m-3')

        details = {}

        if alert_details_div:
            columns = alert_details_div.find('div', class_='row pb-5')
            if columns:
                left_col = columns.find(
                    'div', class_='col-5 col-md-auto cert-gray-50').find_all('p')
                right_col = columns.find(
                    'div', class_='col-7 col-md-9 vertical-line pl-4').find_all('p')

                keys = ["warning_date", "severity_level",
                        "warning_number", "target_sector"]
                for key, value in zip(keys, right_col):
                    details[key] = value.get_text(strip=True)

            paragraph_count = 1
            list_item_count = 1
            for child in alert_details_div.find_all(['p', 'li', 'strong']):
                if child.name == 'p' and child.find('a'):
                    link_text = child.get_text(
                        strip=True).split('click')[0].strip()
                    details[f"link_{paragraph_count}"] = child.find(
                        'a').get('href', '')
                    paragraph_count += 1
                elif child.name == 'li':
                    details[f"i_{list_item_count}"] = child.get_text(
                        strip=True)
                    list_item_count += 1
                elif child.name == 'p':
                    details[f"p_{paragraph_count}"] = child.get_text(
                        strip=True)
                    paragraph_count += 1
                elif child.name == 'strong':
                    strong_text = child.get_text(strip=True)
                    if strong_text:
                        details[f"strong_{paragraph_count}"] = strong_text
                        paragraph_count += 1

        return details
    else:
        return f"Failed to retrieve alert details. Status code: {response.status_code}"


def scrape_page(page_number):
    url = f"https://cert.gov.sa/en/security-warnings/?page={page_number}"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        alerts_severity = soup.find_all('div', class_='card-header')
        alerts_title = soup.find_all('p', class_='cert-card-body-warning')
        alert_images = soup.find_all(
            'img', class_=['card-img-top', 'security-alerts-cover-image'])
        alert_cards = soup.find_all(
            'div', class_='card mb-4 light-gray-border')
        alerts_data = []

        for severity, title, image, card in zip(alerts_severity, alerts_title, alert_images, alert_cards):
            alert_url = "https://cert.gov.sa" + card.find('a').get('href')
            alert_details = scrape_alert_details(alert_url)

            alert_info = {
                "title": title.text.strip(),
                "severity": severity.text.strip(),
                "logo": "https://cert.gov.sa" + image.get('src'),
                "alert_url": alert_url,
                "details": alert_details
            }
            alerts_data.append(alert_info)

        return alerts_data
    else:
        return f"Failed to retrieve data from page {page_number}. Status code: {response.status_code}"
