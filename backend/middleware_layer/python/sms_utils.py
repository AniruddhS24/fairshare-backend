import boto3
from botocore.exceptions import ClientError
import os


def subscribe_phone_number(phone_number):
    return
    # try:
    #     response = sns_client.subscribe(
    #         TopicArn=SNS_ARN,
    #         Protocol='sms',
    #         Endpoint=phone_number
    #     )
    #     return response['SubscriptionArn']
    # except ClientError as e:
    #     if "SubscriptionAlreadyExists" in str(e):
    #         return "The phone number is already subscribed to this topic."
    #     else:
    #         raise e
    
def send_sms(phone_number, message):
    return
    # sns_client.publish(
    #     PhoneNumber=phone_number,
    #     Message=message
    # )