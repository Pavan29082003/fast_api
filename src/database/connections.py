import boto3
from src.settings import settings


class Connectons():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name='ap-south-1',
        aws_access_key_id=settings.aws_access_key,
        aws_secret_access_key=settings.aws_secret_key
    )


connections = Connectons()