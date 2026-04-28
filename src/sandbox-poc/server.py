"""샌드박스 코드 실행 POC — Docker 기반"""
from __future__ import annotations

import os
import uuid
import docker
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Sandbox POC")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = docker.from_env()
SESSIONS: dict[str, docker.models.containers.Container] = {}
WORKSPACE_ROOT = os.path.abspath("./workspaces")
os.makedirs(WORKSPACE_ROOT, exist_ok=True)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


class RunCodeRequest(BaseModel):
    code: str
    filename: str = "script.ts"


class RunCodeResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


class WriteFileRequest(BaseModel):
    path: str
    content: str


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session():
    """세션별 독립 컨테이너 생성"""
    sid = str(uuid.uuid4())[:8]
    workspace = os.path.join(WORKSPACE_ROOT, sid)
    os.makedirs(workspace, exist_ok=True)

    container = client.containers.run(
        "denoland/deno:latest",
        command="sleep infinity",
        detach=True,
        name=f"sandbox-{sid}",
        mem_limit="256m",
        cpu_period=100000,
        cpu_quota=50000,
        volumes={workspace: {"bind": "/workspace", "mode": "rw"}},
        working_dir="/workspace",
        labels={"sandbox": "true", "session": sid},
    )
    SESSIONS[sid] = container
    return CreateSessionResponse(session_id=sid, status="running")


@app.post("/sessions/{sid}/run", response_model=RunCodeResponse)
def run_code(sid: str, body: RunCodeRequest):
    """컨테이너 안에서 코드 실행"""
    container = SESSIONS.get(sid)
    if not container:
        raise HTTPException(404, "Session not found")

    # 파일 쓰기
    workspace = os.path.join(WORKSPACE_ROOT, sid)
    filepath = os.path.join(workspace, body.filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body.code)

    # 실행
    if body.filename.endswith(".ts") or body.filename.endswith(".js"):
        cmd = ["deno", "run", "--allow-all", f"/workspace/{body.filename}"]
    elif body.filename.endswith(".py"):
        cmd = ["python3", f"/workspace/{body.filename}"]
    else:
        cmd = ["cat", f"/workspace/{body.filename}"]

    result = container.exec_run(cmd, workdir="/workspace")
    output = result.output.decode("utf-8", errors="replace")

    return RunCodeResponse(
        stdout=output if result.exit_code == 0 else "",
        stderr=output if result.exit_code != 0 else "",
        exit_code=result.exit_code,
    )


@app.post("/sessions/{sid}/files")
def write_file(sid: str, body: WriteFileRequest):
    """워크스페이스에 파일 쓰기"""
    workspace = os.path.join(WORKSPACE_ROOT, sid)
    filepath = os.path.join(workspace, body.path.lstrip("/"))
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body.content)
    return {"status": "ok", "path": body.path}


@app.get("/sessions/{sid}/files")
def list_files(sid: str):
    """워크스페이스 파일 목록"""
    workspace = os.path.join(WORKSPACE_ROOT, sid)
    if not os.path.exists(workspace):
        return {"files": []}
    files = []
    for root, dirs, fnames in os.walk(workspace):
        for fn in fnames:
            rel = os.path.relpath(os.path.join(root, fn), workspace)
            files.append(rel.replace("\\", "/"))
    return {"files": files}


@app.post("/sessions/{sid}/serve")
def start_web_server(sid: str):
    """컨테이너 안에서 웹서버 시작 (프리뷰용)"""
    container = SESSIONS.get(sid)
    if not container:
        raise HTTPException(404, "Session not found")

    # Deno로 간단한 파일 서버 시작 (백그라운드)
    container.exec_run(
        ["sh", "-c", "deno run --allow-all --allow-net https://deno.land/std/http/file_server.ts /workspace --port 3000 &"],
        detach=True,
    )

    # 컨테이너 IP 가져오기
    container.reload()
    ip = container.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]
    return {"preview_url": f"http://{ip}:3000", "message": "웹서버 시작됨. 컨테이너 내부 IP로 접근 가능"}


@app.delete("/sessions/{sid}")
def delete_session(sid: str):
    """세션 정리"""
    container = SESSIONS.pop(sid, None)
    if container:
        container.stop(timeout=3)
        container.remove()
    # 워크스페이스 파일도 정리
    workspace = os.path.join(WORKSPACE_ROOT, sid)
    if os.path.exists(workspace):
        import shutil
        shutil.rmtree(workspace)
    return {"status": "deleted"}


@app.get("/sessions")
def list_sessions():
    """활성 세션 목록"""
    result = []
    for sid, container in SESSIONS.items():
        container.reload()
        result.append({
            "session_id": sid,
            "status": container.status,
            "name": container.name,
        })
    return {"sessions": result}


@app.on_event("shutdown")
def cleanup():
    """서버 종료 시 모든 컨테이너 정리"""
    for sid, container in SESSIONS.items():
        try:
            container.stop(timeout=3)
            container.remove()
        except Exception:
            pass


# 간단한 테스트 UI
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html><head><title>Sandbox POC</title>
<style>
  body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; padding: 2rem; max-width: 800px; margin: 0 auto; }
  h1 { color: #e94560; }
  button { background: #e94560; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin: 0.25rem; }
  textarea { width: 100%; height: 200px; background: #0f3460; color: #e0e0e0; border: 1px solid #333; padding: 0.5rem; font-family: monospace; }
  pre { background: #0a0a1a; padding: 1rem; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
  #output { min-height: 100px; }
  .session-id { color: #50c878; font-size: 1.2rem; }
</style></head><body>
<h1>🏗️ Sandbox POC</h1>
<p>Docker 컨테이너 기반 코드 실행 샌드박스</p>

<button onclick="createSession()">1. 세션 생성</button>
<span class="session-id" id="sid"></span>

<h3>2. 코드 작성 (TypeScript)</h3>
<textarea id="code">// Deno TypeScript 코드
const data = { message: "Hello from sandbox!", time: new Date().toISOString() };
console.log(JSON.stringify(data, null, 2));

// 파일 쓰기 테스트
await Deno.writeTextFile("/workspace/output.json", JSON.stringify(data, null, 2));
console.log("파일 저장 완료: /workspace/output.json");
</textarea>
<br>
<button onclick="runCode()">3. 실행</button>
<button onclick="listFiles()">4. 파일 목록</button>
<button onclick="deleteSession()">5. 세션 삭제</button>

<h3>결과</h3>
<pre id="output">여기에 결과가 표시됩니다...</pre>

<script>
let sessionId = null;
const out = document.getElementById('output');

async function createSession() {
  const res = await fetch('/sessions', { method: 'POST' });
  const data = await res.json();
  sessionId = data.session_id;
  document.getElementById('sid').textContent = `세션: ${sessionId}`;
  out.textContent = JSON.stringify(data, null, 2);
}

async function runCode() {
  if (!sessionId) { out.textContent = '먼저 세션을 생성하세요'; return; }
  const code = document.getElementById('code').value;
  const res = await fetch(`/sessions/${sessionId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, filename: 'script.ts' }),
  });
  const data = await res.json();
  out.textContent = `Exit: ${data.exit_code}\\n\\n--- stdout ---\\n${data.stdout}\\n--- stderr ---\\n${data.stderr}`;
}

async function listFiles() {
  if (!sessionId) { out.textContent = '먼저 세션을 생성하세요'; return; }
  const res = await fetch(`/sessions/${sessionId}/files`);
  const data = await res.json();
  out.textContent = '파일 목록:\\n' + data.files.join('\\n');
}

async function deleteSession() {
  if (!sessionId) return;
  await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  out.textContent = '세션 삭제됨';
  sessionId = null;
  document.getElementById('sid').textContent = '';
}
</script>
</body></html>
"""
