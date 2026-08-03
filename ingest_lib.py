"""資料の取り込み(共通処理)。URL取り込みとアップロードの両方から使う。

画像は ingest_images.py の「説明+OCR」経路を通す(精度重視の方針を維持)。
"""
import os
from datetime import datetime

import chromadb
import requests
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import config

DOCS_DIR = config.DOCS_DIR
IMAGES_DIR = os.getenv("IMAGES_DIR", "images")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
TAVILY_EXTRACT = "https://api.tavily.com/extract"


def _storage():
    Settings.embed_model = OllamaEmbedding(
        model_name=config.EMBED_MODEL, base_url=config.OLLAMA_BASE_URL,
    )
    Settings.node_parser = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
    )
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = client.get_or_create_collection(config.COLLECTION)
    return StorageContext.from_defaults(
        vector_store=ChromaVectorStore(chroma_collection=collection)
    )


def add_documents(documents) -> int:
    """Documentのリストを埋め込んでChromaに追加する。"""
    if not documents:
        return 0
    VectorStoreIndex.from_documents(documents, storage_context=_storage())
    return len(documents)


def _extract_url(url: str) -> str:
    """Tavilyの本文抽出を使う(広告やナビを除いた本文が得られる)。"""
    if not config.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY が未設定です")
    r = requests.post(
        TAVILY_EXTRACT,
        headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
        json={"api_key": config.TAVILY_API_KEY, "urls": [url]},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        failed = data.get("failed_results") or []
        raise RuntimeError(f"本文を取得できませんでした: {failed}")
    return (results[0].get("raw_content") or "").strip()


def ingest_url(url: str, title: str = "") -> str:
    """WebページをRAGの資料として保存する。以後 search_documents で検索できる。"""
    if not url.startswith(("http://", "https://")):
        return "URLは http:// または https:// で始まる必要があります。"
    try:
        body = _extract_url(url)
    except Exception as e:
        return f"ページの取得に失敗しました: {e}"

    if len(body) < 50:
        return "本文がほとんど取得できませんでした(JavaScript主体のページの可能性があります)。"

    name = title or url
    now = datetime.now().strftime("%Y-%m-%d")
    text = f"Webページ「{name}」({url}) の内容 [取込日: {now}]\n\n{body}"
    doc = Document(
        text=text,
        metadata={"file_name": name, "source_url": url, "type": "web", "ingested": now},
    )
    try:
        add_documents([doc])
    except Exception as e:
        return f"保存に失敗しました: {e}"
    return f"資料に追加しました: {name}\n({len(body)}文字 / 出典 {url})"


def ingest_file(path: str) -> str:
    """保存済みファイル1件を取り込む。画像は説明+OCR、それ以外は本文をそのまま。"""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if ext in IMAGE_EXTS:
        import ingest_images
        try:
            desc = ingest_images.describe_image(path)
        except Exception as e:
            desc = ""
            print(f"[ingest] 画像説明に失敗: {e}")
        try:
            ocr = ingest_images.ocr_text(path)
        except Exception as e:
            ocr = ""
            print(f"[ingest] OCRに失敗: {e}")
        if not desc and not ocr:
            return f"{name}: 説明もOCRも取得できず、登録しませんでした。"
        body = f"画像ファイル「{name}」の内容説明:\n"
        if desc:
            body += f"[説明] {desc}\n"
        if ocr:
            body += f"\n[画像内の文字(OCR抽出)]\n{ocr}\n"
        add_documents([Document(text=body, metadata={"file_name": name, "type": "image"})])
        return f"{name}: 画像として登録しました(説明{len(desc)}字 / OCR{len(ocr)}字)"

    from llama_index.core import SimpleDirectoryReader
    try:
        docs = SimpleDirectoryReader(input_files=[path]).load_data()
    except Exception as e:
        return f"{name}: 読み込みに失敗しました({e})"
    for d in docs:
        d.metadata["file_name"] = name
    n = add_documents(docs)
    return f"{name}: 文書として登録しました({n}件)"


def save_upload(filename: str, data: bytes) -> str:
    """アップロードされたファイルを保存し、保存先パスを返す。"""
    ext = os.path.splitext(filename)[1].lower()
    target_dir = IMAGES_DIR if ext in IMAGE_EXTS else DOCS_DIR
    os.makedirs(target_dir, exist_ok=True)

    base = os.path.basename(filename).replace("/", "_")
    path = os.path.join(target_dir, base)
    stem, ext2 = os.path.splitext(path)
    i = 1
    while os.path.exists(path):  # 同名があれば連番を付ける
        path = f"{stem}_{i}{ext2}"
        i += 1

    with open(path, "wb") as f:
        f.write(data)
    return path
