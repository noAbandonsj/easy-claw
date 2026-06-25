/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(resolve(process.cwd(), 'src', 'styles.css'), 'utf-8');

function declarationsFor(selector: string) {
  const selectorStart = styles.indexOf(`${selector} {`);
  const bodyStart = selectorStart >= 0 ? styles.indexOf('{', selectorStart) + 1 : 0;
  const bodyEnd = bodyStart > 0 ? styles.indexOf('}', bodyStart) : 0;
  const body = bodyStart > 0 && bodyEnd > bodyStart ? styles.slice(bodyStart, bodyEnd) : '';

  return Object.fromEntries(
    body
      .split(';')
      .map(declaration => declaration.trim())
      .filter(Boolean)
      .map(declaration => {
        const [property, ...valueParts] = declaration.split(':');
        return [property.trim(), valueParts.join(':').trim()];
      }),
  );
}

describe('styles', () => {
  it('defines the Obsidian Runbook theme tokens', () => {
    expect(declarationsFor(':root')).toMatchObject({
      '--color-bg': '#080b0f',
      '--color-panel': '#10161d',
      '--color-panel-raised': '#151d26',
      '--color-line': '#263442',
      '--color-text': '#e6edf3',
      '--color-muted': '#8493a3',
      '--color-agent': '#7dd3fc',
      '--color-user': '#facc15',
      '--color-risk': '#fb7185',
      '--color-ok': '#34d399',
      '--color-warn': '#f59e0b',
      '--color-command': '#a78bfa',
      '--font-ui': '"Segoe UI Variable", "Microsoft YaHei UI", system-ui, sans-serif',
      '--font-mono': '"Cascadia Code", "JetBrains Mono", "Consolas", monospace',
    });
  });

  it('keeps the cockpit shell inside the viewport', () => {
    expect(declarationsFor('.app-shell')).toMatchObject({
      height: '100vh',
      overflow: 'hidden',
    });
    expect(declarationsFor('.workbench-grid')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
    expect(declarationsFor('.sidebar')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
    expect(declarationsFor('.chat-pane')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
  });

  it('contains Claw Rail, responsive, and reduced-motion rules', () => {
    expect(styles).toContain('.claw-rail');
    expect(styles).toContain('.rail-event::before');
    expect(styles).toContain('@media (max-width: 1120px)');
    expect(styles).toContain('@media (max-width: 720px)');
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
  });
});
