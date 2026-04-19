import base64
import os
from io import BytesIO

from PIL import Image, ImageOps


MAX_IMAGE_SIZE_BYTES = 200 * 1024

# 默认图片映射：当调用方只传目录、不传具体文件名时，会按这里的顺序自动查找。
# 这样 user/member 的头像接口和 news 的 banner 接口可以共用同一个入口。
IMAGE_FILES = {
    'avatar.jpg': 'avatar_cmp_cache.jpg',
    'banner.jpg': 'banner_cmp_cache.jpg',
}

# Pillow 10 以后把 LANCZOS 放到了 Image.Resampling 里；老版本仍然在 Image 上。
# 这里做兼容，避免部署环境 Pillow 版本不同导致 resize 报错。
RESAMPLE_LANCZOS = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS')


def get_compressed_image_data_url(image_dir: str, image_file_name: str = None) -> str:
    """
    获取压缩后的图片，并以 data URL 形式返回。

    用法分两种：
    1. 只传 image_dir：
       自动在目录下查找 avatar.jpg 或 banner.jpg，命中后使用对应缓存文件。
       例如：
       - user/xxx/avatar.jpg -> user/xxx/avatar_cmp_cache.jpg
       - news/xxx/banner.jpg -> news/xxx/banner_cmp_cache.jpg

    2. 同时传 image_dir 和 image_file_name：
       用于 news 正文图片这类动态文件名。
       例如：
       - news/xxx/a-b-c.jpg -> news/xxx/a-b-c_cmp_cache.jpg

    如果缓存文件已经存在，会直接读取缓存；如果不存在，才会压缩原图并写入缓存。
    返回值保持 controller 原来的格式：data:image/jpeg;base64,...
    """
    compressed_path = _ensure_compressed_image(image_dir, image_file_name)
    with open(compressed_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f'data:image/jpeg;base64,{image_data}'


def get_compressed_image_path(image_dir: str, image_file_name: str = None) -> str:
    """
    获取压缩后的图片文件路径。

    这个方法用于需要直接返回图片 blob 的接口。内部会复用同一套缓存逻辑：
    缓存存在就直接返回缓存路径，缓存不存在就先压缩原图并写入缓存。
    """
    return _ensure_compressed_image(image_dir, image_file_name)


def clear_compressed_image_cache(image_dir: str, image_file_name: str = None) -> None:
    """
    清理压缩缓存。

    - 不传 image_file_name 时：只清理默认图片的缓存，也就是 avatar_cmp_cache.jpg
      和 banner_cmp_cache.jpg。上传头像或 banner 后调用这个模式即可。
    - 传 image_file_name 时：只清理这个具体图片对应的缓存。例如 a.jpg 对应
      a_cmp_cache.jpg。

    注意：这里不会删除原图，只删除压缩后的缓存文件。
    """
    cache_file_names = [_cache_file_name(image_file_name)] if image_file_name else IMAGE_FILES.values()
    for cache_file_name in cache_file_names:
        cache_path = os.path.join(image_dir, cache_file_name)
        if os.path.exists(cache_path):
            os.remove(cache_path)


def _ensure_compressed_image(image_dir: str, image_file_name: str = None) -> str:
    """
    确保压缩缓存存在，并返回缓存文件路径。

    这是压缩流程的核心调度：
    1. 先解析出原图路径和缓存路径。
    2. 如果缓存已经存在，直接返回缓存路径。
    3. 如果缓存不存在，压缩原图、写入缓存，再返回缓存路径。
    """
    image_path, cache_path = _resolve_image_paths(image_dir, image_file_name)
    if os.path.exists(cache_path):
        return cache_path

    image_bytes = _compress_image_to_bytes(image_path)
    with open(cache_path, 'wb') as f:
        f.write(image_bytes)
    return cache_path


def _resolve_image_paths(image_dir: str, image_file_name: str = None) -> tuple[str, str]:
    """
    根据目录和可选文件名，解析原图路径与缓存路径。

    image_file_name 存在时，说明调用方明确指定了要取哪张图，常用于 news 正文图。
    image_file_name 不存在时，按 IMAGE_FILES 中的默认规则自动查找 avatar.jpg
    或 banner.jpg，方便头像和 banner 接口共用同一套逻辑。
    """
    if image_file_name:
        image_path = os.path.join(image_dir, image_file_name)
        if os.path.exists(image_path):
            return image_path, os.path.join(image_dir, _cache_file_name(image_file_name))
        raise FileNotFoundError(f'{image_file_name} not found')

    for image_file_name, cache_file_name in IMAGE_FILES.items():
        image_path = os.path.join(image_dir, image_file_name)
        if os.path.exists(image_path):
            return image_path, os.path.join(image_dir, cache_file_name)
    raise FileNotFoundError('avatar.jpg or banner.jpg not found')


def _cache_file_name(image_file_name: str) -> str:
    """
    生成单张图片对应的缓存文件名。

    统一规则是：去掉原扩展名，在文件名后追加 _cmp_cache，再固定保存为 jpg。
    例如：
    - avatar.jpg -> avatar_cmp_cache.jpg
    - banner.jpg -> banner_cmp_cache.jpg
    - 550e8400.jpg -> 550e8400_cmp_cache.jpg
    """
    file_stem, _ = os.path.splitext(image_file_name)
    return f'{file_stem}_cmp_cache.jpg'


def _compress_image_to_bytes(image_path: str) -> bytes:
    """
    将原图压缩成不超过 MAX_IMAGE_SIZE_BYTES 的 JPEG 字节。

    压缩策略：
    1. 先修正 EXIF 方向，避免手机照片横竖方向异常。
    2. 统一转成 RGB，因为 JPEG 不支持透明通道。
    3. 先用 quality=85 保存一次，如果已经小于 200KB 就直接返回。
    4. 如果仍然太大，先在当前尺寸上逐步降低 JPEG quality。
    5. quality 降到 20 仍然太大时，把图片宽高缩小到 85%，再重复质量压缩。

    这样可以优先保留分辨率，只有质量压缩不够时才缩小尺寸。
    """
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = _to_rgb(image)

        image_bytes = _save_jpeg(image, quality=85)
        if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
            return image_bytes

        current_image = image
        while len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            # 先尝试只降低 JPEG 质量；这一步通常能在不改变尺寸的情况下显著减小体积。
            image_bytes = _compress_by_quality(current_image)
            if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
                return image_bytes

            # 如果质量已经压到较低仍然超限，再缩小图片尺寸继续尝试。
            width, height = current_image.size
            next_size = (max(1, int(width * 0.85)), max(1, int(height * 0.85)))
            if next_size == current_image.size:
                return image_bytes
            current_image = current_image.resize(next_size, RESAMPLE_LANCZOS)

        return image_bytes


def _compress_by_quality(image: Image.Image) -> bytes:
    """
    在当前图片尺寸下，逐步降低 JPEG quality，寻找第一个小于 200KB 的结果。

    如果 quality=20 仍然超限，会返回 quality=20 的结果，让上层决定是否继续缩小尺寸。
    """
    for quality in range(85, 19, -5):
        image_bytes = _save_jpeg(image, quality=quality)
        if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
            return image_bytes
    return _save_jpeg(image, quality=20)


def _save_jpeg(image: Image.Image, quality: int) -> bytes:
    """
    将 PIL Image 按指定 JPEG quality 写入内存，并返回 bytes。

    使用 BytesIO 是为了先判断压缩后的大小，只有最终结果确定后才写入缓存文件。
    optimize=True 会让 Pillow 尽量优化 JPEG 编码体积。
    """
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue()


def _to_rgb(image: Image.Image) -> Image.Image:
    """
    将图片转换成 JPEG 可保存的 RGB 模式。

    JPEG 不支持透明通道，所以 RGBA/LA/带透明信息的调色板图片需要先铺到白色背景上。
    这样透明区域不会在转换时变成黑色，也能避免 Pillow 保存 JPEG 时报错。
    """
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        background = Image.new('RGB', image.size, (255, 255, 255))
        alpha_image = image.convert('RGBA')
        background.paste(alpha_image, mask=alpha_image.getchannel('A'))
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image
