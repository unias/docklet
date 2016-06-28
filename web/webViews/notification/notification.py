import json

from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class NotificationView(normalView):
    template_path = 'notification.html'

    @classmethod
    def get(cls):
        result = dockletRequest.post('/notification/list/')
        groups = dockletRequest.post('/user/groupNameList/')['groups']
        notifications = result['data']
        return cls.render(cls.template_path, notifications=notifications, groups=groups)


class CreateNotificationView(normalView):
    template_path = 'create_notification.html'

    @classmethod
    def get(cls):
        groups = dockletRequest.post('/user/groupNameList/')['groups']
        return cls.render(cls.template_path, groups=groups)

    @classmethod
    def post(cls):
        dockletRequest.post('/notification/create/', request.form)
        # return redirect('/admin/')
        return redirect('/notification/')


class QuerySelfNotificationsView(normalView):
    @classmethod
    def post(cls):
        result = dockletRequest.post('/notification/query_self/')
        return json.dumps(result)


class QueryNotificationView(normalView):
    template_path = 'notification_info.html'

    @classmethod
    def get_by_id(cls, notify_id):
        notifies = []
        if notify_id == 'all':
            notifies.extend(dockletRequest.post('/notification/query/all/')['data'])
        else:
            notifies.append(dockletRequest.post('/notification/query/', data={'notify_id': notify_id})['data'])
        return cls.render(cls.template_path, notifies=notifies)


class ModifyNotificationView(normalView):
    @classmethod
    def post(cls):
        dockletRequest.post('/notification/modify/', request.form)
        return redirect('/notification/')

class MailNotificationView(normalView):
    @classmethod
    def post(cls):
        dockletRequest.post('/notification/mail/', request.form)
        return redirect('/notification/')

class DeleteNotificationView(normalView):
    @classmethod
    def post(cls):
        dockletRequest.post('/notification/delete/', request.form)
        return redirect('/notification/')
