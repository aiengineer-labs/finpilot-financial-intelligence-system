type StatusCardProps = {
  label: string;
  value: string;
  tone?: "good" | "neutral" | "warning";
};

export function StatusCard({ label, value, tone = "neutral" }: StatusCardProps) {
  return (
    <article className={`status-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
