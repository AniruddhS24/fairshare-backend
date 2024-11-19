import json
import os
import jwt
import boto3
from boto3.dynamodb.conditions import Key
import uuid
from http_utils import create_response, create_error_response

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('users')

SECRET_KEY = os.getenv("SECRET_JWT_KEY")
ALGORITHM = "HS256"

def create_token_lambda(event, context):
    user_data = json.loads(event['body'])
    return create_response(200, {"token": create_token(user_data.get("name"), user_data.get("phone"))})

def get_user_lambda(event, context):
    token = event.get("headers", {}).get("Authorization")
    if not token:
        return create_error_response(401, "Authorization token missing")
    try:
        token = token.split(" ")[-1] # Bearer token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return create_response(200, {"data": payload})
    except jwt.exceptions.InvalidTokenError:
        return create_response(401, "Invalid token")
    
def create_token(name, phone):
    response = table.query(
        IndexName='usersByPhoneNumber',
        KeyConditionExpression=Key('phone').eq(phone)
    )

    if not response.get("Items"):
        user = {
            'id': uuid.uuid4().hex,
            'name': name,
            'phone': phone,
        }
        table.put_item(Item=user)
    else:
        user = response["Items"][0]
    payload = {
        "id": user["id"],
        "name": user["name"],
        "phone": user["phone"]
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
