FROM continuumio/miniconda3:4.9.2-alpine
MAINTAINER tslmy
COPY . ~/
WORKDIR ~/
RUN conda config --add channels conda-forge && conda install -y --file conda-requirements.txt && pip install -r pip-requirements.txt
EXPOSE 80
CMD gunicorn run:app --worker-class gevent --bind 0.0.0.0:80