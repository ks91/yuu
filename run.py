from flask import Flask


app = Flask(__name__)


from kmdmarche.app import kmdmarche
app.register_blueprint(kmdmarche, url_prefix='/kmdmarche')


app.secret_key = '6-mP76Hj*gJFEq8*LysB!wi@TYzkdLxtNEp*cY'


if __name__ == '__main__':
    app.run(host='0.0.0.0')

# end of run.py
