FROM python:3.10-alpine

WORKDIR /app

COPY . /app

RUN pip install -e . --no-cache-dir
CMD uvicorn stremio_addons.main:app --host 0.0.0.0 --port 7777