import { describe, expect, it } from 'vitest';
import { parseSlashCommand } from './slashCommands';

describe('parseSlashCommand', () => {
  it('parses supported slash commands', () => {
    expect(parseSlashCommand('/skills')).toEqual({ name: 'skills' });
    expect(parseSlashCommand('/resume abc123')).toEqual({ arg: 'abc123', name: 'resume' });
  });

  it('returns null for normal chat input', () => {
    expect(parseSlashCommand('请总结 README')).toBeNull();
  });

  it('marks unsupported commands for a CLI-only message', () => {
    expect(parseSlashCommand('/doctor')).toEqual({ arg: undefined, name: 'unsupported' });
  });
});
