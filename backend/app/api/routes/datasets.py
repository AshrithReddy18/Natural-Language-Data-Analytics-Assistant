from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models.entities import User
from app.schemas.api import DataSourceCreate, DataSourceOut, DataSourceUpdate, SchemaOut
from app.services.datasource_service import DataSourceService, to_out

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DataSourceOut])
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[DataSourceOut]:
    return DataSourceService(db, user).list()


@router.post("", response_model=DataSourceOut, status_code=201)
def create_dataset(
    body: DataSourceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DataSourceOut:
    return DataSourceService(db, user).create(body)


@router.post("/upload", response_model=DataSourceOut, status_code=201)
async def upload_dataset(
    files: list[UploadFile] = File(...),
    name: str = Form(default="", max_length=120),
    description: str | None = Form(default=None, max_length=1000),
    currency: str = Form(default="INR", min_length=3, max_length=3),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DataSourceOut:
    """Create a data source from CSV / Excel files: each file (or Excel sheet) becomes a table."""
    limit = int(get_settings().max_upload_mb * 1024 * 1024)
    contents: list[tuple[str, bytes]] = []
    total = 0
    for f in files:
        data = await f.read(limit + 1 - total)
        total += len(data)
        if total > limit:
            raise BadRequestError(f"Uploads are limited to {get_settings().max_upload_mb:g} MB in total.")
        contents.append((f.filename or "data.csv", data))
    return DataSourceService(db, user).create_upload(
        name=name, files=contents, description=description, currency=currency
    )


@router.get("/{source_id}", response_model=DataSourceOut)
def get_dataset(source_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DataSourceOut:
    return to_out(DataSourceService(db, user).get(source_id), check=True)


@router.patch("/{source_id}", response_model=DataSourceOut)
def update_dataset(
    source_id: str, body: DataSourceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DataSourceOut:
    return DataSourceService(db, user).update(source_id, body)


@router.delete("/{source_id}", status_code=204)
def delete_dataset(source_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    DataSourceService(db, user).delete(source_id)
    return Response(status_code=204)


@router.get("/{source_id}/schema", response_model=SchemaOut)
def get_schema(
    source_id: str, refresh: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SchemaOut:
    return DataSourceService(db, user).schema(source_id, refresh=refresh)
