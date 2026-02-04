# MCP HTTP Transport: A Clear Explanation

## The Basic Problem

MCP (Model Context Protocol) needs a way for clients and servers to talk over the network. HTTP is the obvious choice, but vanilla HTTP has a limitation: it's request-response only. The client asks, the server answers, done.

But sometimes the server wants to:
- Send progress updates during a long-running tool call
- Notify the client that available tools changed
- Push log messages

This requires the server to *initiate* communication, which vanilla HTTP doesn't support.

---

## SSE (Server-Sent Events)

SSE is a standard web technology that solves this. It works like this:

1. Client opens an HTTP connection
2. Server keeps the connection open
3. Server sends text messages whenever it wants
4. Connection stays open until someone closes it

```
Client                          Server
   |                               |
   |-------- GET /stream --------->|
   |                               |
   |<------ data: hello -----------|
   |                               |
   |        (time passes)          |
   |                               |
   |<------ data: update 1 --------|
   |                               |
   |        (time passes)          |
   |                               |
   |<------ data: update 2 --------|
   |                               |
   ...
```

The response never "finishes" — it's a continuous stream of `data:` lines.

**Key point:** SSE is one-directional. Server → Client only. The client can't send messages back on the same connection.

---

## Streamable HTTP Transport

This is MCP's HTTP-based transport. It uses a single endpoint (`/mcp`) and supports two HTTP methods:

### POST /mcp — Client sends requests

The client sends JSON-RPC requests (like "call this tool" or "list available tools").

The server can respond in two ways:
- **JSON response:** Single JSON object, connection closes immediately
- **SSE response:** Stream of messages (progress updates, then final result)

### GET /mcp — Server-initiated notifications

The client opens this connection and keeps it open. The server uses it to push notifications whenever it wants — tool list changes, log messages, etc.

This connection stays open indefinitely (or until the client disconnects). 

https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#listening-for-messages-from-the-server

---

## The Two Parameters

### `stateless_http`

Controls whether the server maintains sessions between requests.

**`stateless_http=False` (default):**
- Server tracks sessions with a session ID
- State persists across requests
- Useful for multi-step interactions where the server needs memory

**`stateless_http=True`:**
- Each request is independent
- No session tracking, no memory between requests
- Better for horizontal scaling (any server instance can handle any request)
- Required for serverless (Lambda) where instances are ephemeral

### `json_response`

Controls how the server responds to POST requests.

**`json_response=False` (default):**
- Server can respond with SSE streams
- Enables progress updates during tool execution
- GET /mcp opens a persistent SSE connection for server notifications

**`json_response=True`:**
- All responses are plain JSON
- No streaming, no progress updates
- GET /mcp returns immediately (no persistent connection)
- Required for environments that don't support long-lived connections

---

## The Four Combinations

| stateless_http | json_response | Use Case |
|----------------|---------------|----------|
| `False` | `False` | Full-featured MCP server with sessions and streaming. Traditional server deployment. |
| `False` | `True` | Sessions without streaming. Unusual combination. |
| `True` | `False` | Stateless but with streaming. Works if your infra supports long connections. |
| `True` | `True` | Fully stateless, no streaming. **Best for serverless (Lambda).** |

https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/servers/streamable_config.py

---

## Why Lambda Requires `json_response=True`

With `json_response=False`, a GET request to `/mcp` opens an SSE connection that stays open forever, waiting for server-initiated notifications.

Lambda charges by the millisecond. A connection sitting idle for 15 minutes (Lambda's max timeout) costs money and does nothing. Eventually Lambda kills it, the client gets an error, and you've wasted resources.

With `json_response=True`, GET /mcp returns immediately with nothing (or an error), and POST /mcp returns a single JSON response and closes. Lambda handles the request and terminates. Clean.

---

## What You Lose with `json_response=True`

1. **Progress updates during tool calls** — The server can't send "10% done... 50% done..." updates. The client waits in silence until the final result.

2. **Server-initiated notifications** — The server can't proactively tell the client "hey, my tools changed." The client must poll if it wants updates.

For Ankify, neither matters:
- Tool calls (TTS + deck creation) complete in reasonable time
- Tools don't change at runtime
- No need for server → client notifications

---

## Visual Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamable HTTP Transport                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POST /mcp (client → server requests)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  json_response=False     │  json_response=True          │    │
│  │  ─────────────────────   │  ────────────────────        │    │
│  │  Response can be SSE     │  Response is always JSON     │    │
│  │  (stream of messages)    │  (single response, closes)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  GET /mcp (server → client notifications)                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  json_response=False     │  json_response=True          │    │
│  │  ─────────────────────   │  ────────────────────        │    │
│  │  Opens persistent SSE    │  Returns immediately         │    │
│  │  connection (forever)    │  (no streaming)              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  stateless_http controls session tracking (orthogonal to above) │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Recommendation for Serverless Deployment

```python
app = mcp.http_app(
    stateless_http=True,   # No sessions (Lambda instances are ephemeral)
    json_response=True,    # No SSE (Lambda can't hold connections open)
)
```

This gives you a clean request-response model that works with Lambda, API Gateway, and Function URLs.
