import os
import json
import base64
import datetime
from typing import Optional
from tortoise.expressions import Q
from fastapi import APIRouter, File, UploadFile
from api.models.body import response_body, User, UserInfo, UserSecurityInfo
from api.models.db_init import ensure_folder
from api.models.regular_manager import validate_username
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import Auth
from api.models.db_models import UserDBModel
from api.utils.image_compress import clear_compressed_image_cache, get_compressed_image_data_url

router = APIRouter(tags=['User'])

pwd_prefix = 'pku_dair'

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


def _encode_pwd(raw_pwd: str) -> str:
    return base64.b64encode(f'{pwd_prefix}{raw_pwd}'.encode('utf-8')).decode('utf-8')


def _sanitize_user(data: dict) -> dict:
    safe_data = data.copy()
    safe_data.pop('pwd', None)
    safe_data.pop('avatar', None)
    return safe_data


@router.post('/apply_user', summary='Apply for a user account', operation_id='ApplyUser')
async def apply(user: User):
    if user.userid == app_config['root_name']:
        return response_body(code=4001, status='failed', message='invlid invite userid: illegal userid)')
    if user.invite_code != app_config['invite_code']:
        return response_body(code=403, status='failed', message='invlid invite code')
    if not validate_username(user.userid):
        return response_body(code=4001, status='failed', message='invlid invite userid: must be Email, Number only, letter only, or letter + number (letter first)')
    if len(user.pwd) < 6:
        return response_body(code=4002, status='failed', message='passwords too short')

    if await UserDBModel.filter(userid=user.userid).exists():
        return response_body(code=4003, status='failed', message='User already exists')

    user_data = user.dict()
    user_data['pwd'] = _encode_pwd(user_data['pwd'])
    user_data['apply_time'] = datetime.datetime.now().isoformat()
    await UserDBModel.create(**user_data)

    return response_body(code=200, status='success', message='User registered successfully', data=user_data)


@router.post('/login', summary='Login', operation_id='Login')
async def login(user: User):
    if user.userid == app_config['root_name'] and user.pwd == app_config['root_pwd']:
        role = 'admin'
        token, exp = create_jwt({'userid': user.userid, 'role': role}, key=app_config['jwt_key'])
        return response_body(data={'token': token, 'userid': user.userid, 'role': role, 'exp': exp})

    result_list = await UserDBModel.filter(userid=user.userid).values('userid', 'pwd', 'role')
    if len(result_list) == 0:
        return response_body(code=4004, status='failed', message='user does not exist')
    result = result_list[0]

    if _encode_pwd(user.pwd) != result['pwd']:
        return response_body(code=403, status='failed', message='password error')

    role = result.get('role') or 'user'
    token, exp = create_jwt({'userid': user.userid, 'role': role}, key=app_config['jwt_key'])
    await UserDBModel.filter(userid=user.userid).update(last_login=datetime.datetime.now().isoformat())
    return response_body(data={'token': token, 'userid': user.userid, 'role': role, 'exp': exp})


@router.get('/info_me', summary='Get user info', operation_id='GetUserInfo')
@auth.require_user()
async def get_my_info(valid_info=None):
    userid = valid_info['userid']
    result_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    if len(result_list) == 0:
        user = UserInfo().dict()
        if userid == app_config['root_name']:
            user['userid'] = app_config['root_name']
            user['role'] = 'admin'
        result = user
    else:
        result = result_list[0]
    result = _sanitize_user(result)
    return response_body(code=200, data=result)


@router.post('/update_me', summary='Update user info', operation_id='UpdateUserInfo')
@auth.require_user()
async def update_myself(user: UserInfo, valid_info=None):
    userid = valid_info['userid']
    user_data = user.dict()
    remove_key = ['userid', 'pwd', 'invite_code', 'apply_time', 'last_login']
    for key in remove_key:
        user_data.pop(key, None)
    final_data = {k: v for k, v in user_data.items() if v is not None}

    await UserDBModel.filter(userid=userid).update(**final_data)
    result_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    if len(result_list) == 0:
        return response_body(code=404, status='failed', message='user does not exist')
    result = result_list[0]

    result = _sanitize_user(result)
    return response_body(code=200, status='success', message='Update user info successfully', data=result)


@router.post('/update_pwd', summary='Update user password', operation_id='UpdateUserPassword')
@auth.require_user()
async def update_pwd_when_login(user: UserSecurityInfo, valid_info=None):
    userid = valid_info['userid']
    result_list = await UserDBModel.filter(userid=userid).values('pwd')
    if len(result_list) == 0:
        return response_body(code=404, status='failed', message='user does not exist')
    result = result_list[0]

    if result['pwd'] != _encode_pwd(user.pwd):
        return response_body(code=403, status='failed', message='password error')

    await UserDBModel.filter(userid=userid).update(pwd=_encode_pwd(user.confirm_pwd))
    return response_body(code=200, status='success', message='Update user password successfully')


@router.post('/reset_pwd', summary='Reset user password (Admin)', operation_id='ResetUserPassword')
@auth.require_admin()
async def reset_user_pwd(user: UserSecurityInfo, valid_info=None):
    userid = user.userid
    if userid == app_config['root_name']:
        return response_body(code=400, status='failed', message='root user password cannot be reset here')

    user_exists = await UserDBModel.filter(userid=userid).exists()
    if not user_exists:
        return response_body(code=404, status='failed', message='user does not exist')

    await UserDBModel.filter(userid=userid).update(pwd=_encode_pwd(userid))
    return response_body(
        code=200,
        status='success',
        message='Reset user password successfully',
        data={'userid': userid, 'pwd': userid}
    )


@router.get('/user/get_users', summary='Get all users (Admin)', operation_id='GetAllUsers')
@auth.require_admin()
async def get_users(valid_info=None):
    all_data = await UserDBModel.all().values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    for data in all_data:
        data['pwd'] = ''
    res = response_body(data=all_data)
    return res()


@router.get('/list_users', summary='List users (Admin)', operation_id='ListUsers')
@auth.require_admin()
async def list_users(search: Optional[str] = None, offset: int = 0, limit: int = 20):
    user_fields = ['userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login']
    if search:
        users = await UserDBModel.filter(Q(userid__icontains=search) | Q(email__icontains=search)).values(*user_fields)
    else:
        users = await UserDBModel.all().values(*user_fields)

    paginated_users = users[offset:offset + limit]
    for item in paginated_users:
        item.pop('pwd', None)
        item.pop('avatar', None)

    return response_body(data=paginated_users)


@router.get('/list_users_size', summary='Get total user count (Admin)', operation_id='GetTotalUserCount')
@auth.require_admin()
async def list_users_size(search: Optional[str] = None):
    if search:
        total_users = await UserDBModel.filter(Q(userid__icontains=search) | Q(email__icontains=search)).count()
    else:
        total_users = await UserDBModel.all().count()
    return response_body(data=total_users)


@router.post('/upload_avatar', summary='Upload user avatar', operation_id='UploadAvatar')
@auth.require_user()
async def upload_avatar(user_avatar: UploadFile = File(...), valid_info=None):
    user_id = valid_info['userid']
    image_dir = f'user/{user_id}'
    ensure_folder(image_dir)
    clear_compressed_image_cache(image_dir)
    file_path = os.path.join(image_dir, 'avatar.jpg')
    with open(file_path, 'wb') as buffer:
        buffer.write(user_avatar.file.read())
    return response_body(code=200, status='success', message='Avatar uploaded successfully', data={'file_path': file_path})


@router.get('/user/avatar', summary='Get user avatar', operation_id='GetUserAvatar')
async def get_user_avatar(id):
    image_dir = f'user/{id}'
    file_path = os.path.join(image_dir, 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    return response_body(code=200, status='success', data=get_compressed_image_data_url(image_dir))


@router.get('/me/avatar', summary='Get my avatar', operation_id='GetMyAvatar')
@auth.require_user()
async def get_my_avatar(valid_info=None):
    user_id = valid_info['userid']
    image_dir = f'user/{user_id}'
    file_path = os.path.join(image_dir, 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    return response_body(code=200, status='success', data=get_compressed_image_data_url(image_dir))


@router.get('/user/get_users_roles', summary='Get all user roles (Admin)', operation_id='GetAllUserRoles')
@auth.require_admin()
async def get_users_roles():
    roles = [{'id': 'user', 'name': 'User'}, {'id': 'admin', 'name': 'Admin'}]
    res = response_body(data=roles)
    return res()


@router.post('/add/role', summary='Add user role (Admin)', operation_id='AddUserRole')
@auth.require_admin()
async def add_user_role(user: UserInfo):
    userid = user.userid
    add_role = user.role
    user_data_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    if len(user_data_list) == 0:
        return response_body(code=404, status='failed', message='user does not exist')
    user_data = user_data_list[0]

    ori_role = user_data.get('role')
    if ori_role is None:
        ori_role = add_role
    elif ori_role.find(add_role) < 0:
        role_list = ori_role.split(',')
        role_list.append(add_role)
        ori_role = ','.join(role_list)

    await UserDBModel.filter(userid=userid).update(role=ori_role)
    result_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    result = result_list[0]
    result = _sanitize_user(result)
    return response_body(code=200, status='success', message='Update user info successfully', data=result)


@router.post('/del/role', summary='Remove user role (Admin)', operation_id='RemoveUserRole')
@auth.require_admin()
async def remove_user_role(user: UserInfo):
    userid = user.userid
    del_role = user.role
    user_data_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    if len(user_data_list) == 0:
        return response_body(code=404, status='failed', message='user does not exist')
    user_data = user_data_list[0]

    ori_role = user_data.get('role')
    if ori_role is None:
        new_role = []
    else:
        new_role = []
        for role in ori_role.split(','):
            if role == del_role:
                continue
            new_role.append(role)
    new_role = ','.join(new_role)

    await UserDBModel.filter(userid=userid).update(role=new_role)
    result_list = await UserDBModel.filter(userid=userid).values(
        'userid', 'name', 'pwd', 'avatar', 'email', 'phone', 'gender', 'invite_code', 'role', 'apply_time', 'last_login'
    )
    result = result_list[0]
    result = _sanitize_user(result)
    return response_body(code=200, status='success', message='Update user info successfully', data=result)
