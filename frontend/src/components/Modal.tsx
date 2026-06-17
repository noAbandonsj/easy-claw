import type { ReactNode } from 'react';

export function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div className="modal" onClick={event => event.stopPropagation()}>
        {children}
        <button className="modal-close" onClick={onClose} type="button">
          关闭
        </button>
      </div>
    </div>
  );
}
