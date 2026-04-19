import os
import json
import uuid
from typing import Optional
from tortoise.expressions import Q
from fastapi import APIRouter, Form, File, UploadFile
from api.models.body import response_body, MemberInfo
from api.models.db_init import ensure_folder
from api.models.verify_tool import Auth
from api.models.db_models import MemberDBModel
from api.utils.image_compress import clear_compressed_image_cache, get_compressed_image_data_url

router = APIRouter(tags=['Member'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

MEMBER_FIELDS = [
    'id', 'name', 'grade', 'session', 'major', 'title', 'toWhere', 'postAddress',
    'educations', 'teams', 'groups', 'introduction', 'photo', 'userid', 'awards', 'email', 'mobile'
]


@router.get('/list_members_client', operation_id='ListMembersClient')
async def list_members_client(offset: int = 0, limit: int = 99999):
    members = await MemberDBModel.all().values(*MEMBER_FIELDS)
    total_members = len(members)
    paginated_members = members[offset:offset + limit]
    for member in paginated_members:
        member.pop('mobile', None)
    return response_body(code=200, status='success', data={'list': paginated_members, 'total': total_members})


@router.get('/list_members', operation_id='ListMembers')
@auth.require_admin()
async def list_members(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    if search:
        members = await MemberDBModel.filter(
            Q(name__icontains=search) | Q(email__icontains=search) | Q(mobile__icontains=search)
        ).values(*MEMBER_FIELDS)
    else:
        members = await MemberDBModel.all().values(*MEMBER_FIELDS)

    total_members = len(members)
    paginated_members = members[offset:offset + limit]
    for member in paginated_members:
        member.pop('mobile', None)

    return response_body(code=200, status='success', data={'list': paginated_members, 'total': total_members})


@router.get('/get_member', operation_id='GetMember')
@auth.require_admin()
async def get_member(id):
    result = await MemberDBModel.filter(id=id).values(*MEMBER_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='Member not found')

    member = result[0]
    with open(f'member_cv/{id}/cv.json') as f:
        intro = f.read()
    member['introduction'] = json.loads(intro)
    return response_body(code=200, status='success', data=member)


@router.get('/get_member_client', operation_id='GetMemberClient')
async def get_member_client(id):
    result = await MemberDBModel.filter(id=id).values(*MEMBER_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='Member not found')

    member = result[0]
    with open(f'member_cv/{id}/cv.json') as f:
        intro = f.read()
    member['mobile'] = ''
    member['introduction'] = json.loads(intro)
    return response_body(code=200, status='success', data=member)


@router.get('/get_my_cv', operation_id='GetMyCv')
@auth.require_user()
async def get_myself(valid_info=None):
    userid = valid_info['userid']
    result = await MemberDBModel.filter(userid=userid).values(*MEMBER_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='Member not found', data=userid)

    member = result[0]
    with open(f'member_cv/{member["id"]}/cv.json') as f:
        intro = f.read()
    member['introduction'] = json.loads(intro)
    return response_body(code=200, status='success', data=member)


@router.post('/add_member', operation_id='AddMember')
@auth.require_user()
async def add_member(member: MemberInfo):
    member_data = member.dict()
    intro = member.introduction
    member_id = str(uuid.uuid4())
    ensure_folder(f'member_cv/{member_id}')
    with open(f'member_cv/{member_id}/cv.json', encoding='utf-8', mode='w+') as f:
        f.write(json.dumps(intro, ensure_ascii=False))

    member_data['id'] = member_id
    member_data['introduction'] = member_id
    member_data['photo'] = member_id

    if member_data['userid'] is not None:
        if await MemberDBModel.filter(userid=member_data['userid']).exists():
            return response_body(code=4001, status='failed', message=f'Member already binding: {member_data["userid"]}')
    if await MemberDBModel.filter(id=member_data['id']).exists():
        return response_body(code=4001, status='failed', message='Member already exists')

    await MemberDBModel.create(**member_data)
    return response_body(code=200, status='success', message='Member added successfully', data=member_data)


@router.post('/update_member', operation_id='UpdateMember')
@auth.require_user()
async def update_member(member: MemberInfo):
    existed = await MemberDBModel.filter(id=member.id).exists()
    if not existed:
        return response_body(code=404, status='failed', message='Member not found')

    member_data = member.dict()
    intro = member.introduction
    member_id = member.id
    ensure_folder(f'member_cv/{member_id}')
    with open(f'member_cv/{member_id}/cv.json', encoding='utf-8', mode='w+') as f:
        f.write(json.dumps(intro, ensure_ascii=False))
    member_data['introduction'] = member_id
    member_data['photo'] = member_id

    await MemberDBModel.filter(id=member.id).update(**member_data)
    return response_body(code=200, status='success', message='Member updated successfully', data=member_data)


@router.post('/upload_member_avatar', operation_id='UploadMemberAvatar')
@auth.require_user()
async def upload_member_avatar(id: str = Form(...), member_avatar: UploadFile = File(...)):
    image_dir = f'member_cv/{id}'
    ensure_folder(image_dir)
    clear_compressed_image_cache(image_dir)
    file_path = os.path.join(image_dir, 'avatar.jpg')
    with open(file_path, 'wb') as buffer:
        buffer.write(member_avatar.file.read())
    return response_body(code=200, status='success', message='Avatar uploaded successfully', data={'file_path': file_path})


@router.get('/get_member_avatar', operation_id='GetMemberAvatar')
async def get_member_avatar(id):
    image_dir = f'member_cv/{id}'
    file_path = os.path.join(image_dir, 'avatar.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Avatar not found')

    return response_body(code=200, status='success', data=get_compressed_image_data_url(image_dir))


@router.get('/remove_member', operation_id='DeleteMember')
@auth.require_admin()
async def delete_member(id):
    removed = await MemberDBModel.filter(id=id).delete()
    if removed == 0:
        return response_body(code=404, status='failed', message='Member not found')
    return response_body(code=200, status='success', message='Member deleted successfully')
