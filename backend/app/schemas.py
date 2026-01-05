"""Pydantic 模型定义"""
from typing import List, Optional
from pydantic import BaseModel


class ResolverResult(BaseModel):
    """单个解析器的结果"""
    resolver: str
    name: str
    status: str  # ok, nxdomain, timeout, error
    ips: List[str] = []
    msg: Optional[str] = None


class TwResolverResult(ResolverResult):
    """台湾解析器结果（含分类）"""
    category: str  # 正常, 解析差异, 被阻断, 已封锁, 超时, 错误


class BaselineInfo(BaseModel):
    """基准解析信息"""
    ips: List[str]
    detail: List[ResolverResult]


class DomainSummary(BaseModel):
    """域名摘要（列表展示用）"""
    domain: str
    status: str  # 正常, 异常
    last_probe_at: str


class RedirectStep(BaseModel):
    """单步跳转信息"""
    url: str
    status: int


class RedirectTrace(BaseModel):
    """跳转追踪结果"""
    final_url: Optional[str] = None
    final_domain: Optional[str] = None
    chain: List[RedirectStep] = []
    success: bool = False
    error: Optional[str] = None


class DomainDetail(BaseModel):
    """域名详情"""
    domain: str
    status: str
    reasons: List[str]
    baseline: BaselineInfo
    tw: List[TwResolverResult]
    redirect_trace: Optional[RedirectTrace] = None
    last_probe_at: str


class StatusResponse(BaseModel):
    """状态列表响应"""
    timestamp: str
    interval_sec: int
    domains: List[DomainSummary]


class HealthResponse(BaseModel):
    """健康检查响应"""
    ok: bool


class CheckResponse(BaseModel):
    """单域名检测响应"""
    domain: str
    available: bool  # 域名是否可用（True=未被污染）
    status: str  # 正常, 异常, 空解析
    reasons: List[str]  # 异常原因列表
    baseline: BaselineInfo
    tw: List[TwResolverResult]
    redirect_trace: Optional[RedirectTrace] = None
    checked_at: str
