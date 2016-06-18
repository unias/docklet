from flask import session, request, abort, redirect
from functools import wraps
from webViews.log import logger

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        if request.method == 'POST' :
            if not is_authenticated():
                abort(401)
            else:
                return func(*args, **kwargs)
        else:
            if not is_authenticated():
                return redirect("/login/" + "?next=" + request.path)
            else:
                return func(*args, **kwargs)

    return wrapper

def administration_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_admin():
            abort(401)
        else:
            return func(*args, **kwargs)


    return wrapper

def activated_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_activated():
            abort(401)
        else:
            return func(*args, **kwargs)


    return wrapper

def is_authenticated():
    if "username" in session:
        return True
    else:
        return False
def is_admin():
    if not "username" in session:
        return False
    if not (session['usergroup'] == 'root' or session['usergroup'] == 'admin'):
        return False
    return True

def is_activated():
    if not "username" in session:
        return False
    if not (session['status']=='normal'):
        return False
    return True
