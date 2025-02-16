import os
import json
import base64
from tinydb import Query
from fastapi import APIRouter, Header
from api.models.body import response_body, User, UserInfo, UserSecurityInfo
from api.models.db_init import ensure_db
from api.models.regular_manager import validate_username
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import valid_user
import asyncio

router = APIRouter()

apply_lock = asyncio.Lock()

pwd_prefix = 'pku_dair'

with open('./api/app_config.json') as f:
    app_config = json.load(f)

user_db = ensure_db('user_db.json')


@router.post("/apply_user")
async def apply(user: User):
    if user.userid == app_config['root_name']:
        return response_body(code=4001, status='failed', message='invlid invite userid: illegal userid)')
    if user.invite_code != app_config['invite_code']:
        return response_body(code=403, status='failed', message='invlid invite code')
    if not validate_username(user.userid):
        return response_body(code=4001, status='failed', message='invlid invite userid: must be Email, Number only, letter only, or letter + number (letter first)')
    if len(user.pwd) < 6:
        return response_body(code=4002, status='failed', message='passwords too short')
    async with apply_lock:
        if user_db.search(lambda x: x['userid'] == user.userid):
            return response_body(code=4003, status='failed', message='User already exists')

        user_data = user.dict()  # 将 Pydantic 模型转换为字典
        encode_pwd = pwd_prefix + user_data['pwd']
        encode_pwd = encode_pwd.encode('utf-8')
        encode_pwd = base64.b64encode(encode_pwd)
        encode_pwd = encode_pwd.decode('utf-8')
        user_data['pwd'] = encode_pwd
        user_db.insert(user_data)

    return response_body(code=200, status='success', message='User registered successfully', data=user_data)


@router.post("/login")
async def login(user: User):
    if user.userid == app_config['root_name'] and user.pwd == app_config['root_pwd']:
        role = 'admin'
        token = create_jwt(
            {'userid': user.userid, 'role': role}, key=app_config['jwt_key'])
        return response_body(data={'token': token, 'userid': user.pwd, 'role': role})
    user_data = user.dict()

    async with apply_lock:
        User = Query()
        result = user_db.search(User.userid == user_data['userid'])
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='user does not exists')
        pwd = user_data['pwd']
        encode_pwd = pwd_prefix + pwd
        encode_pwd = encode_pwd.encode('utf-8')
        encode_pwd = base64.b64encode(encode_pwd)
        encode_pwd = encode_pwd.decode('utf-8')
        if encode_pwd != result[0]['pwd']:
            return response_body(code=403, status='failed', message='password error')
        role = result[0]['role']
        if role is None:
            role = 'user'
        token = create_jwt(
            {'userid': user_data['userid'], 'role': role}, key=app_config['jwt_key'])
        return response_body(data={'token': token, 'userid': user_data['userid'], 'role': role})


@router.get("/info_me")
async def get_my_info(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    userid = valid_info['userid']
    async with apply_lock:
        User = Query()
        result = user_db.search(User.userid == userid)
        if len(result) == 0:
            user = UserInfo().dict()
            result.append(user)
        remove_key = ['pwd', 'avatar']
        for key in remove_key:
            del result[0][key]

    return response_body(code=200, data=result[0])


@router.post("/update_me")
async def update_myself(user: UserInfo, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    userid = valid_info['userid']
    user_data = user.dict()
    remove_key = ['userid', 'pwd', 'invite_code']
    for key in remove_key:
        del user_data[key]
    final_data = {}
    for key in user_data:
        if user_data[key] is not None:
            final_data[key] = user_data[key]
    async with apply_lock:
        User = Query()
        user_db.update(final_data, User.userid == userid)
        result = user_db.search(User.userid == userid)
        for key in remove_key:
            del result[0][key]

    return response_body(code=200, status='success', message='Update user info successfully', data=result[0])


@router.post("/update_pwd")
async def update_pwd_when_login(user: UserSecurityInfo, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    userid = valid_info['userid']
    pwd = user.pwd
    confirm_pwd = user.confirm_pwd
    async with apply_lock:
        User = Query()
        result = user_db.search(User.userid == userid)
        encode_pwd = pwd_prefix + pwd
        encode_pwd = encode_pwd.encode('utf-8')
        encode_pwd = base64.b64encode(encode_pwd)
        encode_pwd = encode_pwd.decode('utf-8')
        if result[0]['pwd'] != encode_pwd:
            return response_body(code=403, status='failed', message='password error')
        encode_pwd = pwd_prefix + confirm_pwd
        encode_pwd = encode_pwd.encode('utf-8')
        encode_pwd = base64.b64encode(encode_pwd)
        encode_pwd = encode_pwd.decode('utf-8')
        user_db.update({'pwd': encode_pwd}, User.userid == userid)

    return response_body(code=200, status='success', message='Update user password successfully')


@router.get("/user/get_users")
def get_users(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    all_data = user_db.all()
    for data in all_data:
        data['pwd'] = ""
    res = response_body(data=all_data)
    return res()
