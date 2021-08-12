# distroless is debian based and has python 3.7.3
FROM python:3.7-slim-buster AS build
ARG POETRY_VERSION=1.1.7
#ARG POETRY_HASH=d9ece46b4874e93e1464025891d14c83d75420feec8621a680be14376e77198b
SHELL ["/bin/bash", "-o", "pipefail", "-o", "errexit", "-o", "nounset", "-c"]
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes wget && \
    wget -O - https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python - && \
    python -m venv /venv && \
    /venv/bin/pip install --upgrade pip

# Build the virtualenv as a separate step: Only re-execute this step when requirements change
FROM build as build-venv
ADD . /app
WORKDIR /app
RUN /root/.local/bin/poetry export | /venv/bin/pip install -r /dev/stdin && \
    # distroless has /usr/bin/python, and python:3-slim-buster has /usr/local/bin/python
    ln -sf /usr/bin/python /venv/bin/python

# To debug, use `debug` tag, which has busybox to debug issues
#FROM gcr.io/distroless/python3:debug
FROM gcr.io/distroless/python3
COPY --from=build-venv /app /app
COPY --from=build-venv /venv /venv
WORKDIR /app
ENTRYPOINT ["/venv/bin/python", "s3_account_search/cli.py"]
