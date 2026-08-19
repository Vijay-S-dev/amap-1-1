import { SideScaffold } from "@/shared/components/SideScaffold";

export default function WorkerPage() {
  return (
    <SideScaffold
      side="worker"
      title="Worker workspace"
      description="This will be the worker's personalized workspace: assigned tasks, gesture and voice interaction, real-time feedback, and error recovery. None of that is built yet — it depends on the intent/action pipeline and interaction configuration contracts."
      upcoming={[
        "Capability discovery flow (MASTER_SPEC §5.1, Phase 1)",
        "Task guidance and multimodal command input",
        "Real-time action feedback and error recovery",
        "Personalized interaction settings display",
      ]}
    />
  );
}
