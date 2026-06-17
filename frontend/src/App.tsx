export function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Workspace">
        <div>
          <p className="eyebrow">Easy Claw</p>
          <h1>Local Agent</h1>
        </div>
        <div className="status-pill" aria-label="Connection status">
          Ready
        </div>
      </aside>
      <section className="chat-pane" aria-label="Chat workspace">
        <div className="message">
          <span className="message-label">Easy Claw</span>
          <p>React web UI shell is ready.</p>
        </div>
        <form className="composer">
          <input aria-label="Message" disabled placeholder="Chat migration continues in the next task" />
          <button disabled type="button">
            Send
          </button>
        </form>
      </section>
    </main>
  );
}
