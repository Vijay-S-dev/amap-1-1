\\# AMAP Database



\\\*\\\*Status:\\\*\\\* Implemented Foundation



\\\*\\\*Database:\\\*\\\* PostgreSQL 16



\\\*\\\*Database Development:\\\*\\\* Docker



\\\*\\\*Migration Range:\\\*\\\* 001–039



\\\*\\\*Current Tables:\\\*\\\* 38



\\---



\\## 1. Purpose



This document describes the AMAP PostgreSQL database foundation implemented through the migration files in:



\\`\\`\\`text



database/migrations/



The database is organization-scoped and provides the persistence foundation for AMAP users, workers, jobs, workflows, tasks, interactions, execution, assistance, personalization, notifications, and audit history.



The migration files are the implementation source of truth for the database schema.



2\\. Database Technology



Database: PostgreSQL



Version: 16



Development: Docker Compose



Schema: public



Database owner: amap\\\_user



The PostgreSQL container is managed through the project's Docker Compose configuration.



3\\. Migration Structure



The database is built incrementally through migrations:



001\\\_extensions.sql



002\\\_organizations.sql



003\\\_departments.sql



004\\\_users.sql



005\\\_user\\\_departments.sql



006\\\_roles.sql



007\\\_permissions.sql



008\\\_user\\\_roles.sql



009\\\_role\\\_permissions.sql



010\\\_worker\\\_profiles.sql



011\\\_jobs.sql



012\\\_responsibilities.sql



013\\\_worker\\\_job\\\_assignments.sql



014\\\_workflows.sql



015\\\_workflow\\\_steps.sql



016\\\_workflow\\\_step\\\_responsibilities.sql



017\\\_workflow\\\_assignments.sql



018\\\_workflow\\\_step\\\_executions.sql



019\\\_tasks.sql



020\\\_task\\\_responsibilities.sql



021\\\_task\\\_workflows.sql



022\\\_worker\\\_task\\\_assignments.sql



023\\\_task\\\_results.sql



024\\\_actions.sql



025\\\_action\\\_requirements.sql



026\\\_workflow\\\_step\\\_actions.sql



027\\\_task\\\_actions.sql



028\\\_interaction\\\_configurations.sql



029\\\_gesture\\\_configurations.sql



030\\\_voice\\\_configurations.sql



031\\\_worker\\\_capability\\\_profiles.sql



032\\\_worker\\\_personalizations.sql



033\\\_personalization\\\_history.sql



034\\\_execution\\\_events.sql



035\\\_work\\\_sessions.sql



036\\\_interaction\\\_events.sql



037\\\_assistance\\\_requests.sql



038\\\_notifications.sql



039\\\_audit\\\_events.sql



Migration 001\\\_extensions.sql installs the PostgreSQL pgcrypto extension used for UUID generation.



The remaining migrations create the 38 application tables.



4\\. Core Organization Structure



AMAP is organization-scoped.



The primary organization hierarchy is:



Organization



├── Departments



├── Users



├── Jobs



├── Workflows



├── Tasks



├── Interaction Configurations



├── Notifications



└── Audit Events



Organizations



organizations represents an AMAP organization.



Important properties include:



UUID primary key



unique organization name



organization status



creation and update timestamps



Supported organization statuses:



active



inactive



archived



Departments



departments belong to an organization.



A department name is unique within its organization.



Users



users belong to an organization.



User email addresses are unique within an organization.



User Departments



user\\\_departments provides the many-to-many relationship between users and departments.



5\\. RBAC Foundation



AMAP contains a database foundation for role-based access control.



User



↓



User Role



↓



Role



↓



Role Permission



↓



Permission



Tables:



roles



permissions



user\\\_roles



role\\\_permissions



The database establishes the relationships required for RBAC.



The actual authentication and authorization behavior belongs to the backend implementation phase and is not defined by these migrations alone.



6\\. Workforce



Worker-related data is represented through:



users



↓



worker\\\_profiles



├── worker\\\_capability\\\_profiles



├── worker\\\_personalizations



├── worker\\\_job\\\_assignments



├── worker\\\_task\\\_assignments



├── workflow\\\_assignments



└── work\\\_sessions



Worker Profiles



worker\\\_profiles provides the worker-specific profile associated with a user.



Each user can have at most one worker profile.



Worker Capability Profiles



worker\\\_capability\\\_profiles stores capability information as JSONB.



Worker Personalizations



worker\\\_personalizations stores worker-specific personalization data.



Personalization History



personalization\\\_history records historical personalization changes.



7\\. Jobs and Responsibilities



Jobs are organization-scoped.



Organization



↓



Job



↓



Responsibility



Tables:



jobs



responsibilities



worker\\\_job\\\_assignments



A responsibility belongs to a job.



Workers can be assigned to jobs through worker\\\_job\\\_assignments.



8\\. Workflows



The workflow structure is:



Workflow



↓



Workflow Steps



├── Responsibilities



└── Actions



Tables:



workflows



workflow\\\_steps



workflow\\\_step\\\_responsibilities



workflow\\\_step\\\_actions



workflow\\\_assignments



workflow\\\_step\\\_executions



Workflow Steps



Workflow steps have a positive step\\\_order.



The combination of:



workflow\\\_id + step\\\_order



is unique.



Workflow Assignments



A workflow can be assigned to a worker through workflow\\\_assignments.



Workflow Step Executions



workflow\\\_step\\\_executions tracks execution state for individual workflow steps.



Supported execution states:



pending



in\\\_progress



completed



skipped



failed



9\\. Tasks



The task structure is:



Task



├── Responsibilities



├── Workflows



├── Actions



└── Worker Assignments



Tables:



tasks



task\\\_responsibilities



task\\\_workflows



task\\\_actions



worker\\\_task\\\_assignments



task\\\_results



Tasks are organization-scoped.



Task statuses include:



draft



active



inactive



archived



Task results are associated with worker task assignments.



Supported task result outcomes:



completed



failed



partial



cancelled



10\\. Actions



Actions represent executable capabilities in the application.



Tables:



actions



action\\\_requirements



workflow\\\_step\\\_actions



task\\\_actions



Actions contain:



name



display name



description



category



status



Supported action categories:



general



navigation



workflow



task



assistance



system



Action requirements can represent:



validation



permission



state



context



confirmation



The database stores requirement-specific information using JSONB.



11\\. Interaction Configuration



Interaction configuration connects user interaction modes to actions.



Interaction Configuration



├── Gesture Configuration



└── Voice Configuration



↓



Action



Tables:



interaction\\\_configurations



gesture\\\_configurations



voice\\\_configurations



Gesture and voice configurations support confidence thresholds between 0 and 1.



The database does not make recognition confidence equivalent to authorization.



Backend authorization remains responsible for determining whether an action may actually execute.



12\\. Runtime Execution and Sessions



AMAP records runtime execution information through:



work\\\_sessions



execution\\\_events



interaction\\\_events



Work Sessions



work\\\_sessions track worker activity periods.



Supported statuses:



active



paused



completed



cancelled



The database ensures:



ended\\\_at >= started\\\_at



when an end timestamp is present.



Execution Events



execution\\\_events provide event records associated with organization, workers, workflow assignments, and task assignments.



Event-specific information is stored as JSONB.



Interaction Events



interaction\\\_events record interaction activity.



Supported interaction modes:



gesture



voice



ui



other



Confidence values, when present, must be between 0 and 1.



13\\. Assistance



assistance\\\_requests represents worker assistance requests.



An assistance request may be associated with:



organization



worker



work session



workflow assignment



worker task assignment



Supported statuses:



open



acknowledged



in\\\_progress



resolved



cancelled



Supported priorities:



low



normal



high



urgent



14\\. Notifications



notifications stores user-facing notification records.



Notifications belong to an organization and have a recipient user.



Supported notification states:



unread



read



archived



Notification-specific information can be stored in JSONB.



15\\. Audit Events



audit\\\_events provides an audit trail for important system events.



An audit event belongs to an organization and may optionally identify the user responsible for the event.



Audit records can identify:



event\\\_type



resource\\\_type



resource\\\_id



event\\\_data



occurred\\\_at



Event-specific information is stored as JSONB.



16\\. Foreign Key Integrity



The current database contains:



38 tables



61 foreign-key constraints



Foreign keys establish relationships between organizations, users, workers, jobs, tasks, workflows, actions, interactions, execution records, assistance records, notifications, and audit records.



Most destructive parent-row operations use:



ON DELETE RESTRICT



This protects referenced records from being deleted while dependent records still exist.



17\\. Constraints and Validation



The schema uses:



primary keys



unique constraints



foreign keys



check constraints



indexes



timestamp validation



JSONB fields



UUID identifiers



Examples of enforced rules include:



organization names are unique



user email is unique within an organization



department names are unique within an organization



task names are unique within an organization



workflow names are unique within an organization



workflow step order is positive



workflow step order is unique within a workflow



confidence values are between 0 and 1



ended\\\_at cannot precede started\\\_at



completed\\\_at cannot precede started\\\_at



18\\. Verification Performed



The implemented database foundation has been manually verified for:



Migration files 001–039 PASS



Application tables: 38 PASS



Foreign keys: 61 PASS



Foreign-key enforcement PASS



Unique constraint enforcement PASS



Check constraint enforcement PASS



Date constraint enforcement PASS



JSONB storage PASS



Cross-table relationship testing PASS



Temporary test-data cleanup PASS



Temporary verification records were created and subsequently removed.



The database is currently structurally populated but contains no permanent application seed data.



19\\. Current Database State



At the completion of the database foundation verification:



Migration files: 001–039



Application tables: 38



Foreign keys: 61



Permanent seed data: Not yet established



Temporary verification data: Removed



An empty application database at this stage is expected.



20\\. Backend Integration Boundary



The backend specification establishes the following future direction:



Backend



↓



Database Integration



↓



Authentication



↓



Authorization / RBAC



↓



Organization-scoped Business APIs



The database foundation is now available for backend integration.



Authentication, authorization, and business APIs are separate implementation phases and must not be assumed to be implemented merely because their database tables exist.



21\\. Migration Rules



Future database changes must use a new migration rather than modifying an already-applied migration.



Migration files should:



use sequential numbering



describe one logical database change



preserve existing data where possible



maintain foreign-key integrity



include appropriate indexes and constraints



be tested against PostgreSQL



The current completed migration range is:



001–039



22\\. Source of Truth



For the implemented database structure, the migration files are authoritative:



database/migrations/001\\\_extensions.sql



through



database/migrations/039\\\_audit\\\_events.sql



This document describes and organizes the implemented schema but does not replace the migration files.



23\\. Current Status



Database foundation: COMPLETE



Migrations: 001–039



Tables: 38



Foreign keys: 61



Verification: COMPLETE



Cleanup: COMPLETE



Next approved phase:



Database integration with the backend

