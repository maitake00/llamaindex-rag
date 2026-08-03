"""RAGを OpenAI互換API として公開するFastAPIサーバ。

これを起動すると、LobeChat / Open WebUI などのチャットUIから「1つのモデル」として繋げる。

公開モデル(UIのモデル選択で切り替え):
  - secretary        … 通常(高速・思考オフ)
  - secretary-think  … 熟考モード(思考オン・遅いが深い)

エンドポイント(OpenAI互換):
  GET  /v1/models
  POST /v1/chat/completions   (stream対応)

認証: Authorization: Bearer <APIキー>  (.env の API_KEY と一致が必要)

起動:
  uvicorn server:app --host 0.0.0.0 --port 8000
"""
import json
import os
import time
import uuid
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()  # .env を読み込む(API_KEY など)

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import chromadb
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

import agent
import config
from xinference_rerank import XinferenceRerank

# --- 認証キー(.env の API_KEY) ---
API_KEY = os.getenv("API_KEY", "change-me")

MODEL_NORMAL = "secretary"
MODEL_THINK = "secretary-think"

app = FastAPI(title="RAG OpenAI-compatible API")

# 起動時に一度だけ準備する重い部品
_index = None
_reranker = None
_tools = None


def _get_tools():
    """文書検索ツール(+Web検索ツール)を用意する。初回だけ重い準備を行う。"""
    global _index, _reranker, _tools
    if _tools is None:
        Settings.embed_model = OllamaEmbedding(
            model_name=config.EMBED_MODEL, base_url=config.OLLAMA_BASE_URL,
        )
        client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        collection = client.get_or_create_collection(config.COLLECTION)
        vs = ChromaVectorStore(chroma_collection=collection)
        _index = VectorStoreIndex.from_vector_store(vs)
        _reranker = XinferenceRerank(
            base_url=config.XINFERENCE_BASE_URL, model=config.RERANK_MODEL,
            top_n=config.RERANK_TOP_N,
        )
        _tools = agent.build_tools(_index, _reranker)
        names = [t.metadata.name for t in _tools]
        print(f"[server] 利用可能なツール: {names}")
    return _tools


def _make_llm(think: bool) -> Ollama:
    return Ollama(
        model=config.LLM_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        request_timeout=600.0,
        # ツールの結果(文書チャンク+Web本文)を載せるため、従来より広く取る
        context_window=config.AGENT_NUM_CTX,
        thinking=think,
        temperature=0.0,
        is_function_calling_model=True,
        additional_kwargs={"num_predict": 3000 if think else 800, "presence_penalty": 0.0},
    )


# ---------- OpenAI互換 スキーマ ----------
class Msg(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    model: str = MODEL_NORMAL
    messages: List[Msg]
    stream: bool = False


def _check_auth(authorization: Optional[str]):
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/v1/models")
def list_models(authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": MODEL_NORMAL, "object": "model", "created": now, "owned_by": "local"},
            {"id": MODEL_THINK, "object": "model", "created": now, "owned_by": "local"},
        ],
    }


def _split(messages: List[Msg]):
    """最後のuserメッセージを質問に、それ以前を履歴にする。"""
    history: List[ChatMessage] = []
    question = ""
    for m in messages:
        if m.role == "system":
            continue
        if m.role == "user":
            question = m.content
            history.append(ChatMessage(role=MessageRole.USER, content=m.content))
        elif m.role == "assistant":
            history.append(ChatMessage(role=MessageRole.ASSISTANT, content=m.content))
    # 最後のuser発話は「今の質問」なので履歴から除く
    if history and history[-1].role == MessageRole.USER:
        history = history[:-1]
    return question, history


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatReq, authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    think = req.model == MODEL_THINK
    question, history = _split(req.messages)
    if not question:
        raise HTTPException(status_code=400, detail="No user message")

    tools = _get_tools()
    llm = _make_llm(think)
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if req.stream:
        def gen():
            for token in agent.stream_chat(llm, tools, question, history, think):
                chunk = {
                    "id": cid, "object": "chat.completion.chunk", "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            done = {
                "id": cid, "object": "chat.completion.chunk", "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    answer = agent.chat(llm, tools, question, history, think)
    return {
        "id": cid, "object": "chat.completion", "created": created, "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- 資料アップロード画面 ----------
# スマホ/PCのブラウザから写真・PDF・テキストを投げ込むと、そのままRAGに登録される。
# 認証は URL の ?key=<APIキー>(ブラウザからはBearerヘッダを付けられないため)。

UPLOAD_HTML = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>資料の追加</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#f6f7f9;color:#111}
 .card{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;
       box-shadow:0 1px 4px rgba(0,0,0,.08)}
 h1{font-size:20px;margin:0 0 4px} p.sub{color:#666;font-size:13px;margin:0 0 20px}
 input[type=file]{width:100%;padding:14px;border:2px dashed #cbd5e1;border-radius:8px;
                  background:#fafbfc;margin-bottom:16px}
 button{width:100%;padding:14px;font-size:16px;border:0;border-radius:8px;
        background:#2563eb;color:#fff;font-weight:600}
 button:disabled{background:#94a3b8}
 .result{margin-top:20px;padding:14px;border-radius:8px;background:#f1f5f9;
         font-size:14px;white-space:pre-wrap;line-height:1.6}
</style></head><body>
<div class="card">
  <h1>資料の追加</h1>
  <p class="sub">画像・PDF・テキストを選ぶと、秘書の資料として登録されます。</p>
  <form id="f" method="post" enctype="multipart/form-data">
    <input type="file" name="files" multiple required>
    <button type="submit" id="b">登録する</button>
  </form>
  <div class="result" id="r" style="display:none"></div>
</div>
<script>
const f=document.getElementById('f'),b=document.getElementById('b'),r=document.getElementById('r');
f.onsubmit=async e=>{
  e.preventDefault();
  b.disabled=true; b.textContent='処理中...(画像は1分ほどかかります)';
  r.style.display='block'; r.textContent='アップロード中...';
  try{
    const res=await fetch(location.href,{method:'POST',body:new FormData(f)});
    r.textContent=await res.text();
  }catch(err){ r.textContent='エラー: '+err; }
  b.disabled=false; b.textContent='登録する';
};
</script></body></html>"""


def _check_key(key: str):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")


@app.get("/upload", response_class=HTMLResponse)
def upload_form(key: str = ""):
    _check_key(key)
    return UPLOAD_HTML


@app.post("/upload")
async def upload_files(key: str = "", files: List[UploadFile] = File(...)):
    _check_key(key)
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
    return "\n".join(lines)
