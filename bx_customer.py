from flask import Flask, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# Third-party libraries for Google Login API
from flask_login import LoginManager,current_user,login_required,login_user,logout_user

from datetime import datetime
import json
import os
import sqlite3
import requests
import pika
import oauthlib.oauth2 as oo

from flask_graphql import GraphQLView
from graphene import ObjectType, String, Int, Field, List, Schema, Float
from graphene.types.datetime import Date

######## google api settings #########

file = open("googleAPI.txt")
line1 = file.readline()
line2 = file.readline()
GOOGLE_CLIENT_ID = line1
os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = line2
os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
# using flask"s login manager for user session mgmt setup

host = "172.31.30.44"
port = 5300

# OAuth 2 client setup
client = oo.WebApplicationClient(GOOGLE_CLIENT_ID)
dbName = "customer"
dbURL = os.environ.get("dbURL")
dbURL += dbName

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = dbURL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

login_manager = LoginManager()
login_manager.init_app(app)

CORS(app)

######## GRAPHQL settings ##########

class Customer(ObjectType):
    userID = Int()
    name = String()
    email = String()
    telehandle = String()
    teleID = Int()
    point = Int()
    exp = Int()
    tier = Int()
    message = String()

class usePoints(ObjectType):
    status = Int()
    message = String()
    deduction = Float()

class Query(ObjectType):
    retrieveCustomer = Field(Customer, userID = Int())
    getCustomers = List(Customer, tier = Int())
    use = Field(usePoints, userID = Int(), points = Int())
    login = Field(Customer, email = String())
    register = Field(Customer, name = String(), email = String(), telehandle = String())

    def resolve_retrieveCustomer(parent, info, userID):
        r = requests.get("http://{}:{}/viewUser/{}".format(host,port,userID)).json()
        return r

    def resolve_getCustomers(parent, info, tier):
        payload = {"tier":tier}
        r = requests.get("http://{}:{}/view".format(host,port), params = payload).json()
        return r

    def resolve_use(parent, info, userID, points):
        payload = {"userID":userID,"points":points}
        r = requests.put("http://{}:{}/use".format(host,port), json = payload).json()
        return r

    def resolve_login(parent, info, email):
        payload = {"email": email}
        r = requests.post("http://{}:{}/login".format(host,port), json = payload).json()
        return r

    def resolve_register(parent, info, name, email, telehandle):
        payload = {
            "email": email,
            "telehandle": telehandle,
            "name": name
        }
        r = requests.post("http://{}:{}/register".format(host,port), json = payload).json()
        return r

customer_schema = Schema(query = Query)

app.add_url_rule("/graphql", view_func=GraphQLView.as_view("graphql", schema=customer_schema, graphiql=True))
######## GraphQL END #########

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"

    userID = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    email = db.Column(db.String(64), nullable=False)
    telehandle = db.Column(db.String(32), nullable=False)
    teleID = db.Column(db.Integer())
    point = db.Column(db.Integer(), nullable=False)
    exp = db.Column(db.Integer(), nullable=False)

    # def __init__(self, userID, name, email, telehandle, teleID, point, exp, **kwargs):
    #     self.userID = userID
    #     self.name = name
    #     self.email = email
    #     self.telehandle = telehandle
    #     self.teleID = teleID
    #     self.point = point
    #     self.exp = exp

    def json(self):
        return {"userID": self.userID, "name": self.name, "email": self.email, "telehandle": self.telehandle, "teleID": self.teleID, "point": self.point, "exp": self.e
xp, "tier": getTier(self.exp)}


def getTier(exp):
    tier = 3
    if exp >= 5000:
        tier = 1
    elif exp >= 2000:
        tier = 2
    return tier

# Still requires some touchup based on the Google API implementation
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data["email"]
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify(user.json()),201
    return jsonify({"message": "Unsuccessful login"}), 404

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    if User.query.filter_by(email = data["email"]).first():
        return jsonify({"message": "An account tied to that email has already been registered"}), 404
    elif User.query.filter_by(telehandle = data["telehandle"]).first():
        return jsonify({"message": "An account tied to that telehandle has already been registered"}), 404
    else:
        user = User(userID=None,name=data["name"],email=data["email"],telehandle=data["telehandle"],teleID=None,point=0,exp=0)
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            print(e)
            return jsonify({"message": "An error occurred during registration"}), 500
        print(user)

    return jsonify(user.json()), 201

@app.route("/viewUser/<int:userID>")
def view_user(userID):
    user = User.query.filter_by(userID=userID).first()
    if user:
        return jsonify(user.json()),201
    return jsonify({"message": "User not found for id " + str(userID)}), 404

@app.route("/view")
def view_users():
    data = request.args
    createID()
    users = User.query.all()
    result = []
    tier = str(data["tier"]) if "tier" in data else "123"
    for user in users:
        if str(getTier(user.exp)) in tier:
            result.append(user.json())
    return jsonify(result)

@app.route("/use", methods=["PUT"])
def usePoints():
    data = request.get_json()
    userID = data["userID"]
    points = int(data["points"])
    status = 201
    result = {"message": "Points used!"}

    user = User.query.filter_by(userID=userID).first()
    if not user:
        status = 500
        result = {"status": status, "message": "Invalid userID!"}
    elif user.point < points:
        status = 500
        result = {"status": status, "message": "Insufficient points!"}
    else:
        user.point = User.point - points
        db.session.commit()
        result["dedeuction"] = points/100

    return jsonify(result),status

def receiveAmt():
    hostname = "172.31.30.44" # default host
    port = 5672 # default port
    # connect to the broker and set up a communication channel in the connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=hostname, port=port))
    channel = connection.channel()

    # set up the exchange if the exchange doesn"t exist
    exchangename="rewards_direct"
    channel.exchange_declare(exchange=exchangename, exchange_type="direct")

    # prepare a queue for receiving messages
    channelqueue = channel.queue_declare(queue="customer", durable=True) # "" indicates a random unique queue name; "exclusive" indicates the queue is used only by thi
s receiver and will be deleted if the receiver disconnects.
        # If no need durability of the messages, no need durable queues, and can use such temp random queues.
    queue_name = channelqueue.method.queue
    channel.queue_bind(exchange=exchangename, queue="customer", routing_key="rewards.info") # bind the queue to the exchange via the key
        # Can bind the same queue to the same exchange via different keys

    # set up a consumer and start to wait for coming messages
    channel.basic_consume(queue="customer", on_message_callback=callback, auto_ack=True)
    channel.start_consuming() # an implicit loop waiting to receive messages; it doesn"t exit by default. Use Ctrl+C in the command window to terminate it.

def callback(channel, method, properties, body): # required signature for the callback; no return
    print("Received a successful amount by " + __file__)
    updatePoints(json.loads(body))
    print() # print a new line feed

def updatePoints(amt): # Assumes {"userID": userID, "amt": amount }
    print("Recording a successful transaction amt:")
    print(amt)
    user = User.query.filter_by(userID=amt["userID"]).first()
    user.point = User.point + amt["amt"] * 10
    user.exp = User.exp + amt["amt"] * 10
    db.session.commit()

def user_ID():
    users = User.query.all()

    userIDs = {}
    for user in users:
        userIDs[user.telehandle] = user.teleID

    return userIDs

def createID():
    userIDs = user_ID()

    r = requests.get("https://api.telegram.org/bot1072538370:AAH2EvVRZJUpoE0SfIXgD2KKrrsN8E8Flq4/getupdates")
    data = r.json()

    for message in data["result"]:
        if "message" in message:
            username = message["message"]["from"]["username"]
            userID = message["message"]["from"]["id"]

            if username in userIDs and userIDs[username] is None:
                userIDs[username] = userID
                user = User.query.filter_by(telehandle=username).first()
                user.teleID = userID
                db.session.commit()

######### google api settings ##########

# flask loginmanager helps to get a user from OUR db
@login_manager.user_loader
def load_user(userID):
    return User.get(userID)

# TODO: Do up GraphQL for this?
@app.route("/home")
def index():
    if current_user.is_authenticated:
        return (
            "<p>Hello, {}! You're logged in! Email: {}</p>"
            "<div><p>Google Profile Picture:</p>"
            "<img src='{}' alt='Google profile pic'></img></div>"
            "<a class='button' href='/logout'>Logout</a>".format(
                current_user.name, current_user.email, current_user.profile_pic
            )
        )
    else:
        return "<a class='button' href='/ESDproject/google_login'>Google Login</a>"

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# TODO: GraphQL for this?
@app.route("/google_login")
def google_login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user"s profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

# TODO: GraphQL for this?
@app.route("/google_login/google_callback")
def google_callback():
    # Get authorization code Google sent back
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # prepare and send a request to get tokens
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens
    client.parse_request_body_response(json.dumps(token_response.json()))

    # from google find all d info
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # email must be verified
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # if user doenst exist then add to db
    if not User.get(users_email):
        # Send user to login page to continue filling up details
        # if user is new
        return redirect(url_for("login"))
    else:
        # send user to home page if user is existing
        return redirect(url_for("home"))

# TODO: GraphQL for this?
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)