"""DNS 查询模块"""
import asyncio
import time
from typing import Dict
import dns.resolver
import dns.asyncresolver
from . import config
from .redirect_trace import trace_redirects


async def query_resolver(domain: str, server_ip: str, timeout: float) -> Dict:
    """向指定 DNS 服务器查询 A/AAAA 记录"""
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = [server_ip]
    resolver.lifetime = timeout
    resolver.timeout = timeout
    
    ips = []
    
    # 查询 A 记录
    try:
        answers = await resolver.resolve(domain, "A")
        ips.extend(r.to_text() for r in answers)
    except dns.resolver.NXDOMAIN:
        return {"status": "nxdomain", "ips": []}
    except dns.resolver.Timeout:
        return {"status": "timeout", "ips": []}
    except dns.resolver.NoAnswer:
        pass
    except Exception as e:
        return {"status": "error", "ips": [], "msg": str(e)}
    
    # 查询 AAAA 记录
    try:
        answers = await resolver.resolve(domain, "AAAA")
        ips.extend(r.to_text() for r in answers)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
        pass
    except Exception:
        pass
    
    return {"status": "ok", "ips": sorted(set(ips))}


async def probe_domain(domain: str, with_redirect_trace: bool = True) -> Dict:
    """
    探测单个域名
    
    Args:
        domain: 要探测的域名
        with_redirect_trace: 是否执行重定向追踪（默认 True）
    """
    start_time = time.perf_counter()
    tasks = []
    
    for ip, name in config.BASELINE_RESOLVERS.items():
        tasks.append(("baseline", ip, name, config.BASELINE_TIMEOUT))
    
    for ip, name in config.TW_RESOLVERS.items():
        tasks.append(("tw", ip, name, config.TW_TIMEOUT))
    
    results = await asyncio.gather(
        *[query_resolver(domain, ip, timeout) for _, ip, _, timeout in tasks],
        return_exceptions=True
    )
    
    baseline_results = []
    tw_results = []
    
    for i, (type_, ip, name, _) in enumerate(tasks):
        res = results[i]
        if isinstance(res, Exception):
            res = {"status": "error", "ips": [], "msg": str(res)}
        
        item = {"resolver": ip, "name": name, **res}
        
        if type_ == "baseline":
            baseline_results.append(item)
        else:
            tw_results.append(item)
    
    redirect_result = None
    if with_redirect_trace:
        redirect_result = await trace_redirects(domain)
    
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    
    return {
        "domain": domain,
        "baseline": baseline_results,
        "tw": tw_results,
        "redirect_trace": redirect_result,
        "latency_ms": latency_ms
    }


async def probe_domain_simple(domain: str) -> Dict:
    """简化版探测（不做重定向追踪，供 Worker 调用）"""
    return await probe_domain(domain, with_redirect_trace=False)

