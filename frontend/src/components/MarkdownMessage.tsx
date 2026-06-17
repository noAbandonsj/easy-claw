import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';

export function MarkdownMessage({
  content,
  streaming,
}: {
  content: string;
  streaming: boolean;
}) {
  return (
    <article className="message assistant-message markdown-body">
      <span className="message-label">Easy Claw</span>
      <ReactMarkdown
        components={{
          a({ children, href }) {
            return (
              <a href={href} rel="noreferrer" target="_blank">
                {children}
              </a>
            );
          },
          code({ children, className }) {
            const value = String(children).replace(/\n$/, '');
            const match = /language-(\w+)/.exec(className || '');
            if (match) {
              return <CodeBlock language={match[1]} value={value} />;
            }
            return <code className={className}>{children}</code>;
          },
        }}
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
      {streaming ? <span className="cursor" /> : null}
    </article>
  );
}
