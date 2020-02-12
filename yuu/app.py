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
import base64
import bbc1
import qrcode  as qr
import requests
import time

from bbc1.core import bbclib
from bbc1.lib.app_support_lib import Database
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, session, redirect
from flask import g, url_for
from io import BytesIO
from PIL import Image


# Prior to use this web application, please define a currency using API,
# and put the mint_id here.
MINT_ID = '1f35585c480efc3f924d85029defe1242437b3ef4f42aedabcbec0e4acd2b3af'

# Put the initial amount when signed up
INIT_AMOUNT = '24'

# Put API host name here, plus prefix for URL encoded in QR code.
PREFIX_API = 'http://127.0.0.1:5000'
PREFIX_QR  = 'http://127.0.0.1:5000'

# Put base time (to count transactions) in Unix time here.
BASE_TIME = 0

# Put the number of transactions to show in a list page here.
LIST_COUNT = 10


NAME_OF_DB = 'yuu_db'

yuu_contributions_table_definition = [
    ["timestamp", "INTEGER"],
    ["good_until", "INTEGER"],
    ["name", "TEXT"],
    ["item", "TEXT"],
    ["deleted", "INTEGER"],
]

yuu_needs_table_definition = [
    ["timestamp", "INTEGER"],
    ["good_until", "INTEGER"],
    ["name", "TEXT"],
    ["item", "TEXT"],
    ["deleted", "INTEGER"],
]

IDX_TIMESTAMP  = 0
IDX_GOOD_UNTIL = 1
IDX_NAME       = 2
IDX_ITEM       = 3
IDX_DELETED    = 4


FORMAT_TIME = '%Y-%m-%d %H:%M'
INFTY_TIME = 2**63 - 1


JST = timezone(timedelta(hours=+9), 'JST')
domain_id = bbclib.get_new_id("payment_test_domain", include_timestamp=False)


class Store:

    def __init__(self):
        self.db = Database()
        self.db.setup_db(domain_id, NAME_OF_DB)


    def close(self):
        self.db.close_db(domain_id, NAME_OF_DB)


    def get_contribution_items(self, name):
        rows = self.db.exec_sql(
            domain_id,
            NAME_OF_DB,
            'select item from contributions_table where name=? and ' + \
            'deleted=0 and good_until>=? and timestamp>=? ' + \
            'order by rowid desc',
            name,
            int(time.time()),
            BASE_TIME
        )
        items = []
        for row in rows:
            items.append(row[0])
        return items


    def get_item_list(self, type='contributions', count=None):
        if count is not None:
            s_limit = ' limit {0}'.format(count)
        else:
            s_limit = ''

        rows = self.db.exec_sql(
            domain_id,
            NAME_OF_DB,
            'select * from ' + type + '_table where deleted=0 and ' + \
            'good_until>=? and timestamp>=?' + \
            'order by rowid desc' + s_limit,
            int(time.time()),
            BASE_TIME
        )

        dics = []
        for row in rows:
            dics.append({
                'timestamp': row[IDX_TIMESTAMP],
                'good_until': row[IDX_GOOD_UNTIL],
                'name': row[IDX_NAME],
                'item': row[IDX_ITEM]
            })

        return dics


    def setup(self):
        self.db.create_table_in_db(domain_id, NAME_OF_DB,
                'contributions_table', yuu_contributions_table_definition)
        self.db.create_table_in_db(domain_id, NAME_OF_DB,
                'needs_table', yuu_needs_table_definition)


    def write_item(self, timestamp, good_until, name, item,
            type='contributions'):
        self.db.exec_sql(
            domain_id,
            NAME_OF_DB,
            'insert into ' + type + '_table values (?, ?, ?, ?, ?)',
            timestamp,
            good_until,
            name,
            item,
            0
        )


def get_balance(name, user_id, done=False):
    r = requests.get(PREFIX_API + '/api/status/' + user_id,
            params={'mint_id': MINT_ID})
    res = r.json()

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'])

    to_name = request.args.get('to_name')
    items = []

    if not done:
        if to_name is None or len(to_name) <= 0:
            return render_template('yuu/error.html',
                    message='to_name is missing')

        store = Store()
        store.setup()
        items = store.get_contribution_items(to_name)
        store.close()

    return render_template('yuu/send.html', name=name, user_id=user_id,
            balance=int(res['balance']), symbol=res['symbol'],
            to_name=to_name, items=items, sending=request.method=='GET')


def qrmaker(s):
    qr_img = qr.make(s)

    # allocate buffer and write the image there
    buf = BytesIO()
    qr_img.save(buf,format="png")

    # encode the binary data into base64 and decode with UTF-8
    qr_b64str = base64.b64encode(buf.getvalue()).decode("utf-8")

    # to embed it as src attribute of image element
    qr_b64data = "data:image/png;base64,{}".format(qr_b64str)

    return qr_b64data


def reform_list(txs):
    for tx in txs:
        t = datetime.fromtimestamp(tx['timestamp'], JST)
        tx['timestamp'] = t.strftime(FORMAT_TIME)
        if len(tx['from_name']) <= 0:
            tx['from_name'] = "yuu'"
            tx['label'] = '*** JOINED ***'


def render_top():
    timeString = datetime.now(JST).strftime(FORMAT_TIME)
    return render_template('yuu/register.html', time=timeString)


yuu = Blueprint('yuu', __name__, template_folder='templates',
        static_folder='./static')


@yuu.route('/')
@yuu.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return render_template('yuu/top.html', name=session['name'])

    if request.method == 'GET':
        return render_top()

    name = request.form.get('name')

    if name is None or len(name) <= 0:
        return render_template('yuu/error.html',
                message='name is missing', back_name='Register')

    r = requests.post(PREFIX_API + '/api/user', data={'name': name})
    res = r.json()

    if r.status_code != 201:
        return render_template('yuu/error.html',
                message=res['error']['message'], back_name='Register')

    user_id = res['user_id']

    session['name'] = name
    session['user_id'] = user_id

    r = requests.post(PREFIX_API + '/api/issue/' + MINT_ID,
            data={'user_id': user_id, 'amount': INIT_AMOUNT})

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'])

    return render_template('yuu/top.html', name=name)


@yuu.route('/log-in', methods=['GET', 'POST'])
def log_in():
    if request.method == 'GET':
        return render_template('yuu/login.html')

    name = request.form.get('name')

    if name is None or len(name) <= 0:
        return render_template('yuu/error.html',
                message='name is missing', back_name='Log In')

    r = requests.get(PREFIX_API + '/api/user', params={'name': name})
    res = r.json()

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'], back_name='Log In')

    session['name'] = name
    session['user_id'] = res['user_id']

    return render_template('yuu/top.html', name=name)


@yuu.route('/log-out')
def log_out():
    session.pop('user_id', None)
    session.pop('name', None)

    return render_top()


# payment
@yuu.route("/pay", methods=['POST','GET'])
def pay():
    if 'user_id' not in session:
        return render_top()

    name = session['name']

    s_url = PREFIX_QR + '/yuu/send?to_name=' + name
    qr_b64data = qrmaker(s_url)
    return render_template('yuu/pay.html',
        qr_b64data=qr_b64data,
        qr_name=s_url
    )


@yuu.route('/send', methods=['GET', 'POST'])
def send():
    if 'user_id' not in session:
        return render_top()

    name = session['name']
    user_id = session['user_id']

    if request.method == 'GET':
        return get_balance(name, user_id)

    to_name = request.form.get('to_name')
    amount = request.form.get('amount')
    item = request.form.get('item')
    balance = int(request.form.get('balance'))

    if to_name is None or len(to_name) <= 0:
        return render_template('yuu/error.html',
                message='to_name is missing')

    if amount is None or len(amount) <= 0:
        return render_template('yuu/error.html',
                message='amount is missing', back_name='Transfer')

    x = int(amount) if amount.isdecimal() else 0
    if x <= 0:
        return render_template('yuu/error.html',
                message='amount must be non-zero positive number',
                back_name='Transfer')
    if x > balance:
        return render_template('yuu/error.html',
                message='not enough fund', back_name='Transfer')

    r = requests.get(PREFIX_API + '/api/user', params={'name': to_name})
    res = r.json()

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'])

    to_user_id = res['user_id']

    r = requests.post(PREFIX_API + '/api/transfer/' + MINT_ID, data={
        'from_user_id': user_id,
        'to_user_id': to_user_id,
        'amount': amount,
        'label': item
    })

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'])

    return get_balance(name, user_id, done=True)


# contribution registration
@yuu.route("/contributions", methods=['GET'])
def contributions_prepare():
    if 'user_id' not in session:
        return render_top()

    menu_name = "Register a contributions!"
    info = ""
    now = datetime.now(JST)
    timeString = now.strftime(FORMAT_TIME)
    return render_template("yuu/contributions.html", menu_name = menu_name,
            info = info, time=timeString)


@yuu.route("/contributions", methods=['POST'])
def contributions_write():
    if 'user_id' not in session:
        return render_top()

    name = session['name']

    item = request.form.get('a')

    if item is None or len(item) <= 0:
        return render_template('yuu/error.html',
                message='item is missing', back_name='Open a Shop')

    store = Store()
    store.setup()
    store.write_item(int(time.time()), INFTY_TIME, name, item,
            type='contributions')
    store.close()

    return render_template("yuu/contributions_posted.html")


# list of transactions
@yuu.route("/tx")
def tx():
    if 'user_id' not in session:
        return render_top()

    menu_name = "Transactions"
    info = "Your transactions can be seen at 'My Page'"
    now = datetime.now(JST)
    timeString = now.strftime(FORMAT_TIME)

    offset = request.args.get('offset')

    if offset is None:
        offset = 0

    r = requests.get(PREFIX_API + '/api/transactions/' + MINT_ID, params={
        'basetime': BASE_TIME,
        'count': LIST_COUNT,
        'offset': offset,
    })
    res = r.json()

    reform_list(res['transactions'])

    return render_template("yuu/tx.html", menu_name=menu_name,
            info=info, time=timeString,
            transactions=res['transactions'], count=LIST_COUNT,
            count_before=res['count_before'], count_after=res['count_after'])


# list of contributions
@yuu.route("/contributionlist")
def contributionlist():
    if 'user_id' not in session:
        return render_top()

    name = session['name']

    menu_name = "Recommended Givers"
    info = "Newest Ones First"
    now = datetime.now(JST)
    timeString = now.strftime(FORMAT_TIME)

    store = Store()
    store.setup()
    contributions = store.get_item_list('contributions', 10)
    store.close()

    for contribution in contributions:
        t = datetime.fromtimestamp(contribution['timestamp'], JST)
        contribution['timestamp'] = t.strftime(FORMAT_TIME)
        t = datetime.fromtimestamp(contribution['good_until'], JST)
        contribution['good_until'] = t.strftime(FORMAT_TIME)

    return render_template("yuu/contributionlist.html", menu_name=menu_name,
            info=info, time=timeString, name=name,
            contributions=contributions)


@yuu.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return render_top()

    name = session['name']
    user_id = session['user_id']

    r = requests.get(PREFIX_API + '/api/status/' + user_id,
            params={'mint_id': MINT_ID})
    res = r.json()

    if r.status_code != 200:
        return render_template('yuu/error.html',
                message=res['error']['message'])

    balance=res['balance']
    symbol=res['symbol']

    r = requests.get(PREFIX_API + '/api/transactions/' + MINT_ID, params={
        'name': name,
        'basetime': BASE_TIME,
    })
    res = r.json()

    reform_list(res['transactions'])

    spendcoin = 0
    getcoin = 0

    for tx in res['transactions']:
        if tx['to_name'] == name:
            getcoin += int(tx['amount'])
        else:
            spendcoin += int(tx['amount'])

    menu_name = "My Page"
    now = datetime.now(JST)
    timeString = now.strftime(FORMAT_TIME)
    return render_template("yuu/mypage.html", menu_name=menu_name,
        name=name, balance=balance, symbol=symbol,
        time=timeString, spendcoin=spendcoin, getcoin=getcoin,
        transactions=res['transactions'])


# end of app.py
