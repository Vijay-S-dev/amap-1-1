import { SideScaffold } from "@/shared/components/SideScaffold";

export default function OrganizationPage() {
  return (
    <SideScaffold
      side="organization"
      title="Organization governance"
      description="This will cover organizational structure, workforce lifecycle, accessibility and accommodation governance, and org-level analytics. Depends on the multi-tenancy and permission model, which are not yet frozen."
      upcoming={[
        "Organization and department structure setup",
        "Accessibility and accommodation governance",
        "Access and permission governance",
        "Organization-level analytics and compliance/audit views",
      ]}
    />
  );
}
