import os
import re
import pandas as pd
from typing import Tuple
from fastapi import UploadFile, HTTPException
from app.core.config import settings

def sanitize_filename(filename: str) -> str:
    """Strip path traversal characters and dangerous symbols."""
    base = os.path.basename(filename)
    # Remove all characters except alphanumeric, underscore, dash, and dot
    clean = re.sub(r"[^\w\.-]", "_", base)
    return clean or "dataset"

async def validate_and_read_file(file: UploadFile) -> Tuple[pd.DataFrame, str, int, str]:
    """
    Validates file extension, size, and safely parses CSV / Excel into a Pandas DataFrame.
    Returns (DataFrame, clean_filename, file_size_bytes, extension).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    clean_name = sanitize_filename(file.filename)
    ext = clean_name.split(".")[-1].lower() if "." in clean_name else ""

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Supported formats are: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # Read contents into memory with size check
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is completely empty (0 bytes).")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({file_size / (1024*1024):.2f}MB) exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    # Parse into Pandas DataFrame
    import io
    try:
        if ext == "csv":
            try:
                df = pd.read_csv(io.BytesIO(content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(content), encoding="latin1")
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse {clean_name}: The file content appears corrupted or invalid. Error: {str(e)}",
        )

    if df.empty or len(df.columns) == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file contains headers only or no readable data rows.",
        )

    # Clean up column names: trim whitespace and ensure string type
    df.columns = [str(col).strip() for col in df.columns]

    return df, clean_name, file_size, ext
