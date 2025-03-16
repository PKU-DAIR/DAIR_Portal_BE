import datetime
from fastapi import Header
from api.models.body import response_body
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

class Auth():

    def __init__(self, app_config, algorithms=['HS256']):
        self.app_config = app_config
        self.algorithms = algorithms
    
    @staticmethod
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
    
    async def is_user(self, api_key: str = Header(None)):
        valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
        if not valid_status:
            return (False, response_body(code=403, status='failed', message=valid_info['message']))
        return (True, valid_info)
    
    async def is_admin(self, api_key: str = Header(None)):
        valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
        if not valid_status:
            return (False, response_body(code=403, status='failed', message=valid_info['message']))
        role = valid_info['role']
        if role.find('admin') < 0:
            return (False, response_body(code=403, status='failed', message='permission denied'))
        return (True, valid_info)