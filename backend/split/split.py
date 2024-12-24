import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from auth_utils import authenticate
from http_utils import create_response, create_error_response

table = boto3.resource('dynamodb').Table('splits')

@authenticate
def get(event, context):
    only_mine = False
    if event['queryStringParameters']:
        only_mine = event['queryStringParameters'].get('only_mine', 'false') == 'true'
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    if only_mine:
        response = table.query(
            IndexName="splitsByUser",
            KeyConditionExpression=Key("receipt_id").eq(receipt_id) & Key("user_id").eq(user['id'])
        )
    else:
        response = table.query(
            KeyConditionExpression=Key('receipt_id').eq(receipt_id)
        )
    items = response['Items']
    return create_response(200, {'data': items})

@authenticate
def post(event, context):
    user = event['user']
    receipt_id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    item = {
        'id': uuid.uuid4().hex,
        'receipt_id': receipt_id,
        'quantity': str(data.get('quantity', 0)),
        'split': str(data.get('split', 'auto')),
        'user_id': user['id'],
        'item_id': data.get('item_id', ''),
    }
    table.put_item(Item=item)
    return create_response(201, {'message': 'Item created', 'data': item})

@authenticate
def get_by_id(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    id = event['pathParameters']['split_id']
    try:
        response = table.get_item(Key={'receipt_id': receipt_id, 'id': id})
    except ClientError as e:
        return create_error_response(500, str(e))
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    return create_error_response(404, "Item not found")

@authenticate
def update_by_id(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    id = event['pathParameters']['split_id']
    data = json.loads(event['body'])
    update_expression = "SET "
    expression_attribute_values = {}
    if 'split' in data:
        data['split'] = str(int(data['split']))
        update_expression += "#split = :split, "
        expression_attribute_values[':split'] = data['split']
    if 'quantity' in data:
        data['quantity'] = str(int(data['quantity']))
        update_expression += "#quantity = :quantity, "
        expression_attribute_values[':quantity'] = data['quantity']
    update_expression = update_expression.rstrip(", ")
    expression_attribute_names = {
        "#split": "split",
        "#quantity": "quantity"
    }
    table.update_item(
        Key={'receipt_id': receipt_id, 'id': id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

@authenticate
def delete_by_id(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    id = event['pathParameters']['split_id']
    table.delete_item(Key={'receipt_id': receipt_id, 'id': id})
    return create_response(200, {"message": "Item deleted"})
    