import asyncio
import time
import dns.asyncresolver
import dns.message
import dns.rdatatype
import dns.flags
from typing import Dict, List, Optional
from app.config import RESOLVERS, DNS_TIMEOUT, DNS_LIFETIME
from app.schemas import ResolverResult, DnsAnswer

async def query_once(resolver_ip: str, domain: str, rdtype: str) -> DnsAnswer:
    # 构造查询
    try:
        # Create a UDP query
        qname = dns.name.from_text(domain)
        request = dns.message.make_query(qname, getattr(dns.rdatatype, rdtype))
        
        # Send query
        response = await dns.asyncquery.udp(
            request, 
            resolver_ip, 
            timeout=DNS_TIMEOUT
        )
        
        # Parse result
        answers = []
        min_ttl = None
        
        if response.rcode() == dns.rcode.NOERROR:
            status = "NOERROR"
            for rrset in response.answer:
                if rrset.rdtype == getattr(dns.rdatatype, rdtype):
                    if min_ttl is None:
                        min_ttl = rrset.ttl
                    else:
                        min_ttl = min(min_ttl, rrset.ttl)
                    
                    for rr in rrset:
                        answers.append(rr.to_text())
        elif response.rcode() == dns.rcode.NXDOMAIN:
            status = "NXDOMAIN"
        elif response.rcode() == dns.rcode.SERVFAIL:
            status = "SERVFAIL"
        elif response.rcode() == dns.rcode.REFUSED:
            status = "REFUSED"
        else:
            status = f"RCODE_{response.rcode()}"
            
        return DnsAnswer(status=status, answers=answers, ttl=min_ttl)

    except dns.exception.Timeout:
        return DnsAnswer(status="TIMEOUT", answers=[], ttl=None)
    except Exception as e:
        return DnsAnswer(status=f"ERROR_{type(e).__name__}", answers=[], ttl=None)

async def probe_resolver(name: str, ip: str, domain: str) -> ResolverResult:
    start_time = time.time()
    
    # Concurrent A and AAAA
    task_a = query_once(ip, domain, "A")
    task_aaaa = query_once(ip, domain, "AAAA")
    
    res_a, res_aaaa = await asyncio.gather(task_a, task_aaaa)
    
    elapsed = int((time.time() - start_time) * 1000)
    
    return ResolverResult(
        ip=ip,
        A=res_a,
        AAAA=res_aaaa,
        elapsed_ms=elapsed
    )

async def probe_domain(domain: str) -> Dict[str, ResolverResult]:
    tasks = []
    names = []
    
    for name, ip in RESOLVERS.items():
        names.append(name)
        tasks.append(probe_resolver(name, ip, domain))
    
    results_list = await asyncio.gather(*tasks)
    
    results = {}
    for name, res in zip(names, results_list):
        results[name] = res
        
    return results
