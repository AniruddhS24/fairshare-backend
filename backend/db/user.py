import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('users')


def batch_get_users(user_ids):
    keys = [{'id': user_id} for user_id in user_ids]
    response = table.batch_get_item(
        RequestItems={
            'Items': {
                'Keys': keys
            }
        }
    )
    return response.get('Responses', {}).get('Items', [])


def get_user(user_id):
    try:
        response = table.get_item(Key={'id': user_id})
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
            'body': json.dumps({'message': 'Split not found'})
        }


def create_user(name, phone, venmo_handle):
    user = {
        'id': uuid.uuid4().hex,
        'name': name,
        'phone': phone,
        'venmo_handle': venmo_handle,
    }
    table.put_item(Item=user)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'Split created', 'data': user})
    }


def update_user(user_id, user_data):
    table.update_item(
        Key={'id': user_id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': user_data}
    )
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Split updated', 'data': user_data})
    }


def delete_user(user_id):
    table.delete_item(Key={'id': user_id})
    return {
        'statusCode': 204,
        'body': None
    }
