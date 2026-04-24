import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shared import PCB, JobType


class MemoryManager:
    def __init__(self):
        self.total_frames = 32
        self.free_frames = list(range(32))
        self.page_table = {}
        self.tlb = {}
        self.lru_tracker = {}
        self.swap_space = {}
        self.fault_counters = {}
        self.page_owners = {}

    def allocate_pages(self, pcb, num_pages):
        if len(self.free_frames) < num_pages:
            self._deadline_replace(num_pages - len(self.free_frames))
        if len(self.free_frames) < num_pages:
            raise MemoryError(f"Not enough free frames: need {num_pages}, have {len(self.free_frames)}")
        if pcb.pid not in self.page_table:
            self.page_table[pcb.pid] = {}
        for i in range(num_pages):
            frame = self.free_frames.pop(0)
            virtual_page = len(self.page_table[pcb.pid])
            self.page_table[pcb.pid][virtual_page] = frame
            self.page_owners[(pcb.pid, virtual_page)] = pcb.job_type
        return True

    def access_page(self, pcb, virtual_page, tick=0):
        key = (pcb.pid, virtual_page)
        if key in self.tlb:
            self.lru_tracker[key] = tick
            return self.tlb[key]
        if pcb.pid in self.page_table and virtual_page in self.page_table[pcb.pid]:
            frame = self.page_table[pcb.pid][virtual_page]
            if len(self.tlb) >= 8:
                lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
                del self.tlb[lru_key]
            self.tlb[key] = frame
            self.lru_tracker[key] = tick
            return frame
        return self._page_fault_handler(pcb, virtual_page, tick)

    def free_pages(self, pcb):
        if pcb.pid not in self.page_table:
            return
        frames = list(self.page_table[pcb.pid].values())
        self.free_frames.extend(frames)
        self.free_frames.sort()
        del self.page_table[pcb.pid]
        for k in [k for k in self.tlb if k[0] == pcb.pid]: del self.tlb[k]
        for k in [k for k in self.lru_tracker if k[0] == pcb.pid]: del self.lru_tracker[k]
        for k in [k for k in self.swap_space if k[0] == pcb.pid]: del self.swap_space[k]
        for k in [k for k in self.page_owners if k[0] == pcb.pid]: del self.page_owners[k]

    def _deadline_replace(self, num_needed):
        priority_order = [JobType.PRACTICE, JobType.RESEARCH, JobType.EXAM, JobType.EVALUATION]
        candidates = []
        for pid, pages_dict in self.page_table.items():
            for vpage, frame in pages_dict.items():
                key = (pid, vpage)
                job_type = self.page_owners.get(key, JobType.PRACTICE)
                lru_time = self.lru_tracker.get(key, 0)
                pri = priority_order.index(job_type) if job_type in priority_order else 999
                candidates.append({'key': key, 'pid': pid, 'vpage': vpage, 'frame': frame, 'priority': pri, 'lru_time': lru_time})
        candidates.sort(key=lambda x: (x['priority'], x['lru_time']))
        evicted = 0
        for c in candidates:
            if evicted >= num_needed: break
            key, pid, vpage, frame = c['key'], c['pid'], c['vpage'], c['frame']
            self.swap_space[key] = 'data'
            del self.page_table[pid][vpage]
            if key in self.tlb: del self.tlb[key]
            self.free_frames.append(frame)
            self.free_frames.sort()
            evicted += 1

    def _page_fault_handler(self, pcb, vpage, tick=0):
        key = (pcb.pid, vpage)
        job_name = pcb.job_type.name
        self.fault_counters[job_name] = self.fault_counters.get(job_name, 0) + 1
        if not self.free_frames:
            self._deadline_replace(1)
        if not self.free_frames:
            raise MemoryError("No free frames after eviction")
        frame = self.free_frames.pop(0)
        if key in self.swap_space: del self.swap_space[key]
        if pcb.pid not in self.page_table: self.page_table[pcb.pid] = {}
        self.page_table[pcb.pid][vpage] = frame
        self.page_owners[key] = pcb.job_type
        if len(self.tlb) >= 8:
            lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
            del self.tlb[lru_key]
        self.tlb[key] = frame
        self.lru_tracker[key] = tick
        return frame

    def plot_page_faults(self, acados_faults, lru_faults):
        os.makedirs('outputs', exist_ok=True)
        job_types = sorted(set(list(acados_faults.keys()) + list(lru_faults.keys())))
        x = range(len(job_types))
        width = 0.35
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar([i - width/2 for i in x], [acados_faults.get(jt, 0) for jt in job_types], width, label='AcadOS')
        ax.bar([i + width/2 for i in x], [lru_faults.get(jt, 0) for jt in job_types], width, label='LRU')
        ax.set_xlabel('Job Type'); ax.set_ylabel('Page Faults')
        ax.set_title('Page Faults Comparison'); ax.set_xticks(list(x)); ax.set_xticklabels(job_types); ax.legend()
        plt.tight_layout(); plt.savefig('outputs/page_faults.png'); plt.close()

_memory_manager = MemoryManager()

def allocate_pages(pcb, num_pages): return _memory_manager.allocate_pages(pcb, num_pages)
def access_page(pcb, virtual_page, tick=0): return _memory_manager.access_page(pcb, virtual_page, tick)
def free_pages(pcb): _memory_manager.free_pages(pcb)
def plot_page_faults(a, l): _memory_manager.plot_page_faults(a, l)