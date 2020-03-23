from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

from datetime import datetime
import json
import pika

import csv
import urllib.request, time

app = Flask(__name__)
# TODO: Change the name of the database when moved to cloud
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost:3306/customer'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

class User(db.Model):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    point = db.Column(db.Integer(), nullable=False)
    exp = db.Column(db.Integer(), nullable=False)
    telehandle = db.Column(db.String(32), nullable=False)
    tele_id = db.Column(db.Integer())
    email = db.Column(db.String(64))

    def json(self):
        return {'user_id': self.user_id, 'name': self.name, 'point': self.point, 'exp': self.exp, 'telehande': self.telehandle, 'tele_id': self.tele_id, 'email': self.email, 'tier': getTier(self.exp)}


def getTier(exp):
    tier = 3
    if exp >= 5000:
        tier = 1
    elif exp >= 2000:
        tier = 2
    return tier

@app.route("/ESDproject/login", methods=['POST'])
def g_login():
    data = request.get_json()
    # depending on the data given by Google, we may need to use the ID associated to google
    user_id = data['user_id']
    user = User.query.filter_by(user_id=user_id).first()
    if user:
        return jsonify(user.json())
    return jsonify({'message': 'User not found for id ' + str(user_id)}), 404

@app.route("/ESDproject/viewUser/<int:user_id>")
def view_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if user:
        return jsonify(user.json())
    return jsonify({'message': 'User not found for id ' + str(user_id)}), 404

@app.route("/ESDproject/view")
def view_users():
    data = request.args
    createID()
    users = User.query.all()
    result = []
    tier = str(data['tier'])
    for user in users:
        if str(getTier(user.exp)) in tier:
            result.append(user.json())
    return jsonify(result)

@app.route("/ESDproject/use", methods=['POST'])
def usePoints():
    data = request.get_json()
    user_id = data['user_id']
    points = int(data['points'])
    status = 201
    result = {"status": status, "message": "Points used!"}

    user = User.query.filter_by(user_id=user_id).first()

    if user.point < points:
        status = 500
        result = {"message": "Insufficient points!"}
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

def updatePoints(amt): # Assumes {'user_id': user_id, 'amt': amount }
    print("Recording a successful transaction amt:")
    print(amt)
    user = User.query.filter_by(user_id=amt['user_id']).first()
    user.point = User.point + amt['amt'] * 10
    user.exp = User.exp + amt['amt'] * 10
    db.session.commit()

def login():
    data = request.get_json()
    user_id = data['user_id']
    status = 201
    result = {}

    user = User.query.filter_by(user_id=user_id).first()

    if (user):
        result = {"Welcome to Petrol Home"}
    else:
        return jsonify({"message": "Invalid 'user_id'"}), 404

    return jsonify(result), status

def userID():
    users = User.query.all()

    user_ids = {}
    for user in users:
        user_ids[user.telehandle] = user.tele_id

    return user_ids

def createID():
    user_ids = userID()
    with urllib.request.urlopen("https://api.telegram.org/bot1072538370:AAH2EvVRZJUpoE0SfIXgD2KKrrsN8E8Flq4/getupdates") as url:
        data = json.loads(url.read().decode())
        for message in data['result']:
            if 'message' in message:
                username = message['message']['from']['username']
                user_id = message['message']['from']['id']
                if username in user_ids and user_ids[username] is None:
                    user_ids[username] = user_id
                    user = User.query.filter_by(telehandle=username).first()
                    user.tele_id = user_id
                    db.session.commit()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)

