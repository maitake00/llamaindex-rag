"""Web検索(Tavily)。検索結果は既存のリランカーで精密に絞ってからLLMに渡す。"""
from typing import List

import requests
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

import config
from xinference_rerank import XinferenceRerank

TAVILY_URL = "https://api.tavily.com/search"


def _rerank(query: str, results: List[dict]) -> List[dict]:
    """検索結果を bge-reranker で並べ替える(落ちていても素通しで継続)。"""
    if not results:
        return results
    nodes = [
        NodeWithScore(
            node=TextNode(text=r.get("content", ""), metadata={"idx": i}),
            score=float(r.get("score", 0.0)),
        )
        for i, r in enumerate(results)
    ]
    reranker = XinferenceRerank(
        base_url=config.XINFERENCE_BASE_URL,
        model=config.RERANK_MODEL,
        top_n=config.WEB_RERANK_TOP_N,
    )
    ranked = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(query))
    out = []
    for n in ranked:
        idx = n.node.metadata.get("idx")
        if idx is not None and idx < len(results):
            out.append(results[idx])
    return out or results[: config.WEB_RERANK_TOP_N]


def search_web(query: str) -> str:
    """Webを検索し、出典URL付きの根拠テキストを返す。LLMからツールとして呼ばれる。"""
    if not config.TAVILY_API_KEY:
        return "Web検索は未設定です(TAVILY_API_KEY が設定されていません)。"

    try:
        resp = requests.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
            json={
                "api_key": config.TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": config.WEB_TOP_K,
            },
            timeout=config.WEB_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"[web_search] 検索失敗: {e}")
        return f"Web検索に失敗しました({e})。この情報は取得できませんでした。"

    if not results:
        return "Web検索の結果が見つかりませんでした。"

    results = _rerank(query, results)

    parts = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(タイトルなし)")
        url = r.get("url", "")
        content = (r.get("content") or "").strip()
        parts.append(f"[{i}] {title}\nURL: {url}\n{content}")
    return "\n\n".join(parts)
