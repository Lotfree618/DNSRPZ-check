export async function onRequest(context) {
    // 修改为你的后端 VPS IP 地址 (必须是 HTTP)
    const BACKEND_URL = "http://35.206.230.61:8000";

    const url = new URL(context.request.url);
    const targetUrl = `${BACKEND_URL}/api/resolve${url.search}`;

    try {
        const response = await fetch(targetUrl, {
            method: context.request.method,
            headers: {
                // 传递必要的 headers，或者根据需要过滤
                'Content-Type': context.request.headers.get('Content-Type') || 'application/json',
            }
        });

        // 重新构建响应以解决 CORS 或其他问题（虽然同源代理通常不需要 CORS）
        return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers
        });
    } catch (err) {
        return new Response(JSON.stringify({ error: "Backend Proxy Failed", details: err.message }), {
            status: 502,
            headers: { "Content-Type": "application/json" }
        });
    }
}
