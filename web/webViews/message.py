from flask import redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest

import json

class createmessageView(normalView):
    @classmethod
    def post(cls):
        return json.dumps(dockletRequest.post('/message/create/', request.form))

class querymessagelistView(normalView):
    @classmethod
    def post(cls):
        return json.dumps(dockletRequest.post('/message/queryList/', request.form))

class querymessageView(normalView):
    @classmethod
    def post(cls):
        return json.dumps(dockletRequest.post('/message/query/', request.form))