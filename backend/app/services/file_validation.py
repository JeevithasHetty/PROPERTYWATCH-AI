from io import BytesIO

from fastapi import HTTPException
from PIL import ExifTags, Image, UnidentifiedImageError


FILE_SIGNATURES = {
    "application/pdf": lambda content: content.startswith(b"%PDF-"),
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda content: len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
    "image/tiff": lambda content: content.startswith((b"II*\x00", b"MM\x00*")),
}


def validate_upload_content(content: bytes, content_type: str, filename: str, allowed_types: dict, max_size: int) -> None:
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File exceeds the maximum allowed size of {max_size // (1024 * 1024)} MB.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_extensions = allowed_types[content_type]
    if f".{extension}" not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File extension does not match its declared file type.")

    signature_check = FILE_SIGNATURES.get(content_type)
    if signature_check and not signature_check(content):
        raise HTTPException(status_code=400, detail="File content does not match its declared file type.")


def extract_file_metadata(content: bytes, content_type: str) -> dict:
    metadata = {"mime_type": content_type, "size_bytes": len(content)}
    if not content_type.startswith("image/"):
        return metadata

    try:
        image = Image.open(BytesIO(content))
        image.verify()
        image = Image.open(BytesIO(content))
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Image file could not be decoded.") from exc

    metadata.update({"width": image.width, "height": image.height, "format": image.format})
    exif = image.getexif()
    if exif:
        for key, value in exif.items():
            name = ExifTags.TAGS.get(key, str(key))
            if name in {"DateTimeOriginal", "DateTime", "Make", "Model"} and isinstance(value, (str, int, float)):
                metadata[name] = value
    return metadata
