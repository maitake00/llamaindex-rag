"""共通設定。Ollama / Xinference の接続先やモデル名、チャンク設定をここで一元管理。"""
import os

# --- 接続先(既存の自前サービス) ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
XINFERENCE_BASE_URL = os.getenv("XINFERENCE_BASE_URL", "http://localhost:9997/v1")

# --- モデル ---
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:9b")        # 生成(Ollama)
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")         # 埋め込み(Ollama, 多言語)
RERANK_MODEL = os.getenv("RERANK_MODEL", "bge-reranker-v2-m3")  # リランク(Xinference, 多言語)

# --- チャンク(日英混在なので 512 tokens 目安、重複 64) ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))

# --- 検索 ---
RETRIEVE_TOP_K = int(os.getenv("RETRIEVE_TOP_K", "40"))  # 1次候補(ベクトル)。recall重視で40
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))        # リランク後に残す数

# --- 思考モード。既定OFF(速い・安定)。複雑な推論/比較/分析の質問だけ THINK=1 でON ---
THINK = os.getenv("THINK", "0") == "1"

# --- 生成の文脈長(VRAM節約のため制限)。
#     思考ONは考える余地が要るので、明示指定が無ければ自動で8192に拡張(OFFは4096) ---
NUM_CTX = int(os.getenv("NUM_CTX", "8192" if THINK else "4096"))

# --- 保存先 ---
DOCS_DIR = os.getenv("DOCS_DIR", "docs")            # 取り込む文書を置くフォルダ
CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")   # ベクトルDBの永続化先
COLLECTION = os.getenv("COLLECTION", "rag")
