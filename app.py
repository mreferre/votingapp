import hmac
import os
import secrets

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS, cross_origin
from random import randrange
import simplejson as json
import boto3
from multiprocessing import Pool
from multiprocessing import cpu_count

app = Flask(__name__)
# Used to sign the session cookie of the /votes page. If unset, /votes denies access.
app.secret_key = os.getenv('SECRET_KEY') or None
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

cors = CORS(app, resources={r"/api/*": {"Access-Control-Allow-Origin": "*"}})

cpustressfactor = os.getenv('CPUSTRESSFACTOR', 1)
memstressfactor = os.getenv('MEMSTRESSFACTOR', 1)
ddb_aws_region = os.getenv('DDB_AWS_REGION')
ddb_table_name = os.getenv('DDB_TABLE_NAME', "votingapp-restaurants")

ddb = boto3.resource('dynamodb', region_name=ddb_aws_region)
ddbtable = ddb.Table(ddb_table_name)

print("The cpustressfactor variable is set to: " + str(cpustressfactor))
print("The memstressfactor variable is set to: " + str(memstressfactor))
memeater=[]
memeater=[0 for i in range(10000)] 

## https://gist.github.com/tott/3895832
def f(x):
    for x in range(1000000 * int(cpustressfactor)):
        x*x

def readvote(restaurant):
    response = ddbtable.get_item(Key={'name': restaurant})
    # this is required to convert decimal to integer 
    normilized_response = json.dumps(response)
    json_response = json.loads(normilized_response)
    votes = json_response["Item"]["restaurantcount"]
    return str(votes)

def updatevote(restaurant, votes):
    ddbtable.update_item(
        Key={
            'name': restaurant
        },
        UpdateExpression='SET restaurantcount = :value',
        ExpressionAttributeValues={
            ':value': votes
        },
        ReturnValues='UPDATED_NEW'
    )
    return str(votes)

@app.route('/')
def home():
    return "<h1>Welcome to the Voting App</h1><p><b>To vote, you can call the following APIs:</b></p><p>/api/outback</p><p>/api/bucadibeppo</p><p>/api/ihop</p><p>/api/chipotle</p><b>To query the votes, you can call the following APIs:</b><p>/api/getvotes</p><p>/api/getheavyvotes (this generates artificial CPU/memory load)</p>"

@app.route("/api/outback")
def outback():
    string_votes = readvote("outback")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("outback", votes)
    return string_new_votes 

@app.route("/api/bucadibeppo")
def bucadibeppo():
    string_votes = readvote("bucadibeppo")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("bucadibeppo", votes)
    return string_new_votes 

@app.route("/api/ihop")
def ihop():
    string_votes = readvote("ihop")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("ihop", votes)
    return string_new_votes 

@app.route("/api/chipotle")
def chipotle():
    string_votes = readvote("chipotle")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("chipotle", votes)
    return string_new_votes 

@app.route("/api/getvotes")
def getvotes():
    string_outback = readvote("outback")
    string_ihop = readvote("ihop")
    string_bucadibeppo = readvote("bucadibeppo")
    string_chipotle = readvote("chipotle")
    string_votes = '[{"name": "outback", "value": ' + string_outback + '},' + '{"name": "bucadibeppo", "value": ' + string_bucadibeppo + '},' + '{"name": "ihop", "value": '  + string_ihop + '}, ' + '{"name": "chipotle", "value": '  + string_chipotle + '}]'
    return string_votes

@app.route("/api/getheavyvotes")
def getheavyvotes():
    string_outback = readvote("outback")
    string_ihop = readvote("ihop")
    string_bucadibeppo = readvote("bucadibeppo")
    string_chipotle = readvote("chipotle")
    string_votes = '[{"name": "outback", "value": ' + string_outback + '},' + '{"name": "bucadibeppo", "value": ' + string_bucadibeppo + '},' + '{"name": "ihop", "value": '  + string_ihop + '}, ' + '{"name": "chipotle", "value": '  + string_chipotle + '}]'
    print("You invoked the getheavyvotes API. I am eating 100MB * " + str(memstressfactor) + " at every votes request")
    memeater[randrange(10000)] = bytearray(1024 * 1024 * 100 * memstressfactor, encoding='utf8') # eats 100MB * memstressfactor
    print("You invoked the getheavyvotes API. I am eating some cpu * " + str(cpustressfactor) + " at every votes request")
    processes = cpu_count()
    pool = Pool(processes)
    pool.map(f, range(processes))
    return string_votes

# ---- /votes: password protected page -------------------------------------
RESTAURANTS = [
    ("outback", "Outback"),
    ("bucadibeppo", "Buca di Beppo"),
    ("ihop", "IHOP"),
    ("chipotle", "Chipotle"),
]

def votes_configured():
    # no hardcoded default: without both variables nobody gets in
    return bool(os.getenv('VOTES_PASSWORD')) and bool(app.secret_key)

def is_authed():
    return votes_configured() and session.get('votes_auth') is True

def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']

def csrf_ok():
    sent = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token') or ''
    expected = session.get('csrf', '')
    return bool(expected) and hmac.compare_digest(sent.encode(), expected.encode())

def no_store(resp):
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.route('/votes')
def votes_page():
    if not votes_configured():
        return no_store(app.make_response(("The votes page is disabled: VOTES_PASSWORD and SECRET_KEY are not set.", 503)))
    if not is_authed():
        return no_store(app.make_response(render_template('votes_login.html', csrf_token=csrf_token(), error=request.args.get('error'))))
    rows = []
    error = None
    for key, label in RESTAURANTS:
        try:
            rows.append({"key": key, "label": label, "votes": int(readvote(key))})
        except Exception:
            rows.append({"key": key, "label": label, "votes": None})
            error = "Some counts could not be loaded."
    return no_store(app.make_response(render_template('votes.html', rows=rows, csrf_token=csrf_token(), error=error, notice=request.args.get('notice'))))

@app.route('/votes/login', methods=['POST'])
def votes_login():
    if not votes_configured():
        abort(503)
    if not csrf_ok():
        abort(403)
    supplied = request.form.get('password', '')
    if hmac.compare_digest(supplied.encode(), os.environ['VOTES_PASSWORD'].encode()):
        session.clear()
        session['votes_auth'] = True
        csrf_token()
        return redirect(url_for('votes_page'))
    return redirect(url_for('votes_page', error=1)), 303

@app.route('/votes/logout', methods=['POST'])
def votes_logout():
    if not csrf_ok():
        abort(403)
    session.clear()
    return redirect(url_for('votes_page'))

@app.route('/votes/vote/<key>', methods=['POST'])
def votes_vote(key):
    if not is_authed():
        abort(401)
    if not csrf_ok():
        abort(403)
    if key not in dict(RESTAURANTS):
        abort(404)
    # same read-then-write logic as the /api/<restaurant> routes
    new_votes = int(updatevote(key, int(readvote(key)) + 1))
    if request.headers.get('X-Requested-With') == 'fetch':
        return no_store(jsonify(name=key, votes=new_votes))
    return redirect(url_for('votes_page', notice=dict(RESTAURANTS)[key]))

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
