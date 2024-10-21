import boto3
from src.database.connections import connections

def create_users_table():
    table = connections.dynamodb.create_table(
        TableName='UsersTable',
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH'  
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'  
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("UsersTable created")

def create_credentials_table():
    table = connections.dynamodb.create_table(
        TableName='CredentialsTable',
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH'  
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S' 
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("CredentialsTable created")


def create_roles_table():
    table = connections.dynamodb.create_table(
        TableName='RolesTable',
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH' 
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'  
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("RolesTable created")


def create_notes_table():
    table = connections.dynamodb.create_table(
        TableName='NotesTable',
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH' 
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S' 
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("NotesTable created")


def create_user_audit_table():
    table = connections.dynamodb.create_table(
        TableName="UserAudit",
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH'  
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'  
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("UserAudit Table created")


def create_rating_table():
    table = connections.dynamodb.create_table(
        TableName="RatingTable",
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH' 
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'  
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print("RatingTable created")


# Create the tables
create_users_table()
create_roles_table()
create_credentials_table()
create_notes_table()
create_user_audit_table()
create_rating_table()
