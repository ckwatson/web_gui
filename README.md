CKWatson Online
===============

A Chemical Kinetics Simulator Game as a webapp, written in Python.

[Screenshot](http://i.imgur.com/UVizS1S.png)

Installation
------------

Assuming you have `conda` installed:

```
conda create -n ckw --file conda-requirements.txt
conda activate ckw
pip install -r pip-requirements.txt
```


Run the server
--------------

### Run locally

#### The complete method
In one terminal, do:

    $ redis-server

Then, in another terminal:

    $ sudo /Library/Frameworks/Python.framework/Versions/3.5/bin/gunicorn run:app --worker-class gevent --bind 127.0.0.1:80 --reload --timeout 6000

#### The short method
_Alternatively_, you can run the boot script directly:

    $ sudo run.py

This uses Flask itself to host the server, but would lose the ability to send [Server-Sent Events](https://github.com/singingwolfboy/flask-sse).

### Run on Heroku 

Please use [this Buildpack](https://github.com/dmathieu/heroku-buildpack-submodules#installation) for Auto-Deployment Support on submodules.

~~Please note that GitHub Auto-Deployment on Heroku does not support `git submodules`, so we have to do it manually.

Heroku does not support `git submodules` unless they are specified with a URL using a `git://` protocol. Therefore, to push a commit to the Heroku server, one has to use this command:

    perl -pi -e 's/url = https/url = git/g' .gitmodules && git push heroku && perl -pi -e 's/url = git/url = https/g' .gitmodules

We have to do the double `perl` call every time we want to push to Heroku, since GitHub needs `https://` protocol for writing access.~~

Folder Structure
----------------

- `kernel` is where the actual code are stored.
- `puzzles` is the repository of puzzle definitions. Admin can add puzzles there using the `create` page.
- `web` stores the server program for web-based GUI. It translates user inputs into codes that the `kernel` could understand.
- `results` stores the computed results as well as plotted figures generated by the `kernel`. Not really human-readable.
