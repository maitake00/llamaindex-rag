"""ツール呼び出し型エージェント。LLM自身が文書検索/Web検索/直接回答を判断する。"""
from datetime import datetime, timedelta, timezone
from typing import Iterator, List

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import QueryBundle
from llama_index.core.tools import FunctionTool

import config
from web_search import search_web

import todo_tool

try:
    import gmail_tool
    GMAIL_OK = True
except Exception as _e:
    print(f"[agent] メール無効: {_e}")
    GMAIL_OK = False

try:
    import calendar_tool
    CALENDAR_OK = True
except Exception as _e:  # 認証未設定などで読み込めない場合も本体は動かす
    print(f"[agent] カレンダー無効: {_e}")
    CALENDAR_OK = False

SYSTEM_PROMPT = """あなたは私専属の秘書です。日本語で、結論を先に簡潔に答えてください。

重要な前提:
あなたは私の環境・資料・予定・最新情報について何も知りません。
自分の記憶から答えることは禁止です。必ず道具で調べてから答えてください。

道具の使い分け:
- 予定・スケジュール・空き時間の確認 → calendar_list を使う。
  「今日」は days=1、「明日」は days=2、「今週」は days=7。
- 予定を入れる・登録する → calendar_add を使う。日時は '2026-08-05T14:00' の形式。
- 「監視」「構成」「設定」など、私の環境や資料に関する質問 → search_documents を使う。
  質問が私自身についてかAI自身についてか曖昧な場合も、必ず search_documents で調べる。
- メールの確認・未読の要約 → gmail_list を使う(未読は query='is:unread')。
  本文が必要なら gmail_read でIDを指定して読む。
- 返信を書く → gmail_draft で下書きを作る。送信はできないので、下書きを作ったことを伝える。
- やること・タスク・ToDoの追加、確認、完了 → todo を使う。
  追加は action='add'、一覧は action='list'、完了は action='done' と task_id。
- 最新情報、時事、一般的な調べもの、資料に無かったこと → search_web を使う。
- 道具を使わずに答えてよいのは、挨拶・雑談・直前の会話の単なる言い換えだけ。

答え方:
- 道具で得た根拠だけに基づいて答え、推測で補わないこと。
- Webの情報を使った場合は、末尾に出典URLを示すこと。
- 見つからなければ、無いと正直に述べること。"""


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
    if CALENDAR_OK:
        tools.append(FunctionTool.from_defaults(fn=calendar_tool.calendar_list))
        tools.append(FunctionTool.from_defaults(fn=calendar_tool.calendar_add))
    if GMAIL_OK:
        tools.append(FunctionTool.from_defaults(fn=gmail_tool.gmail_list))
        tools.append(FunctionTool.from_defaults(fn=gmail_tool.gmail_read))
        tools.append(FunctionTool.from_defaults(fn=gmail_tool.gmail_draft))
    tools.append(FunctionTool.from_defaults(fn=todo_tool.todo))
    return tools


def _run_tools(llm, tools, chat_history: List[ChatMessage]) -> List[ChatMessage]:
    """ツール呼び出しが落ち着くまで回し、確定した会話履歴を返す。

    9Bモデルは道具が増えると「道具を使います」と言うだけで実行しないことがある。
    そこで2段構えにする:
      1手目で未使用 → 「道具を使え」と促してやり直す(どの道具かはモデルに選ばせる)
      それでも未使用 → 資料検索を強制(従来RAGの確実性を最低限担保)
    """
    tools_by_name = {t.metadata.name: t for t in tools}
    question = next(
        (m.content for m in reversed(chat_history) if m.role == MessageRole.USER), ""
    )
    nudged = False
    forced = False
    used_tool = False  # 一度でも道具を実行したか

    for step in range(config.AGENT_MAX_STEPS):
        resp = llm.chat_with_tools(tools=tools, chat_history=chat_history)
        tool_calls = llm.get_tool_calls_from_response(resp, error_on_no_tool_call=False)

        if not tool_calls:
            # 既に道具を実行済みなら、この応答が最終回答
            if used_tool:
                return chat_history + [resp.message]

            # 段階1: 道具を使うよう促す(選択はモデルに任せる)
            if not nudged:
                nudged = True
                print("[agent] ツール未使用のため再指示")
                chat_history = chat_history + [
                    ChatMessage(
                        role=MessageRole.USER,
                        content=(
                            "道具を使わずに答えないでください。"
                            "上記の道具から適切なものを選び、実際に実行してから答えてください。"
                        ),
                    )
                ]
                continue

            # 段階2: それでも使わないなら資料検索を強制
            if not forced and config.FORCE_DOC_SEARCH and "search_documents" in tools_by_name:
                forced = True
                print("[agent] 再指示後も未使用のため search_documents を強制実行")
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
                        ),
                    )
                ]
                continue

            return chat_history + [resp.message]

        chat_history = chat_history + [resp.message]
        used_tool = True

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
    now = datetime.now(timezone(timedelta(hours=9)))
    system = SYSTEM_PROMPT + f"\n\n現在日時: {now.strftime('%Y-%m-%d(%a) %H:%M')} (日本時間)"
    if GMAIL_OK:
        import google_auth
        system += (
            f"\n使えるメールアカウント: {', '.join(google_auth.ACCOUNTS)}"
            f" (既定: {google_auth.MAIN_ACCOUNT}。指定が無ければ既定を使う)"
        )
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
