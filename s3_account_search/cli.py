#!/usr/bin/env python
import sys
from argparse import ArgumentParser
from typing import Tuple, Optional

import boto3 as boto3
from aws_assume_role_lib import assume_role
from botocore.exceptions import ClientError


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

    # try accessing the bucket without any restrictions
    if not can_access_with_policy(session, bucket, key, role_arn, {}):
        print(f"f{role_arn} cannot access {bucket}", file=sys.stderr)
        exit(1)

    print("Starting search (this can take a while)")
    digits = ""
    # do 12 iterations, so we never have an infinte loop
    for _ in range(0, 12):
        for i in range(0, 10):
            test = f"{digits}{i}"
            policy = get_policy(test)
            if can_access_with_policy(session, bucket, key, role_arn, policy):
                print(f"found: {test}")
                digits = test
                break
    if len(digits) < 12:
        print("Something went wrong, we couldn't  find all 12 digits")
        exit(1)


def get_policy(digits: str):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowResourceAccount",
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": "*",
                "Condition": {
                    "StringLike": {"s3:ResourceAccount": [f"{digits}*"]},
                },
            },
        ],
    }


def can_access_with_policy(
    session: boto3.session.Session,
    bucket: str,
    key: Optional[str],
    role_arn: str,
    policy: dict,
):
    if not policy:
        assumed_role_session = assume_role(session, role_arn)
    else:
        assumed_role_session = assume_role(session, role_arn, Policy=policy)

    s3 = assumed_role_session.client("s3")
    if key:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "403":
                pass  # try the next thing
            else:
                raise
    try:
        s3.head_bucket(Bucket=bucket)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "403":
            pass  # continue to default return False
        else:
            raise
    return False


def to_s3_args(path: str) -> Tuple[str, Optional[str]]:
    if path.startswith("s3://"):
        path = path[5:]
    assert path, "no bucket name provided"

    parts = path.split("/")
    if len(parts) > 1:
        return parts[0], "/".join(parts[1:])
    # exactly 1 part
    return parts[0], None


if __name__ == "__main__":
    run()
