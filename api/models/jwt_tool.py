# %%
import jwt
import datetime


def create_jwt(obj: dict, key, algorithm='HS256'):
    headers = {
        'alg': algorithm,
        'typ': 'JWT'
    }  # jwt的头部，包含了类型和算法的指定

    payload = obj
    payload['exp'] = datetime.datetime.now() + datetime.timedelta(days=14)

    token = jwt.encode(headers=headers, payload=payload,
                       algorithm=algorithm, key=key)  # 对上面内容进行加密，这里的key就是加的盐
    return token


def decode_jwt(token, key, algorithms=['HS256']):
    # 对jwt进行解密,这里用的key必须和上面用的key一样，否则是无法解密出来的
    try:
        content = jwt.decode(jwt=token, key=key, algorithms=algorithms)
        return content
    except:
        return {}

# %%
