from datetime import datetime, timezone
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import BASELINE_RESOLVERS, TW_RESOLVERS, BASELINE_TIMEOUT, TW_TIMEOUT
from .schemas import (
    ResolveResponse, BaselineResult, TwResolverResult, Conclusion,
    ResolverResult, ResolveStatus, TwClassification
)
from .dns_probe import normalize_domain, probe_all
from .verdict import classify_tw_result, aggregate_conclusion


app = FastAPI(title="台湾DNS RPZ检测", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/resolve", response_model=ResolveResponse)
async def resolve(target: str = Query(..., description="域名或URL")):
    """
    DNS RPZ检测API
    """
    original_input = target.strip()
    
    # 域名规范化
    domain = normalize_domain(original_input)
    if not domain:
        raise HTTPException(status_code=400, detail="无效的域名或URL")

    # 查询所有DNS
    results = await probe_all(
        domain, BASELINE_RESOLVERS, TW_RESOLVERS,
        BASELINE_TIMEOUT, TW_TIMEOUT
    )

    # 处理基准结果
    baseline_ips = set()
    baseline_detail = []
    for r in results["baseline"]:
        baseline_detail.append(ResolverResult(
            name=r["name"],
            ip=r["ip"],
            status=ResolveStatus(r["status"]),
            ips=r["ips"],
            msg=r["msg"]
        ))
        if r["status"] == "ok":
            baseline_ips.update(r["ips"])

    # 基准解析失败检查
    if not baseline_ips:
        # 检查是否NXDOMAIN
        if any(r["status"] == "nxdomain" for r in results["baseline"]):
            raise HTTPException(status_code=404, detail="域名不存在（基准DNS返回NXDOMAIN）")
        raise HTTPException(status_code=502, detail="无法获取基准DNS解析结果，请检查网络")

    # 处理台湾DNS结果
    tw_results = []
    tw_classifications = []
    for r in results["tw"]:
        classification = classify_tw_result(r, baseline_ips)
        tw_classifications.append(classification)
        tw_results.append(TwResolverResult(
            name=r["name"],
            ip=r["ip"],
            status=ResolveStatus(r["status"]),
            ips=r["ips"],
            classification=classification,
            msg=r["msg"]
        ))

    # 聚合结论
    conclusion_status, reasons = aggregate_conclusion(tw_classifications)

    return ResolveResponse(
        input=original_input,
        domain=domain,
        timestamp=datetime.now(timezone.utc).isoformat(),
        baseline=BaselineResult(
            ips=list(baseline_ips),
            detail=baseline_detail
        ),
        tw_resolvers=tw_results,
        conclusion=Conclusion(
            status=conclusion_status,
            reason=reasons
        )
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
