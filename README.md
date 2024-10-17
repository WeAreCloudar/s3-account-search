# S3 Account Search
This tool lets you find the account id an S3 bucket belongs too.

For this to work you need to have at least one of these permissions:

- Permission to download a known file from the bucket (`s3:getObject`).
- Permission to list the contents of the bucket (`s3:ListBucket`).

Additionally, you will need a role that you can assume with (one of) these permissions on the bucket 
you're examining

Some more background can be found on the [Cloudar Blog](https://cloudar.be/awsblog/finding-the-account-id-of-any-public-s3-bucket/)

## Installation
This package is available on pypi, you can for example use on of these commands (pipx is recommended)
```shell
pipx install s3-account-search
pip install s3-account-search
```

## Usage Examples
```shell
# with a bucket
s3-account-search arn:aws:iam::123456789012:role/s3_read s3://my-bucket

# with an object
s3-account-search arn:aws:iam::123456789012:role/s3_read s3://my-bucket/path/to/object.ext

# You can also leave out the s3://
s3-account-search arn:aws:iam::123456789012:role/s3_read my-bucket

# Or start from a specified source profile
s3-account-search --profile source_profile arn:aws:iam::123456789012:role/s3_read s3://my-bucket
```

## How this works
There is an IAM policy condition `s3:ResourceAccount`, that is meant to be used to give access to S3
in specified (set of) account(s), but also supports wildcards. By constructing the right patterns,
and seeing which  ones will lead to a Deny or an Allow, we can determine the account id by
discovering it one digit at a time.

1. We verify that we can access the object or bucket with the provided role
2. We assume the same role again, but this time add a policy that restricts our access to S3 buckets
   that exist in an account starting with `0`. If our access is allowed we know that the account id
   has to start with `0`. If the request is denied, we try again with `1` as the first digit. We keep
   incrementing until our request is allowed, and we find the first digit
3. We repeat this process for every digit. Using the already discovered digits as a prefix. E.g. if 
   the first digit was `8`, we test account ids starting with `80`, `81`, `82`, etc.

## Development
We use poetry to manage this project

1. Clone this repository
2. Run `poetry install`
3. Activate the virtualenvironment with `poetry shell` (you can also use `poetry run $command`)

### Releasing a new version to pypi
1. Edit pyproject.toml to update the version number
2. Commit the version number bump
3. Run `poetry publish --build`
4. Push to GitHub
5. Create a new release in GitHub


## Possible improvements
- Instead of checking one digit at a time, we could use a binary search-like algorithm. Eg. the
  following condition is equivalent to `s3:ResourceAccount < 500000000000` 
  ```json
  "Condition": {
    "StringLike": {"s3:ResourceAccount": [
      "0*", "1*", "2*", "3*", "4*",
    ]},
  },
   ```
- Similarly, there is a speed improvement possible by checking multiple digits per position in
  parallel (There is a small risk of being rate limited by STS when using this approach)
  
In practice this tool should be fast enough in most cases.
