export function CodeBlock({ language, value }: { language?: string; value: string }) {
  function copy() {
    void navigator.clipboard?.writeText(value);
  }

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{language || 'text'}</span>
        <button onClick={copy} type="button">
          复制代码
        </button>
      </div>
      <pre>
        <code>{value}</code>
      </pre>
    </div>
  );
}
