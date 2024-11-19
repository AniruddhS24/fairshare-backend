import json
import uuid
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from http_utils import create_response, create_error_response
from price_utils import formatPrice
from auth_utils import authenticate

table = boto3.resource('dynamodb').Table('roles')

@authenticate
def post(event, context):
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    item = {
        'id': uuid.uuid4().hex,
        'receipt_id': receipt_id,
        'user_id': user['id'],
        'role': data.get('role', 'unauthorized'),
    }
    table.put_item(Item=item)
    return create_response(201, {'message': 'Item created', 'data': item})

@authenticate
def get_receipt_participants(event, context):
    users_table = boto3.resource('dynamodb').Table('users')
    receipt_id = event['pathParameters']['receipt_id']
    response = table.query(
        KeyConditionExpression=Key('receipt_id').eq(receipt_id)
    )
    items = response['Items']
    hosts = []
    consumers = []
    for item in items:
        user = users_table.get_item(Key={'id': item['user_id']})
        if item['role'] == 'host':
            hosts.append(user['Item'])
        else:
            consumers.append(user['Item'])
    return create_response(200, {'data': {'hosts': hosts, 'consumers': consumers}})

@authenticate
def get(event, context):
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    try:
        response = table.get_item(Key={'receipt_id': receipt_id, 'user_id': user['id']})
    except ClientError as e:
        return create_error_response(500, str(e))
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    return create_error_response(404, 'Item not found')

@authenticate
def update(event, context):
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    update_expression = "SET "
    expression_attribute_values = {}
    if 'role' in data:
        update_expression += "#role = :role, "
        expression_attribute_values[':role'] = data['role']
    update_expression = update_expression.rstrip(", ")
    expression_attribute_names = {
        "#role": "role",
    }
    table.update_item(
        Key={'receipt_id': receipt_id, 'user_id': user['id']},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

@authenticate
def delete_by_id(event, context):
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    table.delete_item(Key={'receipt_id': receipt_id, 'user_id': user['id']})
    return create_response(200, {"message": "Item deleted"})
    