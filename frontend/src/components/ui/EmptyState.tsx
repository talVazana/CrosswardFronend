interface EmptyStateProps {
  title?: string;
  message?: string;
  className?: string;
}

export default function EmptyState({
  title = "Nothing here yet",
  message = "There is no data to display.",
  className,
}: EmptyStateProps) {
  return (
    <div
      data-testid="empty-state"
      className={`flex flex-col items-center gap-1 rounded border border-dashed border-gray-300 p-6 text-center ${className ?? ""}`}
    >
      <p className="font-medium text-gray-700">{title}</p>
      <p className="text-sm text-gray-500">{message}</p>
    </div>
  );
}
