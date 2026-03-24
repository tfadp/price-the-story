import type { PriceEfficiencyVerdict } from '@/types/api';

interface Props {
  verdict: PriceEfficiencyVerdict | null | undefined;
  notes?: string | null;
}

const CONFIG: Record<PriceEfficiencyVerdict, { label: string; className: string }> = {
  appears_inflated:     { label: 'Inflated',         className: 'bg-red-900 text-red-300 border-red-700' },
  fairly_priced:        { label: 'Fairly Priced',    className: 'bg-green-900 text-green-300 border-green-700' },
  appears_conservative: { label: 'Conservative',     className: 'bg-blue-900 text-blue-300 border-blue-700' },
  insufficient_data:    { label: 'Price: Unknown',   className: 'bg-gray-800 text-gray-400 border-gray-600' },
};

export default function PriceEfficiencyBadge({ verdict, notes }: Props) {
  if (!verdict) return null;
  const { label, className } = CONFIG[verdict];
  return (
    <div>
      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${className}`}>
        {label}
      </span>
      {notes && <p className="mt-1 text-xs text-gray-400">{notes}</p>}
    </div>
  );
}
