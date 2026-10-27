import os
import boto3
from dotenv import load_dotenv

load_dotenv()
s3 = boto3.client(
    "s3",
    region_name=os.getenv("AWS_DEFAULT_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
bucket = os.getenv("AWS_S3_BUCKET")
r = s3.list_objects_v2(Bucket=bucket)
print(f"OBJETOS EN BUCKET {bucket}:")
for o in sorted(r.get("Contents", []), key=lambda x: x["Key"]):
    print(f"  {o['Key']}  {o['Size']/1024:.1f} KB")
print(f"Total: {len(r.get('Contents', []))} objetos")
