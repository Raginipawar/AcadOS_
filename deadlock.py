import ctypes, os, sqlite3, threading
from typing import Dict, List
from shared import PCB, Role, JobType, State, transition_state

_banker_lib = None
def _load_banker():
    global _banker_lib
    so_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'c_src', 'banker.so')
    if not os.path.exists(so_path): return
    try:
        lib = ctypes.CDLL(os.path.abspath(so_path))
        lib.is_safe_state.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
        lib.is_safe_state.restype = ctypes.c_int
        _banker_lib = lib
    except: _banker_lib = None
_load_banker()

def _is_safe_python(available, allocation, need, pids):
    resources = list(available.keys())
    work = {r: available[r] for r in resources}
    finish = {pid: False for pid in pids}
    changed = True
    while changed:
        changed = False
        for pid in pids:
            if finish[pid]: continue
            if all(need[pid].get(r,0) <= work.get(r,0) for r in resources):
                for r in resources: work[r] += allocation[pid].get(r,0)
                finish[pid] = True; changed = True
    return all(finish.values())

def _is_safe(available, allocation, need, pids):
    if not pids: return True
    if _banker_lib is None: return _is_safe_python(available, allocation, need, pids)
    resources = sorted(available.keys()); n, r = len(pids), len(resources)
    avail_arr = (ctypes.c_int * r)(*[available[res] for res in resources])
    alloc_flat = (ctypes.c_int * (n*r))(*[allocation[pid].get(res,0) for pid in pids for res in resources])
    need_flat = (ctypes.c_int * (n*r))(*[need[pid].get(res,0) for pid in pids for res in resources])
    return _banker_lib.is_safe_state(avail_arr, alloc_flat, need_flat, n, r) == 1

class ResourceManager:
    def __init__(self):
        self.available = {'CPU': 4, 'MEM_BLOCK': 8}
        self.allocation = {}; self.max_need = {}; self._lock = threading.Lock()
    def register(self, pcb, max_dict):
        with self._lock:
            self.max_need[pcb.pid] = {r: max_dict.get(r,0) for r in self.available}
            self.allocation[pcb.pid] = {r: 0 for r in self.available}
    def request_resources(self, pcb, request_dict):
        with self._lock:
            pid = pcb.pid
            if pid not in self.max_need:
                self.max_need[pid] = {r: request_dict.get(r,0) for r in self.available}
                self.allocation[pid] = {r: 0 for r in self.available}
            need = {r: self.max_need[pid].get(r,0) - self.allocation[pid].get(r,0) for r in self.available}
            for r, qty in request_dict.items():
                if qty > need.get(r,0) or qty > self.available.get(r,0): return False
            hypo_avail = {r: self.available[r] - request_dict.get(r,0) for r in self.available}
            hypo_alloc = {p: dict(a) for p, a in self.allocation.items()}
            hypo_alloc[pid] = {r: self.allocation[pid].get(r,0) + request_dict.get(r,0) for r in self.available}
            hypo_need = {p: {r: self.max_need[p].get(r,0) - hypo_alloc[p].get(r,0) for r in self.available} for p in self.allocation}
            if _is_safe(hypo_avail, hypo_alloc, hypo_need, list(self.allocation.keys())):
                self.available = hypo_avail; self.allocation[pid] = hypo_alloc[pid]; pcb.resources_held = dict(self.allocation[pid]); return True
            return False
    def release_resources(self, pcb):
        with self._lock:
            pid = pcb.pid
            if pid in self.allocation:
                for r, qty in self.allocation[pid].items(): self.available[r] = self.available.get(r,0) + qty
                del self.allocation[pid]
            if pid in self.max_need: del self.max_need[pid]
            pcb.resources_held = {}
    def deadlock_recover(self, all_pcbs):
        _priority = [JobType.PRACTICE, JobType.RESEARCH, JobType.EXAM, JobType.EVALUATION]
        candidates = sorted([p for p in all_pcbs if p.state is not State.EXIT and p.pid in self.allocation], key=lambda p: _priority.index(p.job_type) if p.job_type in _priority else 99)
        terminated = []
        for pcb in candidates:
            self.release_resources(pcb); pcb.state = State.EXIT; terminated.append(pcb.pid)
            if not self.allocation: break
            need_map = {p: {r: self.max_need.get(p,{}).get(r,0) - self.allocation[p].get(r,0) for r in self.available} for p in self.allocation}
            if _is_safe(self.available, self.allocation, need_map, list(self.allocation.keys())): break
        return terminated

_resource_manager = ResourceManager()
def request_resources(pcb, request_dict): return _resource_manager.request_resources(pcb, request_dict)
def release_resources(pcb): _resource_manager.release_resources(pcb)
def deadlock_recover(all_pcbs): return _resource_manager.deadlock_recover(all_pcbs)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'acados.db')
def create_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS job_log (pid INTEGER PRIMARY KEY, user_id INTEGER, role TEXT, job_type TEXT, cpu_used INTEGER, start_time REAL, end_time REAL, missed_deadline INTEGER)')
    conn.commit(); conn.close()

class AcadosSemaphore:
    def __init__(self): self.readers_count = 0; self.mutex = threading.Lock(); self.write_lock = threading.Lock()
    def db_read(self, pid):
        with self.mutex:
            self.readers_count += 1
            if self.readers_count == 1: self.write_lock.acquire()
        try:
            conn = sqlite3.connect(_DB_PATH); cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_log WHERE pid = ?", (pid,)); row = cursor.fetchone(); conn.close(); return row
        finally:
            with self.mutex:
                self.readers_count -= 1
                if self.readers_count == 0: self.write_lock.release()
    def db_write(self, pid, data):
        with self.write_lock:
            conn = sqlite3.connect(_DB_PATH); cursor = conn.cursor()
            cols = ', '.join(data.keys()); placeholders = ', '.join(['?'] * len(data))
            cursor.execute(f"INSERT OR REPLACE INTO job_log (pid, {cols}) VALUES (?, {placeholders})", (pid, *data.values()))
            conn.commit(); conn.close()

_semaphore = AcadosSemaphore()
def db_read(pid): return _semaphore.db_read(pid)
def db_write(pid, data): _semaphore.db_write(pid, data)