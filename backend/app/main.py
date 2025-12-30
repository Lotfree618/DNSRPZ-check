from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import idna

from app.schemas import ResolveResponse
from app.dns_probe import probe_domain
from app.verdict import analyze_results

app = FastAPI(title="DNSRPZ Check API")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    
    # Remove protocol prefixes
    if domain.startswith("http://"):
        domain = domain[7:]
    elif domain.startswith("https://"):
        domain = domain[8:]
        
    # Remove path/query if present (simplistic approach, taking everything before first /)
    if "/" in domain:
        domain = domain.split("/")[0]

    if not domain:
        raise ValueError("域名不能为空")
    
    # Remove trailing dot
    if domain.endswith("."):
        domain = domain[:-1]
    
    # Validation after cleanup
    if " " in domain or ":" in domain: # ':' usually implies port
         # Check if it has port and strip it
        if ":" in domain:
             domain = domain.split(":")[0]
    
    # Final check for invalid chars
    if any(c in domain for c in " /:"):
        raise ValueError("域名包含无效字符")
    
    # Punycode conversion
    try:
        domain = idna.encode(domain).decode("ascii")
    except idna.IDNAError:
        raise ValueError("域名格式无效")
        
    return domain

@app.get("/api/resolve", response_model=ResolveResponse)
async def resolve(domain: str = Query(..., min_length=1, max_length=253)):
    try:
        safe_domain = normalize_domain(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Probe
    results = await probe_domain(safe_domain)
    
    # Verdict
    baseline, comparison, conclusion = analyze_results(results)
    
    return ResolveResponse(
        domain=safe_domain,
        timestamp=datetime.utcnow(),
        baseline=baseline,
        resolvers=results,
        comparison=comparison,
        conclusion=conclusion
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
