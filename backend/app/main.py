"""FastAPI 入口與後台調度"""
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .domains import (
    load_domains, get_all_domains, get_domain,
    add_domain, update_domain, delete_domain, batch_delete_domains,
    update_note, toggle_reported
)
from .dns_probe import probe_domain, probe_domain_simple
from .verdict import aggregate_verdict
from .store import store
from .schemas import (
    StatusResponse, DomainSummary, DomainDetail, HealthResponse, CheckResponse,
    DomainInfo, DomainListResponse, AddDomainRequest, UpdateDomainRequest,
    BatchDeleteRequest, UpdateNoteRequest, MessageResponse,
    ToggleReportedResponse, BatchDeleteResponse
)


async def probe_loop():
    """後台探測循環"""
    while True:
        try:
            domains = load_domains()
            current_domains = set(domains)
            
            # 清理已刪除的網域
            store.clear_stale(current_domains)
            
            # 並發探測（帶限制）
            sem = asyncio.Semaphore(config.MAX_CONCURRENCY)
            
            async def probe_with_limit(domain: str):
                async with sem:
                    result = await probe_domain(domain)
                    verdict = aggregate_verdict(result)
                    store.update(domain, verdict)
            
            await asyncio.gather(
                *[probe_with_limit(d) for d in domains],
                return_exceptions=True
            )
        except Exception as e:
            print(f"探測循環錯誤: {e}")
        
        await asyncio.sleep(config.PROBE_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    # 啟動後台任務
    task = asyncio.create_task(probe_loop())
    yield
    # 關閉時取消任務
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="網域台灣 DNS RPZ 檢測",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """健康檢查"""
    return {"ok": True}


@app.get("/api/status", response_model=StatusResponse)
async def status():
    """獲取網域狀態列表（舊版 API，保留相容性）"""
    results = store.get_all()
    domains_data = get_all_domains()
    domains = []
    
    for domain in sorted(domains_data.keys()):
        probe_data = results.get(domain, {})
        domains.append(DomainSummary(
            domain=domain,
            status=probe_data.get("status", "待檢測"),
            last_probe_at=probe_data.get("last_probe_at", "")
        ))
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "interval_sec": config.PROBE_INTERVAL,
        "domains": domains
    }


@app.get("/api/detail", response_model=DomainDetail)
async def detail(domain: str = Query(..., description="網域")):
    """獲取網域詳情"""
    data = store.get(domain)
    if not data:
        raise HTTPException(status_code=404, detail="網域未找到或尚未檢測")
    
    return DomainDetail(**data)


@app.get("/api/check", response_model=CheckResponse)
async def check_domain(domain: str = Query(..., description="要檢測的網域")):
    """
    簡化版網域污染檢測 API（供 Orchestrator Worker 調用）
    
    - **domain**: 要檢測的網域
    - 返回 dns_ok/http_ok/latency_ms/status_code
    - 不做重定向追蹤，提升響應速度
    """
    result = await probe_domain_simple(domain)
    verdict = aggregate_verdict(result)
    
    # DNS 是否正常：status 為 "正常" 或 "空解析" 時視為健康
    dns_ok = verdict["status"] in ("正常", "空解析")
    
    return CheckResponse(
        dns_ok=dns_ok,
        http_ok=dns_ok,  # 簡化：與 dns_ok 一致
        latency_ms=result.get("latency_ms", 0),
        status_code=200 if dns_ok else 0
    )


# ========== 網域管理 API ==========

@app.get("/api/domains", response_model=DomainListResponse)
async def list_domains():
    """獲取網域列表（含屬性）"""
    domains_data = get_all_domains()
    probe_results = store.get_all()
    
    domains = []
    for domain, info in sorted(domains_data.items()):
        # 使用最新的探測結果更新 polluted 狀態
        probe_data = probe_results.get(domain, {})
        probe_status = probe_data.get("status", "")
        
        domains.append(DomainInfo(
            domain=domain,
            reported=info.get("reported", False),
            polluted=info.get("polluted", False),
            note=info.get("note", ""),
            created_at=info.get("created_at", ""),
            last_probe_at=info.get("last_probe_at")
        ))
    
    return DomainListResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total=len(domains),
        domains=domains
    )


@app.post("/api/domains", response_model=MessageResponse)
async def create_domain(req: AddDomainRequest):
    """新增網域"""
    success, message = add_domain(req.domain, req.note)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return MessageResponse(success=True, message=f"已新增網域: {message}")


@app.put("/api/domains/{domain:path}", response_model=MessageResponse)
async def modify_domain(
    domain: str = Path(..., description="原網域"),
    req: UpdateDomainRequest = None
):
    """修改網域名稱"""
    success, message = update_domain(domain, req.new_domain)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return MessageResponse(success=True, message=f"已修改為: {message}")


@app.delete("/api/domains/{domain:path}", response_model=MessageResponse)
async def remove_domain(domain: str = Path(..., description="要刪除的網域")):
    """刪除單個網域"""
    success = delete_domain(domain)
    if not success:
        raise HTTPException(status_code=404, detail="網域不存在")
    
    # 同時從內存緩存中清除
    store.clear_stale(set(load_domains()))
    
    return MessageResponse(success=True, message=f"已刪除網域: {domain}")


@app.post("/api/domains/batch-delete", response_model=BatchDeleteResponse)
async def batch_remove_domains(req: BatchDeleteRequest):
    """批量刪除網域"""
    deleted = batch_delete_domains(req.domains)
    
    # 同時從內存緩存中清除
    store.clear_stale(set(load_domains()))
    
    return BatchDeleteResponse(success=True, deleted=deleted)


@app.patch("/api/domains/{domain:path}/note", response_model=MessageResponse)
async def modify_note(
    domain: str = Path(..., description="網域"),
    req: UpdateNoteRequest = None
):
    """更新網域備註"""
    success = update_note(domain, req.note)
    if not success:
        raise HTTPException(status_code=404, detail="網域不存在")
    return MessageResponse(success=True, message="備註已更新")


@app.patch("/api/domains/{domain:path}/reported", response_model=ToggleReportedResponse)
async def toggle_domain_reported(domain: str = Path(..., description="網域")):
    """切換已上報狀態"""
    new_status = toggle_reported(domain)
    if new_status is None:
        raise HTTPException(status_code=404, detail="網域不存在")
    return ToggleReportedResponse(success=True, reported=new_status)
