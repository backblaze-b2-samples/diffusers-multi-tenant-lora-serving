from fastapi import APIRouter

from app.service import workers
from app.types import WorkerStatus

router = APIRouter()


@router.get("/workers", response_model=list[WorkerStatus])
def list_workers():
    return workers.list_workers()
