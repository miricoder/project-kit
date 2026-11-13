import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, Client, type LogEntry } from "./client";
import * as idb from "./idb";
import { afterOpen, APP_VERSION, offerReload, shown } from "./version";
import { activeTrip, dueLabel, dueSoon, euros, headline, localDay, month, tooLong, tripSpan } from "./derive";

type Screen = "dashboard" | "capture" | "devices";

function useClient(client: Client) {
  const [, force] = useState(0);
  useEffect(() => client.subscribe(() => force((n) => n + 1)), [client]);
  return client;
}

export function App({ client }: { client: Client }) {
  const c = useClient(client);
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [today, setToday] = useState(localDay());
  const [announce, setAnnounce] = useState("");

  useEffect(() => {
    const refresh = () => {
      setToday(localDay());
      if (document.visibilityState === "visible") { void c.sync(); void c.flush(); void c.checkHealth(); }
    };
    const online = () => { c.online = true; void c.flush(); void c.sync(); };
    const offline = () => { c.online = false; };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") { void c.sync(); void c.checkHealth(); }
    }, 30000);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
      window.clearInterval(timer);
    };
  }, [c]);

  if (c.signedIn === false) return <SignIn client={c} />;
  if (c.signedIn === null && !c.items.length) return <main className="screen center"><p className="muted">Loading…</p></main>;

  const send = async (text: string) => {
    setScreen("capture");
    await c.capture(text);
    setAnnounce(c.online ? "Filing…" : "Saved. Will file when you're back online.");
  };

  return (
    <>
      {c.health?.model === "demo" && (
        <div className="demo" role="note">Demo filer: understands simple sentences only. Add an Anthropic API key for the real one.</div>
      )}
      {offerReload(c.health?.app_version, APP_VERSION) && <UpdateOffer />}
      <WhatsNew />
      {screen === "dashboard" && <Dashboard client={c} today={today} onSend={send} onDevices={() => setScreen("devices")} />}
      {screen === "capture" && <Capture client={c} onBack={() => setScreen("dashboard")} onSend={send} />}
      {screen === "devices" && <Devices client={c} onBack={() => setScreen("dashboard")} />}
      <div className="sr-only" aria-live="polite">{announce}</div>
    </>
  );
}

// ---------------------------------------------------------------- versions

type Entry = { version: string; date: string | null; notes: string[] };

/** After an update: "Updated to 0.2.0" and what changed since the version this device last ran. */
function WhatsNew() {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  useEffect(() => {
    let live = true;
    void (async () => {
      const seen = await idb.get<string>("meta", "seen_version");
      const notice = afterOpen(seen, APP_VERSION);
      if (notice === "first-run") await idb.put("meta", APP_VERSION, "seen_version");
      if (notice !== "updated") return;
      let found: Entry[] = [];
      try {
        const res = await fetch(`/v1/whats-new?since=${encodeURIComponent(seen ?? "")}`);
        if (res.ok) found = (await res.json()).entries;
      } catch { /* offline: say it was updated, without the list */ }
      if (live) setEntries(found);
    })();
    return () => { live = false; };
  }, []);
  if (!entries) return null;
  const dismiss = async () => { await idb.put("meta", APP_VERSION, "seen_version"); setEntries(null); };
  return (
    <section className="notice whats-new" aria-label="What's new">
      <p className="heading">Updated to {shown(APP_VERSION)}</p>
      {entries.map((e) => (
        <div key={e.version}>
          {entries.length > 1 && <p className="meta">{shown(e.version)}</p>}
          <ul>{e.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      ))}
      <button className="btn secondary" type="button" onClick={dismiss}>Got it</button>
    </section>
  );
}

/** While open: the server now runs a different version than this page. */
function UpdateOffer() {
  return (
    <div className="notice update-offer" role="status">
      <span>A new version of Dumpit is ready.</span>
      <button className="btn" type="button" onClick={() => window.location.reload()}>Update now</button>
    </div>
  );
}

// ---------------------------------------------------------------- sign-in

function SignIn({ client }: { client: Client }) {
  const expired = new URLSearchParams(location.search).get("signin") === "expired";
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api("/v1/auth/link", { method: "POST", body: JSON.stringify({ email }) });
      if (res.status === 202) setSent(true); else setError("That didn't work. Check the address and try again.");
    } catch {
      setError("You're offline. Connect and try again.");
    }
  };
  const devSignIn = async () => {
    const res = await fetch("/v1/dev/last-link");
    const { link } = await res.json();
    if (link) location.href = new URL(link).pathname + new URL(link).search;
    else setError("No link yet. Send one first.");
  };

  return (
    <main className="screen signin">
      <h1 className="title-lg">Dumpit</h1>
      <p className="muted">Tell it your life admin in passing. It files tasks, spending and trips.</p>
      {expired && !sent && (
        <p className="notice" role="alert">That sign-in link has expired or was already used. Send yourself a new one.</p>
      )}
      {sent ? (
        <div className="card" role="status">
          <h2 className="heading">Check your email</h2>
          <p>If <strong>{email}</strong> can use Dumpit, a sign-in link is on its way. It works once, for 15 minutes.</p>
          <button className="btn secondary" type="button" onClick={() => setSent(false)}>Use a different email</button>
          {client.health?.dev && <button className="btn" type="button" onClick={devSignIn}>Dev: open the sign-in link</button>}
        </div>
      ) : (
        <form className="card form" onSubmit={submit}>
          <label htmlFor="email" className="heading">Email</label>
          <input id="email" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          <button className="btn" type="submit">{expired ? "Send a new link" : "Email me a sign-in link"}</button>
          {error && <p className="error" role="alert">{error}</p>}
        </form>
      )}
    </main>
  );
}

// ---------------------------------------------------------------- dashboard

function Dashboard({ client, today, onSend, onDevices }: { client: Client; today: string;
  onSend: (t: string) => void; onDevices: () => void }) {
  const items = client.items;
  const m = month(items, today, client.me?.monthly_budget_cents ?? null);
  const due = dueSoon(items, today);
  const trip = activeTrip(items, today);
  const empty = !items.some((i) => i.kind !== "note") && !client.me?.monthly_budget_cents;

  return (
    <main className="screen with-bar">
      <header className="dash-head">
        <h1 className="title-lg">{headline(today)}</h1>
        <button className="icon-btn" type="button" aria-label="Devices and sign-out" onClick={onDevices}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>
        </button>
      </header>
      {!client.online && <p className="notice">You're offline. Captures are saved and file when you're back.</p>}

      {empty ? (
        <section className="empty">
          <p>Tell it anything — a payment, a plan, a reminder. It'll sort it out.</p>
          <div className="examples">
            {["paid 42 for groceries", "book the car service", "my budget is 1400 a month"].map((ex) => (
              <button key={ex} type="button" className="chip" onClick={() => onSend(ex)}>“{ex}”</button>
            ))}
          </div>
        </section>
      ) : (
        <>
          <section className="card" aria-labelledby="due-h">
            <h2 id="due-h" className="heading">Due soon</h2>
            {due.shown.length === 0 ? <p className="muted">Nothing due this week.</p> : (
              <ul className="tasks">
                {due.shown.map((t) => (
                  <li key={t.id}>
                    <label className={`task ${t.state}`}>
                      <input type="checkbox" checked={t.done} onChange={(e) => client.setDone(t.id, e.target.checked)} />
                      <span><span className="item">{t.title}</span><span className="meta">{dueLabel(t, today)}</span></span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {due.more > 0 && <p className="meta">+{due.more} more</p>}
          </section>

          <section className="card" aria-labelledby="month-h" data-testid="month">
            <h2 id="month-h" className="heading">{m.name} {m.budget != null ? "budget" : "spending"}</h2>
            {m.budget != null ? (
              <>
                <p className="figure-lg">{m.over ? `${euros(-m.left!)} over` : `${euros(m.left!)} left`}</p>
                <div className={`bar ${m.over ? "over" : ""}`} aria-hidden="true"><span style={{ width: `${Math.round(m.ratio * 100)}%` }} /></div>
                <p className="meta">{euros(m.spent)} spent of {euros(m.budget)}</p>
              </>
            ) : (
              <>
                <p className="figure-lg">{euros(m.spent)} spent</p>
                <p className="meta">Set a monthly budget by saying it: “my budget is 1400 a month”</p>
              </>
            )}
            {m.top.length > 0 && (
              <dl className="cats">
                {m.top.map((t) => <div key={t.category}><dt>{t.category}</dt><dd>{euros(t.spent)}</dd></div>)}
              </dl>
            )}
          </section>

          {trip && (
            <section className="card" aria-labelledby="trip-h">
              <p className="tag tag-trip">Trip</p>
              <h2 id="trip-h" className="heading">{trip.name} · {tripSpan(trip)}</h2>
              {trip.budget_cents ? (
                <>
                  <p className="figure">{euros(trip.budget_cents - trip.spent)} left</p>
                  <div className="bar" aria-hidden="true"><span style={{ width: `${Math.min(100, Math.round(trip.spent / trip.budget_cents * 100))}%` }} /></div>
                  <p className="meta">{euros(trip.spent)} spent of {euros(trip.budget_cents)}</p>
                </>
              ) : <p className="meta">No budget set · {euros(trip.spent)} spent</p>}
            </section>
          )}
        </>
      )}
      <CaptureBar onSend={onSend} />
    </main>
  );
}

// ---------------------------------------------------------------- capture

function Capture({ client, onBack, onSend }: { client: Client; onBack: () => void; onSend: (t: string) => void }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [client.log.length]);
  return (
    <main className="screen with-bar">
      <header className="screen-head">
        <button className="back" type="button" aria-label="Back to dashboard" onClick={onBack}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
        </button>
        <h1 className="title">Capture</h1>
      </header>
      <ol className="log" role="log" aria-live="polite">
        {client.log.map((e) => <LogItem key={e.capture_id} entry={e} onRetry={() => client.retry(e.capture_id)} />)}
      </ol>
      <div ref={end} />
      <CaptureBar onSend={onSend} autoFocus />
    </main>
  );
}

function LogItem({ entry, onRetry }: { entry: LogEntry; onRetry: () => void }) {
  return (
    <li className="entry">
      <p className="bubble"><span className="sr-only">You said: </span>{entry.text}</p>
      {entry.status === "sending" && <p className="pending" role="status"><span className="spinner" aria-hidden="true" />{entry.reason || "Filing…"}</p>}
      {entry.status === "waiting" && (
        <p className="pending waiting"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
          Waiting to file · {entry.reason || "you were offline"}</p>
      )}
      {entry.status === "failed" && (
        <div className="failed" role="alert">
          <p>Couldn't file this. Your words are saved; nothing was lost.</p>
          <button className="btn secondary" type="button" onClick={onRetry}>Retry</button>
        </div>
      )}
      {(entry.status === "filed" || entry.status === "note") && (
        <ul className="filed">
          {entry.lines?.map((line, i) => (
            <li key={i} className="filed-row">
              <span className={`tag tag-${line.tag.toLowerCase()}`}>{line.tag}</span>
              <span className="row-text">{line.text}</span>
              {line.undo && (
                <button className="undo" type="button" aria-disabled="true" title="Undo arrives with slice 8"
                  aria-label={`Undo ${line.text}`} onClick={(e) => e.preventDefault()}>Undo</button>
              )}
              {line.suggestions && line.suggestions.length > 0 && (
                <span className="suggestions">{line.suggestions.slice(0, 3).map((s) => <span key={s} className="chip">{s}</span>)}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function CaptureBar({ onSend, autoFocus = false }: { onSend: (t: string) => void; autoFocus?: boolean }) {
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const field = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (autoFocus) field.current?.focus(); }, [autoFocus]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const problem = tooLong(text);
    if (problem) { setMessage(problem); return; }     // nothing is sent; the text stays
    setMessage("");
    setText("");
    onSend(trimmed);
    field.current?.focus();
  };
  const key = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };
  return (
    <div className="capture-bar-wrap">
      {message && <p className="error" role="alert" id="capture-msg">{message}</p>}
      <form className="capture-bar" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <label htmlFor="capture" className="sr-only">Tell me anything</label>
        <textarea id="capture" ref={field} rows={1} value={text} aria-describedby={message ? "capture-msg" : undefined}
          placeholder="Tell me anything… “paid 42 for groceries”" onKeyDown={key}
          onChange={(e) => { setText(e.target.value); if (message && !tooLong(e.target.value)) setMessage(""); }} />
        {text.trim() ? (
          <button className="send" type="submit" aria-label="Send">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        ) : (
          <button className="mic" type="button" aria-label="Dictate" onClick={() => field.current?.focus()}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </button>
        )}
      </form>
    </div>
  );
}

// ---------------------------------------------------------------- devices

type Session = { id: number; device: string; last_seen_at: string; current: boolean };

function Devices({ client, onBack }: { client: Client; onBack: () => void }) {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      const res = await api("/v1/sessions");
      if (res.status === 401) { client.signedOut(); return; }
      setSessions((await res.json()).sessions);
    } catch { setError("You're offline. Devices show when you're back online."); }
  };
  useEffect(() => { void load(); }, []);

  const signOut = async (s: Session) => {
    if (s.current) {
      await api("/v1/auth/sign-out", { method: "POST" });
      await client.forget();
      client.signedOut();
      return;
    }
    const res = await api(`/v1/sessions/${s.id}`, { method: "DELETE" });
    if (res.status === 204) await load(); else setError("Couldn't sign that device out. Try again.");
  };

  return (
    <main className="screen">
      <header className="screen-head">
        <button className="back" type="button" aria-label="Back to dashboard" onClick={onBack}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
        </button>
        <h1 className="title">Devices</h1>
      </header>
      {client.me && <p className="muted">Signed in as {client.me.email}</p>}
      <p className="meta">Dumpit {shown(APP_VERSION)}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="card devices">
        {sessions?.map((s) => (
          <li key={s.id}>
            <span><span className="item">{s.device}{s.current ? " (this device)" : ""}</span>
              <span className="meta">Last used {new Date(s.last_seen_at).toLocaleString()}</span></span>
            <button className="btn secondary" type="button" onClick={() => signOut(s)}
              aria-label={s.current ? "Sign out this device" : `Sign out ${s.device}`}>Sign out</button>
          </li>
        ))}
      </ul>
    </main>
  );
}
