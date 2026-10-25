interface LoadingSpinnerProps {
  label?: string;
  className?: string;
}

export default function LoadingSpinner({
  label = "Loading...",
  className,
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-3 text-gray-600 ${className ?? ""}`}
    >
      <span
        data-testid="loading-spinner"
        className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"
      />
      <span>{label}</span>
    </div>
  );
}
