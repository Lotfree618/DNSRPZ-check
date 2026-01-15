"""FastAPI 入口與後台調度"""
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from . import config

# 配置調試日誌（在 config.py 中設置 LOG_LEVEL）
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from .domains import (
    load_domains, get_all_domains, get_domain,
    add_domain, update_domain, delete_domain, batch_delete_domains,
    update_note, toggle_reported, batch_set_reported
)
from .dns_probe import probe_domain, probe_domain_simple
from .verdict import aggregate_verdict
from .store import store
from .schemas import (
    StatusResponse, DomainSummary, DomainDetail, HealthResponse, CheckResponse,
    DomainInfo, DomainListResponse, AddDomainRequest, UpdateDomainRequest,
    BatchDeleteRequest, UpdateNoteRequest, MessageResponse,
    ToggleReportedResponse, BatchDeleteResponse,
    BatchSetReportedRequest, BatchSetReportedResponse
)


async def probe_loop():
    """後台探測循環"""
    from .domains import get_domain, auto_add_domain, extract_root_domain
    from urllib.parse import urlparse
    
    loop_count = 0
    while True:
        loop_count += 1
        logger.info(f"========== 探測循環 #{loop_count} 開始 ==========")
        
        try:
            domains = load_domains()
            current_domains = set(domains)
            now = datetime.now(timezone.utc)
            
            logger.info(f"[循環#{loop_count}] 從 domains.json 載入 {len(domains)} 個域名")
            
            # 清理已刪除的網域
            store.clear_stale(current_domains)
            
            # 過濾需要探測的域名（異常域名使用較長間隔）
            domains_to_probe = []
            skipped_polluted = 0  # 因污染跳過的計數
            
            for domain in domains:
                domain_info = get_domain(domain)
                if domain_info:
                    last_probe_str = domain_info.get("last_probe_at")
                    is_polluted = domain_info.get("polluted", False)
                    
                    # 異常/已封鎖域名使用較長間隔
                    if is_polluted and last_probe_str:
                        try:
                            # 解析 ISO 時間
                            last_probe = datetime.fromisoformat(last_probe_str.replace("Z", "+00:00"))
                            elapsed = (now - last_probe).total_seconds()
                            if elapsed < config.ABNORMAL_PROBE_INTERVAL:
                                skipped_polluted += 1
                                continue  # 跳過，尚未到探測時間
                        except Exception as e:
                            logger.warning(f"[循環#{loop_count}] 時間解析失敗 {domain}: {e}")
                
                domains_to_probe.append(domain)
            
            logger.info(f"[循環#{loop_count}] 需探測: {len(domains_to_probe)}, 跳過(污染未到時間): {skipped_polluted}")
            
            # 並發探測（帶限制）
            sem = asyncio.Semaphore(config.MAX_CONCURRENCY)
            probe_success_count = 0
            probe_error_count = 0
            
            async def probe_with_limit(domain: str):
                nonlocal probe_success_count, probe_error_count
                async with sem:
                    try:
                        logger.debug(f"[循環#{loop_count}] 開始探測: {domain}")
                        result = await probe_domain(domain)
                        verdict = aggregate_verdict(result)
                        store.update(domain, verdict)
                        probe_success_count += 1
                        logger.debug(f"[循環#{loop_count}] 探測完成: {domain}, 狀態={verdict.get('status')}")
                        
                        # 自動收錄跳轉追蹤中發現的新域名
                        redirect_trace = verdict.get("redirect_trace")
                        if redirect_trace:
                            # 更新域名組
                            from .domain_groups import extract_domains_from_trace, update_domain_group
                            domains_in_chain = extract_domains_from_trace(domain, redirect_trace)
                            update_domain_group(domains_in_chain)
                            
                            chain = redirect_trace.get("chain", [])
                            for step in chain:
                                url = step.get("url", "")
                                if url:
                                    try:
                                        parsed = urlparse(url)
                                        hostname = parsed.hostname
                                        if hostname:
                                            # www 收斂到根域名
                                            root_domain = extract_root_domain(hostname)
                                            if root_domain and root_domain not in current_domains:
                                                added = auto_add_domain(hostname)
                                                if added:
                                                    logger.info(f"[循環#{loop_count}] 自動收錄新域名: {hostname} -> {root_domain}")
                                                current_domains.add(root_domain)
                                    except Exception as e:
                                        logger.warning(f"[循環#{loop_count}] 自動收錄異常: {url}, 錯誤={e}")
                    except Exception as e:
                        probe_error_count += 1
                        logger.error(f"[循環#{loop_count}] 探測異常: {domain}, 錯誤={e}", exc_info=True)
            
            # 執行並發探測
            logger.info(f"[循環#{loop_count}] 開始並發探測 {len(domains_to_probe)} 個域名，並發限制={config.MAX_CONCURRENCY}")
            results = await asyncio.gather(
                *[probe_with_limit(d) for d in domains_to_probe],
                return_exceptions=True
            )
            
            # 檢查 gather 結果中的異常
            exception_count = sum(1 for r in results if isinstance(r, Exception))
            if exception_count > 0:
                logger.warning(f"[循環#{loop_count}] gather 返回 {exception_count} 個異常")
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.error(f"[循環#{loop_count}] 任務 {i} 異常: {r}")
            
            # 批量寫入待處理的更新到 domains.json
            try:
                flushed = store.flush_pending()
                if flushed > 0:
                    logger.info(f"[循環#{loop_count}] 批量寫入 {flushed} 條記錄到 domains.json")
            except Exception as e:
                logger.error(f"[循環#{loop_count}] 批量寫入失敗: {e}", exc_info=True)
            
            logger.info(f"[循環#{loop_count}] 探測完成: 成功={probe_success_count}, 錯誤={probe_error_count}, gather異常={exception_count}")
            
        except Exception as e:
            logger.error(f"[循環#{loop_count}] 探測循環主體錯誤: {e}", exc_info=True)
        
        logger.info(f"========== 探測循環 #{loop_count} 結束，等待 {config.PROBE_INTERVAL} 秒 ==========")
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


@app.get("/api/related-domains")
async def related_domains(domain: str = Query(..., description="網域")):
    """獲取某網域的相關網站列表"""
    from .domain_groups import get_related_domains
    from .domains import extract_root_domain
    
    related = get_related_domains(domain)
    all_domains = get_all_domains()
    probe_results = store.get_all()
    
    result = []
    for rd in related:
        # 獲取該域名的監控狀態
        domain_info = all_domains.get(rd)
        probe_data = probe_results.get(rd, {})
        
        result.append({
            "domain": rd,
            "in_list": rd in all_domains,
            "status": probe_data.get("status") if rd in all_domains else None,
            "polluted": domain_info.get("polluted", False) if domain_info else False
        })
    
    return {"domain": extract_root_domain(domain), "related": result}


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
    
    # DNS 是否正常：未污染/解析失敗 → dns_ok: true，已污染 → dns_ok: false
    dns_ok = verdict["status"] in ("未污染", "解析失敗")
    
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
        probe_data = probe_results.get(domain, {})
        
        domains.append(DomainInfo(
            domain=domain,
            reported=info.get("reported", False),
            polluted=info.get("polluted", False),
            note=info.get("note", ""),
            created_at=info.get("created_at", ""),
            last_probe_at=info.get("last_probe_at"),
            trace_status=info.get("trace_status")
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


@app.post("/api/domains/batch-reported", response_model=BatchSetReportedResponse)
async def batch_set_domain_reported(req: BatchSetReportedRequest):
    """批量設置上報狀態"""
    updated = batch_set_reported(req.domains, req.reported)
    return BatchSetReportedResponse(success=True, updated=updated)
