const INLINE_PATTERN = /(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))/g;

export function markdownToBlocks(markdown) {
    const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
        const line = lines[index];
        if (!line.trim()) {
            index += 1;
            continue;
        }

        const fence = line.match(/^```([A-Za-z0-9_-]+)?\s*$/);
        if (fence) {
            const language = fence[1] || '';
            const codeLines = [];
            index += 1;
            while (index < lines.length && !lines[index].startsWith('```')) {
                codeLines.push(lines[index]);
                index += 1;
            }
            if (index < lines.length) index += 1;
            blocks.push({ type: 'code', language, text: codeLines.join('\n') });
            continue;
        }

        const heading = line.match(/^(#{1,6})\s+(.+)$/);
        if (heading) {
            blocks.push({
                type: 'heading',
                level: heading[1].length,
                text: heading[2].trim(),
            });
            index += 1;
            continue;
        }

        const list = readList(lines, index);
        if (list) {
            blocks.push(list.block);
            index = list.nextIndex;
            continue;
        }

        const paragraph = [];
        while (index < lines.length && lines[index].trim()) {
            if (
                lines[index].startsWith('```')
                || /^(#{1,6})\s+/.test(lines[index])
                || /^\s*(?:[-*]|\d+\.)\s+/.test(lines[index])
            ) {
                break;
            }
            paragraph.push(lines[index].trim());
            index += 1;
        }
        if (paragraph.length) {
            blocks.push({ type: 'paragraph', text: paragraph.join(' ') });
        }
    }

    return blocks;
}

function readList(lines, startIndex) {
    const first = lines[startIndex].match(/^\s*((?:[-*])|\d+\.)\s+(.+)$/);
    if (!first) return null;

    const ordered = /\d+\./.test(first[1]);
    const items = [];
    let index = startIndex;
    while (index < lines.length) {
        const match = lines[index].match(/^\s*((?:[-*])|\d+\.)\s+(.+)$/);
        if (!match) break;
        if (/\d+\./.test(match[1]) !== ordered) break;
        items.push(match[2].trim());
        index += 1;
    }
    return {
        block: { type: ordered ? 'ordered-list' : 'list', items },
        nextIndex: index,
    };
}

export function inlineTokens(text) {
    const value = String(text || '');
    const tokens = [];
    let lastIndex = 0;

    for (const match of value.matchAll(INLINE_PATTERN)) {
        if (match.index > lastIndex) {
            tokens.push({ type: 'text', text: value.slice(lastIndex, match.index) });
        }
        if (match[2] !== undefined) {
            tokens.push({ type: 'code', text: match[2] });
        } else if (match[4] !== undefined) {
            tokens.push({ type: 'strong', text: match[4] });
        } else {
            tokens.push({ type: 'link', text: match[6], href: match[7] });
        }
        lastIndex = match.index + match[0].length;
    }

    if (lastIndex < value.length) {
        tokens.push({ type: 'text', text: value.slice(lastIndex) });
    }
    return tokens;
}

export function renderMarkdown(markdown, doc = document) {
    const fragment = doc.createDocumentFragment();
    const blocks = markdownToBlocks(markdown);
    for (const block of blocks) {
        fragment.append(renderBlock(block, doc));
    }
    if (!blocks.length) {
        fragment.append(doc.createTextNode(''));
    }
    return fragment;
}

function renderBlock(block, doc) {
    if (block.type === 'heading') {
        const heading = doc.createElement('h' + Math.min(block.level, 6));
        appendInline(heading, block.text, doc);
        return heading;
    }
    if (block.type === 'code') {
        const pre = doc.createElement('pre');
        const code = doc.createElement('code');
        if (block.language) code.dataset.language = block.language;
        code.textContent = block.text;
        pre.append(code);
        return pre;
    }
    if (block.type === 'list' || block.type === 'ordered-list') {
        const list = doc.createElement(block.type === 'ordered-list' ? 'ol' : 'ul');
        for (const itemText of block.items) {
            const item = doc.createElement('li');
            appendInline(item, itemText, doc);
            list.append(item);
        }
        return list;
    }
    const paragraph = doc.createElement('p');
    appendInline(paragraph, block.text, doc);
    return paragraph;
}

function appendInline(parent, text, doc) {
    for (const token of inlineTokens(text)) {
        parent.append(renderInlineToken(token, doc));
    }
}

function renderInlineToken(token, doc) {
    if (token.type === 'code') {
        const code = doc.createElement('code');
        code.textContent = token.text;
        return code;
    }
    if (token.type === 'strong') {
        const strong = doc.createElement('strong');
        strong.textContent = token.text;
        return strong;
    }
    if (token.type === 'link' && isSafeHref(token.href)) {
        const link = doc.createElement('a');
        link.textContent = token.text;
        link.href = token.href;
        link.target = '_blank';
        link.rel = 'noreferrer';
        return link;
    }
    return doc.createTextNode(token.text || token.href || '');
}

function isSafeHref(href) {
    try {
        const url = new URL(href, 'http://localhost');
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (e) {
        return false;
    }
}
