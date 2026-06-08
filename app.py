import os

from flask import Flask, request
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
votes_password = os.getenv('VOTES_PASSWORD', 'voting123')

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

@app.route("/votes")
def votes():
    page_password = votes_password
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Restaurant Voting App</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .container {{
            width: 100%;
            max-width: 900px;
        }}

        /* Login Section */
        .login-section {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 60px 40px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            text-align: center;
            animation: fadeIn 0.6s ease-out;
        }}

        .login-section h1 {{
            font-size: 2rem;
            color: #333;
            margin-bottom: 10px;
        }}

        .login-section p {{
            color: #666;
            margin-bottom: 30px;
            font-size: 1.05rem;
        }}

        .login-form {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
        }}

        .login-form input[type="password"] {{
            width: 100%;
            max-width: 320px;
            padding: 14px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 1rem;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            outline: none;
        }}

        .login-form input[type="password"]:focus {{
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15);
        }}

        .login-form button {{
            padding: 14px 40px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}

        .login-form button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }}

        .login-form button:active {{
            transform: translateY(0);
        }}

        .error-message {{
            color: #e53e3e;
            font-size: 0.9rem;
            min-height: 1.2em;
            margin-top: 4px;
        }}

        /* Voting Section */
        .voting-section {{
            display: none;
            animation: fadeIn 0.6s ease-out;
        }}

        .voting-header {{
            text-align: center;
            margin-bottom: 40px;
        }}

        .voting-header h1 {{
            font-size: 2.2rem;
            color: #fff;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            margin-bottom: 8px;
        }}

        .voting-header p {{
            color: rgba(255, 255, 255, 0.85);
            font-size: 1.1rem;
        }}

        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 24px;
        }}

        .restaurant-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 32px 24px;
            text-align: center;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .restaurant-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }}

        .restaurant-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
        }}

        .restaurant-icon {{
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            font-size: 1.5rem;
        }}

        .restaurant-name {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #333;
            margin-bottom: 8px;
            text-transform: capitalize;
        }}

        .vote-count {{
            font-size: 2.5rem;
            font-weight: 800;
            color: #667eea;
            margin-bottom: 20px;
            transition: transform 0.3s ease;
        }}

        .vote-count.updated {{
            animation: pulse 0.4s ease;
        }}

        .vote-label {{
            font-size: 0.85rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}

        .vote-btn {{
            width: 100%;
            padding: 12px 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
        }}

        .vote-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }}

        .vote-btn:active {{
            transform: translateY(0);
        }}

        .vote-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}

        .logout-btn {{
            display: block;
            margin: 40px auto 0;
            padding: 12px 32px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.4);
            border-radius: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s ease, border-color 0.3s ease;
        }}

        .logout-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.7);
        }}

        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.2); }}
            100% {{ transform: scale(1); }}
        }}

        @media (max-width: 600px) {{
            .cards-grid {{
                grid-template-columns: 1fr;
            }}

            .login-section {{
                padding: 40px 24px;
            }}

            .voting-header h1 {{
                font-size: 1.6rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Login Section -->
        <section class="login-section" id="loginSection" aria-label="Login form">
            <h1>Restaurant Voting</h1>
            <p>Enter the password to access the voting dashboard</p>
            <form class="login-form" id="loginForm" onsubmit="handleLogin(event)" aria-label="Password authentication">
                <label for="passwordInput" class="sr-only" style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);border:0;">Password</label>
                <input type="password" id="passwordInput" placeholder="Enter password" required autocomplete="current-password" aria-describedby="errorMsg">
                <button type="submit" aria-label="Submit password">Unlock Dashboard</button>
                <div class="error-message" id="errorMsg" role="alert" aria-live="polite"></div>
            </form>
        </section>

        <!-- Voting Section -->
        <section class="voting-section" id="votingSection" aria-label="Voting dashboard">
            <header class="voting-header">
                <h1>Restaurant Voting Dashboard</h1>
                <p>Cast your vote for your favorite restaurant</p>
            </header>
            <div class="cards-grid" role="list" aria-label="Restaurant voting cards">
                <article class="restaurant-card" role="listitem" aria-label="Outback Steakhouse">
                    <div class="restaurant-icon" aria-hidden="true">&#127830;</div>
                    <h2 class="restaurant-name">Outback</h2>
                    <div class="vote-label">Total Votes</div>
                    <div class="vote-count" id="count-outback" aria-live="polite">-</div>
                    <button class="vote-btn" onclick="castVote('outback')" aria-label="Vote for Outback">Vote</button>
                </article>
                <article class="restaurant-card" role="listitem" aria-label="Buca di Beppo">
                    <div class="restaurant-icon" aria-hidden="true">&#127837;</div>
                    <h2 class="restaurant-name">Buca di Beppo</h2>
                    <div class="vote-label">Total Votes</div>
                    <div class="vote-count" id="count-bucadibeppo" aria-live="polite">-</div>
                    <button class="vote-btn" onclick="castVote('bucadibeppo')" aria-label="Vote for Buca di Beppo">Vote</button>
                </article>
                <article class="restaurant-card" role="listitem" aria-label="IHOP">
                    <div class="restaurant-icon" aria-hidden="true">&#129374;</div>
                    <h2 class="restaurant-name">IHOP</h2>
                    <div class="vote-label">Total Votes</div>
                    <div class="vote-count" id="count-ihop" aria-live="polite">-</div>
                    <button class="vote-btn" onclick="castVote('ihop')" aria-label="Vote for IHOP">Vote</button>
                </article>
                <article class="restaurant-card" role="listitem" aria-label="Chipotle">
                    <div class="restaurant-icon" aria-hidden="true">&#127798;</div>
                    <h2 class="restaurant-name">Chipotle</h2>
                    <div class="vote-label">Total Votes</div>
                    <div class="vote-count" id="count-chipotle" aria-live="polite">-</div>
                    <button class="vote-btn" onclick="castVote('chipotle')" aria-label="Vote for Chipotle">Vote</button>
                </article>
            </div>
            <button class="logout-btn" onclick="handleLogout()" aria-label="Log out">Log Out</button>
        </section>
    </div>

    <script>
        const APP_PASSWORD = "{page_password}";

        function handleLogin(event) {{
            event.preventDefault();
            const input = document.getElementById('passwordInput');
            const errorMsg = document.getElementById('errorMsg');

            if (input.value === APP_PASSWORD) {{
                document.getElementById('loginSection').style.display = 'none';
                document.getElementById('votingSection').style.display = 'block';
                errorMsg.textContent = '';
                loadVotes();
            }} else {{
                errorMsg.textContent = 'Incorrect password. Please try again.';
                input.value = '';
                input.focus();
            }}
        }}

        function handleLogout() {{
            document.getElementById('votingSection').style.display = 'none';
            document.getElementById('loginSection').style.display = 'block';
            document.getElementById('passwordInput').value = '';
        }}

        async function loadVotes() {{
            try {{
                const response = await fetch('/api/getvotes');
                const data = await response.json();
                data.forEach(function(item) {{
                    const el = document.getElementById('count-' + item.name);
                    if (el) {{
                        const oldValue = el.textContent;
                        el.textContent = item.value;
                        if (oldValue !== '-' && oldValue !== String(item.value)) {{
                            el.classList.add('updated');
                            setTimeout(function() {{ el.classList.remove('updated'); }}, 400);
                        }}
                    }}
                }});
            }} catch (err) {{
                console.error('Failed to load votes:', err);
            }}
        }}

        async function castVote(restaurant) {{
            const btn = event.currentTarget;
            btn.disabled = true;
            btn.textContent = 'Voting...';

            try {{
                await fetch('/api/' + restaurant);
                await loadVotes();
            }} catch (err) {{
                console.error('Failed to cast vote:', err);
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Vote';
            }}
        }}
    </script>
</body>
</html>'''

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
