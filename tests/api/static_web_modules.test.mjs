import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function importBrowserModule(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf-8');
  return import('data:text/javascript;charset=utf-8,' + encodeURIComponent(source));
}

const {
  inlineTokens,
  markdownToBlocks,
} = await importBrowserModule('../../src/easy_claw/api/static/js/markdown.js');
const {
  ToolRunStore,
  summarizeToolPayload,
  summarizeToolResult,
} = await importBrowserModule('../../src/easy_claw/api/static/js/tools.js');

test('markdownToBlocks preserves common chat markdown without evaluating HTML', () => {
  const blocks = markdownToBlocks(`# 标题

这里有 **重点** 和 \`pytest\`。

- 第一项
- 第二项

\`\`\`powershell
uv run pytest
\`\`\`

<script>alert(1)</script>`);

  assert.deepEqual(
    blocks.map(block => block.type),
    ['heading', 'paragraph', 'list', 'code', 'paragraph'],
  );
  assert.equal(blocks[0].level, 1);
  assert.equal(blocks[0].text, '标题');
  assert.deepEqual(blocks[2].items, ['第一项', '第二项']);
  assert.equal(blocks[3].language, 'powershell');
  assert.equal(blocks[3].text, 'uv run pytest');
  assert.equal(blocks[4].text, '<script>alert(1)</script>');
});

test('inlineTokens identifies emphasis, code, and links as renderable tokens', () => {
  const tokens = inlineTokens('运行 `pytest`、**ruff**，再看 [文档](https://example.com)。');

  assert.deepEqual(tokens, [
    { type: 'text', text: '运行 ' },
    { type: 'code', text: 'pytest' },
    { type: 'text', text: '、' },
    { type: 'strong', text: 'ruff' },
    { type: 'text', text: '，再看 ' },
    { type: 'link', text: '文档', href: 'https://example.com' },
    { type: 'text', text: '。' },
  ]);
});

test('ToolRunStore merges a tool result into the matching pending call', () => {
  const store = new ToolRunStore();

  const started = store.start('search_web', { query: 'easy-claw' });
  const finished = store.finish('search_web', ['result']);

  assert.equal(finished, started);
  assert.equal(finished.status, 'finished');
  assert.deepEqual(finished.result, ['result']);
  assert.equal(store.pendingCount(), 0);
  assert.equal(store.runs.length, 1);
});

test('tool summaries keep the useful fields visible', () => {
  assert.deepEqual(summarizeToolPayload({ query: 'easy-claw', ignored: true }), [
    ['query', 'easy-claw'],
  ]);
  assert.deepEqual(summarizeToolResult('line 1\nline 2'), [
    ['摘要', 'line 1 line 2'],
    ['长度', '13 字符'],
  ]);
});
