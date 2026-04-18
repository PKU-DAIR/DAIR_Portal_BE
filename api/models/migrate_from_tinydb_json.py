import os
import json
import asyncio
from typing import List, Dict, Any, Type
from tortoise import Tortoise
from tortoise.models import Model

from api.models.db_models import (
    UserDBModel,
    MajorDBModel,
    GroupDBModel,
    EduDBModel,
    TeamDBModel,
    ClientTeamDBModel,
    ToWhereDBModel,
    AwardItemDBModel,
    AwardLevelDBModel,
    MemberDBModel,
    NewsDBModel,
    PublicationDBModel,
)


def load_tinydb_records(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        raw = f.read().strip()
    if not raw:
        return []

    data = json.loads(raw)
    if isinstance(data, dict):
        default_table = data.get('_default')
        if isinstance(default_table, dict):
            return [v for _, v in default_table.items() if isinstance(v, dict)]
        return []
    if isinstance(data, list):
        return [v for v in data if isinstance(v, dict)]
    return []


async def migrate_with_pk(model: Type[Model], records: List[Dict[str, Any]], pk_name: str = 'id'):
    for rec in records:
        pk = rec.get(pk_name)
        if pk is None:
            continue
        exists = await model.filter(**{pk_name: pk}).exists()
        if exists:
            continue
        await model.create(**rec)


async def migrate_users(records: List[Dict[str, Any]]):
    for rec in records:
        userid = rec.get('userid')
        if not userid:
            continue
        exists = await UserDBModel.filter(userid=userid).exists()
        if exists:
            continue
        await UserDBModel.create(**rec)


async def main():
    await Tortoise.init(db_url='sqlite://./db/db.sqlite3', modules={'models': ['api.models.db_models']})
    await Tortoise.generate_schemas()

    db_dir = './db'
    await migrate_users(load_tinydb_records(os.path.join(db_dir, 'user_db.json')))
    await migrate_with_pk(MajorDBModel, load_tinydb_records(os.path.join(db_dir, 'major_db.json')))
    await migrate_with_pk(GroupDBModel, load_tinydb_records(os.path.join(db_dir, 'group_db.json')))
    await migrate_with_pk(EduDBModel, load_tinydb_records(os.path.join(db_dir, 'edu_db.json')))
    await migrate_with_pk(TeamDBModel, load_tinydb_records(os.path.join(db_dir, 'team_db.json')))
    await migrate_with_pk(ClientTeamDBModel, load_tinydb_records(os.path.join(db_dir, 'client_team_db.json')))
    await migrate_with_pk(ToWhereDBModel, load_tinydb_records(os.path.join(db_dir, 'towhere_db.json')))
    await migrate_with_pk(AwardItemDBModel, load_tinydb_records(os.path.join(db_dir, 'award_item_db.json')))
    await migrate_with_pk(AwardLevelDBModel, load_tinydb_records(os.path.join(db_dir, 'award_level_db.json')))
    await migrate_with_pk(MemberDBModel, load_tinydb_records(os.path.join(db_dir, 'member_db.json')))
    await migrate_with_pk(NewsDBModel, load_tinydb_records(os.path.join(db_dir, 'news_db.json')))
    await migrate_with_pk(PublicationDBModel, load_tinydb_records(os.path.join(db_dir, 'publications_db.json')))

    await Tortoise.close_connections()
    print('Migration finished.')


if __name__ == '__main__':
    asyncio.run(main())
