"""画像を「内容説明 + 正確な文字(OCR)」にして知識ベースに取り込む(精度重視版)。

仕組み:
  ① qwen3.5:9b(画像認識)が「これは何か+内容」を説明 … 意味検索に効く(地図/グラフ等を理解)
  ② PaddleOCR(日本語)が画像内の文字を正確に抽出 … キーワード検索に効く(店名・金額・固有名詞)
  ①②を1つのチャンクにまとめ、bge-m3で埋め込んで Chroma に登録する。
→ 「内容」でも「書かれている文字」でも、query.py で検索してヒットする。

使い方:
  1. images/ フォルダに画像を置く
  2. python ingest_images.py

初回はPaddleOCRのモデル(日本語)を自動ダウンロードするため少し時間がかかる。
必要な追加インストール:  pip install paddleocr paddlepaddle
"""
import base64
import os
import sys

import chromadb
import requests
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import config

IMAGES_DIR = os.getenv("IMAGES_DIR", "images")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# 「まず画像の種類を判定してから説明」させることで、地図/グラフ等を正しく捉える
DESCRIBE_PROMPT = (
    "次の手順で日本語で答えてください。\n"
    "1. この画像が何か(地図・グラフ・図表・書類・写真・スクリーンショット等)をまず判定する\n"
    "2. その種類を踏まえ、写っている内容(被写体・場所・状況・数値の意味など)を、"
    "後で検索で見つけやすいように具体的に説明する\n"
    "前置きや感想は不要。説明の本文だけを簡潔に。"
)

# --- OCRエンジン ---
# OCR_ENGINE:  auto(既定, PaddleOCR→ダメならTesseract) / paddle / tesseract
#   PaddleOCR(精度重視): pip install paddleocr paddlepaddle
#   Tesseract(確実・軽量): sudo apt install -y tesseract-ocr tesseract-ocr-jpn / pip install pytesseract pillow
OCR_ENGINE = os.getenv("OCR_ENGINE", "auto")
_paddle = None


def _paddle_ocr(path: str) -> str:
    global _paddle
    if _paddle is None:
        from paddleocr import PaddleOCR
        _paddle = PaddleOCR(lang="japan", use_textline_orientation=True)
    result = _paddle.predict(path)  # PaddleOCR 3.x
    texts = []
    for page in result:
        try:
            texts.extend([t for t in page["rec_texts"] if t])
        except Exception:
            if isinstance(page, list):
                for line in page:
                    try:
                        texts.append(line[1][0])
                    except Exception:
                        pass
    return "\n".join(texts)


def _tesseract_ocr(path: str) -> str:
    import pytesseract
    from PIL import Image
    return pytesseract.image_to_string(Image.open(path), lang="jpn+eng").strip()


def ocr_text(path: str) -> str:
    """画像内の文字を抽出。auto は PaddleOCR を試し、失敗したら Tesseract に切替。"""
    engines = {"paddle": _paddle_ocr, "tesseract": _tesseract_ocr}
    order = [OCR_ENGINE] if OCR_ENGINE in engines else ["paddle", "tesseract"]
    for eng in order:
        try:
            return engines[eng](path)
        except Exception as e:
            print(f"  OCR({eng})が使えません: {e}")
    return ""


def describe_image(path: str) -> str:
    """qwen3.5:9b に画像を見せて内容説明を生成する。"""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.LLM_MODEL,
            "prompt": DESCRIBE_PROMPT,
            "images": [b64],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "num_ctx": 4096},
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def main() -> None:
    if not os.path.isdir(IMAGES_DIR):
        print(f"フォルダが見つかりません: {IMAGES_DIR}/  (画像を置いてから実行)")
        sys.exit(1)

    files = [
        os.path.join(IMAGES_DIR, f)
        for f in sorted(os.listdir(IMAGES_DIR))
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    ]
    if not files:
        print(f"{IMAGES_DIR}/ に画像が見つかりませんでした。")
        sys.exit(0)

    Settings.embed_model = OllamaEmbedding(
        model_name=config.EMBED_MODEL, base_url=config.OLLAMA_BASE_URL,
    )
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = client.get_or_create_collection(config.COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    documents = []
    for i, path in enumerate(files, 1):
        name = os.path.basename(path)
        print(f"[{i}/{len(files)}] 処理中: {name}")
        try:
            desc = describe_image(path)
        except Exception as e:
            print(f"  説明生成に失敗: {e}")
            desc = ""
        try:
            text = ocr_text(path)
        except Exception as e:
            print(f"  OCRに失敗: {e}")
            text = ""

        if not desc and not text:
            print("  スキップ(説明もOCRも空)")
            continue

        # 説明 + OCR文字 を1チャンクに合体
        body = f"画像ファイル「{name}」の内容説明:\n"
        if desc:
            body += f"[説明] {desc}\n"
        if text:
            body += f"\n[画像内の文字(OCR抽出)]\n{text}\n"

        documents.append(Document(text=body, metadata={"file_name": name, "type": "image"}))
        print(f"  説明: {desc[:40]}...  / OCR文字数: {len(text)}")

    if not documents:
        print("登録できる画像がありませんでした。")
        sys.exit(0)

    print(f"埋め込み(bge-m3)を生成してChromaに登録中... ({len(documents)}件)")
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    print(f"完了。{len(documents)}件の画像(説明+文字)を知識ベースに追加しました。")


if __name__ == "__main__":
    main()
