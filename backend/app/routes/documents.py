from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile

from app.db import fetch_all
from app.deps import PoolDep, ProviderDep, SettingsDep
from app.ingestion.parsers import UnsupportedFileTypeError
from app.ingestion.pipeline import EmptyDocumentError, ingest_document
from app.models import DocumentOut, IngestResult

router = APIRouter(prefix="/api/documents")


@router.post("")
async def upload_document(
    file: UploadFile, pool: PoolDep, provider: ProviderDep, settings: SettingsDep
) -> IngestResult:
    # Read one byte past the limit so an oversized file is rejected without loading all of it.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(413, f"file is larger than the {limit_mb} MB limit")
    try:
        return await ingest_document(pool, provider, settings, file.filename or "untitled", data)
    except UnsupportedFileTypeError as error:
        raise HTTPException(415, str(error)) from error
    except EmptyDocumentError as error:
        raise HTTPException(422, str(error)) from error


@router.get("")
async def list_documents(pool: PoolDep) -> list[DocumentOut]:
    rows = await fetch_all(
        pool, "SELECT id, filename, num_chunks, updated_at FROM documents ORDER BY filename"
    )
    return [DocumentOut(**row) for row in rows]


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: UUID, pool: PoolDep) -> None:
    async with pool.connection() as conn:
        cursor = await conn.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "document not found")
