import os
import json
import uuid
import shutil
import datetime
from typing import Optional
from tortoise.expressions import Q
from fastapi import APIRouter, Form, File, UploadFile
from fastapi.responses import FileResponse
from api.models.body import response_body, NewsItem
from api.models.db_init import ensure_folder
from api.models.verify_tool import Auth
from api.models.db_models import NewsDBModel
from api.utils.image_compress import clear_compressed_image_cache, get_compressed_image_data_url, get_compressed_image_path

router = APIRouter(tags=['News'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

NEWS_FIELDS = ['id', 'title', 'description', 'news_type', 'publisher_id', 'publish_time', 'update_time', 'external']


async def _query_news(search: Optional[str] = None):
    if search:
        return await NewsDBModel.filter(Q(title__icontains=search) | Q(description__icontains=search)).values(*NEWS_FIELDS)
    return await NewsDBModel.all().values(*NEWS_FIELDS)


@router.get('/news/get_news', operation_id='ListNews')
@auth.require_admin()
async def list_news(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    news_items = await _query_news(search)
    total_news = len(news_items)
    paginated_news = news_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_news, 'total': total_news})


@router.get('/list_news_size', operation_id='ListNewsSize')
@auth.require_admin()
async def list_news_size(search: Optional[str] = None, limit: int = 99999):
    news = await _query_news(search)
    total_news = len(news) // limit + 1
    return response_body(data=total_news)


@router.get('/news/client/news', operation_id='ListClientNews')
async def list_client_news(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    news_items = await _query_news(search)
    computed_news_items = [item for item in news_items if item.get('news_type') is not None and 'news' in item.get('news_type')]
    total_news = len(computed_news_items)
    paginated_news = computed_news_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_news, 'total': total_news})


@router.get('/news/client/projs', operation_id='ListClientProjects')
async def list_client_projs(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    news_items = await _query_news(search)
    computed_news_items = [item for item in news_items if item.get('news_type') is not None and 'proj' in item.get('news_type')]
    total_news = len(computed_news_items)
    paginated_news = computed_news_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_news, 'total': total_news})


@router.get('/news/client/top_news', operation_id='ListClientTopNews')
async def list_client_top_news(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    news_items = await _query_news(search)
    computed_news_items = [item for item in news_items if item.get('news_type') is not None and 'top_news' in item.get('news_type')]
    total_news = len(computed_news_items)
    paginated_news = computed_news_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_news, 'total': total_news})


@router.get('/news/client/top_projs', operation_id='ListClientTopProjects')
async def list_client_top_projs(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    news_items = await _query_news(search)
    computed_news_items = [item for item in news_items if item.get('news_type') is not None and 'top_proj' in item.get('news_type')]
    total_news = len(computed_news_items)
    paginated_news = computed_news_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_news, 'total': total_news})


@router.get('/get_news', operation_id='GetNews')
@auth.require_admin()
async def get_news(id: str):
    result = await NewsDBModel.filter(id=id).values(*NEWS_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='News not found')

    news_item = result[0]
    if os.path.exists(f'news/{id}/content.json'):
        with open(f'news/{id}/content.json') as f:
            content = f.read()
    else:
        content = '{}'
    news_item['content'] = json.loads(content)
    return response_body(code=200, status='success', data=news_item)


@router.get('/client/get_news', operation_id='GetNewsClient')
async def get_news_client(id: str):
    result = await NewsDBModel.filter(id=id).values(*NEWS_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='News not found')

    news_item = result[0]
    if os.path.exists(f'news/{id}/content.json'):
        with open(f'news/{id}/content.json') as f:
            content = f.read()
    else:
        content = '{}'
    news_item['content'] = json.loads(content)
    return response_body(code=200, status='success', data=news_item)


@router.post('/news/update', operation_id='AddOrUpdateNews')
@auth.require_admin()
async def add_or_update_news(news_item: NewsItem, valid_info=None):
    userid = valid_info['userid']
    if news_item.id:
        result = await NewsDBModel.filter(id=news_item.id).exists()
        if not result:
            return response_body(code=404, status='failed', message='News not found')

        if news_item.content:
            with open(f'news/{news_item.id}/content.json', 'w', encoding='utf-8') as f:
                f.write(json.dumps(news_item.content, ensure_ascii=False))

        update_data = {
            'title': news_item.title,
            'news_type': news_item.news_type,
            'description': news_item.description,
            'external': news_item.external,
            'update_time': datetime.datetime.now().isoformat(),
        }
        await NewsDBModel.filter(id=news_item.id).update(**update_data)
        return response_body(code=200, status='success', message='News updated successfully')

    news_id = str(uuid.uuid4())
    ensure_folder(f'news/{news_id}')
    if news_item.content:
        with open(f'news/{news_id}/content.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(news_item.content, ensure_ascii=False))

    news_data = {
        'id': news_id,
        'title': news_item.title,
        'news_type': news_item.news_type,
        'description': news_item.description,
        'publisher_id': userid,
        'publish_time': datetime.datetime.now().isoformat(),
        'update_time': datetime.datetime.now().isoformat(),
        'external': news_item.external,
    }
    await NewsDBModel.create(**news_data)
    return response_body(code=200, status='success', message='News added successfully', data=news_data)


@router.post('/news/update/info', operation_id='UpdateNewsInfo')
@auth.require_admin()
async def update_news_info(news_item: NewsItem, valid_info=None):
    if news_item.id:
        result = await NewsDBModel.filter(id=news_item.id).exists()
        if not result:
            return response_body(code=404, status='failed', message='News not found')

        update_data = {
            'title': news_item.title,
            'news_type': news_item.news_type,
            'description': news_item.description,
            'external': news_item.external,
            'update_time': datetime.datetime.now().isoformat(),
        }
        await NewsDBModel.filter(id=news_item.id).update(**update_data)
        return response_body(code=200, status='success', message='News updated successfully')


@router.post('/upload_banner', operation_id='UploadNewsBanner')
@auth.require_admin()
async def upload_banner(id: str = Form(...), banner: UploadFile = File(...)):
    result = await NewsDBModel.filter(id=id).exists()
    if not result:
        return response_body(code=404, status='failed', message='News not found')

    image_dir = f'news/{id}'
    clear_compressed_image_cache(image_dir)
    banner_path = os.path.join(image_dir, 'banner.jpg')
    with open(banner_path, 'wb') as buffer:
        buffer.write(banner.file.read())

    return response_body(code=200, status='success', message='Banner uploaded successfully')


@router.get('/get_news_banner', operation_id='GetNewsBanner')
async def get_news_banner(id: str):
    image_dir = f'news/{id}'
    file_path = os.path.join(image_dir, 'banner.jpg')
    if not os.path.exists(file_path):
        return response_body(code=404, status='failed', message='Banner not found')

    return response_body(code=200, status='success', data=get_compressed_image_data_url(image_dir))


@router.post('/upload_news_image', operation_id='UploadNewsImage')
@auth.require_admin()
async def upload_news_image(id: str = Form(...), image: UploadFile = File(...)):
    result = await NewsDBModel.filter(id=id).exists()
    if not result:
        return response_body(code=404, status='failed', message='News not found')

    image_dir = f'news/{id}'
    ensure_folder(image_dir)
    image_name = f'{uuid.uuid4()}.jpg'
    image_path = os.path.join(image_dir, image_name)
    with open(image_path, 'wb') as buffer:
        buffer.write(image.file.read())

    return response_body(
        code=200,
        status='success',
        message='Image uploaded successfully',
        data={'image_name': image_name},
    )


@router.get('/get_news_image', operation_id='GetNewsImage')
async def get_news_image(newsid: str, image_name: str):
    def _is_valid_news_image_name(image_name: str) -> bool:
        return (
            image_name
            and image_name == os.path.basename(image_name)
            and image_name.endswith('.jpg')
            and '_cmp_cache' not in image_name
        )
    if not _is_valid_news_image_name(image_name):
        return response_body(code=400, status='failed', message='Invalid image name')

    image_dir = f'news/{newsid}'
    image_path = os.path.join(image_dir, image_name)
    if not os.path.exists(image_path):
        return response_body(code=404, status='failed', message='Image not found')

    return FileResponse(get_compressed_image_path(image_dir, image_name), media_type='image/jpeg')


@router.get('/remove_news', operation_id='DeleteNews')
@auth.require_admin()
async def delete_news(id: str):
    removed = await NewsDBModel.filter(id=id).delete()
    if removed == 0:
        return response_body(code=404, status='failed', message='News not found')

    if os.path.exists(f'news/{id}'):
        shutil.rmtree(f'news/{id}')

    return response_body(code=200, status='success', message='News deleted successfully')
