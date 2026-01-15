"""結果判定與聚合"""
from typing import Dict, List, Set
from . import config


def classify_tw_result(
    result: Dict,
    baseline_ips: Set[str]
) -> str:
    """對台灣解析器結果進行分類"""
    status = result.get("status")
    ips = set(result.get("ips", []))
    
    # 解析失敗情況
    if status == "timeout":
        return "逾時"
    if status == "error":
        # SERVFAIL 等錯誤視為解析失敗
        return "解析失敗"
    if status == "nxdomain":
        # NXDOMAIN 視為正常（域名不存在）
        return "正常"
    
    # status == "ok"
    if not ips:
        # 無 IP 返回，視為正常（未被污染）
        return "正常"
    
    # 檢查是否命中黑名單
    if ips & config.BLOCK_PAGE_IPS:
        return "已封鎖"
    
    # 檢查是否為基準子集（正常）
    if baseline_ips and ips.issubset(baseline_ips):
        return "正常"
    
    # 有解析差異但未命中黑名單
    if baseline_ips and not ips.issubset(baseline_ips):
        return "解析差異"
    
    # 無基準時有 IP 視為正常
    return "正常"


def aggregate_verdict(probe_result: Dict) -> Dict:
    """聚合域名級判定結果"""
    domain = probe_result["domain"]
    baseline_results = probe_result["baseline"]
    tw_results = probe_result["tw"]
    redirect_trace = probe_result.get("redirect_trace")
    
    # 優先使用預計算的 baseline_ips，避免重複計算
    if "baseline_ips" in probe_result:
        baseline_ips = set(probe_result["baseline_ips"])
    else:
        # 兼容舊格式：從 baseline_results 構建
        baseline_ips = set()
        for r in baseline_results:
            if r.get("status") == "ok":
                baseline_ips.update(r.get("ips", []))
    
    # 分類台灣解析器結果
    tw_classified = []
    reasons = []
    has_resolve_failure = False
    has_pollution = False
    
    for r in tw_results:
        category = classify_tw_result(r, baseline_ips)
        tw_classified.append({
            **r,
            "category": category
        })
        
        # 收集原因
        if category == "已封鎖":
            reasons.append("污染：已封鎖")
            has_pollution = True
        elif category == "解析差異":
            reasons.append("污染：解析差異")
            has_pollution = True
        elif category == "逾時":
            reasons.append("解析失敗：逾時")
            has_resolve_failure = True
        elif category == "解析失敗":
            reasons.append("解析失敗")
            has_resolve_failure = True
    
    # 去重
    reasons = list(dict.fromkeys(reasons))
    
    # 域名級狀態判定：已污染 / 未污染 / 解析失敗
    if has_pollution:
        status = "已污染"
    elif has_resolve_failure and not any(c["category"] == "正常" for c in tw_classified):
        # 全部解析器都失敗才算解析失敗
        status = "解析失敗"
    else:
        status = "未污染"
    
    # 確定 trace_status：追蹤成功 / 追蹤失敗
    # 若無基準 IP（空解析），追蹤視為成功（無需追蹤）
    trace_status = None
    if not baseline_ips:
        # 空解析，無需追蹤
        trace_status = "追蹤成功"
    elif redirect_trace:
        if redirect_trace.get("success"):
            trace_status = "追蹤成功"
        else:
            trace_status = "追蹤失敗"
    
    return {
        "domain": domain,
        "status": status,
        "reasons": reasons,
        "baseline": {
            "ips": sorted(baseline_ips),
            "detail": baseline_results
        },
        "tw": tw_classified,
        "redirect_trace": redirect_trace,
        "trace_status": trace_status
    }

