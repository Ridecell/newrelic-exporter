FROM python:3.11.4-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app
RUN pip install --no-cache-dir -r requirements.txt

COPY newrelic_exporter.py /usr/src/app

EXPOSE 9126
ENTRYPOINT [ "python", "-u", "./newrelic_exporter.py" ]