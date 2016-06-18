from model import db, Message, User
from functools import wraps
import hashlib
import pam
from base64 import b64encode
import env
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import json
from log import logger
from lvmtool import *
from userManager import token_required, administration_required

class messageManager:
    def __init__(self):
        logger.info("Message Manager init...")
        try:
            Message.query.all()
        except:
            db.create_all()
        logger.info("Message Manager init done...")

    @token_required
    def create_message(self, *args, **kwargs):
        '''
        Usage: create_message(cur_user = 'Your current user', form = 'Post form')
        Post form: { to_user: 'User receive', content: 'Your content', type: 'question' or 'answer' }
        '''
        cur_user = kwargs['cur_user']
        form = kwargs['form']
        message = ''
        if cur_user.user_group != 'root' and cur_user.user_group != 'admin':
            message = Message(form['content'], cur_user.id, -1, 'question')
        else:
            message = Message(form['content'], cur_user.id, form['to_user'], 'answer')
        db.session.add(message)
        db.session.commit()
        return { 'success' : 'true' }

    @administration_required
    def query_message_list(self, *args, **kwargs):
        cur_user = kwargs['cur_user']

        if cur_user.user_group != 'root' and cur_user.user_group != 'admin':
            return { 'success' : 'false', 'message' : 'invalid request', 'Unauthorized': 'True'}

        messages = db.session.query(Message.from_user, db.func.max(Message.send_date).label('last_message_date')).group_by(Message.from_user).all()
        #messages = Message.query.filter_by(from_user = cur_user.id).all()
        res = {
            'success' : 'true',
            'data' : [ {
                            'to_person_name' : db.session.query(User).filter(User.id == message.from_user).first().username,
                            'to_person_id' : message.from_user,
                            'last_message_date' : message.last_message_date
                       }  for message in messages ]
        }
        return res

    @token_required
    def query_messages(self, *args, **kwargs):
        cur_user = kwargs['cur_user']
        form = kwargs['form']
        user_id = None
        if cur_user.user_group == 'root' or cur_user.user_group == 'admin':
            user_id = form['user_id']
        else:
            user_id = cur_user.id
        if not user_id:
            return {'success': 'false', 'message': 'missing user_id parameter'}
        # logger.info('cnm %d'%user_id)
        messages = db.session.query(Message).filter(db.or_(Message.from_user == user_id, Message.to_user == user_id)).all()
        # messages.sort(lambda x: x)
        res = [
            {
                'from_user_name': db.session.query(User).filter(User.id == message.from_user).first().username,
                'from_user': message.from_user,
                'to_user': message.to_user,
                'content': message.content,
                'date': message.send_date,
                'type': message.type
            } for message in messages
        ]
        return {'success': 'true', 'data': res, 'query_id': cur_user.id}