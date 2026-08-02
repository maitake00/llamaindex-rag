"""ツール呼び出し型エージェント。LLM自身が文書検索/Web検索/直接回答を判断する。"""
from typing import Iterator, List

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import QueryBundle
from llama_index.core.tools import FunctionTool

import config
from web_search import search_web

SYSTEM_PROMPT = """あなたは私専属の秘書です。日本語で、結論を先に簡潔に答えてください。

重要な前提:
あなたは私の環境・資料・最新情報について何も知りません。
自分の記憶から答えることは禁止です。必ず道具で調べてから答えてください。

道具の使い分け:
- 「監視」「構成」「設定」など、私の環境や資料に関する質問 → search_documents を使う。
  質問が私自身についてかAI自身についてか曖昧な場合も、必ず私の資料として search_documents で調べる。
- 最新情報、時事、一般的な調べもの、search_documents で見つからなかったこと → search_web を使う。
- 道具を使わずに答えてよいのは、挨拶・雑談・直前の会話の単なる言い換えだけ。

答え方:
- 道具で得た根拠だけに基づいて答え、推測で補わないこと。
- Webの情報を使った場合は、末尾に出典URLを示すこと。
- 資料にもWebにも無ければ、無いと正直に述べること。"""


def _make_doc_search_tool(index, reranker) -> FunctionTool:
    def search_documents(query: str) -> str:
        """自分の保存文書(仕事のメモ、設定、過去の記録、画像やPDFの内容)を検索する。"""
        retriever = index.as_retriever(similarity_top_k=config.RETRIEVE_TOP_K)
        nodes = retriever.retrieve(query)
        if not nodes:
            return "該当する資料は見つかりませんでした。"
        nodes = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(query))
        parts = []
        for n in nodes:
            src = n.node.metadata.get("file_name", "不明な資料")
            parts.append(f"[{src}]\n{n.node.get_content()}")
        return "\n\n".join(parts)

    return FunctionTool.from_defaults(fn=search_documents)


def _make_web_search_tool() -> FunctionTool:
    def search_web_tool(query: str) -> str:
        """最新情報や一般的な調べもののためにWebを検索する。検索語は簡潔にする。"""
        return search_web(query)

    return FunctionTool.from_defaults(fn=search_web_tool, name="search_web")


def build_tools(index, reranker) -> List[FunctionTool]:
    tools = [_make_doc_search_tool(index, reranker)]
    if config.WEB_SEARCH_ENABLED:
        tools.append(_make_web_search_tool())
    return tools


def _run_tools(llm, tools, chat_history: List[ChatMessage]) -> List[ChatMessage]:
    tools_by_name = {t.metadata.name: t for t in tools}
    question = next(
        (m.content for m in reversed(chat_history) if m.role == MessageRole.USER), ""
    )

    for step in range(config.AGENT_MAX_STEPS):
        resp = llm.chat_with_tools(
            tools=tools,
            chat_history=chat_history,
        )
        tool_calls = llm.get_tool_calls_from_response(resp, error_on_no_tool_call=False)

        if not tool_calls:
            # 1手目でツールを使わなかった場合の保険。
            # 9Bモデルは曖昧な質問(主語の無い「監視は何で行っている？」等)で判断を
            # 迷い、「search_documentsで調べます」と言うだけで実行しないことがある。
            # 従来のRAG(必ず資料を検索する)の確実性を失わないよう、資料検索を強制する。
            if step == 0 and config.FORCE_DOC_SEARCH and "search_documents" in tools_by_name:
                print("[agent] ツール未使用のため search_documents を強制実行")
                try:
                    out = str(tools_by_name["search_documents"](query=question))
                except Exception as e:
                    print(f"[agent] 強制検索に失敗: {e}")
                    return chat_history + [resp.message]
                chat_history = chat_history + [
                    ChatMessage(
                        role=MessageRole.USER,
                        content=(
                            f"参考資料:\n{out}\n\n"
                            "上記の資料に基づいて、先ほどの質問に答えてください。"
                            "資料に該当が無ければ、その旨を述べたうえで search_web を使ってください。"
                        ),
                    )
                ]
                continue
            return chat_history + [resp.message]

        chat_history = chat_history + [resp.message]

        for tc in tool_calls:
            tool = tools_by_name.get(tc.tool_name)
            if tool is None:
                output = f"ツール {tc.tool_name} は存在しません。"
            else:
                try:
                    print(f"[agent] {tc.tool_name}({tc.tool_kwargs})")
                    output = str(tool(**tc.tool_kwargs))
                except Exception as e:
                    print(f"[agent] ツール実行失敗: {e}")
                    output = f"ツールの実行に失敗しました: {e}"
            chat_history = chat_history + [
                ChatMessage(
                    role=MessageRole.TOOL,
                    content=output,
                    additional_kwargs={"name": tc.tool_name, "tool_call_id": tc.tool_id},
                )
            ]
    return chat_history


def _prepare(llm, tools, question: str, history: List[ChatMessage], think: bool):
    # 注意: ここに /no_think を付けてはいけない。
    # 思考を抑制するとツールを使うかの判断まで止まり、ツール呼び出しが発行されなくなる。
    # 思考のオフは Ollama の thinking=False で既に効いている。
    system = SYSTEM_PROMPT
    chat_history = (
        [ChatMessage(role=MessageRole.SYSTEM, content=system)]
        + history
        + [ChatMessage(role=MessageRole.USER, content=question)]
    )
    return _run_tools(llm, tools, chat_history)


def chat(llm, tools, question: str, history: List[ChatMessage], think: bool) -> str:
    chat_history = _prepare(llm, tools, question, history, think)
    last = chat_history[-1]
    if last.role == MessageRole.ASSISTANT and last.content:
        return str(last.content)
    return str(llm.chat(chat_history).message.content)


def stream_chat(
    llm, tools, question: str, history: List[ChatMessage], think: bool
) -> Iterator[str]:
    chat_history = _prepare(llm, tools, question, history, think)
    last = chat_history[-1]

    if last.role == MessageRole.ASSISTANT and last.content:
        text = str(last.content)
        for i in range(0, len(text), 24):
            yield text[i : i + 24]
        return

    prev = ""
    for chunk in llm.stream_chat(chat_history):
        cur = chunk.message.content or ""
        if len(cur) > len(prev):
            yield cur[len(prev) :]
            prev = cur
