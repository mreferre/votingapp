import os
import hmac
import secrets
import functools

from flask import (
    Flask,
    session,
    request,
    redirect,
    render_template_string,
    jsonify,
    make_response,
)
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
# votes-web-page feature (additive): password-protected /votes UI.
# All code below is additive; the existing /, /api/*, readvote, updatevote and
# CORS configuration above are intentionally left unchanged.
# ---------------------------------------------------------------------------

# Fixed allow-list of the four restaurants (drives rendering and validation).
RESTAURANTS = ["outback", "bucadibeppo", "ihop", "chipotle"]

# Flask signed sessions require a secret key. Prefer an explicit SECRET_KEY so
# sessions can survive restarts when desired; otherwise generate a per-process
# random key (this simply forces re-login after a restart).
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)

# Maximum accepted password length (Requirement 2.2).
VOTES_PASSWORD_MAX_LEN = 256


def get_configured_password():
    """Read the Configured_Password from the VOTES_PASSWORD env var.

    Returns the raw string, or None when the variable is not set. No default
    secret is ever assumed (fail-closed).
    """
    return os.getenv('VOTES_PASSWORD')


def votes_password_is_configured():
    """True only when VOTES_PASSWORD is set and non-empty after stripping."""
    password = get_configured_password()
    return password is not None and password.strip() != ""


def is_authenticated():
    """True only when a password is configured AND the session is marked authed.

    Tying the session check to current configuration ensures that clearing or
    blanking the password invalidates effective access immediately.
    """
    return votes_password_is_configured() and session.get('votes_authed') is True


def verify_password(submitted):
    """Constant-time, case-sensitive, byte-for-byte password verification.

    Returns True only when the password is configured, the submitted value is a
    non-empty / not whitespace-only string of length <= 256, and it matches the
    Configured_Password exactly. Uses hmac.compare_digest to avoid timing leaks.
    """
    if not votes_password_is_configured():
        return False
    if not isinstance(submitted, str):
        return False
    if submitted == "" or submitted.strip() == "":
        return False
    if len(submitted) > VOTES_PASSWORD_MAX_LEN:
        return False
    configured = get_configured_password()
    return hmac.compare_digest(submitted.encode('utf-8'), configured.encode('utf-8'))


def require_votes_auth(view):
    """Decorator that rejects unauthenticated requests with 401 JSON.

    Runs before any DynamoDB access so rejected requests provably cannot mutate
    or read state (Requirements 2.4, 4.7).
    """
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Inline templates (single-file structure preserved via render_template_string).
# ---------------------------------------------------------------------------

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Votes - Sign in</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      color: #1a1a1a;
    }
    main.login-card {
      background: #ffffff;
      width: 100%;
      max-width: 24rem;
      padding: 2rem;
      border-radius: 14px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.25);
    }
    h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
    p.subtitle { margin: 0 0 1.5rem; color: #555; font-size: 0.95rem; }
    label { display: block; font-weight: 600; margin-bottom: 0.4rem; }
    input[type="password"] {
      width: 100%;
      padding: 0.7rem 0.8rem;
      font-size: 1rem;
      border: 1px solid #c5c9d0;
      border-radius: 8px;
    }
    input[type="password"]:focus { outline: 3px solid #2a5298; border-color: #2a5298; }
    button[type="submit"] {
      margin-top: 1.2rem;
      width: 100%;
      padding: 0.75rem;
      font-size: 1rem;
      font-weight: 600;
      color: #fff;
      background: #2a5298;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }
    button[type="submit"]:hover { background: #1e3c72; }
    .error-banner {
      background: #fdecea;
      color: #8a1c1c;
      border: 1px solid #f5c6cb;
      border-radius: 8px;
      padding: 0.7rem 0.9rem;
      margin-bottom: 1rem;
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <main class="login-card">
    <h1>Restaurant Votes</h1>
    <p class="subtitle">Enter the password to view and cast votes.</p>
    {% if error %}
    <div class="error-banner" role="alert">{{ error }}</div>
    {% endif %}
    <form method="POST" action="/votes/login" autocomplete="off">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required autofocus>
      <button type="submit">Sign in</button>
    </form>
  </main>
</body>
</html>"""


VOTES_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Restaurant Votes</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%);
      color: #1a1a1a;
      padding: 1rem;
    }
    header.page-header {
      max-width: 60rem;
      margin: 1rem auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
    }
    header.page-header h1 { margin: 0; font-size: 1.6rem; }
    .logout-link {
      font-size: 0.9rem;
      color: #2a5298;
      text-decoration: none;
      border: 1px solid #2a5298;
      padding: 0.4rem 0.8rem;
      border-radius: 8px;
    }
    main.votes-wrap { max-width: 60rem; margin: 0 auto; }
    #status-region { min-height: 1.5rem; margin: 0.5rem 0; }
    .alert {
      padding: 0.7rem 0.9rem;
      border-radius: 8px;
      font-size: 0.95rem;
    }
    .alert-error { background: #fdecea; color: #8a1c1c; border: 1px solid #f5c6cb; }
    .alert-success { background: #e7f6ec; color: #1b6b32; border: 1px solid #b6e2c3; }
    table.votes-grid {
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
      table-layout: fixed;
    }
    table.votes-grid caption { text-align: left; padding: 0.75rem 1rem; font-weight: 600; color: #555; }
    table.votes-grid th, table.votes-grid td {
      padding: 0.9rem 1rem;
      text-align: left;
      border-bottom: 1px solid #eef1f5;
      word-break: break-word;
    }
    table.votes-grid th[scope="col"] { background: #2a5298; color: #fff; }
    .restaurant-name { font-weight: 600; text-transform: capitalize; }
    .count-cell { font-variant-numeric: tabular-nums; font-size: 1.1rem; }
    .vote-button {
      padding: 0.55rem 1rem;
      font-size: 0.95rem;
      font-weight: 600;
      color: #fff;
      background: #2a5298;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      width: 100%;
      max-width: 10rem;
    }
    .vote-button:hover:not(:disabled) { background: #1e3c72; }
    .vote-button:disabled { opacity: 0.6; cursor: progress; }
    .control-status { display: block; font-size: 0.8rem; color: #555; min-height: 1rem; margin-top: 0.25rem; }
    @media (max-width: 480px) {
      table.votes-grid th, table.votes-grid td { padding: 0.6rem 0.5rem; font-size: 0.9rem; }
      header.page-header h1 { font-size: 1.3rem; }
    }
  </style>
</head>
<body>
  <header class="page-header">
    <h1>Restaurant Votes</h1>
    <a class="logout-link" href="/votes/logout">Sign out</a>
  </header>
  <main class="votes-wrap">
    <div id="status-region" aria-live="polite"></div>
    <table class="votes-grid">
      <caption>Current standings &mdash; cast your vote below.</caption>
      <thead>
        <tr>
          <th scope="col">Restaurant</th>
          <th scope="col">Votes</th>
          <th scope="col">Action</th>
        </tr>
      </thead>
      <tbody>
        {% for restaurant in restaurants %}
        <tr data-restaurant="{{ restaurant }}">
          <td class="restaurant-name">{{ restaurant }}</td>
          <td class="count-cell" data-count-for="{{ restaurant }}">&hellip;</td>
          <td>
            <button type="button" class="vote-button"
                    data-vote-for="{{ restaurant }}"
                    aria-label="Vote for {{ restaurant }}">Vote</button>
            <span class="control-status" data-status-for="{{ restaurant }}" aria-live="polite"></span>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </main>
  <script>
    (function () {
      "use strict";
      var COUNTS_UNAVAILABLE = "Vote counts are temporarily unavailable.";
      var statusRegion = document.getElementById("status-region");

      function showGlobal(message, kind) {
        statusRegion.innerHTML = "";
        if (!message) { return; }
        var box = document.createElement("div");
        box.className = "alert " + (kind === "success" ? "alert-success" : "alert-error");
        box.setAttribute("role", kind === "success" ? "status" : "alert");
        box.textContent = message;
        statusRegion.appendChild(box);
      }

      function clearCounts() {
        document.querySelectorAll("[data-count-for]").forEach(function (cell) {
          cell.textContent = "";
        });
      }

      function setCount(restaurant, value) {
        var cell = document.querySelector('[data-count-for="' + restaurant + '"]');
        if (cell) { cell.textContent = String(value); }
      }

      function loadCounts() {
        fetch("/votes/data", { headers: { "Accept": "application/json" } })
          .then(function (resp) {
            if (resp.status !== 200) { throw new Error("bad status"); }
            return resp.json();
          })
          .then(function (rows) {
            rows.forEach(function (row) { setCount(row.name, row.value); });
          })
          .catch(function () {
            clearCounts();
            showGlobal(COUNTS_UNAVAILABLE, "error");
          });
      }

      function revealLogin() {
        window.location.href = "/votes";
      }

      function onVote(button) {
        var restaurant = button.getAttribute("data-vote-for");
        var controlStatus = document.querySelector('[data-status-for="' + restaurant + '"]');
        button.disabled = true;
        if (controlStatus) { controlStatus.textContent = "Processing\u2026"; }

        fetch("/votes/vote", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify({ restaurant: restaurant })
        }).then(function (resp) {
          return resp.json().then(function (data) { return { status: resp.status, data: data }; });
        }).then(function (result) {
          if (result.status === 200) {
            setCount(result.data.restaurant, result.data.value);
            showGlobal("Your vote for " + restaurant + " was recorded.", "success");
            if (controlStatus) { controlStatus.textContent = ""; }
            button.disabled = false;
          } else if (result.status === 400) {
            showGlobal("The selected restaurant is invalid.", "error");
            if (controlStatus) { controlStatus.textContent = ""; }
            button.disabled = false;
          } else if (result.status === 401) {
            showGlobal("Your session expired. Please sign in again.", "error");
            revealLogin();
          } else {
            showGlobal("Your vote could not be recorded.", "error");
            if (controlStatus) { controlStatus.textContent = ""; }
            button.disabled = false;
          }
        }).catch(function () {
          showGlobal("Your vote could not be recorded.", "error");
          if (controlStatus) { controlStatus.textContent = ""; }
          button.disabled = false;
        });
      }

      document.querySelectorAll(".vote-button").forEach(function (button) {
        button.addEventListener("click", function () { onVote(button); });
      });

      loadCounts();
    })();
  </script>
</body>
</html>"""


def render_login(error=None, status=200):
    """Render the login form. Contains no vote counts or vote controls."""
    html = render_template_string(LOGIN_TEMPLATE, error=error)
    response = make_response(html, status)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


def render_votes_page():
    """Render the authenticated grid scaffold; counts load client-side."""
    html = render_template_string(VOTES_TEMPLATE, restaurants=RESTAURANTS)
    response = make_response(html, 200)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


# ---------------------------------------------------------------------------
# Routes (all under the /votes prefix; legacy / and /api/* are untouched).
# ---------------------------------------------------------------------------

@app.route('/votes', methods=['GET'])
def votes_page():
    if not is_authenticated():
        # Login form only (no counts/controls) when unauthenticated or unset.
        return render_login(status=200)
    return render_votes_page()


@app.route('/votes/login', methods=['POST'])
def votes_login():
    submitted = request.form.get('password', '')
    if verify_password(submitted):
        session['votes_authed'] = True
        return redirect('/votes', code=302)
    # Do not establish a session on failure.
    session.pop('votes_authed', None)
    return render_login(error="Incorrect password. Please try again.", status=401)


@app.route('/votes/logout', methods=['GET', 'POST'])
def votes_logout():
    session.pop('votes_authed', None)
    return redirect('/votes', code=302)


@app.route('/votes/data', methods=['GET'])
@require_votes_auth
def votes_data():
    try:
        rows = []
        for restaurant in RESTAURANTS:
            value = int(readvote(restaurant))
            rows.append({"name": restaurant, "value": value})
        return jsonify(rows), 200
    except Exception as exc:
        # Generic error only; never leak region/table/stack details.
        print("votes_data read failure: " + repr(exc))
        return jsonify({"error": "counts temporarily unavailable"}), 500


@app.route('/votes/vote', methods=['POST'])
@require_votes_auth
def votes_vote():
    # Parse the restaurant from a JSON body or form field.
    restaurant = None
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        restaurant = payload.get('restaurant')
    if restaurant is None:
        restaurant = request.form.get('restaurant')

    # Validate against the allow-list BEFORE any read/write (Requirement 4.6).
    if restaurant not in RESTAURANTS:
        return jsonify({"error": "selected restaurant is invalid"}), 400

    try:
        current = int(readvote(restaurant))
        updatevote(restaurant, current + 1)
        return jsonify({"restaurant": restaurant, "value": current + 1}), 200
    except Exception as exc:
        # Generic error only; never leak region/table/stack details.
        print("votes_vote read/write failure: " + repr(exc))
        return jsonify({"error": "vote could not be recorded"}), 500


if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
