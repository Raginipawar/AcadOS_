# main.py — run with: python main.py
import os, time
os.makedirs('outputs', exist_ok=True)
from shared import PCB, Role, JobType, State, transition_state
from scheduler import submit_job, scheduler_tick, plot_gantt, clear_current
from memory import allocate_pages, access_page, free_pages, plot_page_faults
from deadlock import request_resources, release_resources, deadlock_recover, create_db
from io_manager import log_job, AbuseMonitor, plot_disk_seeks, cscan, sstf

create_db()

jobs = [
  PCB(pid=1, user_id=101, role=Role.STUDENT,    job_type=JobType.EXAM,       deadline=time.time()+300,  cpu_budget_ns=1000),
  PCB(pid=2, user_id=102, role=Role.STUDENT,    job_type=JobType.PRACTICE,   deadline=time.time()+3600, cpu_budget_ns=1000),
  PCB(pid=3, user_id=201, role=Role.RESEARCHER, job_type=JobType.RESEARCH,   deadline=time.time()+1800, cpu_budget_ns=1000),
  PCB(pid=4, user_id=103, role=Role.STUDENT,    job_type=JobType.PRACTICE,   deadline=time.time()+7200, cpu_budget_ns=1000),
  PCB(pid=5, user_id=301, role=Role.FACULTY,    job_type=JobType.EVALUATION, deadline=time.time()+600,  cpu_budget_ns=1000),
]

# CPU limits per job type
JOB_LIMITS = {JobType.EXAM: 8, JobType.EVALUATION: 6, JobType.RESEARCH: 10, JobType.PRACTICE: 12}

for job in jobs:
    allocate_pages(job, num_pages=4)
    request_resources(job, {'CPU': 1, 'MEM_BLOCK': 2})
    submit_job(job)

monitor = AbuseMonitor(process_table=jobs, tick_interval=5)
monitor.start()

timeline = []
for tick in range(50):
    running, preempted = scheduler_tick(tick)
    if running:
        access_page(running, virtual_page=tick % 4)
        running.cpu_used += 1
        timeline.append((running.pid, running.job_type.name, tick))
        # Exit job when it hits its CPU limit
        limit = JOB_LIMITS.get(running.job_type, 10)
        if running.cpu_used >= limit:
            try: transition_state(running, State.EXIT)
            except: running.state = State.EXIT
            try: free_pages(running)
            except: pass
            try: release_resources(running)
            except: pass
            clear_current()
            print(f"[TICK {tick:02d}] PID {running.pid} ({running.job_type.name}) -> EXIT (cpu_used={running.cpu_used})")
    else:
        timeline.append((-1, "IDLE", tick))
        print(f"[TICK {tick:02d}] IDLE")

    if running and running.state != State.EXIT:
        print(f"[TICK {tick:02d}] PID {running.pid} ({running.job_type.name}) -> RUNNING")

monitor.stop()

for job in jobs:
    if job.state != State.EXIT:
        try: release_resources(job)
        except: pass
        try: free_pages(job)
        except: pass
    log_job(job)

plot_gantt(timeline)
plot_disk_seeks(cscan([95,180,34,119,11,123,62,64,66], 50), sstf([95,180,34,119,11,123,62,64,66], 50))
print("\nDone! Check outputs/ for gantt.png and disk_seeks.png")