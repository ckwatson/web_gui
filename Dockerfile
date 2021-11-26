FROM python:3.8-slim
MAINTAINER tslmy
COPY . ~/
WORKDIR ~/
RUN pip install -r requirements.txt
EXPOSE 80
CMD gunicorn run:app --worker-class gevent --bind 0.0.0.0:80
