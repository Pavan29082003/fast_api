import boto3
# from dotenv import load_dotenv
# from src.settings import settings

# load_dotenv()

# dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
#     aws_access_key_id=settings.aws_access_key,
#     aws_secret_access_key=settings.aws_secret_key
# )  
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')  

def create_users_table():
    table = dynamodb.create_table(
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

# CredentialsTable
def create_credentials_table():
    table = dynamodb.create_table(
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

# RolesTable
def create_roles_table():
    table = dynamodb.create_table(
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

# NotesTable
def create_notes_table():
    table = dynamodb.create_table(
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

# UserAuditTable
def create_user_audit_table():
    table = dynamodb.create_table(
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

# RatingTable
def create_rating_table():
    table = dynamodb.create_table(
        TableName="RatingTable",
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH'  # Partition key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'  # String type for user_id
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
