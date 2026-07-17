import type { ReactNode } from "react";
import { createPortal } from "react-dom";

export function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="modal-panel" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.body,
  );
}
