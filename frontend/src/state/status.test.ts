import { describe, expect, it } from 'vitest';
import { statusForEvent } from './status';

describe('statusForEvent', () => {
  it('keeps the app busy until done arrives', () => {
    expect(statusForEvent({ type: 'tool_call_result', tool_name: 'read_file' })).toBe(
      '整理回复...',
    );
    expect(statusForEvent({ type: 'token', content: 'hello' })).toBe('回复中...');
    expect(statusForEvent({ type: 'done' })).toBe('就绪');
  });
});
