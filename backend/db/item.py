import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('items')


def get_all_items(receipt_id):
    response = table.query(
        IndexName='itemsByReceiptId',
        KeyConditionExpression=Key('receipt_id').eq(receipt_id)
    )
    items = response['Items']
    return {
        'statusCode': 200,
        'body': json.dumps(items)
    }


def get_item(item_id):
    try:
        response = table.get_item(Key={'id': item_id})
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
            'body': json.dumps({'message': 'Item not found'})
        }


def create_item(name, quantity, price, receipt_id):
    item = {
        'id': uuid.uuid4().hex,
        'name': name,
        'quantity': str(quantity),
        'price': str(price),
        'receipt_id': receipt_id
    }
    table.put_item(Item=item)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'Item created', 'data': item})
    }


def update_item(item_id, item_data):
    table.update_item(
        Key={'id': item_id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': item_data}
    )
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Item updated', 'data': item_data})
    }


def delete_item(item_id):
    table.delete_item(Key={'id': item_id})
    return {
        'statusCode': 204,
        'body': None
    }
