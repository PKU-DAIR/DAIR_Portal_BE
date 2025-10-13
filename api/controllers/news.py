import os
import json
import uuid
import datetime
from tinydb import Query
from typing import Optional
from fastapi import APIRouter, Header, Depends, Form, File, UploadFile
from api.models.body import response_body, NewsItem
from api.models.db_init import ensure_db, ensure_folder
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import Auth
import asyncio
import base64

router = APIRouter()

news_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

news_db = ensure_db('news_db.json')


@router.get("/news/get_news")
@auth.require_admin()
async def list_news(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取新闻列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量")
    """
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

@router.get("/list_news_size")
@auth.require_admin()
async def list_news_size(
    search: Optional[str] = None,
    limit: int = 99999
):
    """
    获取推文总数（支持模糊搜索）
    search: Optional[str] = Query(None, description="模糊搜索关键字")
    """
    async with news_lock:
        UserQuery = Query()
        if search:
            # 模糊搜索推文名、昵称、邮箱等字段
            news = news_db.search(
                (UserQuery.title.search(search)) |
                (UserQuery.description.search(search)))
        else:
            news = news_db.all()

        total_news = len(news) // limit + 1

    return response_body(
        data=total_news
    )

@router.get("/news/client/news")
async def list_client_news(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取新闻列表或项目列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    """

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

        computed_news_items = []
        for item in news_items:
            if item.get("news_type") is not None and 'news' in item.get("news_type"):
                computed_news_items.append(item)

        # 分页逻辑
        total_news = len(computed_news_items)
        paginated_news = computed_news_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_news,
            "total": total_news
        }
    )

@router.get("/news/client/projs")
async def list_client_projs(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取项目列表或项目列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    """

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
        
        computed_news_items = []
        for item in news_items:
            if item.get("news_type") is not None and 'proj' in item.get("news_type"):
                computed_news_items.append(item)

        # 分页逻辑
        total_news = len(computed_news_items)
        paginated_news = computed_news_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_news,
            "total": total_news
        }
    )

@router.get("/news/client/top_news")
async def list_client_top_news(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取新闻列表或项目列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    """

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
        
        computed_news_items = []
        for item in news_items:
            if item.get("news_type") is not None and 'top_news' in item.get("news_type"):
                computed_news_items.append(item)

        # 分页逻辑
        total_news = len(computed_news_items)
        paginated_news = computed_news_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_news,
            "total": total_news
        }
    )

@router.get("/news/client/top_projs")
async def list_client_top_projs(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取项目列表或项目列表（支持模糊搜索和分页）
    search: Optional[str] = Query(None, description="模糊搜索关键字"),
    offset: int = Query(0, description="分页偏移量"),
    limit: int = Query(20, description="每页数量"),
    """

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
        
        computed_news_items = []
        for item in news_items:
            if item.get("news_type") is not None and 'top_proj' in item.get("news_type"):
                computed_news_items.append(item)

        # 分页逻辑
        total_news = len(computed_news_items)
        paginated_news = computed_news_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_news,
            "total": total_news
        }
    )


@router.get("/get_news")
@auth.require_admin()
async def get_news(
    id: str
):
    """
    获取新闻详情
    """
    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')
        news_item = result[0]
        if os.path.exists(f'news/{id}/content.json'):
            with open(f'news/{id}/content.json') as f:
                content = f.read()
        else:
            content = "{}"
        news_item['content'] = json.loads(content)

    return response_body(code=200, status='success', data=news_item)

@router.get("/client/get_news")
async def get_news_client(
    id: str
):
    """
    获取新闻详情
    """
    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')
        news_item = result[0]
        if os.path.exists(f'news/{id}/content.json'):
            with open(f'news/{id}/content.json') as f:
                content = f.read()
        else:
            content = "{}"
        news_item['content'] = json.loads(content)

    return response_body(code=200, status='success', data=news_item)


@router.post("/news/update")
@auth.require_admin()
async def add_or_update_news(
    news_item: NewsItem,  # 使用 NewsItem 作为请求体
    valid_info=None
):
    """
    添加或更新新闻信息（不包括 banner 图片）
    """
    userid = valid_info['userid']

    async with news_lock:
        if news_item.id:  # 更新新闻
            NewsQuery = Query()
            result = news_db.search(NewsQuery.id == news_item.id)
            if len(result) == 0:
                return response_body(code=404, status='failed', message='News not found')

            # 更新新闻内容
            if news_item.content:
                with open(f'news/{news_item.id}/content.json', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(news_item.content, ensure_ascii=False))

            # 更新新闻记录
            update_data = {
                "title": news_item.title,
                "news_type": news_item.news_type,
                "description": news_item.description,
                "update_time": datetime.datetime.now().isoformat()
            }
            news_db.update(update_data, NewsQuery.id == news_item.id)
            return response_body(code=200, status='success', message='News updated successfully')

        else:  # 新增新闻
            news_id = str(uuid.uuid4())
            ensure_folder(f'news/{news_id}')

            # 保存新闻内容
            if news_item.content:
                with open(f'news/{news_id}/content.json', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(news_item.content, ensure_ascii=False))

            # 插入新闻记录
            news_data = {
                "id": news_id,
                "title": news_item.title,
                "news_type": news_item.news_type,
                "description": news_item.description,
                "publisher_id": userid,
                "publish_time": datetime.datetime.now().isoformat(),
                "update_time": datetime.datetime.now().isoformat()
            }
            news_db.insert(news_data)
            return response_body(code=200, status='success', message='News added successfully', data=news_data)

@router.post("/news/update/info")
@auth.require_admin()
async def update_news_info(
    news_item: NewsItem,  # 使用 NewsItem 作为请求体
    valid_info=None
):
    """
    添加或更新新闻信息（不包括 banner 图片）
    """
    userid = valid_info['userid']

    async with news_lock:
        if news_item.id:  # 更新新闻
            NewsQuery = Query()
            result = news_db.search(NewsQuery.id == news_item.id)
            if len(result) == 0:
                return response_body(code=404, status='failed', message='News not found')

            # 更新新闻记录
            update_data = {
                "title": news_item.title,
                "news_type": news_item.news_type,
                "description": news_item.description,
                "update_time": datetime.datetime.now().isoformat()
            }
            news_db.update(update_data, NewsQuery.id == news_item.id)
            return response_body(code=200, status='success', message='News updated successfully')

@router.post("/upload_banner")
@auth.require_admin()
async def upload_banner(
    id: str = Form(...),  # 新闻 ID
    banner: UploadFile = File(...)  # 上传的 banner 图片
):
    """
    上传或更新新闻的 banner 图片
    """
    async with news_lock:
        NewsQuery = Query()
        result = news_db.search(NewsQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='News not found')

        # 保存或更新 banner 图片
        banner_path = os.path.join(f'news/{id}', 'banner.jpg')
        with open(banner_path, "wb") as buffer:
            buffer.write(banner.file.read())

    return response_body(code=200, status='success', message='Banner uploaded successfully')


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
@auth.require_admin()
async def delete_news(
    id: str
):
    """
    删除新闻
    """
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
