import { FormEvent, KeyboardEvent, useState } from 'react';

export function ChatInput({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (content: string) => void;
}) {
  const [value, setValue] = useState('');

  function submitValue() {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    onSubmit(trimmed);
    setValue('');
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitValue();
  }

  function submitOnEnter(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      submitValue();
    }
  }

  return (
    <form className="composer command-dock" onSubmit={submit}>
      <div className="command-dock-meta">
        <span>自然语言任务或 slash command</span>
        <span>/doctor</span>
        <span>/mcp</span>
        <span>/skills</span>
      </div>
      <div className="command-dock-row">
        <input
          aria-label="消息"
          disabled={disabled}
          onChange={event => setValue(event.target.value)}
          onKeyDown={submitOnEnter}
          placeholder="描述任务，或输入 /doctor、/mcp、/skills"
          value={value}
        />
        <button disabled={disabled || !value.trim()} type="submit">
          执行
        </button>
      </div>
    </form>
  );
}
