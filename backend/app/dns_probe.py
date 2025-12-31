"""DNS 查询模块"""
import asyncio
from typing import Dict, List, Set
import dns.resolver
import dns.asyncresolver
from . import config


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


async def probe_domain(domain: str) -> Dict:
    """探测单个域名"""
    tasks = []
    
    # 基准解析器
    for ip, name in config.BASELINE_RESOLVERS.items():
        tasks.append(("baseline", ip, name, config.BASELINE_TIMEOUT))
    
    # 台湾解析器
    for ip, name in config.TW_RESOLVERS.items():
        tasks.append(("tw", ip, name, config.TW_TIMEOUT))
    
    # 并发查询
    results = await asyncio.gather(
        *[query_resolver(domain, ip, timeout) for _, ip, _, timeout in tasks],
        return_exceptions=True
    )
    
    # 组织结果
    baseline_results = []
    tw_results = []
    
    for i, (type_, ip, name, _) in enumerate(tasks):
        res = results[i]
        if isinstance(res, Exception):
            res = {"status": "error", "ips": [], "msg": str(res)}
        
        item = {
            "resolver": ip,
            "name": name,
            **res
        }
        
        if type_ == "baseline":
            baseline_results.append(item)
        else:
            tw_results.append(item)
    
    return {
        "domain": domain,
        "baseline": baseline_results,
        "tw": tw_results
    }
