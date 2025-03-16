import os
import json
import uuid
from tinydb import Query
from typing import Optional
from fastapi import APIRouter, Header, Depends, Form, File, UploadFile
from api.models.body import response_body
from api.models.db_init import ensure_db, ensure_folder
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import valid_user, Auth
import asyncio
import base64

router = APIRouter()

news_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

news_db = ensure_db('news_db.json')


@router.get("/list_news")
async def list_news(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999,
    vft=Depends(auth.is_admin)
):
    """
    获取新闻列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    vft=Depends(auth.is_admin)
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with news_lock:
        NewsQuery = Query()
        if search:
            # 模糊搜索标题、描述等字段
            news_items = news_db.search(
                (NewsQuery.title.search(search)) |
                (NewsQuery.description.search(search))
            )
        else:
            news_items = news_db.all()

        # 分页逻辑
        total_news = len(news_items)
        paginated_news = news_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_news,
            "total": total_news
        }
    )


@router.get("/get_news")
async def get_news(
    id: str,
    vft=Depends(auth.is_admin)
):
    """
    获取新闻详情
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')
        news_item = result[0]
        with open(f'news/{id}/content.json') as f:
            content = f.read()
        news_item['content'] = json.loads(content)

    return response_body(code=200, status='success', data=news_item)


@router.post("/add_news")
async def add_news(
    title: str = Form(...),
    description: str = Form(...),
    publisher_id: str = Form(...),
    content: str = Form(...),
    banner: UploadFile = File(...),
    vft=Depends(auth.is_admin)
):
    """
    添加新闻
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with news_lock:
        news_id = str(uuid.uuid4())
        ensure_folder(f'news/{news_id}')

        # 保存新闻内容
        with open(f'news/{news_id}/content.json', 'w', encoding='utf-8') as f:
            f.write(content)

        # 保存头图
        banner_path = os.path.join(f'news/{news_id}', 'banner.jpg')
        with open(banner_path, "wb") as buffer:
            buffer.write(banner.file.read())

        # 插入新闻记录
        news_data = {
            "id": news_id,
            "title": title,
            "description": description,
            "publisher_id": publisher_id,
            "publish_time": datetime.datetime.now().isoformat(),
            "update_time": datetime.datetime.now().isoformat()
        }
        news_db.insert(news_data)

    return response_body(code=200, status='success', message='News added successfully', data=news_data)


@router.post("/update_news")
async def update_news(
    id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    banner: Optional[UploadFile] = File(None),
    vft=Depends(auth.is_admin)
):
    """
    更新新闻信息
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')

        # 更新新闻内容
        if content:
            with open(f'news/{id}/content.json', 'w', encoding='utf-8') as f:
                f.write(content)

        # 更新头图
        if banner:
            banner_path = os.path.join(f'news/{id}', 'banner.jpg')
            with open(banner_path, "wb") as buffer:
                buffer.write(banner.file.read())

        # 更新新闻记录
        update_data = {}
        if title:
            update_data['title'] = title
        if description:
            update_data['description'] = description
        update_data['update_time'] = datetime.datetime.now().isoformat()
        news_db.update(update_data, NewsQuery.id == id)

    return response_body(code=200, status='success', message='News updated successfully')


@router.get("/get_news_banner")
async def get_news_banner(id: str):
    """
    获取新闻头图
    """
    file_path = os.path.join(f'news/{id}', 'banner.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Banner not found')

    with open(file_path, "rb") as f:
        banner_data = base64.b64encode(f.read()).decode('utf-8')

    return response_body(code=200, status='success', data=f'data:image/jpeg;base64,{banner_data}')


@router.get("/remove_news")
async def delete_news(
    id: str,
    vft=Depends(auth.is_admin)
):
    """
    删除新闻
    """
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]

    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')
        news_db.remove(NewsQuery.id == id)

        # 删除相关文件
        import shutil
        shutil.rmtree(f'news/{id}')

    return response_body(code=200, status='success', message='News deleted successfully')
