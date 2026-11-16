import hmac
import os
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin
from random import randrange
import simplejson as json
import boto3
from multiprocessing import Pool
from multiprocessing import cpu_count

app = Flask(__name__)

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

# ---------------------------------------------------------------------------
# Password-protected votes page (/votes). Reuses the vote views above.
# ---------------------------------------------------------------------------
# slug -> (display name, existing vote view). Order is the display order.
RESTAURANTS = {
    "outback": ("Outback", outback),
    "bucadibeppo": ("Buca di Beppo", bucadibeppo),
    "ihop": ("IHOP", ihop),
    "chipotle": ("Chipotle", chipotle),
}

def _votes_authorized():
    # Fail closed: with no VOTES_PASSWORD configured nobody gets in.
    # Read per request so the value is never baked in at import time.
    expected = os.getenv("VOTES_PASSWORD")
    if not expected:
        return False
    auth = request.authorization
    if auth is None or auth.password is None:
        return False
    return hmac.compare_digest(auth.password.encode("utf-8"), expected.encode("utf-8"))

def _votes_unauthorized():
    return Response("Authentication required\n", 401,
                    {"WWW-Authenticate": 'Basic realm="Votes", charset="UTF-8"',
                     "Cache-Control": "no-store"})

def votes_protected(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _votes_authorized():
            return _votes_unauthorized()
        response = app.make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store"
        return response
    return wrapper

def _current_counts():
    return {slug: int(readvote(slug)) for slug in RESTAURANTS}

@app.route("/votes")
@votes_protected
def votes_page():
    try:
        counts, error = _current_counts(), None
    except Exception:
        app.logger.exception("Could not read votes")
        counts, error = {slug: None for slug in RESTAURANTS}, "Could not load the current votes."
    restaurants = [{"slug": slug, "name": name, "votes": counts[slug]}
                   for slug, (name, _) in RESTAURANTS.items()]
    return render_template("votes.html", restaurants=restaurants, error=error)

@app.route("/votes/data")
@votes_protected
def votes_data():
    try:
        return jsonify(_current_counts())
    except Exception:
        app.logger.exception("Could not read votes")
        return jsonify(error="Could not load the current votes."), 502

@app.route("/votes/vote/<slug>", methods=["POST"])
@votes_protected
def votes_vote(slug):
    # Basic auth is sent automatically by browsers, so require a custom header:
    # a cross-site form cannot set it and a cross-site fetch would need a CORS preflight.
    if request.headers.get("X-Requested-With") != "fetch":
        return jsonify(error="Missing X-Requested-With header."), 400
    if slug not in RESTAURANTS:
        return jsonify(error="Unknown restaurant."), 404
    try:
        return jsonify(slug=slug, votes=int(RESTAURANTS[slug][1]()))
    except Exception:
        app.logger.exception("Could not record vote")
        return jsonify(error="Could not record your vote."), 502

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
