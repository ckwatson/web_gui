FROM 0.7.5-python3.10-bookworm
MAINTAINER tslmy
WORKDIR /app
COPY . .
RUN uv sync
EXPOSE 80
CMD uv run gunicorn run:app --worker-class gevent --bind 0.0.0.0:80
