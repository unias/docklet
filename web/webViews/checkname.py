import re
from flask import abort, session

pattern = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')
error_msg = ''' Your name may cause errors, Please use names starting with a-z,A-Z or _ and contains only elements in {a-z, A-Z, _, 0-9}
'''
error_title = 'Input Error'

def checkname(str):
    try:
        match = pattern.match(str)
        if (match == None):
            session['500'] = error_msg
            session['500_title'] = error_title
            abort(500)
        if (match.group() != str):
            session['500'] = error_msg
            session['500_title'] = error_title
            abort(500)
        return True
    except:
        session['500'] = error_msg
        session['500_title'] = error_title
        abort(500)
