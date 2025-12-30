export async function onRequest(context) {
    // 修改为你的后端 VPS IP 地址 (必须是 HTTP)
    const BACKEND_URL = "http://35.206.230.61:8000";

    const url = new URL(context.request.url);
    const targetUrl = `${BACKEND_URL}/api/resolve${url.search}`;

    try {
        const response = await fetch(targetUrl, {
            method: context.request.method,
            headers: {
                'Content-Type': context.request.headers.get('Content-Type') || 'application/json',
                // 伪装成普通浏览器，防止部分防火墙/后端拦截空 UA
                'User-Agent': "Mozilla/5.0 (Cloudflare Pages Proxy)",
            }
        });

        // 重新构建响应
        const newHeaders = new Headers(response.headers);
        newHeaders.set("X-Debug-Proxy", "True"); // 标记这是经过 Proxy 的
        newHeaders.set("X-Upstream-Status", response.status); // 记录上游返回的状态码

        return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: newHeaders
        });
    } catch (err) {
        return new Response(JSON.stringify({ error: "Backend Proxy Failed", details: err.message }), {
            status: 502,
            headers: { "Content-Type": "application/json" }
        });
    }
}
