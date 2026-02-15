export default function Spinner({ className = '' }: { className?: string }) {
  return (
    <div className={`inline-block ${className}`}>
      <div className="w-5 h-5 border-2 border-text-ghost border-t-accent rounded-full animate-spin" />
    </div>
  );
}
