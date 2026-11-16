"""Run the real app locally against an in-memory fake DynamoDB (moto).

Usage: VOTES_PASSWORD=... python docs/proof/run_fake_app.py [port]
Not for production: it only exists to exercise the app without AWS.
"""
import os
import sys

os.environ.setdefault("DDB_AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import boto3
from moto import mock_dynamodb

with mock_dynamodb():
    table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
        TableName="votingapp-restaurants",
        KeySchema=[{"AttributeName": "name", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "name", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    for slug, n in {"outback": 12, "bucadibeppo": 7, "ihop": 19, "chipotle": 4}.items():
        table.put_item(Item={"name": slug, "restaurantcount": n})
    import app as votingapp

    votingapp.app.run(host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
