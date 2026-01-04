"""HTTP 跳转追踪模块"""
import httpx
from typing import Dict, List
from urllib.parse import urlparse


async def trace_redirects(domain: str, timeout: float = 10.0) -> Dict:
    """追踪域名的HTTP重定向链"""
    chain = []
    start_url = f"https://{domain}"
    final_url = None
    success = False
    error_msg = None
    
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            verify=False  # 忽略SSL证书错误
        ) as client:
            url = start_url
            max_redirects = 10
            
            for _ in range(max_redirects):
                try:
                    resp = await client.get(url)
                    chain.append({
                        "url": url,
                        "status": resp.status_code
                    })
                    
                    # 判断是否为重定向
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location", "")
                        if not location:
                            break
                        # 处理相对路径
                        if location.startswith("/"):
                            parsed = urlparse(url)
                            location = f"{parsed.scheme}://{parsed.netloc}{location}"
                        url = location
                    else:
                        # 非重定向，结束
                        final_url = url
                        success = True
                        break
                        
                except httpx.ConnectError:
                    chain.append({"url": url, "status": 0})
                    error_msg = "连接失败"
                    break
                except httpx.TimeoutException:
                    chain.append({"url": url, "status": 0})
                    error_msg = "超时"
                    break
                    
    except Exception as e:
        error_msg = str(e) if str(e) else "请求失败"
    
    # 如果没有成功但有链，最后一个是最终URL
    if not final_url and chain:
        final_url = chain[-1]["url"]
    
    # 提取最终域名
    final_domain = None
    if final_url:
        parsed = urlparse(final_url)
        final_domain = parsed.netloc
    
    return {
        "final_url": final_url,
        "final_domain": final_domain,
        "chain": chain,
        "success": success,
        "error": error_msg
    }
