from tortoise import fields, models


class BaseDBModel(models.Model):
    class Meta:
        abstract = True


class UserDBModel(BaseDBModel):
    id = fields.IntField(pk=True)
    userid = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=255, null=True)
    pwd = fields.CharField(max_length=255)
    avatar = fields.TextField(null=True)
    email = fields.CharField(max_length=255, null=True)
    phone = fields.CharField(max_length=64, null=True)
    gender = fields.CharField(max_length=32, null=True)
    invite_code = fields.CharField(max_length=255, null=True)
    role = fields.CharField(max_length=255, null=True)
    apply_time = fields.CharField(max_length=255, null=True)
    last_login = fields.CharField(max_length=255, null=True)


class MajorDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class GroupDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class EduDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class TeamDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class ClientTeamDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)
    groups = fields.JSONField(null=True)


class ToWhereDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class AwardItemDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)


class AwardLevelDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    level = fields.CharField(max_length=255, unique=True)


class MemberDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255)
    grade = fields.CharField(max_length=255)
    session = fields.CharField(max_length=255)
    major = fields.CharField(max_length=255)
    title = fields.CharField(max_length=255)
    toWhere = fields.CharField(max_length=255)
    postAddress = fields.CharField(max_length=255)
    educations = fields.JSONField()
    teams = fields.JSONField()
    groups = fields.JSONField()
    introduction = fields.TextField(null=True)
    photo = fields.TextField(null=True)
    userid = fields.CharField(max_length=255, unique=True, null=True)
    awards = fields.JSONField()
    email = fields.CharField(max_length=255)
    mobile = fields.CharField(max_length=64)


class NewsDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    title = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    news_type = fields.CharField(max_length=255, null=True)
    publisher_id = fields.CharField(max_length=255, null=True)
    publish_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)


class PublicationDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    publisher = fields.TextField(null=True)
    DOI = fields.TextField(null=True)
    year = fields.TextField(null=True)
    createDate = fields.TextField(null=True)
    source = fields.TextField(null=True)
    title = fields.TextField(null=True)
    url = fields.TextField(null=True)
    booktitle = fields.TextField(null=True)
    abstract = fields.TextField(null=True)
    ISSN = fields.TextField(null=True)
    language = fields.TextField(null=True)
    chapter = fields.TextField(null=True)
    volume = fields.TextField(null=True)
    number = fields.TextField(null=True)
    pages = fields.TextField(null=True)
    school = fields.TextField(null=True)
    note = fields.TextField(null=True)
    author = fields.TextField(null=True)
    entry_type = fields.TextField(null=True)
    bib = fields.TextField(null=True)
    update_time = fields.TextField(null=True)
