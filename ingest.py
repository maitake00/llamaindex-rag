"""文書を取り込んでベクトルDB(Chroma)を作る。

使い方:
    1. docs/ フォルダに日本語・英語の文書(.md .txt .pdf など)を置く
    2. python ingest.py

埋め込みは Ollama の bge-m3(多言語)を使うので、日英どちらも同じ精度で扱える。
"""
import chromadb
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import config


def main() -> None:
    Settings.embed_model = OllamaEmbedding(
        model_name=config.EMBED_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )
    Settings.node_parser = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )

    print(f"文書を読み込み中: {config.DOCS_DIR}/")
    documents = SimpleDirectoryReader(config.DOCS_DIR).load_data()
    print(f"  {len(documents)} 件の文書を読み込みました")

    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = client.get_or_create_collection(config.COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("埋め込み(bge-m3)を生成してChromaに保存中...")
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    print(f"完了。ベクトルDB: {config.CHROMA_DIR}/ (collection={config.COLLECTION})")


if __name__ == "__main__":
    main()
