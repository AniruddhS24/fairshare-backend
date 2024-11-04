import json
import uuid
import boto3
from botocore.exceptions import ClientError
from http_utils import create_response
from price_utils import formatPrice

table = boto3.resource('dynamodb').Table('receipts')


def post(event, context):
    data = json.loads(event['body'])
    item = {
        'id': uuid.uuid4().hex,
        'image_url': data.get('image_url', ''),
        'host_id': data.get('host_id', ''),
        'shared_cost': formatPrice(data.get('shared_cost', 0)),
        'grand_total': formatPrice(data.get('grand_total', 0)),
        'num_consumers': data.get('num_consumers', '0'),
    }
    table.put_item(Item=item)
    return create_response(201, {'message': 'Item created', 'data': item})
    

def get_by_id(event, context):
    id = event['pathParameters']['receipt_id']
    try:
        response = table.get_item(Key={'id': id})
    except ClientError as e:
        return create_response(500, {'message': str(e)})
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    else:
        return create_response(404, {'message': 'Item not found'})

def update_by_id(event, context):
    id = event['pathParameters']['receipt_id']
    data = json.loads(event['body'])
    update_expression = "SET "
    expression_attribute_values = {}
    if 'shared_cost' in data:
        data['shared_cost'] = formatPrice(float(data['shared_cost']))
        update_expression += "#shared_cost = :shared_cost, "
        expression_attribute_values[':shared_cost'] = data['shared_cost']
    if 'grand_total' in data:
        data['grand_total'] = formatPrice(float(data['grand_total']))
        update_expression += "#grand_total = :grand_total, "
        expression_attribute_values[':grand_total'] = data['grand_total']
    update_expression = update_expression.rstrip(", ")
    expression_attribute_names = {
        "#shared_cost": "shared_cost",
        "#grand_total": "grand_total",
    }
    table.update_item(
        Key={'id': id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

def delete_by_id(event, context):
    id = event['pathParameters']['receipt_id']
    table.delete_item(Key={'id': id})
    return create_response(204, {'message': 'Item deleted'})
    