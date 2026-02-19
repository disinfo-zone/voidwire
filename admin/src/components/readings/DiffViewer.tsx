interface Props {
  diff: any;
}

export default function DiffViewer({ diff }: Props) {
  if (!diff) return null;

  return (
    <div className="space-y-4">
      <h3 className="text-xs text-text-muted uppercase tracking-wider">Generated vs Published</h3>

      {diff.generated_standard && diff.published_standard && (
        <div>
          <h4 className="text-xs text-accent mb-2">Standard Reading</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <div className="text-xs text-text-muted mb-1">Generated</div>
              <div className="bg-surface border border-text-ghost rounded p-3 text-xs text-text-secondary">
                <div className="font-semibold mb-1">{diff.generated_standard.title}</div>
                <div className="whitespace-pre-wrap">{diff.generated_standard.body}</div>
              </div>
            </div>
            <div>
              <div className="text-xs text-text-muted mb-1">Published</div>
              <div className="bg-surface border border-accent/30 rounded p-3 text-xs text-text-secondary">
                <div className="font-semibold mb-1">{diff.published_standard?.title}</div>
                <div className="whitespace-pre-wrap">{diff.published_standard?.body}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {diff.editorial_diff && (
        <div className="text-xs text-text-muted">
          <span className="text-accent">Editorial diff: </span>
          {JSON.stringify(diff.editorial_diff)}
        </div>
      )}
    </div>
  );
}
