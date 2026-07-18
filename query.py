"""質問して、2段階検索(bge-m3 → リランカー)＋qwen3.5:9bで根拠付き回答を得る。

使い方:
    python query.py "自宅LLM基盤を再起動する手順は?"
    引数なしなら対話モード。
"""
import sys

import chromadb
from llama_index.core import PromptTemplate, Settings, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
from xinference_rerank import XinferenceRerank

def build_qa_template() -> PromptTemplate:
    """QAプロンプト。思考OFF時のみ /no_think を末尾に注入して確実に思考を止める。"""
    body = (
        "あなたは私専属の秘書です。以下の根拠(context)だけを使って、日本語で結論から簡潔に答えてください。"
        "推測はせず、根拠に無い場合は「資料に該当する情報が見つかりませんでした」と述べること。\n"
        "----------------\n"
        "{context_str}\n"
        "----------------\n"
        "質問: {query_str}\n"
    )
    if not config.THINK:  # 思考OFFのときだけ /no_think を入れる(ON時に入れると思考が止まる)
        body += "/no_think\n"
    body += "回答: "
    return PromptTemplate(body)


def build_query_engine():
    Settings.embed_model = OllamaEmbedding(
        model_name=config.EMBED_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )
    Settings.llm = Ollama(
        model=config.LLM_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        request_timeout=600.0,
        context_window=config.NUM_CTX,
        thinking=config.THINK,  # 既定OFF。THINK=1 のとき思考ON(複雑な質問向け)
        temperature=0.0,       # 事実ベースRAG: ブレを無くす(既定1.0は脱線しやすい)
        additional_kwargs={
            # 出力トークン上限。思考ONは考える余地が要るので多め、OFFは短く打ち切り(暴走防止)
            "num_predict": 3000 if config.THINK else 800,
            "presence_penalty": 0.0,  # qwen3.5既定の1.5は脱線要因なので0に
        },
    )

    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = client.get_or_create_collection(config.COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    index = VectorStoreIndex.from_vector_store(vector_store)

    reranker = XinferenceRerank(
        base_url=config.XINFERENCE_BASE_URL,
        model=config.RERANK_MODEL,
        top_n=config.RERANK_TOP_N,
    )
    return index.as_query_engine(
        similarity_top_k=config.RETRIEVE_TOP_K,
        node_postprocessors=[reranker],
        text_qa_template=build_qa_template(),
        response_mode="compact",
    )


def ask(query_engine, question: str) -> None:
    resp = query_engine.query(question)
    print("\n=== 回答 ===")
    print(resp)
    print("\n=== 出典(リランク後) ===")
    for n in resp.source_nodes:
        src = n.node.metadata.get("file_name", "?")
        print(f"[score {n.score:.3f}] {src}: {n.node.get_content()[:80].strip()}...")


def main() -> None:
    query_engine = build_query_engine()
    if len(sys.argv) > 1:
        ask(query_engine, " ".join(sys.argv[1:]))
        return
    print("対話モード(空行 or 'exit' で終了)")
    while True:
        try:
            q = input("\n質問> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() == "exit":
            break
        ask(query_engine, q)


if __name__ == "__main__":
    main()
