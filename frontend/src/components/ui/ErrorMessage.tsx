interface ErrorMessageProps {
  message?: string;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export default function ErrorMessage({
  message = "Unable to connect to server. Please try again.",
  title = "Something went wrong",
  onRetry,
  className,
}: ErrorMessageProps) {
  return (
    <div
      role="alert"
      className={`flex flex-col gap-2 rounded border border-red-200 bg-red-50 p-4 text-red-700 ${className ?? ""}`}
    >
      <p className="font-medium">{title}</p>
      <p className="text-sm">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="w-fit rounded border border-red-300 bg-white px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
