import { useEffect, useState } from 'react'
import {
  ArrowRight, Camera, Check, Clock3, Copy, Crown, ImagePlus,
  LoaderCircle, LogIn, PencilLine, Play, Plus, RotateCcw,
  Shuffle, Sparkles, Trophy, Users, X,
} from 'lucide-react'
import './App.css'
import './PromptSetup.css'

type Player = { id: string; name: string; total_points: number; wins: number }
type Submission = {
  id: string; player_id: string; player_name: string; image_url: string
  status: 'queued' | 'scored' | 'failed'; ai_score: number | null; points: number; rank: number | null
}
type Round = {
  number: number; prompt: string; status: 'pending' | 'active' | 'scored'
  deadline: string | null; submissions: Submission[]
}
type Game = {
  code: string; title: string; status: 'lobby' | 'playing' | 'finished'
  current_round: number; round_count: number; round_seconds: number; max_players: number
  players: Player[]; round: Round | null
}
type Session = {
  code: string
  role: 'host' | 'player'
  token: string
  playerId?: string
  playerToken?: string
}
type PromptPack = 'daily' | 'discovery' | 'chaos'

const SESSION_KEY = 'photo-ogiri-session'
const PROMPT_PACKS: { id: PromptPack; name: string; description: string }[] = [
  { id: 'daily', name: '日常ボケ', description: '身の回りで見つけやすい' },
  { id: 'discovery', name: '発見勝負', description: '観察力と構図で勝負' },
  { id: 'chaos', name: 'カオス', description: '予想外の一枚を狙う' },
]

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `リクエストに失敗しました (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function loadSession(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_KEY)
    return value ? JSON.parse(value) as Session : null
  } catch { return null }
}

function Timer({ deadline }: { deadline: string | null }) {
  const [remaining, setRemaining] = useState(0)
  useEffect(() => {
    const update = () => setRemaining(Math.max(0, Math.ceil(((deadline ? new Date(deadline).getTime() : 0) - Date.now()) / 1000)))
    update()
    const timer = window.setInterval(update, 250)
    return () => window.clearInterval(timer)
  }, [deadline])
  return <div className={`timer ${remaining <= 10 ? 'timer-urgent' : ''}`}><Clock3 size={20} /><span>{Math.floor(remaining / 60)}:{(remaining % 60).toString().padStart(2, '0')}</span></div>
}

function Leaderboard({ players }: { players: Player[] }) {
  return <ol className="leaderboard">{players.map((player, index) => <li key={player.id}>
    <span className="rank-number">{index + 1}</span><span className="player-avatar">{player.name.slice(0, 1).toUpperCase()}</span>
    <span className="player-name">{player.name}</span>{player.wins > 0 && <span className="win-count"><Crown size={14} /> {player.wins}</span>}
    <strong>{player.total_points.toLocaleString()} pt</strong>
  </li>)}</ol>
}

function App() {
  const [session, setSession] = useState<Session | null>(() => loadSession())
  const [game, setGame] = useState<Game | null>(null)
  const [mode, setMode] = useState<'join' | 'create'>(() => new URLSearchParams(location.search).has('code') ? 'join' : 'create')
  const [joinCode, setJoinCode] = useState(() => new URLSearchParams(location.search).get('code')?.toUpperCase() ?? '')
  const [playerName, setPlayerName] = useState('')
  const [title, setTitle] = useState('AI審査員フォト大喜利')
  const [promptMode, setPromptMode] = useState<'preset' | 'custom'>('preset')
  const [promptPack, setPromptPack] = useState<PromptPack>('daily')
  const [prompts, setPrompts] = useState('')
  const [roundCount, setRoundCount] = useState(3)
  const [roundSeconds, setRoundSeconds] = useState(90)
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!session) return
    let active = true
    const refresh = async () => {
      try {
        const state = await api<Game>(`/api/games/${session.code}`)
        if (active) { setGame(state); setError('') }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : 'ゲームを読み込めませんでした')
      }
    }
    void refresh()
    const timer = window.setInterval(refresh, 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [session])

  const remember = (next: Session) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(next))
    history.replaceState(null, '', `?code=${next.code}`)
    setSession(next)
  }

  const createGame = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await api<{ code: string; host_token: string }>('/api/games', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          prompts: promptMode === 'custom' ? prompts.split('\n').map((item) => item.trim()).filter(Boolean) : [],
          prompt_pack: promptMode === 'preset' ? promptPack : null,
          round_count: roundCount,
          round_seconds: roundSeconds,
        }),
      })
      remember({ code: result.code, role: 'host', token: result.host_token })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'ゲームを作成できませんでした') }
    finally { setBusy(false) }
  }

  const joinGame = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const code = joinCode.trim().toUpperCase()
      const result = await api<{ player_id: string; player_token: string }>(`/api/games/${code}/players`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: playerName }),
      })
      remember({ code, role: 'player', token: result.player_token, playerId: result.player_id })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'ゲームに参加できませんでした') }
    finally { setBusy(false) }
  }

  const joinAsHost = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!session || session.role !== 'host') return
    setBusy(true); setError('')
    try {
      const result = await api<{ player_id: string; player_token: string }>(`/api/games/${session.code}/players`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: playerName }),
      })
      remember({ ...session, playerId: result.player_id, playerToken: result.player_token })
    } catch (reason) { setError(reason instanceof Error ? reason.message : '参加できませんでした') }
    finally { setBusy(false) }
  }

  const advance = async () => {
    if (!session) return
    setBusy(true); setError('')
    try {
      await api<void>(`/api/games/${session.code}/advance`, { method: 'POST', headers: { Authorization: `Bearer ${session.token}` } })
      setGame(await api<Game>(`/api/games/${session.code}`))
    } catch (reason) { setError(reason instanceof Error ? reason.message : '進行できませんでした') }
    finally { setBusy(false) }
  }

  const submitImage = async () => {
    if (!session || !selectedImage) return
    const playerToken = session.role === 'host' ? session.playerToken : session.token
    if (!playerToken) return
    setBusy(true); setError('')
    const body = new FormData(); body.append('image', selectedImage)
    try {
      await api(`/api/games/${session.code}/submissions`, { method: 'POST', headers: { Authorization: `Bearer ${playerToken}` }, body })
      setSelectedImage(null); setGame(await api<Game>(`/api/games/${session.code}`))
    } catch (reason) { setError(reason instanceof Error ? reason.message : '画像を提出できませんでした') }
    finally { setBusy(false) }
  }

  const leave = () => {
    localStorage.removeItem(SESSION_KEY); history.replaceState(null, '', location.pathname)
    setSession(null); setGame(null); setSelectedImage(null)
  }
  const copyInvite = async () => {
    if (!game) return
    await navigator.clipboard.writeText(`${location.origin}?code=${game.code}`)
    setCopied(true); window.setTimeout(() => setCopied(false), 1600)
  }

  if (!session) return <main className="entry-shell">
    <header className="brand-bar"><div className="brand-mark"><Camera size={24} /></div><span>AI審査員フォト大喜利</span></header>
    <section className="entry-grid">
      <div className="entry-intro">
        <p className="eyebrow"><Sparkles size={17} /> 写真でボケて、AIに裁かれる。</p>
        <h1>その一枚、<br />AIにはどう見える？</h1>
      </div>
      <div className="entry-console">
        <div className="mode-tabs"><button className={mode === 'create' ? 'active' : ''} onClick={() => setMode('create')}><Plus size={18} /> ゲームを作る</button><button className={mode === 'join' ? 'active' : ''} onClick={() => setMode('join')}><LogIn size={18} /> コードで参加</button></div>
        {mode === 'create' ? <form onSubmit={createGame} className="entry-form">
          <label>ゲーム名<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={80} required /></label>
          <fieldset className="prompt-setup">
            <legend>お題の用意</legend>
            <div className="prompt-mode-control">
              <button type="button" className={promptMode === 'preset' ? 'active' : ''} onClick={() => setPromptMode('preset')}><Shuffle size={16} /> おまかせ</button>
              <button type="button" className={promptMode === 'custom' ? 'active' : ''} onClick={() => setPromptMode('custom')}><PencilLine size={16} /> 自分で作る</button>
            </div>
            {promptMode === 'preset' ? <>
              <div className="pack-options">{PROMPT_PACKS.map((pack) => <label className={promptPack === pack.id ? 'selected' : ''} key={pack.id}>
                <input type="radio" name="prompt-pack" value={pack.id} checked={promptPack === pack.id} onChange={() => setPromptPack(pack.id)} />
                <span><b>{pack.name}</b><small>{pack.description}</small></span><Check size={16} />
              </label>)}</div>
            </> : <label className="custom-prompts">カスタムお題 <small>1行に1つ、最大20個</small><textarea value={prompts} onChange={(event) => setPrompts(event.target.value)} rows={5} placeholder={'例：いちばん偉そうなもの\n映画のラストシーンっぽい場所'} required /></label>}
          </fieldset>
          <div className={`form-pair game-settings ${promptMode === 'custom' ? 'single' : ''}`}>
            {promptMode === 'preset' && <label>ラウンド数<select value={roundCount} onChange={(event) => setRoundCount(Number(event.target.value))}><option value={3}>3ラウンド</option><option value={5}>5ラウンド</option><option value={8}>8ラウンド</option><option value={10}>10ラウンド</option></select></label>}
            <label>制限時間<select value={roundSeconds} onChange={(event) => setRoundSeconds(Number(event.target.value))}><option value={60}>60秒</option><option value={90}>90秒</option><option value={120}>120秒</option><option value={180}>180秒</option></select></label>
          </div>
          <button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <Play />} ルームを作成</button>
        </form> : <form onSubmit={joinGame} className="entry-form join-form">
          <label>参加コード<input className="code-input" value={joinCode} onChange={(event) => setJoinCode(event.target.value.toUpperCase())} maxLength={6} placeholder="ABC123" required /></label>
          <label>表示名<input value={playerName} onChange={(event) => setPlayerName(event.target.value)} maxLength={30} placeholder="ニックネーム" required /></label>
          <button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <ArrowRight />} 参加する</button>
        </form>}
        {error && <p className="error-message"><X size={16} />{error}</p>}
      </div>
    </section>
  </main>

  if (!game) return <main className="loading-screen"><LoaderCircle className="spin" size={42} /><p>ゲームを読み込んでいます</p>{error && <button onClick={leave}>トップへ戻る</button>}</main>

  const isHost = session.role === 'host'
  const canSubmit = session.role === 'player' || Boolean(session.playerToken)
  const ownSubmission = game.round?.submissions.find((item) => item.player_id === session.playerId)
  const isRoundResult = game.round?.status === 'scored' || game.status === 'finished'
  return <main className="game-shell">
    <header className="game-header"><div className="compact-brand"><Camera size={20} /><span>{game.title}</span></div><div className="round-progress">{game.status === 'lobby' ? 'LOBBY' : `ROUND ${game.current_round} / ${game.round_count}`}</div><button className="icon-button" onClick={leave} title="退出"><X size={20} /></button></header>
    {error && <div className="error-banner"><X size={18} />{error}<button onClick={() => setError('')}><X size={15} /></button></div>}

    {game.status === 'lobby' && <section className="lobby-layout">
      <div className="lobby-code"><p>参加コード</p><strong>{game.code}</strong><button onClick={copyInvite}>{copied ? <Check size={18} /> : <Copy size={18} />}{copied ? 'コピーしました' : '招待リンクをコピー'}</button><span>参加者のスマホでコードを入力</span></div>
      <div className="lobby-roster"><div className="section-heading"><div><span>PLAYERS</span><h2>参加者</h2></div><strong><Users size={20} /> {game.players.length} / {game.max_players}</strong></div>
        <div className="player-grid">{game.players.map((player) => <div className="player-chip" key={player.id}><span>{player.name.slice(0, 1)}</span>{player.name}</div>)}{game.players.length === 0 && <p className="empty-state">参加者を待っています...</p>}</div>
        {isHost && !session.playerId && <form className="host-join" onSubmit={joinAsHost}><input value={playerName} onChange={(event) => setPlayerName(event.target.value)} maxLength={30} placeholder="あなたの表示名" required /><button type="submit" disabled={busy}><Plus size={18} /> 自分も参加</button></form>}
        {isHost ? <button className="primary-button start-button" onClick={advance} disabled={busy || game.players.length === 0}>{busy ? <LoaderCircle className="spin" /> : <Play />} 最初のお題を出す</button> : <p className="waiting-note"><LoaderCircle className="spin" size={18} /> ホストが開始するまでお待ちください</p>}
      </div>
    </section>}

    {game.status !== 'lobby' && game.round && !isRoundResult && <section className="play-layout">
      <div className="challenge-band"><div><span className="eyebrow">今回のお題</span><h1>{game.round.prompt}</h1></div><Timer deadline={game.round.deadline} /></div>
      {isHost && <div className="host-dashboard">
        <div className="submission-meter"><span style={{ width: `${game.players.length ? game.round.submissions.length / game.players.length * 100 : 0}%` }} /></div>
        <div className="host-count"><strong>{game.round.submissions.length}</strong><span>/ {game.players.length} 人が提出</span></div>
        <div className="submission-status-grid">{game.players.map((player) => { const submitted = game.round?.submissions.find((item) => item.player_id === player.id); return <div key={player.id} className={submitted ? 'submitted' : ''}>{submitted ? <Check size={17} /> : <Clock3 size={17} />}<span>{player.name}</span><small>{submitted?.status === 'scored' ? '採点済み' : submitted ? '採点中' : '未提出'}</small></div> })}</div>
        <button className="primary-button judge-button" onClick={advance} disabled={busy || game.round.submissions.some((item) => item.status === 'queued')}><Sparkles /> 締め切ってAI審査へ</button>
      </div>}
      {canSubmit && <div className={`upload-stage ${isHost ? 'host-upload-stage' : ''}`}>
        {ownSubmission ? <div className="submitted-view"><div className="submitted-image"><img src={ownSubmission.image_url} alt="提出した作品" /><span><Check size={18} />提出済み</span></div><h2>{ownSubmission.status === 'scored' ? 'AI審査員の採点が完了しました' : 'AI審査員が作品を見ています'}</h2><p>締切までは別の写真へ差し替えられます。</p></div> : <div className="upload-copy"><span className="step-number">01</span><h2>お題に合う一枚を選ぶ</h2><p>その場で撮影するか、手持ちの画像から挑戦してください。</p></div>}
        <label className="file-drop">{selectedImage ? <><img src={URL.createObjectURL(selectedImage)} alt="選択した画像" /><span><RotateCcw size={18} />画像を選び直す</span></> : <><ImagePlus size={38} /><strong>写真を選択</strong><span>JPEG / PNG / WebP、最大8MB</span></>}<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => setSelectedImage(event.target.files?.[0] ?? null)} /></label>
        <button className="primary-button submit-button" onClick={submitImage} disabled={!selectedImage || busy}>{busy ? <LoaderCircle className="spin" /> : <Camera />} この写真で勝負する</button>
      </div>}
    </section>}

    {isRoundResult && game.round && <section className="results-layout">
      <div className="results-heading"><span className="eyebrow"><Sparkles size={17} /> AI審査結果</span><h1>{game.round.prompt}</h1><p>AIの独断と偏見による順位です。</p></div>
      <div className="result-gallery">{game.round.submissions.slice(0, 12).map((submission) => <article key={submission.id} className={submission.rank === 1 ? 'winner' : ''}><div className="result-image"><img src={submission.image_url} alt={`${submission.player_name}の作品`} loading="lazy" />{submission.rank === 1 && <span className="winner-badge"><Crown size={18} />AI審査員賞</span>}</div><div className="result-meta"><span className="result-rank">{submission.rank}<small>位</small></span><div><strong>{submission.player_name}</strong><span>類似度 {submission.ai_score?.toFixed(4)}</span></div><b>+{submission.points}</b></div></article>)}</div>
      <aside className="scoreboard"><div className="section-heading"><div><span>TOTAL SCORE</span><h2>総合ランキング</h2></div><Trophy size={24} /></div><Leaderboard players={game.players} /></aside>
      {isHost && game.status !== 'finished' && <button className="primary-button next-round-button" onClick={advance} disabled={busy}>次のお題へ <ArrowRight /></button>}
      {game.status === 'finished' && <div className="game-finished"><Trophy size={38} /><span>FINAL RESULT</span><h2>{game.players[0]?.name ?? '参加者なし'} の優勝！</h2>{isHost && <button onClick={leave}>新しいゲームを作る</button>}</div>}
    </section>}
  </main>
}

export default App