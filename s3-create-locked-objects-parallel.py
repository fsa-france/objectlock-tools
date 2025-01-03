#
# Company : Pure Storage 
# Date : Nov 2024
# Author : L. Boschet
#
# Purpose : Create random locked (compliance mode) text objects on a given bucket with objec lock enabled
#
import boto3
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import random
import string
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, EndpointConnectionError
from concurrent.futures import ThreadPoolExecutor, as_completed

def init_s3_client():
    try:
        s3_endpoint = f"http://{os.getenv('AWS_ENDPOINT_URL')}"
        access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_DEFAULT_REGION')

        if not isinstance(s3_endpoint, str):
            raise ValueError("AWS_ENDPOINT_URL is not a string")
        if not isinstance(access_key_id, str):
            raise ValueError("AWS_ACCESS_KEY_ID is not a string")
        if not isinstance(secret_access_key, str):
            raise ValueError("AWS_SECRET_ACCESS_KEY is not a string")

        s3_client = boto3.client(
            's3',
            region_name=region, # Region parameter is not used on FlashBlade
            endpoint_url=s3_endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

        # Test the connection by listing buckets
        s3_client.list_buckets()
        print("\t- S3 connection successful.")
        
        return s3_client

    except (NoCredentialsError, PartialCredentialsError):
        print("Error: AWS credentials are not set or incomplete.")
    except EndpointConnectionError:
        print("Error: Unable to connect to the specified endpoint URL.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Load environment variables form file .env
load_dotenv(verbose=True)

print("Connexion to S3 endpoint...")

#print(f"\t- AWS_ENDPOINT_URL: {os.getenv('AWS_ENDPOINT_URL')}")
#print(f"\t- AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID')}")

# Initialize the S3 client with credentials from .env
s3 = init_s3_client()

def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%Y-%m-%dT%H:%M:%SZ')
        return True
    except ValueError:
        return False

def generate_readable_text(size_kb):
    words = [
        "Lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
        "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
        "magna", "aliqua", "ut", "enim", "ad", "minim", "veniam", "quis", "nostrud",
        "exercitation", "ullamco", "laboris", "nisi", "ut", "aliquip", "ex", "ea",
        "commodo", "consequat", "duis", "aute", "irure", "dolor", "in", "reprehenderit",
        "in", "voluptate", "velit", "esse", "cillum", "dolore", "eu", "fugiat", "nulla",
        "pariatur", "excepteur", "sint", "occaecat", "cupidatat", "non", "proident",
        "sunt", "in", "culpa", "qui", "officia", "deserunt", "mollit", "anim", "id", "est", "laborum"
    ]
    content = ' '.join(random.choices(words, k=size_kb * 200))  # Approximate word length to 5 characters

    return content[:size_kb * 1024]

def create_object(bucket_name, object_key, retention):
    # Create a random text file content with random characters (1KB files)
    #content = ''.join(random.choices(string.ascii_letters + string.digits, k=1024))

    # Generate a random size between 1 KB (smallest) and 1024 KB (largest)
    random_size_kb = random.randint(1, 1024)

    # Call the function with this random size
    content = generate_readable_text(random_size_kb)

    s3.put_object(Bucket=bucket_name, Key=object_key, Body=content, ObjectLockMode='GOVERNANCE', ObjectLockRetainUntilDate=retention)
    print(".", end="", flush=True)

# List all buckets for this user
buckets_response = s3.list_buckets()
buckets = buckets_response['Buckets']

# Check which buckets have Object Lock enabled
buckets_with_object_lock = []
for bucket in buckets:
    try:
        object_lock_config = s3.get_object_lock_configuration(Bucket=bucket['Name'])
        if 'ObjectLockConfiguration' in object_lock_config:
            buckets_with_object_lock.append(bucket['Name'])
    except s3.exceptions.ClientError as e:
        # If the bucket does not have Object Lock enabled, an error is raised
        if e.response['Error']['Code'] != 'ObjectLockConfigurationNotFoundError':
            raise

# Display the list of buckets and those with Object Lock enabled
print("All Existing buckets list:")
if not buckets:
    print("\t- None")
    print("Exiting because no bucket available on the system...")
    exit()
else:
    for bucket in buckets:
        print(f"\t- {bucket['Name']}")

# Display the list of buckets with Object Lock enabled
#print("All buckets with ObjectLock Enabled list:")
#if not buckets_with_object_lock:
#    print("\t- None")
#    print("Exiting because no bucket with ObjectLock found on the system...")
#    exit()
#else:
#    for bucket_name in buckets_with_object_lock:
#        print(f"\t- {bucket_name}")

# Display the list of buckets with Object Lock for selection
print("\nList of buckets to create locked objects:")
if not buckets_with_object_lock:
    print("\tNone")
else:
    for i, bucket_name in enumerate(buckets_with_object_lock):
        print(f"\t {i + 1}. {bucket_name}")

# Prompt the user to select a bucket
bucket_index = int(input("\nEnter the number of the bucket with ObjectLock you want to use: ")) - 1
bucket_name = buckets_with_object_lock[bucket_index]
print(f"Selected bucket: {bucket_name}")

# Ask for retention date for objects
retention = input("Specify rétention date using ISO 8601 format (Example: 2024-12-31T00:00:00Z): ")

while not validate_date(retention):
    print("Invalid Date Format. Please Retry.")
    retention = input("Specify rétention date using ISO 8601 format (Example: 2024-12-31T00:00:00Z): ")

num_objects = input("Enter the number of objects to create: ")
while not num_objects.isdigit():
    print("Please enter a valid number.")
    num_objects = input("Enter the number of objects to create: ")
num_objects = int(num_objects)

prefix = input("Enter object prefix to be used for this serie of locked objects: ")

start_index = input("Enter the initial index to use for the objects: ")
while not start_index.isdigit():
    print("Please enter a valid number.")
    start_index = input("Enter the starting index you want to use o number the objects to be created: ")
start_index = int(start_index)

# Create the objects in parallel
with ThreadPoolExecutor() as executor:
    futures = []
    for i in range(start_index, start_index + num_objects):
        object_key = f"{prefix}{i}"+".txt"
        futures.append(executor.submit(create_object, bucket_name, object_key, retention))
    
    for future in as_completed(futures):
        future.result()

print(f"\n{num_objects} locked objects successfully created with prefix '{prefix}' in bucket '{bucket_name}'.") 