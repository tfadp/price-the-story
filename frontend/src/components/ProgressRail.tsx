interface Props {
  stage: string;
  progress_pct: number;
}

const STAGES = [
  'Pulling financials',
  'Reading filings & transcripts',
  'Analyzing the growth story',
  'Checking the price',
  'Running stress scenarios',
  'Writing verdict',
];

export default function ProgressRail({ stage, progress_pct }: Props) {
  const currentIdx = STAGES.findIndex(s => stage.toLowerCase().includes(s.toLowerCase().split(' ')[0]));

  return (
    <div className="w-full max-w-2xl">
      {/* Progress bar */}
      <div className="h-1 bg-gray-700 rounded-full mb-6 overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${progress_pct}%` }}
        />
      </div>

      {/* Stage list */}
      <div className="flex flex-col gap-2">
        {STAGES.map((s, i) => {
          const isDone = currentIdx > i;
          const isActive = currentIdx === i;
          return (
            <div key={s} className={`flex items-center gap-3 text-sm transition-all ${
              isDone ? 'text-green-400' : isActive ? 'text-white' : 'text-gray-600'
            }`}>
              <span className="w-4 h-4 flex-shrink-0">
                {isDone ? '✓' : isActive ? '→' : '○'}
              </span>
              <span className={isActive ? 'font-medium' : ''}>{s}</span>
              {isActive && (
                <span className="text-blue-400 text-xs animate-pulse">running...</span>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-sm text-gray-400">{stage}</p>
    </div>
  );
}
