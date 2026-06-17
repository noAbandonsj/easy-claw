import { FormEvent, useState } from 'react';

export function ChatInput({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (content: string) => void;
}) {
  const [value, setValue] = useState('');

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    onSubmit(trimmed);
    setValue('');
  }

  return (
    <form className="composer" onSubmit={submit}>
      <input
        aria-label="消息"
        disabled={disabled}
        onChange={event => setValue(event.target.value)}
        placeholder="输入消息，或使用 /skills、/mcp、/browser"
        value={value}
      />
      <button disabled={disabled || !value.trim()} type="submit">
        发送
      </button>
    </form>
  );
}
