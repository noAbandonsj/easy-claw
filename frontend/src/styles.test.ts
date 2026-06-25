/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(resolve(process.cwd(), 'src', 'styles.css'), 'utf-8');

function declarationsFor(selector: string) {
  const match = styles.match(new RegExp(String.raw`(?:^|})\s*${selector}\s*\{([^}]*)\}`, 'm'));
  const body = match?.[1] ?? '';

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

function mediaBlockFor(query: string) {
  const start = styles.indexOf(query);
  if (start === -1) {
    return '';
  }

  const blockStart = styles.indexOf('{', start);
  let depth = 0;
  for (let index = blockStart; index < styles.length; index += 1) {
    const char = styles[index];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return styles.slice(blockStart + 1, index);
      }
    }
  }

  return '';
}

function declarationsForInBlock(block: string, selector: string) {
  const match = block.match(new RegExp(String.raw`(?:^|})\s*${selector}\s*\{([^}]*)\}`, 'm'));
  const body = match?.[1] ?? '';

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

  it('does not use hard-coded component colors outside root tokens', () => {
    const componentCss = styles.replace(/:root\s*\{[^}]*\}/, '');

    expect(componentCss).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(componentCss).not.toMatch(/rgba?\(\s*(?:0\s*,\s*0\s*,\s*0|38\s*,\s*52\s*,\s*66|52\s*,\s*211\s*,\s*153)\b/);
  });

  it('contains Claw Rail, responsive, and reduced-motion rules', () => {
    expect(styles).toContain('.claw-rail');
    expect(styles).toContain('.rail-event::before');
    expect(styles).toContain('@media (max-width: 1120px)');
    expect(styles).toContain('@media (max-width: 720px)');
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
  });

  it('preserves the inspector as a compact tablet grid row', () => {
    const tabletBlock = mediaBlockFor('@media (max-width: 1120px)');

    expect(declarationsForInBlock(tabletBlock, '.inspector-panel')).toMatchObject({
      display: 'grid',
      'grid-column': '1 / -1',
    });
  });

  it('disables the running rail pulse for reduced-motion users', () => {
    const reducedMotionBlock = mediaBlockFor('@media (prefers-reduced-motion: reduce)');

    expect(declarationsForInBlock(reducedMotionBlock, '.rail-event-running::before')).toMatchObject({
      animation: 'none !important',
    });
  });
});
