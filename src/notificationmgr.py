import json

from log import logger
from model import db, Notification, NotificationGroups
from userManager import administration_required, token_required
import env

class NotificationMgr:
    def __init__(self):
        logger.info("Notification Manager init...")
        try:
            Notification.query.all()
        except:
            db.create_all()
        try:
            NotificationGroups.query.all()
        except:
            db.create_all()
        logger.info("Notification Manager init done!")

    def query_user_notifications(self, user):
        group_name = user.user_group
        notifies = NotificationGroups.query.filter_by(group_name=group_name).all()
        notifies.extend(NotificationGroups.query.filter_by(group_name='all').all())
        notify_ids = [notify.notification_id for notify in notifies]
        notify_ids = sorted(list(set(notify_ids)), reverse=True)
        return [Notification.query.filter_by(id=notify_id).first() for notify_id in notify_ids]

    def mail_notification(self, notify_id):
        email_from_address = env.getenv('EMAIL_FROM_ADDRESS')
        if (email_from_address in ['\'\'', '\"\"', '']):
            return {'success' : 'true'}
        notify = Notification.query.filter_by(id=notify_id).first()
        notify_groups = NotificationGroups.query.filter_by(notification_id=notify_id).all()
        to_addr = []
        if 'all' in notify_groups:
            users = User.query.all()
            for user in users:
                to_addr.extend(user.e_mail)
        else:
            for group in notify_groups:
                users = User.query.filter_by(user_group=group.group_name).all()
                for user in users:
                    to_addr.extend(user.e_mail)

        content = notify.content
        text = '<html><h4>Dear '+ user.username + ':</h4>'
        text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Your account in <a href='%s'>%s</a> has been recieved a notification:</p>
                   <p>%s</p>
                   <br>
                   <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Note: DO NOT reply to this email!</p>
                   <br><br>
                   <p> <a href='http://docklet.unias.org'>Docklet Team</a>, SEI, PKU</p>
                ''' % (env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"), content)
        text += '<p>'+  str(datetime.utcnow()) + '</p>'
        text += '</html>'
        subject = 'Docklet Notification: ' + notify.title
        msg = MIMEMultipart()
        textmsg = MIMEText(text,'html','utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = email_from_address
        msg.attach(textmsg)
        s = smtplib.SMTP()
        s.connect()
        for address in to_addr:
            msg['To'] = address
            s.sendmail(email_from_address, address, msg.as_string())
        s.close()
        return {"success": 'true'}

    @administration_required
    def create_notification(self, *args, **kwargs):
        '''
        Usage: createNotification(cur_user = 'Your current user', form = 'Post form')
        Post form: {title: 'Your title', content: 'Your content', groups: "['groupA', 'groupB']"}
        '''
        form = kwargs['form']
        notify = Notification(form['title'], form['content'])
        group_names = form.getlist('groups')
        db.session.add(notify)
        db.session.commit()
        # groups = json.loads(form['groups'])
        # for group_name in groups:
        if 'all' in group_names:
            group_names = ['all']
        for group_name in group_names:
            if group_name == 'none':
                continue
            notify_groups = NotificationGroups(notify.id, group_name)
            db.session.add(notify_groups)
        db.session.commit()
        return {"success": 'true'}

    @administration_required
    def list_notifications(self, *args, **kwargs):
        notifies = Notification.query.all()
        notify_infos = []
        for notify in notifies:
            if notify is None or notify.status == 'deleted':
                continue
            groups = NotificationGroups.query.filter_by(notification_id=notify.id).all()
            notify_infos.append({
                'id': notify.id,
                'title': notify.title,
                'content': notify.content,
                'create_date': notify.create_date,
                'status': notify.status,
                'groups': [group.group_name for group in groups]
            })
        notify_infos.reverse()
        return {'success': 'true', 'data': notify_infos}

    @administration_required
    def modify_notification(self, *args, **kwargs):
        form = kwargs['form']
        notify_id = form['notify_id']
        notify = Notification.query.filter_by(id=notify_id).first()
        notify.title = form['title']
        notify.content = form['content']
        notify.status = form['status']
        notifies_groups = NotificationGroups.query.filter_by(notification_id=notify_id).all()
        for notify_groups in notifies_groups:
            db.session.delete(notify_groups)
        group_names = form.getlist('groups')
        if 'all' in group_names:
            group_names = ['all']
        for group_name in group_names:
            if group_name == 'none':
                continue
            notify_groups = NotificationGroups(notify.id, group_name)
            db.session.add(notify_groups)
        db.session.commit()
        if 'sendMail' in form:
            self.mail_notification(notify_id)
        return {"success": 'true'}

    @administration_required
    def delete_notification(self, *args, **kwargs):
        form = kwargs['form']
        notify_id = form['notify_id']
        notify = Notification.query.filter_by(id=notify_id).first()
        # notify.status = 'deleted'
        notifies_groups = NotificationGroups.query.filter_by(notification_id=notify_id).all()
        for notify_groups in notifies_groups:
            db.session.delete(notify_groups)
        db.session.delete(notify)
        db.session.commit()
        return {"success": 'true'}

    @token_required
    def query_self_notification_simple_infos(self, *args, **kwargs):
        user = kwargs['cur_user']
        notifies = self.query_user_notifications(user)
        notify_simple_infos = []
        for notify in notifies:
            if notify is None or notify.status != 'open':
                continue
            notify_simple_infos.append({
                'id': notify.id,
                'title': notify.title,
                'create_date': notify.create_date
            })
        return {'success': 'true', 'data': notify_simple_infos}

    @token_required
    def query_self_notifications_infos(self, *args, **kwargs):
        user = kwargs['cur_user']
        notifies = self.query_user_notifications(user)
        notify_infos = []
        for notify in notifies:
            if notify is None or notify.status != 'open':
                continue
            notify_infos.append({
                'id': notify.id,
                'title': notify.title,
                'content': notify.content,
                'create_date': notify.create_date
            })
        return {'success': 'true', 'data': notify_infos}

    @token_required
    def query_notification(self, *args, **kwargs):
        user = kwargs['cur_user']
        form = kwargs['form']
        group_name = user.user_group
        notify_id = form['notify_id']
        groups = NotificationGroups.query.filter_by(notification_id=notify_id).all()
        if not(group_name in [group.group_name for group in groups]):
            if not('all' in [group.group_name for group in groups]):
                return {'success': 'false', 'reason': 'Unauthorized Action'}
        notify = Notification.query.filter_by(id=notify_id).first()
        notify_info = {
            'id': notify.id,
            'title': notify.title,
            'content': notify.content,
            'create_date': notify.create_date
        }
        if notify.status != 'open':
            notify_info['title'] = 'This notification is not available'
            notify_info['content'] = 'Sorry, it seems that the administrator has closed this notification.'
            return {'success': 'false', 'data': notify_info}
        return {'success': 'true', 'data': notify_info}
