"""HTTP 跳轉追蹤模塊"""
import httpx
from typing import Dict, List, Optional
from urllib.parse import urlparse
from . import config
from .domains import get_domain, extract_root_domain
from .store import store


async def trace_redirects(
    domain: str, 
    timeout: float = 10.0,
    current_tw_results: Optional[List[Dict]] = None
) -> Dict:
    """
    追踪域名的HTTP重定向链
    
    Args:
        domain: 要追踪的域名
        timeout: HTTP 請求超時
        current_tw_results: 當前域名的台灣 DNS 結果（用於判斷空解析）
    """
    chain = []
    start_url = f"https://{domain}"
    final_url = None
    success = False
    trace_status = None
    error_msg = None
    final_status_code = None
    is_empty_resolution = False
    
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            verify=False  # 忽略SSL证书错误
        ) as client:
            url = start_url
            max_redirects = config.MAX_REDIRECTS
            
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
                        # 处理相对路径和 protocol-relative URL
                        if location.startswith("//"):
                            # Protocol-relative URL (如 //www.example.com/path)
                            parsed = urlparse(url)
                            location = f"{parsed.scheme}:{location}"
                        elif location.startswith("/"):
                            # 普通相对路径 (如 /path/to/page)
                            parsed = urlparse(url)
                            location = f"{parsed.scheme}://{parsed.netloc}{location}"
                        url = location
                    else:
                        # 非重定向，记录最终状态
                        final_url = url
                        final_status_code = resp.status_code
                        
                        # 追踪成功判定：200/404 = 成功，其他 = 失敗
                        if resp.status_code in (200, 404):
                            success = True
                            trace_status = "追蹤成功"
                        else:
                            success = False
                            trace_status = "追蹤失敗"
                        break
                        
                except httpx.ConnectError:
                    # 連線失敗，檢查目標域名的解析狀態
                    parsed = urlparse(url)
                    target_domain = parsed.netloc
                    root_domain = extract_root_domain(target_domain) if target_domain else None
                    current_root = extract_root_domain(domain)
                    
                    # 檢查目標域名是否在監控列表且有探測記錄
                    if root_domain:
                        target_info = get_domain(root_domain)
                        if target_info:
                            # 判斷台灣 DNS 是否有解析失敗
                            has_tw_resolve_failure = False
                            tw_results_to_check = None
                            
                            # 如果目標是當前域名，使用傳入的結果
                            if root_domain == current_root and current_tw_results:
                                tw_results_to_check = current_tw_results
                            else:
                                # 否則從 store 獲取
                                probe_result = store.get(root_domain)
                                if probe_result:
                                    tw_results_to_check = probe_result.get("tw")
                            
                            # 檢查台灣 DNS 結果
                            if tw_results_to_check:
                                for tw_result in tw_results_to_check:
                                    category = tw_result.get("category", "")
                                    if category in ("解析失敗", "逾時"):
                                        has_tw_resolve_failure = True
                                        break
                            
                            if has_tw_resolve_failure:
                                # 台灣 DNS 解析失敗，不是空解析
                                chain.append({"url": url, "status": "解析失敗"})
                                error_msg = "解析失敗"
                                trace_status = "追蹤失敗"
                                final_url = url
                                break
                            elif not target_info.get("polluted", True):
                                # 未污染且台灣 DNS 正常，視為空解析
                                is_empty_resolution = True
                                chain.append({"url": url, "status": "空解析"})
                                success = True
                                trace_status = "追蹤成功"
                                final_url = url
                                break
                    
                    chain.append({"url": url, "status": 0})
                    error_msg = "連線失敗"
                    trace_status = "追蹤失敗"
                    break
                except httpx.TimeoutException:
                    chain.append({"url": url, "status": 0})
                    error_msg = "逾時"
                    trace_status = "追蹤失敗"
                    break
                    
    except Exception as e:
        error_msg = str(e) if str(e) else "請求失敗"
        trace_status = "追蹤失敗"
    
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
        "final_status_code": final_status_code,
        "chain": chain,
        "success": success,
        "trace_status": trace_status,
        "error": error_msg if not is_empty_resolution else None,
        "is_empty_resolution": is_empty_resolution
    }

