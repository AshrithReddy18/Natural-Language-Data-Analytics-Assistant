from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.api import DataSourceCreate, DataSourceOut, DataSourceUpdate, SchemaOut
from app.services.datasource_service import DataSourceService, to_out

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DataSourceOut])
def list_datasets(db: Session = Depends(get_db)) -> list[DataSourceOut]:
    return DataSourceService(db).list()


@router.post("", response_model=DataSourceOut, status_code=201)
def create_dataset(body: DataSourceCreate, db: Session = Depends(get_db)) -> DataSourceOut:
    return DataSourceService(db).create(body)


@router.get("/{source_id}", response_model=DataSourceOut)
def get_dataset(source_id: str, db: Session = Depends(get_db)) -> DataSourceOut:
    return to_out(DataSourceService(db).get(source_id), check=True)


@router.patch("/{source_id}", response_model=DataSourceOut)
def update_dataset(source_id: str, body: DataSourceUpdate, db: Session = Depends(get_db)) -> DataSourceOut:
    return DataSourceService(db).update(source_id, body)


@router.delete("/{source_id}", status_code=204)
def delete_dataset(source_id: str, db: Session = Depends(get_db)) -> Response:
    DataSourceService(db).delete(source_id)
    return Response(status_code=204)


@router.get("/{source_id}/schema", response_model=SchemaOut)
def get_schema(source_id: str, refresh: bool = False, db: Session = Depends(get_db)) -> SchemaOut:
    return DataSourceService(db).schema(source_id, refresh=refresh)
