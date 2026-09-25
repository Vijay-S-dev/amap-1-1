import os
import psycopg
from dotenv import load_dotenv

load_dotenv(".env")
db_url = os.getenv("DATABASE_URL", "postgresql://amap_user:Vijay%40amap%40post@localhost:5432/amap")

conn = psycopg.connect(db_url)
cur = conn.cursor()

print("--- USERS (DEMO/REAL) ---")
cur.execute("SELECT id, email, full_name, status, organization_id FROM users WHERE email IN ('alex.worker@amap.com', 'maria.newhire@amap.com', 'supervisor@amap.com', 'admin@amap.com');")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKER PROFILES ---")
cur.execute("SELECT wp.id, wp.user_id, u.email, wp.badge_number, wp.status FROM worker_profiles wp JOIN users u ON wp.user_id = u.id WHERE u.email IN ('alex.worker@amap.com', 'maria.newhire@amap.com');")
for r in cur.fetchall():
    print(" ", r)

print("\n--- TASKS ---")
cur.execute("SELECT id, organization_id, name, description, status FROM tasks;")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKFLOWS ---")
cur.execute("SELECT id, organization_id, name, status FROM workflows;")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKFLOW STEPS ---")
cur.execute("SELECT id, workflow_id, step_order, title, instruction, is_safety_critical FROM workflow_steps ORDER BY step_order;")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKER TASK ASSIGNMENTS ---")
cur.execute("SELECT wta.id, wta.task_id, wta.worker_profile_id, wta.status, wta.assigned_at, wta.started_at, wta.completed_at FROM worker_task_assignments wta;")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKFLOW ASSIGNMENTS ---")
cur.execute("SELECT id, workflow_id, worker_profile_id, status FROM workflow_assignments;")
for r in cur.fetchall():
    print(" ", r)

print("\n--- WORKFLOW STEP EXECUTIONS ---")
cur.execute("SELECT id, workflow_step_id, worker_profile_id, status, started_at, completed_at FROM workflow_step_executions;")
for r in cur.fetchall():
    print(" ", r)

conn.close()
