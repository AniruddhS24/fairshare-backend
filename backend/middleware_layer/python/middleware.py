from functools import wraps
import jwt
from jwt.exceptions import InvalidTokenError
import os
import json

SECRET_KEY = os.getenv("SECRET_JWT_KEY")
ALGORITHM = "HS256"

def jwt_authorization(handler):
    @wraps(handler)
    def wrapper(event, context):
        token = event.get("headers", {}).get("Authorization")
        if not token:
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Authorization token missing"})
            }
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return handler(event, context, payload)
        except InvalidTokenError:
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Invalid token"})
            }
    return wrapper