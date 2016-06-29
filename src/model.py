#coding=utf-8
'''
2 tables: users, usergroup
User:
    id
    username
    password
    avatar
    nickname
    description
    status
    student_number
    department
    truename
    tel
    e_mail
    register_date
    user_group
    auth_method

Usergroup
    id
    name

Token expiration can be set in User.generate_auth_token
'''
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import datetime
from base64 import b64encode, b64decode
import os

#this class from itsdangerous implements token<->user
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired, BadSignature

import env

fsdir = env.getenv('FS_PREFIX')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+fsdir+'/global/sys/UserTable.db'
try:
    secret_key_file = open(env.getenv('FS_PREFIX') + '/local/token_secret_key.txt')
    app.secret_key = secret_key_file.read()
    secret_key_file.close()
except:
    from os import urandom
    secret_key = urandom(24)
    secret_key = b64encode(secret_key).decode('utf-8')
    app.secret_key = secret_key
    secret_key_file = open(env.getenv('FS_PREFIX') + '/local/token_secret_key.txt', 'w')
    secret_key_file.write(secret_key)
    secret_key_file.close()

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10), unique=True)
    password = db.Column(db.String(100))
    avatar = db.Column(db.String(30))
    nickname = db.Column(db.String(10))
    description = db.Column(db.String(15))
    status = db.Column(db.String(10))
    e_mail = db.Column(db.String(20))
    student_number = db.Column(db.String(20))
    department = db.Column(db.String(20))
    truename = db.Column(db.String(20))
    tel = db.Column(db.String(20))
    register_date = db.Column(db.String(10))
    user_group = db.Column(db.String(50))
    auth_method = db.Column(db.String(10))


    def __init__(self, username, password, avatar="default.png", nickname = "", description = "", status = "init",
                    e_mail = "" , student_number = "", department = "", truename = "", tel="", date = None, usergroup = "primary"
                , auth_method = "local"):
        # using sha512
        #if (len(password) <= 6):
        #    self = None
        #    return None
        self.username = username
        self.password = password
        self.avatar = avatar
        self.nickname = nickname
        self.description = description
        self.status = status
        self.e_mail = e_mail
        self.student_number = student_number
        self.department = department
        self.truename = truename
        self.tel = tel
        if (date != None):
            self.register_date = date
        else:
            self.register_date = datetime.utcnow()
        self.user_group = usergroup
        self.auth_method = auth_method

    def __repr__(self):
        return '<User %r>' % self.username

    #token will expire after 3600s
    def generate_auth_token(self, expiration = 3600):
        s = Serializer(app.config['SECRET_KEY'], expires_in = expiration)
        str = s.dumps({'id': self.id})
        return b64encode(str).decode('utf-8')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(b64decode(token))
        except SignatureExpired:
            return None # valid token, but expired
        except BadSignature:
            return None # invalid token
        user = User.query.get(data['id'])
        return user


class UserGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    cpu = db.Column(db.String(10))
    memory = db.Column(db.String(10))
    imageQuantity = db.Column(db.String(10))
    lifeCycle = db.Column(db.String(10))

    def __init__(self, name):
        self.name = name
        self.cpu = '100000'
        self.memory = '2000'
        self.imageQuantity = '10'
        self.lifeCycle = '24'

    def __repr__(self):
        return '<UserGroup %r>' % self.name


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.String(8000))
    create_date = db.Column(db.String(10))
    # Status: 'open' -> Open to user, 'closed' -> Closed to user
    status = db.Column(db.String(20))

    def __init__(self, title, content=''):
        self.title = title
        self.content = content
        self.create_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.status = 'open'

    def __repr__(self):
        return '<Notification %r>' % self.title


class NotificationGroups(db.Model):
    # __tablename__ = 'notification_groups'
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer)
    group_name = db.Column(db.String(100))

    def __init__(self, notification_id, group_name):
        self.notification_id = notification_id
        self.group_name = group_name

    def __repr__(self):
        return '<Notification: %r, Group: %r>' % (self.notification_id, self.group_name)
