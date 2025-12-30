from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime

class DnsAnswer(BaseModel):
    status: str  # NOERROR, NXDOMAIN, etc.
    answers: List[str]
    ttl: Optional[int] = None

class ResolverResult(BaseModel):
    ip: str
    A: DnsAnswer
    AAAA: DnsAnswer
    elapsed_ms: int

class BaselineInfo(BaseModel):
    agreed: bool
    types_checked: List[str]
    reference: Dict[str, List[str]] # "A": ["1.2.3.4"], "AAAA": []

class MismatchDetail(BaseModel):
    resolver: str
    type: str # A or AAAA
    reason: str

class ComparisonInfo(BaseModel):
    mismatches: List[MismatchDetail]

class ConclusionInfo(BaseModel):
    status: str # OK, SUSPECTED_RPZ, POSSIBLE_INTERFERENCE, UNCERTAIN
    reasons: List[str]

class ResolveResponse(BaseModel):
    domain: str
    timestamp: datetime
    baseline: BaselineInfo
    resolvers: Dict[str, ResolverResult]
    comparison: ComparisonInfo
    conclusion: ConclusionInfo
