# -*- coding: utf-8 -*-
from web.main import *

if __name__ == "__main__":
    app.run(host="127.0.0.1",port=int("80"),debug=True,threaded=True)