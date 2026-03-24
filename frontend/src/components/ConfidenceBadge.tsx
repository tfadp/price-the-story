import type { ConfidenceVerdict } from '@/types/api';

interface Props {
  verdict: ConfidenceVerdict | null | undefined;
}

const CONFIG: Record<ConfidenceVerdict, { label: string; className: string }> = {
  high_confidence:    { label: 'High Confidence',    className: 'bg-green-900 text-green-300 border-green-700' },
  moderate_confidence:{ label: 'Moderate Confidence', className: 'bg-yellow-900 text-yellow-300 border-yellow-700' },
  low_confidence:     { label: 'Low Confidence',     className: 'bg-red-900 text-red-300 border-red-700' },
  insufficient_data:  { label: 'Insufficient Data',  className: 'bg-gray-800 text-gray-400 border-gray-600' },
};

export default function ConfidenceBadge({ verdict }: Props) {
  if (!verdict) return null;
  const { label, className } = CONFIG[verdict];
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${className}`}>
      {label}
    </span>
  );
}
