#!/usr/bin/env python
import sys
import time
from argparse import ArgumentParser
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3 as boto3
from aws_assume_role_lib import assume_role
from botocore.exceptions import ClientError

class AccountEnumerator():
    def __init__(self, session, bucket, key, role_arn):
        self.session = session
        self.bucket = bucket
        self.key = key
        self.role_arn = role_arn
        self.digits = ""
        if not self.can_access_with_policy({}):
            print(f"{role_arn} cannot access {bucket}", file=sys.stderr)
            exit(1)

    def can_access_with_policy(self, policy: dict) -> bool:
        if not policy:
            assumed_role_session = assume_role(self.session, self.role_arn)
        else:
            assumed_role_session = assume_role(self.session, self.role_arn, Policy=policy)

        s3 = assumed_role_session.client("s3")
        if self.key:
            try:
                s3.head_object(Bucket=self.bucket, Key=self.key)
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "403":
                    pass  # try the next thing
                else:
                    raise
        try:
            s3.head_bucket(Bucket=self.bucket)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "403":
                pass  # continue to default return False
            else:
                raise
        return False
    
    def get_account_id(self) -> str:
        print("Starting search (this can take a while)")
        
        # do 12 iterations, so we never have an infinte loop
        for _ in range(0, 12):
            self.digits = self.digits + self.find_next_digit()
            print(f"Found {self.digits}")

        if len(self.digits) < 12:
            print("Something went wrong, we couldn't  find all 12 digits")
            exit(1)
        return self.digits

    def can_access_for_number(self, number):
        policy = self.get_policy(str(number))
        return self.can_access_with_policy(policy)
    
    def find_next_digit(self):
        executor = ThreadPoolExecutor(max_workers=10)
        futures = {executor.submit(self.can_access_for_number, job): job for job in range(10)}
        for future in as_completed(futures):
            if future.result() is True:
                executor.shutdown(wait=False, cancel_futures=True)
                return str(futures[future])

        executor.shutdown(wait=False)

    def get_policy(self, digit: str):
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowResourceAccount",
                    "Effect": "Allow",
                    "Action": "s3:*",
                    "Resource": "*",
                    "Condition": {
                        "StringLike": {"s3:ResourceAccount": [f"{self.digits}{digit}*"]},
                    },
                },
            ],
        }


def to_s3_args(path: str) -> Tuple[str, Optional[str]]:
    if path.startswith("s3://"):
        path = path[5:]
    assert path, "no bucket name provided"

    parts = path.split("/")
    if len(parts) > 1:
        return parts[0], "/".join(parts[1:])
    # exactly 1 part
    return parts[0], None

def run():
    parser = ArgumentParser()
    parser.add_argument("--profile", help="Source Profile")
    parser.add_argument(
        "role_arn",
        help="ARN of the role to assume. This role should have s3:GetObject and/or s3:ListBucket permissions",
    )
    parser.add_argument("path", help="s3 bucket or bucket/path to test with")

    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile)
    bucket, key = to_s3_args(args.path)
    role_arn = args.role_arn
    start = time.monotonic()
    enumerator = AccountEnumerator(session, bucket, key, role_arn)
    enumerator.get_account_id()
    elapsed = time.monotonic() - start
    print(f"Completed in {elapsed:.2f}s")

if __name__ == "__main__":
    run()
