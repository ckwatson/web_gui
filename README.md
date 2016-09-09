CKWatson Online
===============

A Chemical Kinetics Simulator Game as a webapp, written in Python.

Installation
------------

###Install Python3 from [Official Website][].

Warning: Do not use `brew`, `pyenv` or `virtualenv`, since they will create a non-framework environment of Python, which is required by the `Matplotlib`. I know this pollutes the system environment, but sorry :(

[Official Website]: https://www.python.org/downloads/

####Append binary file directory of Pyhton3 to your PATH variable

This allows auto detection of Python3 binaries.

    $ echo 'export PATH=$PATH:/Library/Frameworks/Python.framework/Versions/3.5/bin' >> ~/.bashrc 

###Install requirements:

    $ pip3 install -r requirements.txt
    $ brew install redis

the second line of which requires [Homebrew](http://brew.sh/). More info about Redis can be found [here](http://redis.io/).


Run the server
--------------
In one terminal, do:

    $ redis-server

Then, in another terminal:

    $ sudo /Library/Frameworks/Python.framework/Versions/3.5/bin/gunicorn run:app --worker-class gevent --bind 127.0.0.1:80 --reload --timeout 6000

_Alternatively_, you can run the boot script directly:

    $ sudo run.py

This uses Flask itself to host the server, but would lose the ability to send [Server-Sent Events](https://github.com/singingwolfboy/flask-sse).

Folder Structure
----------------

- `ckwatson` is where the actual code are stored.
- `Puzzle` is the repository of puzzle definitions. Admin can add puzzles there using the `create` page.
- `results` stores the computed results as well as plotted figures. Not really human-readable.