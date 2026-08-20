import { SideScaffold } from "@/shared/components/SideScaffold";

export default function AdminPage() {
  return (
    <SideScaffold
      side="admin"
      title="Admin console"
      description="This will be where jobs, tasks, and workflows get defined and assigned, where AI-generated workflow proposals are reviewed before activation, and where worker operational status is monitored. Requires the RBAC matrix and API contracts, which are not yet frozen."
      upcoming={[
        "Job/task/workflow creation and action mapping",
        "AI-generated workflow review and approval (MASTER_SPEC §6)",
        "Worker operational monitoring — status, not surveillance",
        "Exception and assistance-request handling",
      ]}
    />
  );
}
