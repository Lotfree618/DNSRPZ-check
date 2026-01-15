"""Pydantic 模型定義"""
from typing import List, Optional, Union
from pydantic import BaseModel


class ResolverResult(BaseModel):
    """單個解析器的結果"""
    resolver: str
    name: str
    status: str  # ok, nxdomain, timeout, error
    ips: List[str] = []
    msg: Optional[str] = None


class TwResolverResult(ResolverResult):
    """台灣解析器結果（含分類）"""
    category: str  # 正常, 解析差異, 被阻斷, 已封鎖, 逾時, 錯誤


class BaselineInfo(BaseModel):
    """基準解析資訊"""
    ips: List[str]
    detail: List[ResolverResult]


class DomainSummary(BaseModel):
    """網域摘要（列表展示用）"""
    domain: str
    status: str  # 正常, 異常
    last_probe_at: str


class RedirectStep(BaseModel):
    """單步跳轉資訊"""
    url: str
    status: Union[int, str]  # HTTP 狀態碼或 "空解析"


class RedirectTrace(BaseModel):
    """跳轉追蹤結果"""
    final_url: Optional[str] = None
    final_domain: Optional[str] = None
    final_status_code: Optional[int] = None
    chain: List[RedirectStep] = []
    success: bool = False
    trace_status: Optional[str] = None  # 追蹤成功 | 追蹤異常
    error: Optional[str] = None


class DomainDetail(BaseModel):
    """網域詳情"""
    domain: str
    status: str
    reasons: List[str]
    baseline: BaselineInfo
    tw: List[TwResolverResult]
    redirect_trace: Optional[RedirectTrace] = None
    last_probe_at: str


class StatusResponse(BaseModel):
    """狀態列表響應"""
    timestamp: str
    interval_sec: int
    domains: List[DomainSummary]


class HealthResponse(BaseModel):
    """健康檢查響應"""
    ok: bool


class CheckResponse(BaseModel):
    """簡化版檢測響應（供 Orchestrator Worker 調用）"""
    dns_ok: bool  # DNS 是否正常（未被污染）
    http_ok: bool  # HTTP 是否可達（簡化為與 dns_ok 一致）
    latency_ms: int  # 探測耗時（毫秒）
    status_code: int  # 固定返回 200 或 0


# ========== 網域管理相關模型 ==========

class DomainInfo(BaseModel):
    """網域完整資訊"""
    domain: str
    reported: bool
    polluted: bool
    note: str
    created_at: str
    last_probe_at: Optional[str] = None
    trace_status: Optional[str] = None  # 追蹤成功 | 追蹤異常


class DomainListResponse(BaseModel):
    """網域列表響應"""
    timestamp: str
    total: int
    domains: List[DomainInfo]


class AddDomainRequest(BaseModel):
    """新增網域請求"""
    domain: str
    note: str = ""


class UpdateDomainRequest(BaseModel):
    """修改網域請求"""
    new_domain: str


class BatchDeleteRequest(BaseModel):
    """批量刪除請求"""
    domains: List[str]


class UpdateNoteRequest(BaseModel):
    """更新備註請求"""
    note: str


class MessageResponse(BaseModel):
    """通用訊息響應"""
    success: bool
    message: str


class ToggleReportedResponse(BaseModel):
    """切換已上報狀態響應"""
    success: bool
    reported: bool


class BatchDeleteResponse(BaseModel):
    """批量刪除響應"""
    success: bool
    deleted: int


class BatchSetReportedRequest(BaseModel):
    """批量設置上報狀態請求"""
    domains: List[str]
    reported: bool


class BatchSetReportedResponse(BaseModel):
    """批量設置上報狀態響應"""
    success: bool
    updated: int
