import boto3
from src.settings import settings
from pymilvus import MilvusClient

class Connectons():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name='ap-south-1',
        aws_access_key_id=settings.aws_access_key,
        aws_secret_access_key=settings.aws_secret_key
    )
    milvus_client = MilvusClient(uri="http://" + settings.ip + ":19530")
    credentials_table = dynamodb.Table('CredentialsTable')
    roles_table = dynamodb.Table('RolesTable')
    notes_table = dynamodb.Table('NotesTable')
    users_table = dynamodb.Table('UsersTable') 
    history_table = dynamodb.Table('HistoryTable')    
    

connections = Connectons()
