from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

from datetime import datetime
import json
import requests
import pika
import csv
import urllib.request, time

from flask_graphql import GraphQLView
from graphene import ObjectType, String, Int, Field, List, Schema, Float
from graphene.types.datetime import Date

app = Flask(__name__)
# TODO: Change the name of the database when moved to cloud
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost:3306/customer'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

######## GRAPHQL settings ##########

class User(ObjectType):
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
    user = Field(User, userID = Int())
    users = List(User, tier = Int())
    use = Field(usePoints, userID = Int(), points = Int())
    login = Field(User, email = String())
    register = Field(User, name = String(), email = String(), telehandle = String())

    def resolve_user(parent, info, userID):
        r = requests.get("http://127.0.0.1:5001/viewUser/{}".format(userID)).json()
        return r

    def resolve_users(parent, info, tier):
        payload = {"tier":tier}
        r = requests.get("http://127.0.0.1:5001/view", params = payload).json()
        return r

    def resolve_use(parent, info, userID, points):
        payload = {"userID":userID,"points":points}
        r = requests.put("http://127.0.0.1:5001/use", json = payload).json()
        return r

    def resolve_login(parent, info, email):
        payload = {"email": email}
        r = requests.post("http://127.0.0.1:5001/login", json = payload).json()
        return r

    def resolve_register(parent, info, name, email, telehandle):
        payload = {
            "email": email,
            "telehandle": telehandle,
            "name": name
        }
        r = requests.post("http://127.0.0.1:5001/register", json = payload).json()
        return r

customer_schema = Schema(query = Query)

app.add_url_rule('/graphql', view_func=GraphQLView.as_view('graphql', schema=customer_schema, graphiql=True))
######## GraphQL END #########

class User(db.Model):
    __tablename__ = 'user'

    userID = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    email = db.Column(db.String(64), nullable=False)
    telehandle = db.Column(db.String(32), nullable=False)
    teleID = db.Column(db.Integer())
    point = db.Column(db.Integer(), nullable=False)
    exp = db.Column(db.Integer(), nullable=False)

    def json(self):
        return {'userID': self.userID, 'name': self.name, 'email': self.email, 'telehandle': self.telehandle, 'teleID': self.teleID, 'point': self.point, 'exp': self.exp, 'tier': getTier(self.exp)}


def getTier(exp):
    tier = 3
    if exp >= 5000:
        tier = 1
    elif exp >= 2000:
        tier = 2
    return tier

# Still requires some touchup based on the Google API implementation
@app.route("/login", methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify(user.json()),201
    return jsonify({'message': 'Unsuccessful login'}), 404

@app.route("/register", methods=['POST'])
def register():
    data = request.get_json()

    if User.query.filter_by(email = data['email']).first():
        return jsonify({'message': 'An account tied to that email has already been registered'}), 404
    elif User.query.filter_by(telehandle = data['telehandle']).first():
        return jsonify({'message': 'An account tied to that telehandle has already been registered'}), 404
    else:
        user = User(userID=None,name=data['name'],email=data['email'],telehandle=data['telehandle'],teleID=None,point=0,exp=0)
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
    return jsonify({'message': 'User not found for id ' + str(userID)}), 404

@app.route("/view")
def view_users():
    data = request.args
    createID()
    users = User.query.all()
    result = []
    tier = str(data['tier']) if 'tier' in data else '123'
    for user in users:
        if str(getTier(user.exp)) in tier:
            result.append(user.json())
    return jsonify(result)

@app.route("/use", methods=['PUT'])
def usePoints():
    data = request.get_json()
    userID = data['userID']
    points = int(data['points'])
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
        result['dedeuction'] = points/100

    return jsonify(result),status


def receiveAmt():
    hostname = "localhost" # default host
    port = 5672 # default port
    # connect to the broker and set up a communication channel in the connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=hostname, port=port))
    channel = connection.channel()

    # set up the exchange if the exchange doesn't exist
    exchangename="rewards_direct"
    channel.exchange_declare(exchange=exchangename, exchange_type='direct')

    # prepare a queue for receiving messages
    channelqueue = channel.queue_declare(queue='', exclusive=True) # '' indicates a random unique queue name; 'exclusive' indicates the queue is used only by this receiver and will be deleted if the receiver disconnects.
        # If no need durability of the messages, no need durable queues, and can use such temp random queues.
    queue_name = channelqueue.method.queue
    channel.queue_bind(exchange=exchangename, queue=queue_name, routing_key='rewards.info') # bind the queue to the exchange via the key
        # Can bind the same queue to the same exchange via different keys

    # set up a consumer and start to wait for coming messages
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming() # an implicit loop waiting to receive messages; it doesn't exit by default. Use Ctrl+C in the command window to terminate it.

def callback(channel, method, properties, body): # required signature for the callback; no return
    print("Received a successful amount by " + __file__)
    updatePoints(json.loads(body))
    print() # print a new line feed

def updatePoints(amt): # Assumes {'userID': userID, 'amt': amount }
    print("Recording a successful transaction amt:")
    print(amt)
    user = User.query.filter_by(user_id=amt['userID']).first()
    user.point = User.point + amt['amt'] * 10
    user.exp = User.exp + amt['amt'] * 10
    db.session.commit()

def user_ID():
    users = User.query.all()

    userIDs = {}
    for user in users:
        userIDs[user.telehandle] = user.teleID

    return userIDs

def createID():
    userIDs = user_ID()

    with urllib.request.urlopen("https://api.telegram.org/bot1072538370:AAH2EvVRZJUpoE0SfIXgD2KKrrsN8E8Flq4/getupdates") as url:
        data = json.loads(url.read().decode())

        for message in data['result']:
            if 'message' in message:
                username = message['message']['from']['username']
                userID = message['message']['from']['id']

                if username in userIDs and userIDs[username] is None:
                    userIDs[username] = userID
                    user = User.query.filter_by(telehandle=username).first()
                    user.teleID = userID
                    db.session.commit()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)

