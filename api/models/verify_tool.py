import datetime
from api.models.jwt_tool import decode_jwt


def valid_user(token, jwt_key, algorithms=['HS256']):
    if token is None:
        return {
                'status': 1,
                'islogin': False,
                'userid': None,
                'role': None,
                'message': 'no token info'
            }, False
    decode_item = decode_jwt(token, jwt_key, algorithms)
    now = datetime.datetime.now().timestamp()
    try:
        if now >= decode_item['exp']:
            return {
                'status': 1,
                'islogin': False,
                'userid': None,
                'role': None,
                'message': 'expired'
            }, False
        return {
            'status': 0,
            'islogin': True,
            'userid': decode_item['userid'],
            'role': decode_item['role'],
            'message': ''
        }, True
    except:
        return {
            'status': 2,
            'islogin': False,
            'islogin': False,
            'userid': None,
            'role': None,
            'message': 'error'
        }, False
