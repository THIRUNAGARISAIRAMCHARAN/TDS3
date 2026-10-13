import hashlib
import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

EMAIL = "24f2001614@ds.study.iitm.ac.in".strip().lower()
DEFAULT_PROTOCOL = "2025-03-26"
SUPPORTED = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam response for the challenge sent in the X-Exam-Challenge HTTP header.",
    "inputSchema": {"type": "object", "properties": {}},
}


def answer_for(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]


def ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def err(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(msg: dict, headers):
    method = msg.get("method")
    id_ = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        version = requested if requested in SUPPORTED else DEFAULT_PROTOCOL
        return ok(id_, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "exam-challenge-server", "version": "1.0.0"},
        })
    if method == "ping":
        return ok(id_, {})
    if method == "tools/list":
        return ok(id_, {"tools": [TOOL]})
    if method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name != "solve_challenge":
            return err(id_, -32602, f"Unknown tool: {name}")
        challenge = (headers.get("x-exam-challenge") or "").strip()
        if not challenge:
            return ok(id_, {
                "content": [{"type": "text", "text": "Missing X-Exam-Challenge header"}],
                "isError": True,
            })
        return ok(id_, {"content": [{"type": "text", "text": answer_for(challenge)}]})
    if is_notification:
        return None
    return err(id_, -32601, f"Method not found: {method}")


async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(err(None, -32700, "Parse error"), status_code=400)

    if isinstance(body, list):
        results = [r for r in (handle(m, request.headers) for m in body if isinstance(m, dict)) if r is not None]
        if not results:
            return Response(status_code=202)
        return JSONResponse(results)

    if not isinstance(body, dict):
        return JSONResponse(err(None, -32600, "Invalid Request"), status_code=400)

    result = handle(body, request.headers)
    if result is None:
        return Response(status_code=202)
    return JSONResponse(result)


app.add_api_route("/", mcp_endpoint, methods=["POST"])
app.add_api_route("/mcp", mcp_endpoint, methods=["POST"])


@app.get("/")
@app.get("/mcp")
def health():
    return {"status": "ok", "tool": "solve_challenge"}


@app.delete("/mcp")
def end_session():
    return Response(status_code=200)
