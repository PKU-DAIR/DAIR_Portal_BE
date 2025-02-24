import os
import json
import uuid
from tinydb import Query
from typing import Optional
from fastapi import APIRouter, Header, Form, File, UploadFile
from api.models.body import response_body, MemberInfo, MemberAward
from api.models.db_init import ensure_db, ensure_folder
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import valid_user
import asyncio
import base64

router = APIRouter()

member_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

member_db = ensure_db('member_db.json')


@router.get("/list_members_client")
async def list_members(
    offset: int = 0,
    limit: int = 99999
):
    """
    获取成员列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    api_key: Optional[str] = Header(None)
    """
    async with member_lock:
        members = member_db.all()

        # 分页逻辑
        total_members = len(members)
        paginated_members = members[offset:offset + limit]

        # 移除敏感信息（如电话）
        for member in paginated_members:
            member.pop('mobile', None)

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_members,
            "total": total_members
        }
    )


@router.get("/list_members")
async def list_members(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999,
    api_key=Header(None)
):
    """
    获取成员列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    api_key: Optional[str] = Header(None)
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    async with member_lock:
        MemberQuery = Query()
        if search:
            # 模糊搜索姓名、邮箱、电话等字段
            members = member_db.search(
                (MemberQuery.name.search(search)) |
                (MemberQuery.email.search(search)) |
                (MemberQuery.mobile.search(search))
            )
        else:
            members = member_db.all()

        # 分页逻辑
        total_members = len(members)
        paginated_members = members[offset:offset + limit]

        # 移除敏感信息（如电话）
        for member in paginated_members:
            member.pop('mobile', None)

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_members,
            "total": total_members
        }
    )


@router.get("/get_member")
async def get_member(
    id, api_key: Optional[str] = Header(None)
):
    """
    获取成员详情
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    async with member_lock:
        MemberQuery = Query()
        result = member_db.search(MemberQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Member not found')
        member = result[0]
        with open(f'member_cv/{id}/cv.json') as f:
            intro = f.read()
        introduction = json.loads(intro)
        member['introduction'] = introduction

    return response_body(code=200, status='success', data=member)


@router.get("/get_member_client")
async def get_member(
    id
):
    """
    获取成员详情
    """
    async with member_lock:
        MemberQuery = Query()
        result = member_db.search(MemberQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Member not found')
        member = result[0]
        with open(f'member_cv/{id}/cv.json') as f:
            intro = f.read()
        introduction = json.loads(intro)
        member['mobile'] = ''
        member['introduction'] = introduction

    return response_body(code=200, status='success', data=member)


@router.get("/get_my_cv")
async def get_myself(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    userid = valid_info['userid']
    async with member_lock:
        MemberQuery = Query()
        result = member_db.search(MemberQuery.userid == userid)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Member not found', data=userid)
        member = result[0]
        with open(f'member_cv/{member["id"]}/cv.json') as f:
            intro = f.read()
        introduction = json.loads(intro)
        member['introduction'] = introduction

    return response_body(code=200, status='success', data=member)


@router.post("/add_member")
async def add_member(
    member: MemberInfo,
    api_key: Optional[str] = Header(None)
):
    """
    添加成员
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    async with member_lock:
        member_data = member.dict()
        intro = member.introduction
        id = str(uuid.uuid4())
        ensure_folder(f'member_cv/{id}')
        with open(f'member_cv/{id}/cv.json', encoding='utf-8', mode='w+') as f:
            f.write(json.dumps(intro, ensure_ascii=False))
        member_data['id'] = id
        member_data['introduction'] = id
        member_data['photo'] = id
        if member_data['userid'] is not None:
            if member_db.search(lambda x: x['userid'] == member_data['userid']):
                return response_body(code=4001, status='failed', message=f'Member already binding: {member_data["userid"]}')
        if member_db.search(lambda x: x['id'] == member_data['id']):
            return response_body(code=4001, status='failed', message='Member already exists')
        member_db.insert(member_data)

    return response_body(code=200, status='success', message='Member added successfully', data=member_data)


@router.post("/update_member")
async def update_member(
    member: MemberInfo,
    api_key: Optional[str] = Header(None)
):
    """
    更新成员信息
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    async with member_lock:
        MemberQuery = Query()
        result = member_db.search(MemberQuery.id == member.id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Member not found')
        member_data = member.dict()
        intro = member.introduction
        id = member.id
        ensure_folder(f'member_cv/{id}')
        with open(f'member_cv/{id}/cv.json', encoding='utf-8', mode='w+') as f:
            f.write(json.dumps(intro, ensure_ascii=False))
        member_data['introduction'] = id
        member_data['photo'] = id
        member_db.update(member_data, MemberQuery.id == member.id)

    return response_body(code=200, status='success', message='Member updated successfully', data=member_data)


@router.post("/upload_member_avatar")
async def upload_member_avatar(
    id: str = Form(...),
    member_avatar: UploadFile = File(...),
    api_key: Optional[str] = Header(None)
):
    """
    上传成员头像
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    # 保存文件
    ensure_folder(f'member_cv/{id}')
    file_path = os.path.join(f'member_cv/{id}', 'avatar.jpg')
    with open(file_path, "wb") as buffer:
        buffer.write(member_avatar.file.read())

    return response_body(code=200, status='success', message='Avatar uploaded successfully', data={"file_path": file_path})


@router.get("/get_member_avatar")
async def get_member_avatar(id):
    """
    获取成员头像
    """
    file_path = os.path.join(f'member_cv/{id}', 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    with open(file_path, "rb") as f:
        avatar_data = base64.b64encode(f.read()).decode('utf-8')

    return response_body(code=200, status='success', data=f'data:image/jpeg;base64,{avatar_data}')


@router.get("/remove_member")
async def delete_member(
    id,
    api_key: Optional[str] = Header(None)
):
    """
    删除成员
    """
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')

    async with member_lock:
        MemberQuery = Query()
        result = member_db.search(MemberQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Member not found')
        member_db.remove(MemberQuery.id == id)

    return response_body(code=200, status='success', message='Member deleted successfully')
