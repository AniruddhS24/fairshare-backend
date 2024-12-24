import json
import uuid
import boto3
import datetime
import random
import re
from botocore.exceptions import ClientError
from http_utils import create_response, create_error_response
from auth_utils import authenticate
from sms_utils import send_sms, subscribe_phone_number

table = boto3.resource('dynamodb').Table('users')
otp_table = boto3.resource('dynamodb').Table('otp')

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

@authenticate
def get_by_id(event, context):
    user = event['user']
    try:
        response = table.get_item(Key={'id': user['id']})
    except ClientError as e:
        return create_error_response(500, str(e))
    if 'Item' in response:
        return create_response(200, {'data': response['Item']})
    return create_error_response(404, "Item not found")

@authenticate
def update_by_id(event, context):
    # TODO: Refactor this to use the same logic as other updates
    user = event['user']
    data = json.loads(event['body'])
    table.update_item(
        Key={'id': user['id']},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': data}
    )
    return create_response(200, {'message': 'Item updated', 'data': data})

@authenticate
def delete_by_id(event, context):
    user = event['user']
    table.delete_item(Key={'id': user['id']})
    return create_response(200, {"message": "Item deleted"})

def create_otp(event, context):
    data = json.loads(event['body'])
    phone = data.get('phone', '')
    phone = '+1' + re.sub(r'\D', '', phone)
    otp = random.randint(100000, 999999)
    try:
        subscribe_phone_number(phone)
        time_now = datetime.datetime.now()
        otp_table.put_item(
            Item={
                'phone': phone,
                'otp': otp,
                'ttl': int((time_now + datetime.timedelta(minutes=15)).timestamp()),
            }
        )
        send_sms(phone, f"Your OTP is {otp}")
        return create_response(200, {'message': 'OTP created'})
    except Exception as e:
        return create_error_response(500, str(e))

def verify_otp(event, context):
    data = json.loads(event['body'])
    phone = data.get('phone')
    phone = '+1' + re.sub(r'\D', '', phone)
    otp = data.get('otp')
    try:
        response = otp_table.get_item(Key={'phone': phone})
    except ClientError as e:
        return create_error_response(500, str(e))
    if 'Item' in response:
        item = response['Item']
        if item['otp'] == otp:
            return create_response(200, {'message': 'OTP verified'})
    return create_error_response(400, 'OTP not verified')