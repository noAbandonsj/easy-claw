export type SlashCommand =
  | { name: 'browser' }
  | { name: 'clear' }
  | { name: 'delete-session'; arg?: string }
  | { name: 'doctor' }
  | { name: 'exit' }
  | { name: 'help' }
  | { name: 'mcp' }
  | { name: 'model'; arg?: string }
  | { name: 'resume'; arg?: string }
  | { name: 'save'; arg?: string }
  | { name: 'sessions' }
  | { name: 'skills' }
  | { name: 'status' }
  | { name: 'workspace'; arg?: string }
  | { name: 'unsupported'; arg?: string };

const SUPPORTED_COMMANDS = new Set([
  'browser',
  'clear',
  'delete-session',
  'doctor',
  'exit',
  'help',
  'mcp',
  'model',
  'resume',
  'save',
  'sessions',
  'skills',
  'status',
  'workspace',
]);

export function parseSlashCommand(input: string): SlashCommand | null {
  const trimmed = input.trim();
  if (!trimmed.startsWith('/')) {
    return null;
  }

  const [rawName, ...rest] = trimmed.slice(1).split(/\s+/);
  const name = rawName.toLowerCase();
  const arg = rest.join(' ') || undefined;

  if (name === 'delete-session') {
    return { arg, name };
  }
  if (name === 'model') {
    return { arg, name };
  }
  if (name === 'resume') {
    return { arg, name };
  }
  if (name === 'save') {
    return { arg, name };
  }
  if (name === 'workspace') {
    return { arg, name };
  }
  if (SUPPORTED_COMMANDS.has(name)) {
    return { name } as SlashCommand;
  }
  return { arg, name: 'unsupported' };
}
