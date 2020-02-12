# -*- coding: utf-8 -*-
"""
Copyright (c) 2020 beyond-blockchain.org.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from flask import Flask


app = Flask(__name__)


from yuu.app import yuu
app.register_blueprint(yuu, url_prefix='/yuu')


app.secret_key = 'Nnj!fvxbbV8*oU3pWyYb'


if __name__ == '__main__':
    app.run(host='0.0.0.0')

# end of run.py
