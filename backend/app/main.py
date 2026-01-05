"""FastAPI 入口与后台调度"""
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .domains import load_domains
from .dns_probe import probe_domain
from .verdict import aggregate_verdict
from .store import store
from .schemas import StatusResponse, DomainSummary, DomainDetail, HealthResponse, CheckResponse


async def probe_loop():
    """后台探测循环"""
    while True:
        try:
            domains = load_domains()
            current_domains = set(domains)
            
            # 清理已删除的域名
            store.clear_stale(current_domains)
            
            # 并发探测（带限制）
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
            print(f"探测循环错误: {e}")
        
        await asyncio.sleep(config.PROBE_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动后台任务
    task = asyncio.create_task(probe_loop())
    yield
    # 关闭时取消任务
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="域名台湾DNS RPZ检测",
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
    """健康检查"""
    return {"ok": True}


@app.get("/api/status", response_model=StatusResponse)
async def status():
    """获取域名状态列表"""
    results = store.get_all()
    domains = []
    
    for domain, data in sorted(results.items()):
        domains.append(DomainSummary(
            domain=domain,
            status=data.get("status", "异常"),
            last_probe_at=data.get("last_probe_at", "")
        ))
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "interval_sec": config.PROBE_INTERVAL,
        "domains": domains
    }


@app.get("/api/detail", response_model=DomainDetail)
async def detail(domain: str = Query(..., description="域名")):
    """获取域名详情"""
    data = store.get(domain)
    if not data:
        raise HTTPException(status_code=404, detail="域名未找到")
    
    return DomainDetail(**data)


@app.get("/api/check", response_model=CheckResponse)
async def check_domain(domain: str = Query(..., description="要检测的域名")):
    """
    实时检测单个域名的污染状态
    
    - **domain**: 要检测的域名（如 example.com）
    - 返回域名的可用性（是否被污染）和详细解析结果
    """
    # 实时探测
    result = await probe_domain(domain)
    verdict = aggregate_verdict(result)
    
    # 判断可用性：status 为 "正常" 或 "空解析" 时视为可用
    available = verdict["status"] in ("正常", "空解析")
    
    return CheckResponse(
        domain=domain,
        available=available,
        status=verdict["status"],
        reasons=verdict["reasons"],
        baseline=verdict["baseline"],
        tw=verdict["tw"],
        redirect_trace=verdict.get("redirect_trace"),
        checked_at=datetime.now(timezone.utc).isoformat()
    )
