"""秘書の統合Webアプリ(チャット/資料/タスク/予定)。

FastAPIのルーターとして server.py に組み込む。
認証は Authorization: Bearer か ?key= のどちらでも通す
(ブラウザのfetchはヘッダを付けられるが、初回のリンク共有ではクエリが便利なため)。
"""
import os

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from typing import List, Optional

router = APIRouter()
API_KEY = os.getenv("API_KEY", "change-me")


def _auth(authorization: Optional[str] = Header(None), key: str = ""):
    token = (authorization or "").removeprefix("Bearer ").strip() or key
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")
    return True


# ---------- API ----------

@router.post("/api/ingest_url")
def api_ingest_url(
    url: str = Form(...), authorization: Optional[str] = Header(None), key: str = ""
):
    _auth(authorization, key)
    import ingest_lib
    return {"message": ingest_lib.ingest_url(url)}


@router.post("/api/upload")
async def api_upload(
    files: List[UploadFile] = File(...),
    authorization: Optional[str] = Header(None),
    key: str = "",
):
    _auth(authorization, key)
    import ingest_lib

    lines = []
    for uf in files:
        try:
            data = await uf.read()
            if not data:
                lines.append(f"{uf.filename}: 空のファイルです")
                continue
            path = ingest_lib.save_upload(uf.filename, data)
            lines.append(ingest_lib.ingest_file(path))
        except Exception as e:
            lines.append(f"{uf.filename}: 失敗({e})")
    return {"message": "\n".join(lines)}


@router.get("/api/todo")
def api_todo_list(authorization: Optional[str] = Header(None), key: str = ""):
    _auth(authorization, key)
    import todo_tool
    return {"message": todo_tool.todo("list")}


@router.post("/api/todo")
def api_todo_action(
    action: str = Form(...), title: str = Form(""), task_id: int = Form(0),
    due: str = Form(""), authorization: Optional[str] = Header(None), key: str = "",
):
    _auth(authorization, key)
    import todo_tool
    return {"message": todo_tool.todo(action, title=title, task_id=task_id, due=due)}


@router.get("/api/calendar")
def api_calendar(days: int = 7, authorization: Optional[str] = Header(None), key: str = ""):
    _auth(authorization, key)
    try:
        import calendar_tool
        return {"message": calendar_tool.calendar_list(days=days)}
    except Exception as e:
        return {"message": f"カレンダーを取得できません: {e}"}


@router.get("/api/convs")
def api_convs(authorization: Optional[str] = Header(None), key: str = ""):
    _auth(authorization, key)
    import chat_store
    return chat_store.list_convs()


@router.put("/api/convs/{conv_id}")
async def api_conv_put(
    conv_id: str, req: Request,
    authorization: Optional[str] = Header(None), key: str = "",
):
    _auth(authorization, key)
    import chat_store
    body = await req.json()
    chat_store.put(conv_id, body.get("title", "会話"), body.get("msgs", []))
    return {"ok": True}


@router.delete("/api/convs/{conv_id}")
def api_conv_del(
    conv_id: str, authorization: Optional[str] = Header(None), key: str = ""
):
    _auth(authorization, key)
    import chat_store
    chat_store.delete(conv_id)
    return {"ok": True}


@router.get("/apk")
def apk(authorization: Optional[str] = Header(None), key: str = ""):
    """ビルド済みAPKを配信する(スマホのブラウザから直接インストールするため)。"""
    _auth(authorization, key)
    from fastapi.responses import FileResponse
    path = os.path.expanduser(
        "~/secretary-app/app/build/outputs/apk/debug/app-debug.apk"
    )
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="APKが見つかりません")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename="secretary.apk",
    )


@router.get("/api/todo.json")
def api_todo_json(authorization: Optional[str] = Header(None), key: str = ""):
    """Glance等のダッシュボードから使う構造化データ。"""
    _auth(authorization, key)
    import todo_tool
    return todo_tool.list_open()


@router.get("/api/calendar.json")
def api_calendar_json(
    days: int = 7, authorization: Optional[str] = Header(None), key: str = ""
):
    _auth(authorization, key)
    try:
        import calendar_tool
        return calendar_tool.list_events(days=days)
    except Exception:
        return []


@router.get("/api/health.json")
def api_health_json(authorization: Optional[str] = Header(None), key: str = ""):
    """依存サービスの稼働状況(ダッシュボード表示用)。"""
    _auth(authorization, key)
    import health_check
    return health_check.status()


@router.post("/api/stt")
async def api_stt(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None), key: str = "",
):
    """音声を文字起こしして返す。"""
    _auth(authorization, key)
    import stt
    data = await file.read()
    if not data:
        return {"text": "", "error": "音声が空です"}
    try:
        return {"text": stt.transcribe(data, file.filename or "audio.webm")}
    except Exception as e:
        return {"text": "", "error": f"認識に失敗しました: {e}"}


@router.post("/api/tts")
def api_tts(
    text: str = Form(...), speaker: int = Form(0),
    authorization: Optional[str] = Header(None), key: str = "",
):
    """テキストを読み上げ音声(wav)にして返す。"""
    _auth(authorization, key)
    import tts
    try:
        return Response(tts.synth(text, speaker), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"読み上げに失敗しました: {e}")


@router.get("/api/speakers")
def api_speakers(authorization: Optional[str] = Header(None), key: str = ""):
    _auth(authorization, key)
    import tts
    try:
        return tts.speakers()
    except Exception:
        return []


@router.get("/api/me")
def api_me(
    authorization: Optional[str] = Header(None), key: str = "",
    x_authentik_username: Optional[str] = Header(None),
):
    """認証済みかを返す。プロキシ経由なら利用者名も返す。"""
    _auth(authorization, key)
    return {"authenticated": True, "user": x_authentik_username or "local"}


# ---------- PWA ----------

@router.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "秘書", "short_name": "秘書", "start_url": "/app",
        "display": "standalone", "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml",
                   "purpose": "any maskable"}],
    })


@router.get("/icon.svg")
def icon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<rect width="512" height="512" rx="96" fill="#2563eb"/>'
        '<circle cx="256" cy="196" r="72" fill="#fff"/>'
        '<path d="M112 424c0-79 64-143 144-143s144 64 144 143z" fill="#fff"/></svg>'
    )
    return Response(svg, media_type="image/svg+xml")


@router.get("/sw.js")
def service_worker():
    js = "self.addEventListener('fetch', function(e) {});"
    return Response(js, media_type="application/javascript")


# /app は React ビルド成果物(webui_dist)を server.py から配信する
