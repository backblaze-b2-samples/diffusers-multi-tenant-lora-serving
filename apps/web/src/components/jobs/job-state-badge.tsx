import { Badge } from "@/components/ui/badge";
import { jobStateBadge, type JobState } from "@/lib/job-state";

export function JobStateBadge({ state }: { state: JobState }) {
  const { label, variant } = jobStateBadge(state);
  return <Badge variant={variant}>{label}</Badge>;
}
