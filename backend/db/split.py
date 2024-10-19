import json
import uuid
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('splits')


def get_all_splits(receipt_id):
    response = table.query(
        IndexName='splitsByReceiptId',
        KeyConditionExpression=Key('receipt_id').eq(receipt_id)
    )
    splits = response['Items']
    return {
        'statusCode': 200,
        'body': json.dumps(splits)
    }


def get_split(split_id):
    try:
        response = table.get_item(Key={'id': split_id})
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


def create_split(quantity, split, user_id, item_id, receipt_id):
    split = {
        'id': uuid.uuid4().hex,
        'quantity': quantity,
        'split': split,
        'user_id': user_id,
        'item_id': item_id,
        'receipt_id': receipt_id
    }
    table.put_item(Item=split)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'Split created', 'data': split})
    }


def update_split(split_id, split_data):
    table.update_item(
        Key={'id': split_id},
        UpdateExpression='SET #data = :data',
        ExpressionAttributeNames={'#data': 'data'},
        ExpressionAttributeValues={':data': split_data}
    )
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Split updated', 'data': split_data})
    }


def delete_split(split_id):
    table.delete_item(Key={'id': split_id})
    return {
        'statusCode': 204,
        'body': None
    }
