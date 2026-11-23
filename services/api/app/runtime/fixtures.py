from fastapi import APIRouter

from app.service.fixtures import publish_fixtures
from app.types import AdapterDetail

router = APIRouter()


@router.post("/fixtures/publish", response_model=list[AdapterDetail])
def publish_demo_adapters():
    """Publish the pinned demo adapters (acme: 2, globex: 1). Skips existing versions.

    Downloads each pinned file from the Hugging Face Hub once, so the first call
    takes as long as fetching a few hundred MB.
    """
    return publish_fixtures()
