import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from http_utils import create_response

table = boto3.resource('dynamodb').Table('splits')

def get(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    response = table.query(
        IndexName='splitsByReceiptId',
        KeyConditionExpression=Key('receipt_id').eq(receipt_id)
    )
    items = response['Items']
    return create_response(200, {'data': items})
    
def post(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    item = {
        'id': uuid.uuid4().hex,
        'quantity': str(data.get('quantity', 0)),
        'split': str(data.get('split', 0)),
        'user_id': data.get('user_id', ''),
        'item_id': data.get('item_id', ''),
        'receipt_id': receipt_id
    }
    table.put_item(Item=item)
    return create_response(201, {'message': 'Item created', 'data': item})

def get_by_id(event, context):
    id = event['pathParameters']['split_id']
    try:
        response = table.get_item(Key={'id': id})
    except ClientError as e:
        return create_response(500, {'message': str(e)})
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    else:
        return create_response(404, {'message': 'Item not found'})

def update_by_id(event, context):
    id = event['pathParameters']['split_id']
    data = json.loads(event['body'])
    table.update_item(
        Key={'id': id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': data}
    )
    return create_response(200, {'message': 'Item updated', 'data': data})
    
def delete_by_id(event, context):
    id = event['pathParameters']['split_id']
    table.delete_item(Key={'id': id})
    return create_response(204, {'message': 'Item deleted'})
    