from functools import wraps
import jwt
from jwt.exceptions import InvalidTokenError
import os
import json

SECRET_KEY = os.getenv("SECRET_JWT_KEY")
ALGORITHM = "HS256"

def authenticate(handler):
    @wraps(handler)
    def wrapper(event, context):
        token = event.get("headers", {}).get("Authorization")
        if not token:
            return {
                "statusCode": 401,
                'headers': {
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET,PUT,DELETE'
                },
                "body": json.dumps({"error": "Authorization token missing"})
            }
        try:
            token = token.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            event['user'] = payload
            return handler(event, context)
        except InvalidTokenError:
            return {
                "statusCode": 401,
                'headers': {
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET,PUT,DELETE'
                },
                "body": json.dumps({"error": "Invalid token"})
            }
    return wrapper