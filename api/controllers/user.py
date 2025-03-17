import os
import json
import base64
import datetime
from tinydb import Query
from typing import Optional
from fastapi import APIRouter, Header, Depends, Form, File, UploadFile
from api.models.body import response_body, User, UserInfo, UserSecurityInfo
from api.models.db_init import ensure_db, ensure_folder
from api.models.regular_manager import validate_username
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import valid_user, Auth
import asyncio

router = APIRouter()

user_lock = asyncio.Lock()

pwd_prefix = 'pku_dair'

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

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
    async with user_lock:
        if user_db.search(lambda x: x['userid'] == user.userid):
            return response_body(code=4003, status='failed', message='User already exists')

        user_data = user.dict()  # 将 Pydantic 模型转换为字典
        encode_pwd = pwd_prefix + user_data['pwd']
        encode_pwd = encode_pwd.encode('utf-8')
        encode_pwd = base64.b64encode(encode_pwd)
        encode_pwd = encode_pwd.decode('utf-8')
        user_data['pwd'] = encode_pwd
        user_data['apply_time'] = datetime.datetime.now().isoformat()
        user_db.insert(user_data)

    return response_body(code=200, status='success', message='User registered successfully', data=user_data)


@router.post("/login")
async def login(user: User):
    if user.userid == app_config['root_name'] and user.pwd == app_config['root_pwd']:
        role = 'admin'
        token, exp = create_jwt(
            {'userid': user.userid, 'role': role}, key=app_config['jwt_key'])
        return response_body(data={'token': token, 'userid': user.userid, 'role': role, 'exp': exp})
    user_data = user.dict()

    async with user_lock:
        User = Query()
        result = user_db.search(User.userid == user_data['userid'])
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='user does not exist')
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
        token, exp = create_jwt(
            {'userid': user_data['userid'], 'role': role}, key=app_config['jwt_key'])
        user_db.update({'last_login': datetime.datetime.now(
        ).isoformat()}, User.userid == user_data['userid'])
        return response_body(data={'token': token, 'userid': user_data['userid'], 'role': role, 'exp': exp})


@router.get("/info_me")
async def get_my_info(vft=Depends(auth.is_user)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    userid = valid_info['userid']
    async with user_lock:
        User = Query()
        result = user_db.search(User.userid == userid)
        if len(result) == 0:
            user = UserInfo().dict()
            if userid == 'admin':
                user['userid'] = 'admin'
                user['role'] = 'admin'
            result.append(user)
        result = result[0].copy()
        remove_key = ['pwd', 'avatar']
        for key in remove_key:
            if key in result:
                del result[key]

    return response_body(code=200, data=result)


@router.post("/update_me")
async def update_myself(user: UserInfo, vft=Depends(auth.is_user)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    userid = valid_info['userid']
    user_data = user.dict()
    remove_key = ['userid', 'pwd', 'invite_code', 'apply_time', 'last_login']
    for key in remove_key:
        if key in user_data:
            del user_data[key]
    final_data = {}
    for key in user_data:
        if user_data[key] is not None:
            final_data[key] = user_data[key]
    async with user_lock:
        User = Query()
        user_db.update(final_data, User.userid == userid)
        result = user_db.search(User.userid == userid)
        result = result[0].copy()
        for key in remove_key:
            if key in result:
                del result[key]

    return response_body(code=200, status='success', message='Update user info successfully', data=result)


@router.post("/update_pwd")
async def update_pwd_when_login(user: UserSecurityInfo, vft=Depends(auth.is_user)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    userid = valid_info['userid']
    pwd = user.pwd
    confirm_pwd = user.confirm_pwd
    async with user_lock:
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
def get_users(vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    all_data = user_db.all()
    for data in all_data:
        data['pwd'] = ""
    res = response_body(data=all_data)
    return res()


@router.get("/list_users")
async def list_users(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
    vft=Depends(auth.is_admin)
):
    """
    获取用户列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    vft=Depends(auth.is_admin)
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with user_lock:
        UserQuery = Query()
        if search:
            # 模糊搜索用户名、昵称、邮箱等字段
            users = user_db.search(
                (UserQuery.userid.search(search)) |
                (UserQuery.email.search(search)))
        else:
            users = user_db.all()

        # 分页逻辑
        total_users = len(users)
        paginated_users = users[offset:offset + limit]

        paginated_users = paginated_users.copy()
        # 移除敏感信息（如密码）
        for user in paginated_users:
            user.pop('pwd', None)
            user.pop('avatar', None)

    return response_body(
        data=paginated_users
    )


@router.get("/list_users_size")
async def list_users_size(
    search: Optional[str] = None,
    vft=Depends(auth.is_admin)
):
    """
    获取用户总数（支持模糊搜索）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    vft=Depends(auth.is_admin)
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with user_lock:
        UserQuery = Query()
        if search:
            # 模糊搜索用户名、昵称、邮箱等字段
            users = user_db.search(
                (UserQuery.userid.search(search)) |
                (UserQuery.email.search(search)))
        else:
            users = user_db.all()

        total_users = len(users)

    return response_body(
        data=total_users
    )


@router.post("/upload_avatar")
async def upload_avatar(
    user_avatar: UploadFile = File(...),
    vft=Depends(auth.is_user)
):
    """
    上传用户头像
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    id = valid_info['userid']
    # 保存文件
    ensure_folder(f'user/{id}')
    file_path = os.path.join(f'user/{id}', 'avatar.jpg')
    with open(file_path, "wb") as buffer:
        buffer.write(user_avatar.file.read())

    return response_body(code=200, status='success', message='Avatar uploaded successfully', data={"file_path": file_path})


@router.get("/user/avatar")
async def get_user_avatar(id):
    """
    获取用户头像
    """
    file_path = os.path.join(f'user/{id}', 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    with open(file_path, "rb") as f:
        avatar_data = base64.b64encode(f.read()).decode('utf-8')

    return response_body(code=200, status='success', data=f'data:image/jpeg;base64,{avatar_data}')

@router.get("/me/avatar")
async def get_my_avatar(vft=Depends(auth.is_user)):
    """
    获取用户头像
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    id = valid_info['userid']
    
    file_path = os.path.join(f'user/{id}', 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    with open(file_path, "rb") as f:
        avatar_data = base64.b64encode(f.read()).decode('utf-8')

    return response_body(code=200, status='success', data=f'data:image/jpeg;base64,{avatar_data}')


@router.get("/user/get_users_roles")
def get_users_roles(vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    roles = [
        {"id": "user", "name": "User"}, {"id": "admin", "name": "Admin"}
    ]
    res = response_body(data=roles)
    return res()


@router.post("/add/role")
async def add_user_role(user: UserInfo, vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    userid = user.userid
    addRole = user.role
    async with user_lock:
        User = Query()
        ori_role = user_db.search(User.userid == userid)[0]['role']
        if ori_role is None:
            ori_role = addRole
        elif ori_role.find(addRole) < 0:
            ori_role = ori_role.split(',')
            ori_role.append(addRole)
            ori_role = ','.join(ori_role)

        user_db.update({'role': ori_role}, User.userid == userid)
        result = user_db.search(User.userid == userid)
        result = result[0].copy()
        remove_key = ['pwd', 'avatar']
        for key in remove_key:
            if key in result:
                del result[key]

    return response_body(code=200, status='success', message='Update user info successfully', data=result)


@router.post("/del/role")
async def remove_user_role(user: UserInfo, vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    userid = user.userid
    delRole = user.role
    async with user_lock:
        User = Query()
        ori_role = user_db.search(User.userid == userid)[0]['role']
        if ori_role is None:
            new_role = []
        else:
            new_role = []
            ori_role = ori_role.split(',')
            for role in ori_role:
                if role == delRole:
                    continue
                new_role.append(role)
        new_role = ','.join(new_role)

        user_db.update({'role': new_role}, User.userid == userid)
        result = user_db.search(User.userid == userid)
        result = result[0].copy()
        remove_key = ['pwd', 'avatar']
        for key in remove_key:
            if key in result:
                del result[key]

    return response_body(code=200, status='success', message='Update user info successfully', data=result)
