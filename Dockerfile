FROM alpine:latest

WORKDIR /app

RUN apk update && apk add bash curl python3 py3-pip
RUN pip3 install docker requests

COPY . /app
RUN mkdir /state

ENTRYPOINT ["python", "/app/shim.py"]
