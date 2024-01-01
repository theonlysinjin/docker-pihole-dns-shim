FROM alpine:latest

WORKDIR /app

RUN apk add --no-cache \
  bash \
  curl \
  python3 \
  py3-pip \
  py3-docker-py \
  py3-requests

COPY . /app
RUN mkdir /state

ENTRYPOINT ["python", "/app/shim.py"]
