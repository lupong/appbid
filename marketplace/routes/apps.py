"""Routes for bid request publish / list / fetch.

URL paths kept at ``/apps/...`` for backward compatibility with the
original spec; internally these are bid requests, not credit applications.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from marketplace import ledger
from shared.models import BidRequest, BidRequestCreate, RequestStatus

router = APIRouter(prefix="/apps", tags=["bid_requests"])


@router.post("", response_model=BidRequest, status_code=201)
async def create_request(body: BidRequestCreate) -> BidRequest:
    req = BidRequest(**body.model_dump())
    return await ledger.save_request(req)


@router.get("", response_model=list[BidRequest])
async def list_open_requests(status: RequestStatus | None = None) -> list[BidRequest]:
    return await ledger.list_requests(status=status)


@router.get("/{request_id}", response_model=BidRequest)
async def get_request(request_id: UUID) -> BidRequest:
    req = await ledger.get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="bid request not found")
    return req
