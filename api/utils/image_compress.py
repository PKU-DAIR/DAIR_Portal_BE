import base64
import os
from io import BytesIO

from PIL import Image, ImageOps


MAX_IMAGE_SIZE_BYTES = 200 * 1024
IMAGE_FILES = {
    'avatar.jpg': 'avatar_cmp_cache.jpg',
    'banner.jpg': 'banner_cmp_cache.jpg',
}
RESAMPLE_LANCZOS = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS')


def get_compressed_image_data_url(image_dir: str) -> str:
    compressed_path = _ensure_compressed_image(image_dir)
    with open(compressed_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f'data:image/jpeg;base64,{image_data}'


def clear_compressed_image_cache(image_dir: str) -> None:
    for cache_file_name in IMAGE_FILES.values():
        cache_path = os.path.join(image_dir, cache_file_name)
        if os.path.exists(cache_path):
            os.remove(cache_path)


def _ensure_compressed_image(image_dir: str) -> str:
    image_path, cache_path = _resolve_image_paths(image_dir)
    if os.path.exists(cache_path):
        return cache_path

    image_bytes = _compress_image_to_bytes(image_path)
    with open(cache_path, 'wb') as f:
        f.write(image_bytes)
    return cache_path


def _resolve_image_paths(image_dir: str) -> tuple[str, str]:
    for image_file_name, cache_file_name in IMAGE_FILES.items():
        image_path = os.path.join(image_dir, image_file_name)
        if os.path.exists(image_path):
            return image_path, os.path.join(image_dir, cache_file_name)
    raise FileNotFoundError('avatar.jpg or banner.jpg not found')


def _compress_image_to_bytes(image_path: str) -> bytes:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = _to_rgb(image)

        image_bytes = _save_jpeg(image, quality=85)
        if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
            return image_bytes

        current_image = image
        while len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            image_bytes = _compress_by_quality(current_image)
            if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
                return image_bytes

            width, height = current_image.size
            next_size = (max(1, int(width * 0.85)), max(1, int(height * 0.85)))
            if next_size == current_image.size:
                return image_bytes
            current_image = current_image.resize(next_size, RESAMPLE_LANCZOS)

        return image_bytes


def _compress_by_quality(image: Image.Image) -> bytes:
    for quality in range(85, 19, -5):
        image_bytes = _save_jpeg(image, quality=quality)
        if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
            return image_bytes
    return _save_jpeg(image, quality=20)


def _save_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue()


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        background = Image.new('RGB', image.size, (255, 255, 255))
        alpha_image = image.convert('RGBA')
        background.paste(alpha_image, mask=alpha_image.getchannel('A'))
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image
