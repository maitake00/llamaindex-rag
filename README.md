# llamaindex-rag — 日英対応のローカルRAG(自作)

LlamaIndexで自作した、完全ローカルの日英両対応RAGパイプライン。
RAGFlowの「日本語が中国語トークンに変換される」問題を、多言語ベクトル検索主体の設計で根本回避している。
推論(生成・埋め込み・リランク)は既存サービス(Ollama・Xinference)にHTTPで委譲するため、Python側は軽量(torch不要)。

**特徴**
- 日本語で質問して英語資料を引ける(逆も可)— bge-m3 / bge-reranker の言語横断性
- 2段階検索(ベクトル40件 → リランクで精密に5件)でリランカーが正しく機能
- thinking切替: 普段は高速な事実検索、`THINK=1`で深掘り分析モード
- 8GB VRAM向けに実測チューニング済み(num_ctx=4096で100% GPU、約20秒/クエリ)
- 生成モデルは差し替え可能(qwen3.5:9b / LoRA特化モデルなど)

姉妹リポジトリ: **llm-homelab**(Ollama/Xinference/監視の基盤) / **lora-secretary**(秘書スタイルLoRA)

```
文書(日/英) → チャンク化 → bge-m3で埋め込み(多言語) → Chroma(ベクトルDB)
質問 → bge-m3でベクトル検索(20件) → bge-reranker-v2-m3でリランク(上位5件) → qwen3.5:9bが根拠付き回答
        （Ollama）                    （Xinference）                        （Ollama, /no_think）
```

なぜ日英ともに高品質か: bge-m3(埋め込み)と bge-reranker-v2-m3(リランク)は**どちらも多言語・言語横断対応**。
ベクトル検索主体なので、言語ごとのトークナイザー(MeCab等)が不要で、日本語も英語も均一に扱える。

---

## 前提(先に起動しておくもの)

1. **Ollama** が起動し、モデルがある: `qwen3.5:9b`, `bge-m3`
   ```bash
   docker exec -it ollama ollama list   # 2つあるか確認
   ```
2. **Xinference** が起動し、リランカーが launch 済み:
   ```bash
   docker exec xinference xinference list   # bge-reranker-v2-m3 があるか
   # 無ければ:
   docker exec xinference xinference launch --model-name bge-reranker-v2-m3 --model-type rerank
   ```
3. どちらもホストに公開済み(Ollama=11434, Xinference=9997)。

---

## セットアップ

Python は **3.11 か 3.12** を推奨(3.14 等の最新版は一部ライブラリが未対応の場合あり)。

```bash
cd llamaindex-rag
python3.11 -m venv .venv
source .venv/bin/activate        # Windows(PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 使い方

### 1. 文書を入れる
`docs/` フォルダに、日本語・英語の文書(.md .txt .pdf .docx など)を置く。
(まずは llm-homelab の Markdown をコピーしてテストするとよい)

### 2. 取り込み(インデックス作成)
```bash
python ingest.py
```
bge-m3で埋め込みを作り、`chroma_db/` に保存する。文書を追加・変更したら再実行。

### 3. 質問する
```bash
python query.py "自宅LLM基盤を再起動する手順は?"
# 英語もOK:
python query.py "How do I restart the home LLM stack?"
# 引数なしで対話モード
python query.py
```
回答＋出典(リランク後の上位チャンク、スコア付き)が表示される。

---

## 調整ポイント(config.py)

| 項目 | 意味 | 目安 |
| --- | --- | --- |
| `CHUNK_SIZE` | 1チャンクのトークン数 | 日英混在なら 512。議事録等の雑多な文書は 300 |
| `RETRIEVE_TOP_K` | ベクトル検索の1次候補数 | 文書が増えたら 50 に |
| `RERANK_TOP_N` | リランク後にLLMへ渡す数 | 5 前後 |
| `NUM_CTX` | 生成の文脈長 | 8192(VRAM節約。長文根拠が要るなら増やす) |

環境変数でも上書き可(例: `RERANK_TOP_N=8 python query.py "..."`）。

---

## 設計上のポイント

- **言語横断**: 日本語で質問→英語資料を引く(逆も)がそのまま動く。bge-m3/bge-rerankerが多言語だから。
- **RAGFlowとの違い**: RAGFlowは中国語前提のトークナイザーで日本語が壊れる。ここではベクトル検索主体にして根本回避している。
- **軽量設計**: 重い推論(生成・埋め込み・リランク)は全部既存サービス(Ollama/Xinference)に委譲。Python側はオーケストレーションのみで、torch等の重い依存を持たない。
