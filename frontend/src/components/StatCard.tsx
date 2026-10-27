type Tone = "short" | "long" | "plain";

const TONES: Record<Tone, string> = {
  plain: "bg-panel",
  short: "bg-short/10 border-l-4 border-l-short",
  long: "bg-long/10 border-l-4 border-l-long",
};

export default function StatCard(props: { label: string; value: string; detail?: string; tone?: Tone }) {
  const { label, value, detail, tone = "plain" } = props;
  return (
    <div className={`px-5 py-4 ${TONES[tone]}`}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-cond text-[28px] font-semibold leading-tight">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted">{detail}</p>}
    </div>
  );
}
