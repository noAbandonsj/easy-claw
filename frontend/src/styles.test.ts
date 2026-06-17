/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(resolve(process.cwd(), 'src', 'styles.css'), 'utf-8');

function declarationsFor(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = styles.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`));
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
  it('keeps long session lists from pushing the chat composer below the viewport', () => {
    expect(declarationsFor('.app-shell')).toMatchObject({
      height: '100vh',
      overflow: 'hidden',
    });
    expect(declarationsFor('.sidebar')).toMatchObject({
      'max-height': '100vh',
      'min-height': '0',
    });
    expect(declarationsFor('.session-list')).toMatchObject({
      overflow: 'auto',
    });
    expect(declarationsFor('.chat-pane')).toMatchObject({
      'max-height': '100vh',
      'min-height': '0',
    });
  });
});
