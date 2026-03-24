import type { StressVerdict } from '@/types/api';

interface Props {
  verdict: StressVerdict | null | undefined;
  notes?: string | null;
}

const CONFIG: Record<StressVerdict, { label: string; className: string }> = {
  robust:      { label: 'Robust',      className: 'bg-green-900 text-green-300 border-green-700' },
  conditional: { label: 'Conditional', className: 'bg-yellow-900 text-yellow-300 border-yellow-700' },
  fragile:     { label: 'Fragile',     className: 'bg-red-900 text-red-300 border-red-700' },
};

export default function StressBadge({ verdict, notes }: Props) {
  if (!verdict) return null;
  const { label, className } = CONFIG[verdict];
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${className}`}>
        {label}
      </span>
      {notes && <span className="text-sm text-gray-400">{notes}</span>}
    </div>
  );
}
