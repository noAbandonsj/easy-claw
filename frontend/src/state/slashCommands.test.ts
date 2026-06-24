import { describe, expect, it } from 'vitest';
import { parseSlashCommand } from './slashCommands';

describe('parseSlashCommand', () => {
  it('parses supported slash commands', () => {
    expect(parseSlashCommand('/skills')).toEqual({ name: 'skills' });
    expect(parseSlashCommand('/resume abc123')).toEqual({ arg: 'abc123', name: 'resume' });
    expect(parseSlashCommand('/workspace D:\\Pathon\\Programs')).toEqual({
      arg: 'D:\\Pathon\\Programs',
      name: 'workspace',
    });
    expect(parseSlashCommand('/model deepseek-chat')).toEqual({
      arg: 'deepseek-chat',
      name: 'model',
    });
    expect(parseSlashCommand('/doctor')).toEqual({ name: 'doctor' });
    expect(parseSlashCommand('/save D:\\tmp\\chat.md')).toEqual({
      arg: 'D:\\tmp\\chat.md',
      name: 'save',
    });
    expect(parseSlashCommand('/delete-session abc123')).toEqual({
      arg: 'abc123',
      name: 'delete-session',
    });
  });

  it('returns null for normal chat input', () => {
    expect(parseSlashCommand('请总结 README')).toBeNull();
  });

  it('marks unknown commands as unsupported', () => {
    expect(parseSlashCommand('/unknown')).toEqual({ arg: undefined, name: 'unsupported' });
  });
});
