import json
import uuid
import datetime
from typing import Optional
from tortoise.expressions import Q
from fastapi import APIRouter
from api.models.body import response_body, PublicationItem
from api.models.verify_tool import Auth
from api.models.db_models import PublicationDBModel

router = APIRouter(tags=['Publication'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

PUB_FIELDS = [
    'id', 'publisher', 'DOI', 'year', 'createDate', 'source', 'title', 'url', 'booktitle',
    'abstract', 'ISSN', 'language', 'chapter', 'volume', 'number', 'pages', 'school', 'note',
    'author', 'entry_type', 'bib', 'update_time'
]


@router.get('/publications/get_publications')
async def list_publications(search: Optional[str] = None, offset: int = 0, limit: int = 99999):
    if search:
        pub_items = await PublicationDBModel.filter(
            Q(title__icontains=search) | Q(author__icontains=search) | Q(abstract__icontains=search)
        ).values(*PUB_FIELDS)
    else:
        pub_items = await PublicationDBModel.all().values(*PUB_FIELDS)

    total_pubs = len(pub_items)
    paginated_pubs = pub_items[offset:offset + limit]
    return response_body(code=200, status='success', data={'list': paginated_pubs, 'total': total_pubs})


@router.get('/publications/get_publication')
@auth.require_admin()
async def get_publication(id: str):
    result = await PublicationDBModel.filter(id=id).values(*PUB_FIELDS)
    if len(result) == 0:
        return response_body(code=404, status='failed', message='Publication not found')
    return response_body(code=200, status='success', data=result[0])


@router.post('/publications/update')
@auth.require_admin()
async def add_or_update_publication(pub_item: PublicationItem):
    if pub_item.id:
        existed = await PublicationDBModel.filter(id=pub_item.id).exists()
        if not existed:
            return response_body(code=404, status='failed', message='Publication not found')

        update_data = {
            'publisher': pub_item.publisher,
            'DOI': pub_item.DOI,
            'year': pub_item.year,
            'source': pub_item.source,
            'title': pub_item.title,
            'url': pub_item.url,
            'booktitle': pub_item.booktitle,
            'abstract': pub_item.abstract,
            'ISSN': pub_item.ISSN,
            'language': pub_item.language,
            'chapter': pub_item.chapter,
            'volume': pub_item.volume,
            'number': pub_item.number,
            'pages': pub_item.pages,
            'school': pub_item.school,
            'note': pub_item.note,
            'author': pub_item.author,
            'bib': pub_item.bib,
            'entry_type': pub_item.entry_type,
            'update_time': datetime.datetime.now().isoformat(),
        }
        await PublicationDBModel.filter(id=pub_item.id).update(**update_data)
        return response_body(code=200, status='success', message='Publication updated successfully')

    pub_id = str(uuid.uuid4())
    pub_data = {
        'id': pub_id,
        'publisher': pub_item.publisher,
        'DOI': pub_item.DOI,
        'year': pub_item.year,
        'createDate': datetime.datetime.now().isoformat(),
        'source': pub_item.source,
        'title': pub_item.title,
        'url': pub_item.url,
        'booktitle': pub_item.booktitle,
        'abstract': pub_item.abstract,
        'ISSN': pub_item.ISSN,
        'language': pub_item.language,
        'chapter': pub_item.chapter,
        'volume': pub_item.volume,
        'number': pub_item.number,
        'pages': pub_item.pages,
        'school': pub_item.school,
        'note': pub_item.note,
        'author': pub_item.author,
        'bib': pub_item.bib,
        'entry_type': pub_item.entry_type,
    }
    await PublicationDBModel.create(**pub_data)
    return response_body(code=200, status='success', message='Publication added successfully', data=pub_data)


@router.delete('/publications/remove')
@auth.require_admin()
async def delete_publication(id: str):
    removed = await PublicationDBModel.filter(id=id).delete()
    if removed == 0:
        return response_body(code=404, status='failed', message='Publication not found')
    return response_body(code=200, status='success', message='Publication deleted successfully')
