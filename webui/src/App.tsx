import { useEffect, useRef, useState } from 'react'
import { Flexbox } from 'react-layout-kit'
import { ActionIcon, Markdown, ThemeProvider } from '@lobehub/ui'
import { ChatInputArea, ChatItem } from '@lobehub/ui/chat'
import { App as AntApp, Button, Input, Select, Upload, theme as antdTheme } from 'antd'
import {
  Calendar, CheckSquare, FileText, LogOut, Menu, MessageSquare,
  Mic, Moon, Plus, RefreshCw, Copy, SendHorizontal, Square, Trash2, Sun, Upload as UploadIcon, Volume2,
} from 'lucide-react'

// Glanceのテーマ(HSL)をHEXに変換した配色。ダッシュボードに埋め込んだ時に馴染ませる。
const GL = {
  bg: '#1B2128',        // background-color: 210 20 13
  surface: '#222932',   // ウィジェット面(背景よりわずかに明るく)
  line: '#2E3540',
  text: '#E5E9EF',
  dim: '#9AA4B2',
  primary: '#0077FF',   // primary-color: 212 100 50
  positive: '#1FAD4E',  // positive-color: 140 70 40
  negative: '#E7473C',  // negative-color: 4 78 57
}

type Msg = { role: 'user' | 'assistant'; content: string }
type Conv = { id: string; title: string; msgs: Msg[] }

const KEY_STORE = 'key'
const api = (k: string) => ({ Authorization: 'Bearer ' + k })

function Login({ onDone }: { onDone: (k: string) => void }) {
  const [v, setV] = useState('')
  return (
    <Flexbox align="center" justify="center" style={{ height: '100dvh', padding: 24 }}>
      <Flexbox gap={12} style={{ width: 340 }}>
        <h2 style={{ margin: 0 }}>秘書にログイン</h2>
        <div style={{ opacity: .6, fontSize: 13 }}>APIキーを入力してください(この端末に保存されます)</div>
        <Input.Password value={v} onChange={e => setV(e.target.value)} placeholder="APIキー" />
        <Button type="primary" onClick={() => { if (v.trim()) { localStorage.setItem(KEY_STORE, v.trim()); onDone(v.trim()) } }}>
          ログイン
        </Button>
      </Flexbox>
    </Flexbox>
  )
}

function Inner({ apiKey, dark, setDark }: { apiKey: string; dark: boolean; setDark: (v: boolean) => void }) {
  const { message } = AntApp.useApp()
  const [convs, setConvs] = useState<Conv[]>([])
  const [cur, setCur] = useState<string>('')
  const [view, setView] = useState<'chat' | 'doc' | 'todo' | 'cal'>('chat')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [model, setModel] = useState('secretary')
  const [drawer, setDrawer] = useState(false)
  const [stream, setStream] = useState('')
  const [todoText, setTodoText] = useState('読み込み中...')
  const [calText, setCalText] = useState('読み込み中...')
  const [url, setUrl] = useState('')
  const [out, setOut] = useState('')
  const bottom = useRef<HTMLDivElement>(null)

  const conv = convs.find(c => c.id === cur)
  const H = api(apiKey)

  useEffect(() => {
    fetch('/api/convs', { headers: H })
      .then(r => r.json())
      .then((list: Conv[]) => {
        if (list.length) { setConvs(list); setCur(list[0].id) } else newChat()
      })
      .catch(() => newChat())
    loadTodo(); loadCal()
  }, [])

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [conv?.msgs.length, stream])

  const persist = (c: Conv) => {
    fetch('/api/convs/' + c.id, {
      method: 'PUT', headers: { ...H, 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: c.title, msgs: c.msgs }),
    }).catch(() => {})
  }

  function newChat() {
    const c: Conv = { id: String(Date.now()), title: '新しい会話', msgs: [] }
    setConvs(p => [c, ...p]); setCur(c.id); setView('chat'); setDrawer(false)
  }

  function removeConv(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    fetch('/api/convs/' + id, { method: 'DELETE', headers: H }).catch(() => {})
    setConvs(p => {
      const n = p.filter(c => c.id !== id)
      if (id === cur) setCur(n[0]?.id || '')
      return n
    })
  }

  async function run(msgs: Msg[], convId: string, title: string) {
    setBusy(true); setStream('')
    let out = ''
    try {
      const r = await fetch('/v1/chat/completions', {
        method: 'POST', headers: { ...H, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages: msgs, stream: true }),
      })
      const rd = r.body!.getReader(); const dec = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await rd.read(); if (done) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n'); buf = parts.pop() || ''
        for (const p of parts) {
          const l = p.trim(); if (!l.startsWith('data:')) continue
          const d = l.slice(5).trim(); if (d === '[DONE]') continue
          try { const t = JSON.parse(d).choices?.[0]?.delta?.content; if (t) { out += t; setStream(out) } } catch {}
        }
      }
    } catch (e) { out = '通信エラー: ' + e }
    const final: Msg[] = [...msgs, { role: 'assistant', content: out }]
    const c: Conv = { id: convId, title, msgs: final }
    setConvs(p => p.map(x => x.id === convId ? c : x))
    persist(c); setStream(''); setBusy(false)
  }

  // ---- 音声入力(録音 → Whisperで文字起こし) ----
  const recRef = useRef<MediaRecorder | null>(null)
  const [rec, setRec] = useState(false)

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,   // ノイズ対策: エコー除去
          noiseSuppression: true,   // ノイズ対策: 環境音抑制
          autoGainControl: true,    // 小さい声を持ち上げる
          channelCount: 1,
        },
      })
      const mr = new MediaRecorder(stream)
      const chunks: BlobPart[] = []
      mr.ondataavailable = e => chunks.push(e.data)
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: 'audio/webm' })
        if (blob.size < 1000) { setRec(false); return }
        setInput('(認識中...)')
        const fd = new FormData(); fd.append('file', blob, 'audio.webm')
        try {
          const r = await fetch('/api/stt', { method: 'POST', headers: H, body: fd })
          const j = await r.json()
          setInput(j.text || '')
          if (j.error) message.error(j.error)
        } catch (e) { setInput(''); message.error('認識に失敗しました') }
        setRec(false)
      }
      recRef.current = mr
      mr.start()
      setRec(true)
    } catch (e) {
      message.error('マイクを使用できません(権限を確認してください)')
    }
  }

  function stopRec() { recRef.current?.stop() }

  // ---- 読み上げ(VOICEVOX) ----
  async function speak(text: string) {
    try {
      const fd = new FormData(); fd.append('text', text)
      const r = await fetch('/api/tts', { method: 'POST', headers: H, body: fd })
      if (!r.ok) { message.error('読み上げに失敗しました'); return }
      const url = URL.createObjectURL(await r.blob())
      const a = new Audio(url); a.onended = () => URL.revokeObjectURL(url); a.play()
    } catch { message.error('読み上げに失敗しました') }
  }

  function send() {
    const text = input.trim(); if (!text || busy || !conv) return
    setInput('')
    const msgs: Msg[] = [...conv.msgs, { role: 'user', content: text }]
    const title = conv.msgs.length === 0 ? text.slice(0, 28) : conv.title
    setConvs(p => p.map(x => x.id === conv.id ? { ...x, msgs, title } : x))
    run(msgs, conv.id, title)
  }

  function regen(i: number) {
    if (!conv || busy) return
    const msgs = conv.msgs.slice(0, i)
    setConvs(p => p.map(x => x.id === conv.id ? { ...x, msgs } : x))
    run(msgs, conv.id, conv.title)
  }

  function drop(i: number) {
    if (!conv) return
    const msgs = conv.msgs.filter((_, k) => k !== i)
    const c = { ...conv, msgs }
    setConvs(p => p.map(x => x.id === conv.id ? c : x)); persist(c)
  }

  const loadTodo = () => fetch('/api/todo', { headers: H }).then(r => r.json())
    .then(j => setTodoText(j.message)).catch(() => setTodoText('取得できません'))
  const loadCal = () => fetch('/api/calendar?days=7', { headers: H }).then(r => r.json())
    .then(j => setCalText(j.message)).catch(() => setCalText('取得できません'))

  async function postForm(path: string, fd: FormData, busyMsg: string) {
    setOut(busyMsg)
    try {
      const r = await fetch(path, { method: 'POST', headers: H, body: fd })
      setOut((await r.json()).message)
    } catch (e) { setOut('エラー: ' + e) }
  }

  function ingestUrl() {
    if (!url.trim()) return
    const fd = new FormData(); fd.append('url', url.trim())
    setView('doc'); postForm('/api/ingest_url', fd, '取り込み中...')
  }

  // Androidの共有メニューから呼ばれる
  useEffect(() => {
    ;(window as any).handleShare = (kind: string, payload: string, name: string) => {
      if (kind === 'text') {
        const m = payload.match(/https?:\/\/[^\s]+/)
        if (m) { setView('doc'); setUrl(m[0]); const fd = new FormData(); fd.append('url', m[0])
                 postForm('/api/ingest_url', fd, '共有されたURLを取り込み中...') }
        else { setView('chat'); setInput(payload) }
        return
      }
      try {
        const bin = atob(payload); const arr = new Uint8Array(bin.length)
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
        const fd = new FormData(); fd.append('files', new Blob([arr]), name || 'shared')
        setView('doc'); postForm('/api/upload', fd, '共有されたファイルを登録中...')
      } catch (e) { setOut('共有ファイルの処理に失敗: ' + e) }
    }
  }, [apiKey])

  const navBtn = (v: typeof view, Icon: any, label: string) => (
    <ActionIcon
      active={view === v} icon={Icon} key={v} size="large" title={label}
      onClick={() => { setView(v); setDrawer(false); if (v === 'todo') loadTodo(); if (v === 'cal') loadCal() }}
    />
  )

  return (
    <div className="shell">
      <div className="rail">
        {navBtn('chat', MessageSquare, 'チャット')}
        {navBtn('doc', FileText, '資料')}
        {navBtn('todo', CheckSquare, 'タスク')}
        {navBtn('cal', Calendar, '予定')}
        <div className="spacer" />
        <ActionIcon icon={dark ? Sun : Moon} size="large" title="テーマ" onClick={() => setDark(!dark)} />
        <div className="pc-only">
          <ActionIcon icon={LogOut} size="large" title="ログアウト"
            onClick={() => { localStorage.removeItem(KEY_STORE); location.reload() }} />
        </div>
      </div>

      <div className={'mask' + (drawer ? '' : ' hidden')} onClick={() => setDrawer(false)} />

      <div className={'side' + (drawer ? ' open' : '')}
           style={{ background: dark ? GL.surface : '#fafafa' }}>
        <div style={{ padding: 12, borderBottom: '1px solid var(--ln)' }}>
          <Button block icon={<Plus size={15} />} onClick={newChat}>新しい会話</Button>
        </div>
        <div className="list">
          {convs.map(c => (
            <div className="conv" key={c.id} onClick={() => { setCur(c.id); setView('chat'); setDrawer(false) }}
                 style={{ background: c.id === cur ? (dark ? '#2B333E' : '#eaeaec') : undefined }}>
              <MessageSquare size={14} />
              <span className="t">{c.title}</span>
              <Trash2 size={14} opacity={.5} onClick={e => removeConv(c.id, e)} />
            </div>
          ))}
        </div>
      </div>

      <div className="main">
        <div className="top">
          <span className="burger">
            <ActionIcon icon={Menu} onClick={() => setDrawer(true)} title="会話一覧" />
          </span>
          <strong style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {view === 'chat' ? (conv?.title || '新しい会話')
              : { doc: '資料', todo: 'タスク', cal: '予定' }[view]}
          </strong>
          {view === 'chat' && (
            <Select value={model} onChange={setModel} size="small" style={{ width: 96 }}
              options={[{ value: 'secretary', label: '通常' }, { value: 'secretary-think', label: '熟考' }]} />
          )}
        </div>

        <div className="scroll">
          {view === 'chat' && (
            <div className="wrap">
              {conv?.msgs.map((m, i) => (
                <ChatItem
                  key={i}
                  avatar={m.role === 'user'
                    ? { avatar: '🧑', title: '私', backgroundColor: '#1677ff' }
                    : { avatar: '🤖', title: '秘書' }}
                  message={m.content}
                  placement={m.role === 'user' ? 'right' : 'left'}
                  primary={m.role === 'user'}
                  actions={
                    <Flexbox horizontal gap={2}>
                      <ActionIcon icon={Copy} size="small" title="コピー"
                        onClick={() => { navigator.clipboard.writeText(m.content); message.success('コピーしました') }} />
                      {m.role === 'assistant' && <>
                        <ActionIcon icon={Volume2} size="small" title="読み上げ" onClick={() => speak(m.content)} />
                        <ActionIcon icon={RefreshCw} size="small" title="再生成" onClick={() => regen(i)} />
                      </>}
                      <ActionIcon icon={Trash2} size="small" title="削除" onClick={() => drop(i)} />
                    </Flexbox>
                  }
                />
              ))}
              {busy && (
                <ChatItem avatar={{ avatar: '🤖', title: '秘書' }} loading={!stream}
                  message={stream || '...'} placement="left" />
              )}
              <div ref={bottom} />
            </div>
          )}

          {view === 'doc' && (
            <div className="tool">
              <Flexbox gap={16}>
                <Flexbox gap={8}>
                  <strong>ファイルを追加</strong>
                  <div style={{ opacity: .6, fontSize: 13 }}>画像・PDF・テキストを資料として登録します</div>
                  <Upload.Dragger multiple showUploadList={false}
                    beforeUpload={(_f, list) => {
                      const fd = new FormData(); list.forEach(x => fd.append('files', x))
                      postForm('/api/upload', fd, '処理中...(画像は1分ほどかかります)')
                      return false
                    }}>
                    <p style={{ padding: 20 }}><UploadIcon /><br />タップして選択</p>
                  </Upload.Dragger>
                </Flexbox>
                <Flexbox gap={8}>
                  <strong>Webページを追加</strong>
                  <div style={{ opacity: .6, fontSize: 13 }}>URLの本文を取り込み、あとで検索できるようにします</div>
                  <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..."
                    onPressEnter={ingestUrl} />
                  <Button onClick={ingestUrl}>取り込む</Button>
                </Flexbox>
                {out && <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, opacity: .8 }}>{out}</pre>}
              </Flexbox>
            </div>
          )}

          {view === 'todo' && (
            <div className="tool">
              <Flexbox gap={12}>
                <TodoAdd apiKey={apiKey} onDone={loadTodo} />
                <strong>未完了のタスク</strong>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14 }}>{todoText}</pre>
                <Button onClick={loadTodo}>更新</Button>
              </Flexbox>
            </div>
          )}

          {view === 'cal' && (
            <div className="tool">
              <Flexbox gap={12}>
                <strong>今週の予定</strong>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14 }}>{calText}</pre>
                <Button onClick={loadCal}>更新</Button>
              </Flexbox>
            </div>
          )}
        </div>

        {view === 'chat' && (
          <div className="composer">
            <div className="inner">
              <div style={{
                border: '1px solid var(--ln)', borderRadius: 12,
                padding: '8px 12px', background: dark ? GL.surface : '#fafafa',
              }}>
                <ChatInputArea.Inner
                  value={input}
                  onInput={setInput}
                  onSend={send}
                  placeholder="秘書に聞く..."
                  autoSize={{ minRows: 1, maxRows: 6 }}
                />
                <Flexbox horizontal align="center" gap={8} style={{ marginTop: 6 }}>
                  <Button
                    danger={rec}
                    type={rec ? 'primary' : 'default'}
                    icon={rec ? <Square size={13} /> : <Mic size={15} />}
                    onClick={() => (rec ? stopRec() : startRec())}
                    title={rec ? '録音を止めて文字起こし' : '音声で入力'}
                  />
                  <span style={{ fontSize: 11, opacity: .5 }}>
                    {rec ? '録音中... もう一度押すと文字起こし' : 'Enterで送信 / Shift+Enterで改行'}
                  </span>
                  <span style={{ marginLeft: 'auto' }}>
                    <Button type="primary" loading={busy} onClick={send}
                            icon={<SendHorizontal size={15} />} />
                  </span>
                </Flexbox>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TodoAdd({ apiKey, onDone }: { apiKey: string; onDone: () => void }) {
  const [t, setT] = useState(''); const [d, setD] = useState('')
  const add = () => {
    if (!t.trim()) return
    const fd = new FormData(); fd.append('action', 'add'); fd.append('title', t); fd.append('due', d)
    fetch('/api/todo', { method: 'POST', headers: api(apiKey), body: fd })
      .then(() => { setT(''); setD(''); onDone() })
  }
  return (
    <Flexbox gap={8}>
      <strong>タスクを追加</strong>
      <Input value={t} onChange={e => setT(e.target.value)} placeholder="やること" />
      <Input value={d} onChange={e => setD(e.target.value)} placeholder="期限(任意) 例 2026-08-10T18:00" />
      <Button type="primary" onClick={add}>追加</Button>
    </Flexbox>
  )
}

export default function App() {
  const [apiKey, setApiKey] = useState(
    localStorage.getItem(KEY_STORE) || new URLSearchParams(location.search).get('key') || ''
  )
  // プロキシ(authentik)で認証済みならキー入力を省略する
  const [checkAuth, setCheckAuth] = useState(true)
  useEffect(() => {
    fetch('/api/me')
      .then(r => { if (r.ok) setApiKey(k => k || 'proxy') })
      .finally(() => setCheckAuth(false))
  }, [])
  const [dark, setDark] = useState(localStorage.getItem('theme') !== 'light')

  useEffect(() => {
    localStorage.setItem('theme', dark ? 'dark' : 'light')
    document.documentElement.style.setProperty('--ln', dark ? GL.line : '#e4e4e7')
    document.body.style.background = dark ? GL.bg : '#ffffff'
    document.body.style.color = dark ? GL.text : '#18181b'
  }, [dark])

  return (
    <ThemeProvider
      themeMode={dark ? 'dark' : 'light'}
      theme={{
        algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: dark ? {
          colorPrimary: GL.primary,
          colorSuccess: GL.positive,
          colorError: GL.negative,
          colorBgBase: GL.bg,
          colorBgContainer: GL.surface,
          colorBgElevated: GL.surface,
          colorBorder: GL.line,
          colorBorderSecondary: GL.line,
          colorText: GL.text,
          colorTextSecondary: GL.dim,
          borderRadius: 8,
        } : { colorPrimary: GL.primary, borderRadius: 8 },
      }}>
      <AntApp>
        {checkAuth ? null
          : apiKey ? <Inner apiKey={apiKey} dark={dark} setDark={setDark} />
          : <Login onDone={setApiKey} />}
      </AntApp>
    </ThemeProvider>
  )
}
