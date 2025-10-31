import os
import json
import uuid
import datetime
from tinydb import Query
from typing import Optional
from fastapi import APIRouter, Header, Depends, Form, File, UploadFile
from api.models.body import response_body, PublicationItem
from api.models.db_init import ensure_db, ensure_folder
from api.models.jwt_tool import create_jwt
from api.models.verify_tool import Auth
import asyncio
import base64

router = APIRouter(tags=['Publication'])

pub_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

pub_db = ensure_db('publications_db.json')


@router.get("/publications/get_publications")
async def list_publications(
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 99999
):
    """
    获取论文列表（支持模糊搜索和分页）
    """

    async with pub_lock:
        PubQuery = Query()
        if search:
            search = search.lower()
            # 模糊搜索标题、作者、摘要等字段
            pub_items = pub_db.search(
                (PubQuery.title.search(search)) |
                (PubQuery.author.search(search)) |
                (PubQuery.abstract.search(search))
            )
        else:
            pub_items = pub_db.all()

        # 分页逻辑
        total_pubs = len(pub_items)
        paginated_pubs = pub_items[offset:offset + limit]

    return response_body(
        code=200,
        status='success',
        data={
            "list": paginated_pubs,
            "total": total_pubs
        }
    )

@router.get("/publications/get_publication")
@auth.require_admin()
async def get_publication(
    id: str
):
    """
    获取论文详情
    """
    async with pub_lock:
        PubQuery = Query()
        result = pub_db.search(PubQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Publication not found')
        pub_item = result[0]

    return response_body(code=200, status='success', data=pub_item)

@router.post("/publications/update")
@auth.require_admin()
async def add_or_update_publication(
    pub_item: PublicationItem  # 使用 PublicationItem 作为请求体
):
    """
    添加或更新论文信息
    """
    async with pub_lock:
        if pub_item.id:  # 更新论文
            PubQuery = Query()
            result = pub_db.search(PubQuery.id == pub_item.id)
            if len(result) == 0:
                return response_body(code=404, status='failed', message='Publication not found')

            # 更新论文记录
            update_data = {
                "publisher": pub_item.publisher,
                "DOI": pub_item.DOI,
                "year": pub_item.year,
                "source": pub_item.source,
                "title": pub_item.title,
                "url": pub_item.url,
                "booktitle": pub_item.booktitle,
                "abstract": pub_item.abstract,
                "ISSN": pub_item.ISSN,
                "language": pub_item.language,
                "chapter": pub_item.chapter,
                "volume": pub_item.volume,
                "number": pub_item.number,
                "pages": pub_item.pages,
                "school": pub_item.school,
                "note": pub_item.note,
                "author": pub_item.author,
                "bib": pub_item.bib,
                "entry_type": pub_item.entry_type,
                "update_time": datetime.datetime.now().isoformat()
            }
            pub_db.update(update_data, PubQuery.id == pub_item.id)
            return response_body(code=200, status='success', message='Publication updated successfully')

        else:  # 新增论文
            pub_id = str(uuid.uuid4())

            # 插入论文记录
            pub_data = {
                "id": pub_id,
                "publisher": pub_item.publisher,
                "DOI": pub_item.DOI,
                "year": pub_item.year,
                "createDate": datetime.datetime.now().isoformat(),
                "source": pub_item.source,
                "title": pub_item.title,
                "url": pub_item.url,
                "booktitle": pub_item.booktitle,
                "abstract": pub_item.abstract,
                "ISSN": pub_item.ISSN,
                "language": pub_item.language,
                "chapter": pub_item.chapter,
                "volume": pub_item.volume,
                "number": pub_item.number,
                "pages": pub_item.pages,
                "school": pub_item.school,
                "note": pub_item.note,
                "author": pub_item.author,
                "bib": pub_item.bib,
                "entry_type": pub_item.entry_type
            }
            pub_db.insert(pub_data)
            return response_body(code=200, status='success', message='Publication added successfully', data=pub_data)

@router.delete("/publications/remove")
@auth.require_admin()
async def delete_publication(
    id: str
):
    """
    删除论文
    """
    async with pub_lock:
        PubQuery = Query()
        result = pub_db.search(PubQuery.id == id)
        if len(result) == 0:
            return response_body(code=404, status='failed', message='Publication not found')
        pub_db.remove(PubQuery.id == id)

    return response_body(code=200, status='success', message='Publication deleted successfully')