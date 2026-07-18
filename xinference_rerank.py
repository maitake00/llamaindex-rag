"""Xinference のリランカー(bge-reranker-v2-m3)をHTTP経由で使う LlamaIndex 後処理器。

既に動いている Xinference( http://localhost:9997 )の /v1/rerank を叩くだけなので、
Python側に torch や sentence-transformers を入れる必要がない(軽量)。
"""
from typing import List, Optional

import requests
from llama_index.core.bridge.pydantic import Field
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


class XinferenceRerank(BaseNodePostprocessor):
    """検索で拾った候補ノードを、Xinferenceのリランカーで精密に並べ替える。"""

    base_url: str = Field(default="http://localhost:9997/v1")
    model: str = Field(default="bge-reranker-v2-m3")
    top_n: int = Field(default=5)
    timeout: float = Field(default=120.0)

    @classmethod
    def class_name(cls) -> str:
        return "XinferenceRerank"

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        if not nodes or query_bundle is None:
            return nodes

        documents = [n.node.get_content() for n in nodes]
        try:
            resp = requests.post(
                f"{self.base_url}/rerank",
                json={
                    "model": self.model,
                    "query": query_bundle.query_str,
                    "documents": documents,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as e:
            # リランカーが落ちていても検索結果は返す(縮退運転)
            print(f"[XinferenceRerank] rerank失敗のため素の順序を使用: {e}")
            return nodes[: self.top_n]

        reranked: List[NodeWithScore] = []
        for r in results[: self.top_n]:
            idx = r.get("index")
            if idx is None or idx >= len(nodes):
                continue
            node = nodes[idx]
            node.score = float(r.get("relevance_score", 0.0))
            reranked.append(node)
        return reranked
