import json
import uuid
import boto3
from botocore.exceptions import ClientError
from http_utils import create_response

table = boto3.resource('dynamodb').Table('users')

def get(event, context):
    user_ids = event['queryStringParameters'].get('id').split(',')
    keys = [{'id': user_id} for user_id in user_ids]
    response = table.batch_get_item(
        RequestItems={
            'Items': {
                'Keys': keys
            }
        }
    )
    items = response.get('Responses', {}).get('Items', [])
    return create_response(200, {'data': items})

def post(event, context):
    data = json.loads(event['body'])
    item = {
        'id': uuid.uuid4().hex,
        'name': data.get('name', ''),
        'phone': data.get('phone', ''),
        'venmo_handle': data.get('venmo_handle', '')
    }
    table.put_item(Item=item)
    return create_response(201, {'message': 'Item created', 'data': item})

def get_by_id(event, context):
    id = event['pathParameters']['user_id']
    try:
        response = table.get_item(Key={'id': id})
    except ClientError as e:
        return create_response(500, {'message': str(e)})
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    else:
        return create_response(404, {'message': 'Item not found'})

def update_by_id(event, context):
    id = event['pathParameters']['user_id']
    data = json.loads(event['body'])
    table.update_item(
        Key={'id': id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': data}
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

def delete_by_id(event, context):
    id = event['pathParameters']['user_id']
    table.delete_item(Key={'id': id})
    return create_response(204, {'message': 'Item deleted'})
