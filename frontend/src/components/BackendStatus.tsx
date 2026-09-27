interface BackendStatusProps {
  status: "checking" | "online" | "offline";
}

export function BackendStatus({ status }: BackendStatusProps) {
  const label =
    status === "checking"
      ? "Checking backend…"
      : status === "online"
        ? "Backend online"
        : "Backend unavailable";

  return (
    <div className={`backend-status backend-status--${status}`} role="status">
      <span className="backend-status__dot" aria-hidden="true" />
      {label}
    </div>
  );
}
