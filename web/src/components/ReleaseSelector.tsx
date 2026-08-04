import type { Leaderboard, ReleaseView } from "../types";

type Props = {
  data: Leaderboard | null;
  onChange: (value: ReleaseView) => void;
  value: ReleaseView;
};

const OPTIONS: Array<{ value: ReleaseView; label: string }> = [
  { value: "real", label: "OpenKBP workflows" },
  { value: "core", label: "Core physics" },
  { value: "imaging", label: "Imaging" },
  { value: "tg263", label: "TG-263" },
];

export function ReleaseSelector({ data, onChange, value }: Props) {
  return (
    <section className="release-selector" aria-label="Benchmark release">
      <div>
        <strong>{data?.release.title ?? "Loading release…"}</strong>
        <span>{data ? `${data.tasks.length} tasks · ${data.release.release_id}` : "Loading immutable release evidence"}</span>
      </div>
      <div className="release-tabs" role="group" aria-label="Choose benchmark release">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}
