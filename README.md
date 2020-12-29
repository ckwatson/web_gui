CKWatson Online
===============

A Chemical Kinetics Simulator Game as a webapp, written in Python.

![Screenshot](http://i.imgur.com/UVizS1S.png)

## Installation

Assuming you have `conda` installed:

```shell
conda create -n ckw --file conda-requirements.txt
conda activate ckw
pip install -r pip-requirements.txt
```

## Setup

### The complete method
Make sure you are in the correct conda env:

```shell
conda activate ckw
```

In one terminal, do:

```shell
redis-server
```

Then, in another terminal:

```shell
sudo /Library/Frameworks/Python.framework/Versions/3.5/bin/gunicorn run:app --worker-class gevent --bind 127.0.0.1:80 --reload --timeout 6000
```

### The short method
_Alternatively_, you can run the boot script directly:

```shell
sudo run.py
```

This uses Flask itself to host the server, but would lose the ability to send [Server-Sent Events](https://github.com/singingwolfboy/flask-sse).

## Deployment (Heroku)

Please use [this Buildpack](https://github.com/dmathieu/heroku-buildpack-submodules#installation) for Auto-Deployment Support on submodules.

## Folder Structure

- `kernel` is where the actual code are stored.
- `puzzles` is the repository of puzzle definitions. Admin can add puzzles there using the `create` page.
- `web` stores the server program for web-based GUI. It translates user inputs into codes that the `kernel` could understand.
- `results` stores the computed results as well as plotted figures generated by the `kernel`. Not really human-readable.
