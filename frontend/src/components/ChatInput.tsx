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
    <form className="composer" onSubmit={submit}>
      <input
        aria-label="消息"
        disabled={disabled}
        onChange={event => setValue(event.target.value)}
        onKeyDown={submitOnEnter}
        placeholder="输入消息，或使用 /skills、/mcp、/doctor"
        value={value}
      />
      <button disabled={disabled || !value.trim()} type="submit">
        发送
      </button>
    </form>
  );
}
