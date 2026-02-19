from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from codial_service.app.models import (
    CodialRuleAddRequest,
    CodialRuleRemoveRequest,
    CodialRuleResponse,
)
from codial_service.modules.common.deps import get_rule_store, require_auth

router = APIRouter()


@router.get("/codial/rules", response_model=CodialRuleResponse)
async def list_codial_rules(
    request: Request,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    require_auth(request, authorization)
    return CodialRuleResponse(rules=get_rule_store(request).list_rules())


@router.post("/codial/rules", response_model=CodialRuleResponse)
async def add_codial_rule(
    request: Request,
    req: CodialRuleAddRequest,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    require_auth(request, authorization)
    return CodialRuleResponse(rules=await get_rule_store(request).add_rule(req.rule))


@router.delete("/codial/rules", response_model=CodialRuleResponse)
async def remove_codial_rule(
    request: Request,
    req: CodialRuleRemoveRequest,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    require_auth(request, authorization)
    try:
        return CodialRuleResponse(rules=await get_rule_store(request).remove_rule(req.index))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="규칙 번호가 올바르지 않아요.") from exc
