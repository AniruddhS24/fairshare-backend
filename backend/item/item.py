import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from http_utils import create_response, create_error_response
from price_utils import formatPrice

table = boto3.resource('dynamodb').Table('items')


def get(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    try:
        response = table.query(
            IndexName='itemsByReceiptId',
            KeyConditionExpression=Key('receipt_id').eq(receipt_id)
        )
        items = response['Items']
    except ClientError as e:
        return create_error_response(500, str(e))
    return create_response(200, {'data': items})

def post(event, context):
    receipt_id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    try:
        item = {
            'id': uuid.uuid4().hex,
            'name': data.get('name', ''),
            'quantity': str(int(data.get('quantity', 0))),
            'price': formatPrice(float(data.get('price', 0))),
            'receipt_id': str(receipt_id)
        }
        table.put_item(Item=item)
    except ClientError as e:
        return create_error_response(500, str(e))
    return create_response(201, {'message': 'Item created', 'data': item})

def get_by_id(event, context):
    id = event['pathParameters']['item_id']
    try:
        response = table.get_item(Key={'id': id})
    except ClientError as e:
        return create_error_response(500, str(e))
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    else:
        return create_error_response(404, 'Item not found')

def update_by_id(event, context):
    id = event['pathParameters']['item_id']
    data = json.loads(event['body'])
    update_expression = "SET "
    expression_attribute_values = {}
    if 'name' in data:
        update_expression += "#name = :name, "
        expression_attribute_values[':name'] = data['name']
    if 'price' in data:
        data['price'] = formatPrice(float(data['price']))
        update_expression += "#price = :price, "
        expression_attribute_values[':price'] = data['price']
    if 'quantity' in data:
        data['quantity'] = str(int(data['quantity']))
        update_expression += "#quantity = :quantity, "
        expression_attribute_values[':quantity'] = data['quantity']
    update_expression = update_expression.rstrip(", ")
    expression_attribute_names = {
        "#name": "name",
        "#price": "price",
        "#quantity": "quantity"
    }
    table.update_item(
        Key={'id': id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

def delete_by_id(event, context):
    id = event['pathParameters']['item_id']
    table.delete_item(Key={'id': id})
    return create_response(204, {'message': 'Item deleted'})
