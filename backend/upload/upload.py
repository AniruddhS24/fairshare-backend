import os
import json
import uuid
import boto3
from http_utils import create_response

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def presigned_url(event, context):
    file_name = uuid.uuid4().hex
    presigned_url = s3.generate_presigned_post(
        BUCKET_NAME, file_name, ExpiresIn=3600
    )
    return create_response(200, {'presigned_url': presigned_url, 'file_url': f'https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}'})