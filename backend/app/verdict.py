from .config import BLOCK_PAGE_IPS
from .schemas import TwClassification, ConclusionStatus


def classify_tw_result(tw_result: dict, baseline_ips: set) -> TwClassification:
    """
    对单个台湾DNS结果进行分类
    """
    status = tw_result["status"]
    ips = set(tw_result.get("ips", []))

    if status == "timeout":
        return TwClassification.TIMEOUT
    
    if status == "nxdomain":
        return TwClassification.NXDOMAIN
    
    if status == "error":
        return TwClassification.ERROR
    
    # status == "ok"
    # 检查黑名单
    if ips & BLOCK_PAGE_IPS:
        return TwClassification.BLOCKED
    
    # 检查是否为baseline子集
    if ips and ips.issubset(baseline_ips):
        return TwClassification.NORMAL
    
    # 有差异（可能CDN）
    return TwClassification.DIFF


def aggregate_conclusion(tw_classifications: list[TwClassification]) -> tuple[ConclusionStatus, list[str]]:
    """
    聚合最终结论
    返回: (status, reasons)
    """
    reasons = []
    
    has_blocked = False
    has_nxdomain = False
    has_timeout = False
    has_error = False
    has_diff = False
    has_normal = False

    for cls in tw_classifications:
        if cls == TwClassification.BLOCKED:
            has_blocked = True
        elif cls == TwClassification.NXDOMAIN:
            has_nxdomain = True
        elif cls == TwClassification.TIMEOUT:
            has_timeout = True
        elif cls == TwClassification.ERROR:
            has_error = True
        elif cls == TwClassification.DIFF:
            has_diff = True
        elif cls == TwClassification.NORMAL:
            has_normal = True

    # 判定逻辑
    if has_blocked or has_nxdomain:
        status = ConclusionStatus.ABNORMAL
        if has_blocked:
            reasons.append("检测到台湾DNS返回黑名单IP，域名可能已被封锁")
        if has_nxdomain:
            reasons.append("检测到台湾DNS返回NXDOMAIN，域名可能被阻断")
    elif has_timeout or has_error:
        status = ConclusionStatus.UNCERTAIN
        if has_timeout:
            reasons.append("部分台湾DNS查询超时，无法确认状态")
        if has_error:
            reasons.append("部分台湾DNS查询出错，请稍后重试")
    else:
        status = ConclusionStatus.OK
        if has_diff:
            reasons.append("台湾DNS返回IP与基准有差异，可能为CDN/地域差异，属正常现象")
        if has_normal:
            reasons.append("台湾DNS解析正常，未检测到RPZ封锁")
        if not reasons:
            reasons.append("解析结果正常")

    return status, reasons
