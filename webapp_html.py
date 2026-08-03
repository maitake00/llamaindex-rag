"""統合Webアプリの画面(LobeChat風UI)。"""

APP_HTML = r"""<!doctype html>
<html lang="ja" data-theme="dark"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0f11">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.svg">
<title>秘書</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<style>
:root[data-theme="dark"]{
  --bg:#0f0f11; --rail:#141417; --side:#18181b; --line:#27272a;
  --text:#e4e4e7; --dim:#a1a1aa; --card:#1c1c1f; --hover:#232327;
  --me:#1677ff; --meText:#fff; --ai:#1f1f23;
}
:root[data-theme="light"]{
  --bg:#fff; --rail:#f4f4f5; --side:#fafafa; --line:#e4e4e7;
  --text:#18181b; --dim:#71717a; --card:#f4f4f5; --hover:#eaeaec;
  --me:#1677ff; --meText:#fff; --ai:#f4f4f5;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;height:100dvh;display:flex;background:var(--bg);color:var(--text);
  font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;font-size:14px}
button{font-family:inherit;color:inherit}

/* --- 左アイコンレール --- */
.rail{width:56px;background:var(--rail);border-right:1px solid var(--line);
  display:flex;flex-direction:column;align-items:center;padding:10px 0;gap:6px;flex-shrink:0}
.rail .logo{width:32px;height:32px;border-radius:9px;margin-bottom:8px}
.rail button{width:40px;height:40px;border:0;background:none;border-radius:10px;
  font-size:18px;display:flex;align-items:center;justify-content:center;cursor:pointer}
.rail button:hover{background:var(--hover)}
.rail button.on{background:var(--me);color:#fff}
.rail .sp{margin-top:auto}

/* --- 会話リスト --- */
.side{width:268px;background:var(--side);border-right:1px solid var(--line);
  display:flex;flex-direction:column;flex-shrink:0}
.side .hd{padding:12px;border-bottom:1px solid var(--line)}
.side .new{width:100%;padding:9px;border:1px solid var(--line);background:var(--card);
  border-radius:9px;cursor:pointer;font-size:13px;font-weight:600}
.side .new:hover{background:var(--hover)}
.side .list{flex:1;overflow-y:auto;padding:8px}
.item{padding:10px 11px;border-radius:9px;cursor:pointer;display:flex;gap:8px;
  align-items:center;margin-bottom:2px}
.item:hover{background:var(--hover)} .item.on{background:var(--hover)}
.item .t{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.item .x{opacity:0;border:0;background:none;cursor:pointer;color:var(--dim);font-size:15px}
.item:hover .x{opacity:1}

/* --- メイン --- */
.main{flex:1;display:flex;flex-direction:column;min-width:0}
.top{height:52px;border-bottom:1px solid var(--line);display:flex;align-items:center;
  padding:0 16px;gap:10px;flex-shrink:0}
.top .title{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.top .r{margin-left:auto;display:flex;gap:8px;align-items:center}
select{padding:6px 10px;border-radius:8px;border:1px solid var(--line);
  background:var(--card);color:var(--text);font-size:12px}
.ghost{border:1px solid var(--line);background:var(--card);border-radius:8px;
  padding:6px 10px;cursor:pointer;font-size:13px}
.ghost:hover{background:var(--hover)}
.burger{display:none}

.body{flex:1;overflow-y:auto;padding:24px 16px}
.wrap{max-width:760px;margin:0 auto}

/* --- メッセージ --- */
.row{display:flex;gap:12px;margin-bottom:22px}
.row.me{flex-direction:row-reverse}
.av{width:32px;height:32px;border-radius:9px;flex-shrink:0;display:flex;
  align-items:center;justify-content:center;font-size:15px;background:var(--card)}
.av.u{background:var(--me);color:#fff}
.col{min-width:0;max-width:calc(100% - 44px)}
.bub{padding:11px 14px;border-radius:12px;background:var(--ai);line-height:1.75;
  overflow-wrap:break-word}
.row.me .bub{background:var(--me);color:var(--meText)}
.bub p{margin:.4em 0} .bub p:first-child{margin-top:0} .bub p:last-child{margin-bottom:0}
.bub pre{background:#0d1117;border-radius:9px;padding:12px;overflow-x:auto;
  position:relative;margin:.7em 0}
.bub code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.bub :not(pre)>code{background:var(--hover);padding:2px 5px;border-radius:5px}
.bub table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:13px}
.bub th,.bub td{border:1px solid var(--line);padding:6px 9px}
.bub ul,.bub ol{padding-left:1.3em;margin:.4em 0}
.bub a{color:#58a6ff}
.cp{position:absolute;top:7px;right:7px;background:#21262d;border:1px solid #30363d;
  color:#c9d1d9;border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer;opacity:0}
.bub pre:hover .cp{opacity:1}
.acts{display:flex;gap:4px;margin-top:5px;opacity:0;transition:.15s}
.row:hover .acts{opacity:1}
.acts button{border:0;background:none;color:var(--dim);cursor:pointer;font-size:12px;
  padding:3px 7px;border-radius:6px}
.acts button:hover{background:var(--hover);color:var(--text)}
.typing{display:inline-block;width:7px;height:14px;background:var(--dim);
  animation:bl 1s infinite;vertical-align:middle}
@keyframes bl{50%{opacity:0}}

/* --- 入力 --- */
.comp{padding:12px 16px 16px;border-top:1px solid var(--line)}
.cbox{max-width:760px;margin:0 auto;border:1px solid var(--line);border-radius:14px;
  background:var(--card);padding:10px 12px}
.cbox textarea{width:100%;border:0;background:none;color:var(--text);resize:none;
  font-size:15px;font-family:inherit;outline:none;max-height:180px;line-height:1.6}
.crow{display:flex;align-items:center;gap:8px;margin-top:6px}
.crow .hint{font-size:11px;color:var(--dim)}
.snd{margin-left:auto;border:0;background:var(--me);color:#fff;width:32px;height:32px;
  border-radius:9px;cursor:pointer;font-size:15px}
.snd:disabled{background:var(--dim);cursor:default}

/* --- ツール画面 --- */
.tool{max-width:640px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:18px;margin-bottom:14px}
.card h3{margin:0 0 4px;font-size:14px}
.card .d{color:var(--dim);font-size:12.5px;margin:0 0 14px}
.card input{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;
  background:var(--bg);color:var(--text);margin-bottom:10px;font-size:14px}
.btn{width:100%;padding:11px;border:0;border-radius:8px;background:var(--me);color:#fff;
  font-weight:600;cursor:pointer;font-size:14px}
.btn:disabled{background:var(--dim)}
.btn.g{background:var(--card);border:1px solid var(--line);color:var(--text)}
.out{margin-top:12px;padding:12px;background:var(--bg);border:1px solid var(--line);
  border-radius:8px;font-size:13px;white-space:pre-wrap;line-height:1.7;display:none}
.hide{display:none!important}
.mask{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:8}

@media(max-width:860px){
  /* スマホでは左レールをやめ、下部タブバーにする(端に食い込まず押しやすい) */
  body{flex-direction:column}
  .main{order:1;min-height:0;flex:1}
  .rail{order:2;width:100%;height:auto;flex-direction:row;justify-content:space-around;
    align-items:center;padding:6px 0 calc(6px + env(safe-area-inset-bottom));
    border-right:0;border-top:1px solid var(--line);gap:0}
  .rail .logo{display:none}
  .rail .sp{margin-top:0}
  .rail button:last-child{display:none}   /* ログアウトはPCのみ */
  .side{position:fixed;left:0;top:0;bottom:0;width:82vw;max-width:300px;z-index:9;
    transform:translateX(-105%);transition:.22s}
  .side.open{transform:none}
  .mask.open{display:block}
  .burger{display:block}
  .body{padding:16px 12px}
  .wrap{max-width:100%}
  .col{max-width:calc(100% - 44px)}
}
.login{margin:80px auto;max-width:360px}
</style></head><body>

<div id="login" class="login hide">
  <div class="card">
    <h3>秘書にログイン</h3>
    <p class="d">APIキーを入力してください(この端末に保存されます)</p>
    <input type="password" id="k" placeholder="APIキー">
    <button class="btn" onclick="saveKey()">ログイン</button>
  </div>
</div>

<div class="mask" id="mask" onclick="drawer(false)"></div>

<div class="rail hide" id="rail">
  <img src="/icon.svg" class="logo" alt="">
  <button class="on" data-v="chat" onclick="view('chat')" title="チャット">💬</button>
  <button data-v="doc" onclick="view('doc')" title="資料">📄</button>
  <button data-v="todo" onclick="view('todo')" title="タスク">✓</button>
  <button data-v="cal" onclick="view('cal')" title="予定">📅</button>
  <button class="sp" onclick="toggleTheme()" title="テーマ">🌓</button>
  <button onclick="logout()" title="ログアウト">⏻</button>
</div>

<div class="side hide" id="side">
  <div class="hd"><button class="new" onclick="newChat()">＋ 新しい会話</button></div>
  <div class="list" id="convs"></div>
</div>

<div class="main hide" id="main">
  <div class="top">
    <button class="ghost burger" onclick="drawer(true)">☰</button>
    <span class="title" id="title">新しい会話</span>
    <span class="r">
      <select id="model">
        <option value="secretary">通常</option>
        <option value="secretary-think">熟考</option>
      </select>
    </span>
  </div>

  <div class="body" id="body">
    <div class="wrap" id="msgs"></div>

    <div class="tool hide" id="v-doc">
      <div class="card">
        <h3>ファイルを追加</h3><p class="d">画像・PDF・テキストを資料として登録します</p>
        <input type="file" id="files" multiple>
        <button class="btn" id="bup" onclick="upload()">登録する</button>
        <div class="out" id="oup"></div>
      </div>
      <div class="card">
        <h3>Webページを追加</h3><p class="d">URLの本文を取り込み、あとで検索できるようにします</p>
        <input type="text" id="url" placeholder="https://...">
        <button class="btn g" id="burl" onclick="ingestUrl()">取り込む</button>
        <div class="out" id="ourl"></div>
      </div>
    </div>

    <div class="tool hide" id="v-todo">
      <div class="card">
        <h3>タスクを追加</h3>
        <input type="text" id="ttitle" placeholder="やること">
        <input type="text" id="tdue" placeholder="期限(任意) 例 2026-08-10T18:00">
        <button class="btn" onclick="addTodo()">追加</button>
      </div>
      <div class="card">
        <h3>未完了のタスク</h3>
        <div class="out" id="otodo" style="display:block">読み込み中...</div>
        <input type="text" id="tdone" placeholder="完了にするID" style="margin-top:10px">
        <button class="btn g" onclick="doneTodo()">完了にする</button>
      </div>
    </div>

    <div class="tool hide" id="v-cal">
      <div class="card">
        <h3>今週の予定</h3>
        <div class="out" id="ocal" style="display:block">読み込み中...</div>
        <button class="btn g" onclick="loadCal()" style="margin-top:10px">更新</button>
      </div>
    </div>
  </div>

  <div class="comp" id="comp">
    <div class="cbox">
      <textarea id="q" rows="1" placeholder="秘書に聞く..."></textarea>
      <div class="crow">
        <span class="hint">Enterで送信 / Shift+Enterで改行</span>
        <button class="snd" id="send" onclick="send()">↑</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.9/purify.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>
let KEY = localStorage.getItem('key') || new URLSearchParams(location.search).get('key') || '';
let convs = [];
let cur = null, busy = false;
const H = ()=>({'Authorization':'Bearer '+KEY});
const $ = id=>document.getElementById(id);

async function boot(){
  const th = localStorage.getItem('theme') || 'dark';
  document.documentElement.dataset.theme = th;
  if(!KEY){ $('login').classList.remove('hide'); return; }
  localStorage.setItem('key', KEY);
  ['rail','side','main'].forEach(i=>$(i).classList.remove('hide'));
  try{ const r=await fetch('/api/convs',{headers:H()});
       if(r.ok) convs = await r.json(); }catch(e){}
  if(!convs.length) newChat(); else { cur = convs[0].id; render(); }
  drawList();
}
function saveKey(){ const v=$('k').value.trim(); if(v){ localStorage.setItem('key',v); location.href='/app'; } }
function logout(){ if(confirm('ログアウトしますか?')){ localStorage.removeItem('key'); location.href='/app'; } }
function toggleTheme(){
  const t = document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme = t; localStorage.setItem('theme', t);
}
function drawer(o){ $('side').classList.toggle('open',o); $('mask').classList.toggle('open',o); }

function view(v){
  document.querySelectorAll('.rail button[data-v]').forEach(b=>
    b.classList.toggle('on', b.dataset.v===v));
  const chat = v==='chat';
  $('msgs').classList.toggle('hide', !chat);
  $('comp').classList.toggle('hide', !chat);
  $('side').style.display = (chat || window.innerWidth <= 860) ? '' : 'none';
  ['doc','todo','cal'].forEach(x=>$('v-'+x).classList.toggle('hide', x!==v));
  $('title').textContent = chat ? (getConv()?.title||'新しい会話')
    : {doc:'資料',todo:'タスク',cal:'予定'}[v];
  if(v==='todo') loadTodo(); if(v==='cal') loadCal();
  drawer(false);
}

/* ---- 会話管理 ---- */
function getConv(){ return convs.find(c=>c.id===cur); }
function save(){
  const c=getConv(); if(!c) return;
  fetch('/api/convs/'+c.id,{method:'PUT',
    headers:{...H(),'Content-Type':'application/json'},
    body:JSON.stringify({title:c.title, msgs:c.msgs})}).catch(()=>{});
}
function newChat(){
  const c={id:Date.now()+'', title:'新しい会話', msgs:[]};
  convs.unshift(c); cur=c.id; save(); drawList(); render(); view('chat');
}
function pick(id){ cur=id; render(); drawList(); drawer(false); }
function del(id,e){
  e.stopPropagation();
  fetch('/api/convs/'+id,{method:'DELETE',headers:H()}).catch(()=>{});
  convs = convs.filter(c=>c.id!==id);
  if(cur===id){ if(convs.length){ cur=convs[0].id; } else { newChat(); return; } }
  drawList(); render();
}
function drawList(){
  $('convs').innerHTML = convs.map(c=>
    '<div class="item'+(c.id===cur?' on':'')+'" onclick="pick(\''+c.id+'\')">'+
    '<span>💬</span><span class="t">'+esc(c.title)+'</span>'+
    '<button class="x" onclick="del(\''+c.id+'\',event)">×</button></div>').join('');
}
function esc(s){ return (s||'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m])); }

/* ---- 描画 ---- */
function md(t){
  try{ return DOMPurify.sanitize(marked.parse(t)); }catch(e){ return esc(t); }
}
function deco(el){
  el.querySelectorAll('pre code').forEach(c=>{
    try{ hljs.highlightElement(c); }catch(e){}
    const b=document.createElement('button'); b.className='cp'; b.textContent='コピー';
    b.onclick=()=>{ navigator.clipboard.writeText(c.textContent); b.textContent='済'; 
      setTimeout(()=>b.textContent='コピー',1200); };
    c.parentElement.appendChild(b);
  });
}
function render(){
  const c=getConv(); $('title').textContent = c?.title||'新しい会話';
  $('msgs').innerHTML='';
  (c?.msgs||[]).forEach((m,i)=>bubble(m.role,m.content,i));
  $('body').scrollTop = $('body').scrollHeight;
}
function bubble(role, text, idx){
  const me = role==='user';
  const row=document.createElement('div'); row.className='row'+(me?' me':'');
  row.innerHTML = '<div class="av'+(me?' u':'')+'">'+(me?'私':'🤖')+'</div>'+
    '<div class="col"><div class="bub"></div><div class="acts"></div></div>';
  const bub=row.querySelector('.bub');
  if(me){ bub.textContent=text; } else { bub.innerHTML=md(text); deco(bub); }
  const acts=row.querySelector('.acts');
  if(idx!==undefined){
    const cp=document.createElement('button'); cp.textContent='コピー';
    cp.onclick=()=>navigator.clipboard.writeText(text); acts.appendChild(cp);
    if(!me){ const rg=document.createElement('button'); rg.textContent='再生成';
      rg.onclick=()=>regen(idx); acts.appendChild(rg); }
    const dl=document.createElement('button'); dl.textContent='削除';
    dl.onclick=()=>{ const c=getConv(); c.msgs.splice(idx,1); save(); render(); };
    acts.appendChild(dl);
  }
  $('msgs').appendChild(row); return bub;
}

/* ---- 送信 ---- */
async function send(text){
  if(busy) return;
  const q=$('q'); text = text || q.value.trim(); if(!text) return;
  q.value=''; q.style.height='auto';
  const c=getConv();
  c.msgs.push({role:'user',content:text});
  if(c.msgs.length===1){ c.title = text.slice(0,28); drawList(); $('title').textContent=c.title; }
  save(); render();
  await stream(c);
}
async function regen(idx){
  const c=getConv(); c.msgs = c.msgs.slice(0, idx); save(); render(); await stream(c);
}
async function stream(c){
  busy=true; $('send').disabled=true;
  const bub=bubble('assistant','');
  bub.innerHTML='<span class="typing"></span>';
  $('body').scrollTop=$('body').scrollHeight;
  let out='';
  try{
    const r=await fetch('/v1/chat/completions',{method:'POST',
      headers:{...H(),'Content-Type':'application/json'},
      body:JSON.stringify({model:$('model').value, messages:c.msgs, stream:true})});
    if(!r.ok){ bub.textContent='エラー: '+r.status; busy=false; $('send').disabled=false; return; }
    const rd=r.body.getReader(), dec=new TextDecoder(); let buf='';
    while(true){
      const {done,value}=await rd.read(); if(done) break;
      buf+=dec.decode(value,{stream:true});
      const parts=buf.split('\n\n'); buf=parts.pop();
      for(const p of parts){
        const l=p.trim(); if(!l.startsWith('data:')) continue;
        const d=l.slice(5).trim(); if(d==='[DONE]') continue;
        try{ const j=JSON.parse(d); const t=j.choices?.[0]?.delta?.content;
          if(t){ out+=t; bub.textContent=out;
            $('body').scrollTop=$('body').scrollHeight; } }catch(e){}
      }
    }
    bub.innerHTML=md(out); deco(bub);
    c.msgs.push({role:'assistant',content:out}); save(); render();
  }catch(e){ bub.textContent='通信エラー: '+e; }
  busy=false; $('send').disabled=false;
}

$('q')?.addEventListener('input', e=>{
  e.target.style.height='auto';
  e.target.style.height=Math.min(e.target.scrollHeight,180)+'px';
});
$('q')?.addEventListener('keydown', e=>{
  if(e.key==='Enter' && !e.shiftKey && !e.isComposing){ e.preventDefault(); send(); }
});

/* ---- ツール ---- */
async function post(url, fd, outId, btnId, busyMsg){
  const o=$(outId), b=btnId?$(btnId):null;
  o.style.display='block'; o.textContent=busyMsg; if(b) b.disabled=true;
  try{ const r=await fetch(url,{method:'POST',headers:H(),body:fd});
       const j=await r.json(); o.textContent=j.message||JSON.stringify(j); }
  catch(e){ o.textContent='エラー: '+e; }
  if(b) b.disabled=false;
}
function upload(){
  const f=$('files').files; if(!f.length){ alert('ファイルを選んでください'); return; }
  const fd=new FormData(); for(const x of f) fd.append('files',x);
  post('/api/upload',fd,'oup','bup','処理中...(画像は1分ほどかかります)');
}
function ingestUrl(){
  const u=$('url').value.trim(); if(!u) return;
  const fd=new FormData(); fd.append('url',u);
  post('/api/ingest_url',fd,'ourl','burl','取り込み中...');
}
async function loadTodo(){
  try{ const r=await fetch('/api/todo',{headers:H()}); $('otodo').textContent=(await r.json()).message; }catch(e){}
}
function addTodo(){
  const fd=new FormData(); fd.append('action','add');
  fd.append('title',$('ttitle').value); fd.append('due',$('tdue').value);
  fetch('/api/todo',{method:'POST',headers:H(),body:fd}).then(()=>{
    $('ttitle').value=''; $('tdue').value=''; loadTodo(); });
}
function doneTodo(){
  const fd=new FormData(); fd.append('action','done'); fd.append('task_id',$('tdone').value);
  fetch('/api/todo',{method:'POST',headers:H(),body:fd}).then(()=>{ $('tdone').value=''; loadTodo(); });
}
async function loadCal(){
  try{ const r=await fetch('/api/calendar?days=7',{headers:H()}); $('ocal').textContent=(await r.json()).message; }catch(e){}
}
/* ---- Androidの共有メニューから受け取る(ネイティブ側から呼ばれる) ---- */
window.handleShare = function(kind, payload, name){
  if(kind==='text'){
    const m = payload.match(/https?:\/\/[^\s]+/);
    if(m){ view('doc'); $('url').value = m[0];
           $('ourl').style.display='block'; $('ourl').textContent='共有されたURLを取り込みます...';
           ingestUrl(); }
    else { view('chat'); $('q').value = payload;
           $('q').style.height='auto'; $('q').style.height=Math.min($('q').scrollHeight,180)+'px';
           $('q').focus(); }
    return;
  }
  if(kind==='file'){
    view('doc');
    try{
      const bin = atob(payload); const arr = new Uint8Array(bin.length);
      for(let i=0;i<bin.length;i++) arr[i] = bin.charCodeAt(i);
      const fd = new FormData();
      fd.append('files', new Blob([arr]), name || 'shared');
      post('/api/upload', fd, 'oup', 'bup', '共有されたファイルを登録中...');
    }catch(e){
      $('oup').style.display='block'; $('oup').textContent='共有ファイルの処理に失敗: '+e;
    }
  }
};

if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
boot();
</script></body></html>"""
