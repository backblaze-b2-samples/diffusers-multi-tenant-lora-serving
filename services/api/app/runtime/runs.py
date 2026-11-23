"""Runs: compare requests, run detail and the adapters.json report."""

import logging

from fastapi import APIRouter

from app.runtime.generations import REJECTION_CODES
from app.runtime.metrics import record_rejection
from app.service import jobs, runs
from app.types import AdapterReport, AppError, CompareRequest, RunDetail, RunSummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runs/compare", response_model=RunDetail, status_code=202)
def compare(req: CompareRequest):
    """One job per adapter (plus the base model), all on the same prompt and seed."""
    try:
        return jobs.enqueue_compare(req)
    except AppError as e:
        if e.code in REJECTION_CODES:
            record_rejection(e.code)
            logger.warning("compare rejected tenant=%s code=%s", req.tenant_id, e.code)
        raise


@router.get("/runs", response_model=list[RunSummary])
def list_runs():
    return runs.list_runs()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str):
    return runs.get_run(run_id)


@router.get("/runs/{run_id}/report", response_model=AdapterReport)
def get_report(run_id: str):
    return runs.get_report(run_id)
