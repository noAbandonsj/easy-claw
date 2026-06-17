export type SlashCommand =
  | { name: 'browser' }
  | { name: 'clear' }
  | { name: 'exit' }
  | { name: 'help' }
  | { name: 'mcp' }
  | { name: 'resume'; arg?: string }
  | { name: 'save' }
  | { name: 'sessions' }
  | { name: 'skills' }
  | { name: 'status' }
  | { name: 'unsupported'; arg?: string };

const SUPPORTED_COMMANDS = new Set([
  'browser',
  'clear',
  'exit',
  'help',
  'mcp',
  'resume',
  'save',
  'sessions',
  'skills',
  'status',
]);

export function parseSlashCommand(input: string): SlashCommand | null {
  const trimmed = input.trim();
  if (!trimmed.startsWith('/')) {
    return null;
  }

  const [rawName, ...rest] = trimmed.slice(1).split(/\s+/);
  const name = rawName.toLowerCase();
  const arg = rest.join(' ') || undefined;

  if (name === 'resume') {
    return { arg, name };
  }
  if (SUPPORTED_COMMANDS.has(name)) {
    return { name } as SlashCommand;
  }
  return { arg, name: 'unsupported' };
}
