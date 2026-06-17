import type { MessageBlock } from '../api/types';
import { MessageBlockView } from './MessageBlockView';

export function ChatView({ blocks }: { blocks: MessageBlock[] }) {
  return (
    <section className="chat-stream" aria-label="聊天记录">
      {blocks.length ? (
        blocks.map(block => <MessageBlockView block={block} key={block.id} />)
      ) : (
        <article className="message assistant-message">
          <span className="message-label">Easy Claw</span>
          <p>选择或新建会话后即可开始。</p>
        </article>
      )}
    </section>
  );
}
