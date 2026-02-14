interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  destructive?: boolean;
}

export default function ConfirmDialog({ open, title, message, onConfirm, onCancel, destructive }: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative bg-surface-raised border border-text-ghost rounded-lg p-6 max-w-sm w-full mx-4 shadow-xl">
        <h3 className="text-sm font-medium text-text-primary mb-2">{title}</h3>
        <p className="text-xs text-text-secondary mb-6">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-muted hover:text-text-primary rounded"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-3 py-1.5 text-xs rounded ${
              destructive
                ? 'bg-red-900/50 text-red-300 hover:bg-red-900/70'
                : 'bg-accent/20 text-accent hover:bg-accent/30'
            }`}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
