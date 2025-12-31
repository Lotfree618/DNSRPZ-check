from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ResolveStatus(str, Enum):
    OK = "ok"
    NXDOMAIN = "nxdomain"
    TIMEOUT = "timeout"
    ERROR = "error"


class TwClassification(str, Enum):
    NORMAL = "正常"
    BLOCKED = "已封锁"
    NXDOMAIN = "被阻断"
    TIMEOUT = "超时"
    DIFF = "差异（可能CDN）"
    ERROR = "错误"


class ConclusionStatus(str, Enum):
    OK = "OK"
    ABNORMAL = "异常"
    UNCERTAIN = "不确定"


class ResolverResult(BaseModel):
    """单个DNS解析器的查询结果"""
    name: str
    ip: str
    status: ResolveStatus
    ips: list[str] = []
    msg: Optional[str] = None


class BaselineResult(BaseModel):
    """基准解析结果（Google + Cloudflare）"""
    ips: list[str]  # 合并后的IP集合
    detail: list[ResolverResult]


class TwResolverResult(BaseModel):
    """台湾DNS解析结果（含分类）"""
    name: str
    ip: str
    status: ResolveStatus
    ips: list[str] = []
    classification: TwClassification
    msg: Optional[str] = None


class Conclusion(BaseModel):
    """最终结论"""
    status: ConclusionStatus
    reason: list[str]


class ResolveResponse(BaseModel):
    """完整API响应"""
    input: str
    domain: str
    timestamp: str
    baseline: BaselineResult
    tw_resolvers: list[TwResolverResult]
    conclusion: Conclusion
