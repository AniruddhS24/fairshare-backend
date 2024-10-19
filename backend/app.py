from ocr import receipt
import boto3
import os
import json
from decimal import Decimal
import db.item
import db.receipt
import db.split
import db.user


def hello_lambda(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Fairshare Backend!')
    }


def receipt_db_lambda(event, context):
    http_method = event['httpMethod']
    receipt_id = event['queryStringParameters'].get('id')
    if http_method == 'GET':
        return db.receipt.get_receipt(receipt_id)
    elif http_method == 'DELETE':
        return db.receipt.delete_receipt(receipt_id)
    else:
        receipt_data = json.loads(event['body'])
        if http_method == 'POST':
            return db.receipt.create_receipt(**receipt_data)
        elif http_method == 'PUT':
            return db.receipt.update_receipt(receipt_id, receipt_data)
        else:
            return {
                'statusCode': 405,
                'body': json.dumps({'message': 'Method not allowed'})
            }


def all_items_db_lambda(event, context):
    receipt_id = event['queryStringParameters']['receipt_id']
    return db.item.get_all_items(receipt_id)


def item_db_lambda(event, context):
    http_method = event['httpMethod']
    item_id = event['queryStringParameters'].get('id')
    if http_method == 'GET':
        return db.item.get_item(item_id)
    elif http_method == 'DELETE':
        return db.item.delete_item(item_id)
    else:
        item_data = json.loads(event['body'])
        if http_method == 'POST':
            return db.item.create_item(**item_data)
        elif http_method == 'PUT':
            return db.item.update_item(item_id, item_data)
        else:
            return {
                'statusCode': 405,
                'body': json.dumps({'message': 'Method not allowed'})
            }


def all_splits_db_lambda(event, context):
    receipt_id = event['queryStringParameters']['receipt_id']
    return db.split.get_all_splits(receipt_id)


def split_db_lambda(event, context):
    http_method = event['httpMethod']
    split_id = event['queryStringParameters'].get('id')
    if http_method == 'GET':
        return db.split.get_split(split_id)
    elif http_method == 'DELETE':
        return db.split.delete_split(split_id)
    else:
        split_data = json.loads(event['body'])
        if http_method == 'POST':
            return db.split.create_split(**split_data)
        elif http_method == 'PUT':
            return db.split.update_split(split_id, split_data)
        else:
            return {
                'statusCode': 405,
                'body': json.dumps({'message': 'Method not allowed'})
            }


def user_db_lambda(event, context):
    http_method = event['httpMethod']
    user_id = event['queryStringParameters'].get('id').split(',')
    if len(user_id) > 1 and http_method == 'GET':
        # Batch get users
        return db.user.batch_get_users(user_id)
    elif http_method == 'GET':
        return db.user.get_user(user_id)
    elif http_method == 'DELETE':
        return db.user.delete_user(user_id)
    else:
        user_data = json.loads(event['body'])
        if http_method == 'POST':
            return db.user.create_user(**user_data)
        elif http_method == 'PUT':
            return db.user.update_user(user_id, user_data)
        else:
            return {
                'statusCode': 405,
                'body': json.dumps({'message': 'Method not allowed'})
            }


def presigned_url_lambda(event, context):
    packet = json.loads(event.get('body'))
    file_name = packet.get('file_name')
    file_type = packet.get('file_type')
    if not file_name or not file_type:
        return {
            'statusCode': 400,
            'body': 'Invalid request. Please provide file_name and file_type in the request body.'
        }
    S3_BUCKET = os.environ.get("BUCKET_NAME")
    s3_client = boto3.client('s3', region_name=os.environ.get("APP_AWS_REGION"),
                             config=boto3.session.Config(signature_version='s3v4'))
    presigned_url = s3_client.generate_presigned_post(
        S3_BUCKET, file_name, ExpiresIn=3600
    )
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        },
        'body': json.dumps({'presigned_url': presigned_url, 'file_url': f'https://{S3_BUCKET}.s3.amazonaws.com/{file_name}'})
    }


def update_receipt_lambda(event, context):
    packet = json.loads(event.get('body'))
    receipt_id = packet.get('receipt_id')
    items = packet.get('items')
    prices = packet.get('prices')
    grand_total = packet.get('grand_total')
    venmo_handle = packet.get('venmo_handle')
    if not receipt_id or not items or not prices or not grand_total:
        return {
            'statusCode': 400,
            'body': 'Invalid request. Please provide receipt_id, items, prices, and grand_total in the request body.'
        }
    dynamodb = boto3.resource(
        'dynamodb', region_name=os.environ.get("APP_AWS_REGION"))
    table = dynamodb.Table('receipts')
    try:
        table.put_item(
            Item={
                '_id': receipt_id,
                'items': items,
                'prices': [Decimal(str(x)) for x in prices],
                'grand_total': Decimal(str(grand_total)),
                'venmo_handle': venmo_handle
            }
        )
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': 'Internal Server Error'
        }
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        },
        'body': json.dumps({'items': items, 'prices': prices, 'grand_total': grand_total, 'venmo_handle': venmo_handle})
    }


def ocr_lambda(event, context):
    packet = json.loads(event.get('body'))
    receipt_id = packet.get('receipt_id')
    venmo_handle = packet.get('venmo_handle')
    dynamodb = boto3.resource(
        'dynamodb', region_name=os.environ.get("APP_AWS_REGION"),)
    table = dynamodb.Table('receipts')
    try:
        response = table.get_item(
            Key={
                '_id': receipt_id
            }
        )
        if 'Item' in response:
            items = response['Item']['items']
            prices = [float(x) for x in response['Item']['prices']]
            grand_total = float(response['Item']['grand_total'])
            venmo_handle = response['Item'].get('venmo_handle', None)
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
                },
                'body': json.dumps({'items': items, 'prices': prices, 'grand_total': grand_total, 'venmo_handle': venmo_handle})
            }
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': 'Internal Server Error'
        }
    textract = boto3.client(
        'textract', region_name=os.environ.get("APP_AWS_REGION"))
    S3_BUCKET = os.environ.get("BUCKET_NAME")
    response = textract.detect_document_text(
        Document={
            'S3Object': {
                'Bucket': S3_BUCKET,
                'Name': f'{receipt_id}.jpeg'
            }
        }
    )

    words = []
    for item in response['Blocks']:
        if item['BlockType'] == 'WORD':
            bounding_box = item['Geometry']['BoundingBox']
            bounding_box_fmt = [
                {'x': bounding_box['Left'],
                 'y': bounding_box['Top']},
                {'x': bounding_box['Left'] + bounding_box['Width'],
                 'y': bounding_box['Top']},
                {'x': bounding_box['Left'] + bounding_box['Width'],
                 'y': bounding_box['Top'] + bounding_box['Height']},
                {'x': bounding_box['Left'],
                 'y': bounding_box['Top'] + bounding_box['Height']}]
            words.append(
                {'text': item['Text'], 'bounding_box': bounding_box_fmt})

    receipt_model = receipt.Receipt()
    items, prices, grand_total = receipt_model.parse(words)

    try:
        table.put_item(
            Item={
                '_id': receipt_id,
                'items': items,
                'prices': [Decimal(str(x)) for x in prices],
                'grand_total': Decimal(str(grand_total)),
                'venmo_handle': venmo_handle
            }
        )
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': 'Internal Server Error'
        }

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        },
        'body': json.dumps({'items': items, 'prices': prices, 'grand_total': grand_total, 'venmo_handle': venmo_handle})
    }
