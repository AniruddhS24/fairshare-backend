import json
import uuid
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('receipts')


def get_receipt(receipt_id):
    try:
        response = table.get_item(Key={'id': receipt_id})
    except ClientError as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    if 'Item' in response:
        return {
            'statusCode': 200,
            'body': json.dumps(response['Item'])
        }
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'message': 'Receipt not found'})
        }


def create_receipt(image_url, host_id, items, shared_cost):
    receipt = {
        'id': uuid.uuid4().hex,
        'image_url': image_url,
        'host_id': host_id,
        'items': items,
        'shared_cost': str(shared_cost),
        'num_consumers': 0,
    }
    table.put_item(Item=receipt)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'Receipt created', 'data': receipt})
    }


def update_receipt(receipt_id, receipt_data):
    table.update_item(
        Key={'id': receipt_id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': receipt_data}
    )
    return {
        'statusCode': 200,
        'body': json.dumps(receipt_data)
    }


def delete_receipt(receipt_id):
    table.delete_item(Key={'id': receipt_id})
    return {
        'statusCode': 204,
        'body': None
    }
