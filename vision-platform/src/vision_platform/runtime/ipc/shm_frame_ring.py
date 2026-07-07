"""SHM frame ring buffer cho multi-process frame transport.

Layer: runtime/ipc — đây là TRANSPORT (I/O concern), không phải DTO. Vì vậy
nó nằm ở runtime/, KHÔNG ở kernel/ (kernel cấm import multiprocessing — đã ép bằng
import-linter, xem pyproject.toml contract "Kernel ..."). DTO mô tả frame
(`ShmFrameRefData`) ở kernel/shm_frame_ref.py và được import vào đây.

Model:
- N slots, mỗi slot có metadata (state, generation) + data buffer.
- Writer (camera process) write frame vào slot FREE/DONE.
- Reader (inference/consumer process) read frame qua expected_gen check.
- Per-slot multiprocessing.Lock cho serialization.

Simplified vs production (Vision_platform_architecture_design):
- Header layout = v2 (kernel/shm_layout.py, 256B) từ Task 2.2 + ctrl segment fail-fast attach.
  NHƯNG các field v2 (lease/owner_create_time/reader_registry) CHƯA được code dùng (bật ở Task 3+).
- Không có lease deadlines (writer/reader timeout) → xem F-3/ERRATA E-15 dưới.
- Không có QUARANTINED state active (đã định nghĩa trong enum; recovery bật ở Task 3/4).
- Không có reader_count multi-reader pinning (Task 5).
- Đủ để học pattern. Vị trí layer (runtime/ipc) thì GIỐNG production.

INVARIANT QUAN TRỌNG (brief #05 F-4): `generation` là WRITER-LOCAL (mỗi ShmFrameWriter
đếm riêng từ 1). Do đó MỘT ring chỉ an toàn với DUY NHẤT 1 writer (model "1 camera = 1
process"). Nhiều writer/ring → trùng generation → vỡ ABA prevention. KHÔNG dùng 1 ring cho >1 writer.

ERRATA E-15 (brief #05 F-3, = Finding F2): nếu writer acquire-lock LẦN 2 (commit READY)
bị timeout, slot kẹt `WRITING` vĩnh viễn (demo không có lease/quarantine để hồi phục).
Rollback cũng cần lock — không giải được nếu lock poison. Production cần lease-timeout +
QUARANTINED state (việc riêng, ngoài scope step-05).

ERRATA E-15 F-3b (ĐỐI XỨNG, phát hiện khi re-review Pha 2): `ShmFrameReader.read` cũng vậy —
nếu acquire-lock LẦN 2 (mark DONE) timeout → `return frame_copy` nhưng slot kẹt `READING`
vĩnh viễn (writer chỉ tái dùng FREE/DONE). Cùng GỐC + cùng cách giải (lease/quarantine ở
production) như F-3. Demo chấp nhận giới hạn này.
"""
from __future__ import annotations
import multiprocessing as mp
import struct
import sys
import time
import uuid
from multiprocessing import shared_memory
from typing import Callable, Optional
import numpy as np

from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.kernel.shm_layout import (
    SlotState,
    SLOT_HEADER_V2_BYTES, MAX_READERS,
    OFFSET_STATE, STATE_FMT,
    OFFSET_GENERATION, OFFSET_OWNER_PID, OFFSET_OWNER_CREATE_TIME_NS,
    OFFSET_LEASE_DEADLINE_NS, U64_FMT,
    OFFSET_READER_COUNT, COUNT_FMT, READER_ENTRY_FMT, reader_entry_offset,
    RING_CONTROL_BYTES, CTRL_SEGMENT_BYTES, pack_ring_control, check_ring_control,
    OFFSET_WRITER_PID, OFFSET_WRITER_CREATE_TIME_NS, OFFSET_WRITER_LEASE_NS, OFFSET_RING_EPOCH,
)
from vision_platform.runtime.ipc._process_identity import (
    current_identity, owner_liveness, Liveness,
)


class ReaderRegistryFull(RuntimeError):
    """Slot đã đủ MAX_READERS reader pin — fail-fast, KHÔNG spin (Req 3.4 / P1-2)."""


class SingleWriterViolation(RuntimeError):
    """Vi phạm bất biến 1-writer/ring (Req 5 / P1-3): gọi register_writer >1 hoặc ring đã có writer sống/cần rebuild."""


class ObservabilityHook:
    """Hook quan sát sự kiện SHM (Task 6 / P-2). Mặc định NO-OP — thay cho `except: pass` im lặng.

    Taxonomy sự kiện (P2-2): shm_slot_lock_timeout · shm_slot_quarantined · shm_reader_registry_full ·
    shm_reader_reaped · shm_owner_liveness_unknown · shm_ring_capacity_degraded · shm_ring_rebuild_requested.
    Bản này chỉ là callback; structlog đầy đủ để dành #08. Override `emit` để nối logging/metric thật.
    """
    def emit(self, event: str, **fields) -> None:  # noqa: D401 - no-op mặc định
        pass


class StderrObservabilityHook(ObservabilityHook):
    """Hook in ra stderr (dùng khi debug/vận hành nhẹ)."""
    def emit(self, event: str, **fields) -> None:
        print(f"[shm-obs] {event} {fields}", file=sys.stderr)

# SlotState giờ là 1 nguồn sự thật ở kernel/shm_layout (header v2). Re-export để API #05 cũ không đổi.
__all__ = ["SlotState", "ShmRingBuffer", "ShmFrameWriter", "ShmFrameReader"]

SLOT_HEADER_BYTES = SLOT_HEADER_V2_BYTES   # 256B (header v2, thay 32B v1)

# Lease (chốt Codex câu 4): chỉ là CHỈ BÁO kích hoạt recovery khi quá hạn, KHÔNG tự kill.
# Bao pin/copy/unpin, KHÔNG bao model inference. Config (không hard-code rải rác).
WRITE_LEASE_NS = 2_000_000_000   # 2s
READ_LEASE_NS = 2_000_000_000    # 2s
# TÁCH khỏi lease: timeout chờ acquire lock 1 slot trên đường scan realtime. Quá hạn → nghi poison → recovery.
LOCK_ACQUIRE_TIMEOUT_S = 0.1


def new_ring_name(prefix: str = "vp_ring") -> str:
    """Tên ring DUY NHẤT mỗi phiên (Task 9 / cold-start sanitation, R-5.1, P1-4).

    Dùng uuid → creator KHÔNG bao giờ attach segment cũ còn sót từ phiên crash trước (mỗi phiên name khác).
    LƯU Ý nền tảng: `SharedMemory.unlink()` KHÔNG tác dụng trên Windows (block mất khi mọi handle đóng);
    POSIX unlink chặn attach mới nhưng memory sống tới handle cuối. => KHÔNG dựa unlink để dọn — dựa tên epoch/uuid.
    Well-known name (nếu cần) chỉ trỏ control-plane nhỏ; data ring dùng tên này.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


def _read_header(buf) -> tuple[int, int, int]:
    """Đọc (state, generation, owner_pid) từ header v2. GỌI DƯỚI LOCK (đa-byte, không atomic)."""
    state = struct.unpack_from(STATE_FMT, buf, OFFSET_STATE)[0]
    gen = struct.unpack_from(U64_FMT, buf, OFFSET_GENERATION)[0]
    pid = struct.unpack_from(U64_FMT, buf, OFFSET_OWNER_PID)[0]
    return state, gen, pid


def _read_owner(buf) -> tuple[int, int]:
    """Đọc định danh owner (pid, create_time_ns). GỌI DƯỚI LOCK / hoặc trong snapshot recovery."""
    pid = struct.unpack_from(U64_FMT, buf, OFFSET_OWNER_PID)[0]
    create_time_ns = struct.unpack_from(U64_FMT, buf, OFFSET_OWNER_CREATE_TIME_NS)[0]
    return pid, create_time_ns


def _read_lease(buf) -> int:
    """Đọc lease_deadline_ns. GỌI DƯỚI LOCK / hoặc trong snapshot recovery."""
    return struct.unpack_from(U64_FMT, buf, OFFSET_LEASE_DEADLINE_NS)[0]


def _full_snapshot(buf) -> bytes:
    """Chụp TOÀN header (state+gen+owner+lease+reader_registry) cho double-snapshot recovery (P1-1).

    Đọc KHÔNG có lock (lock đang kẹt). Gọi 2 lần liên tiếp; chỉ hành động nếu 2 snapshot GIỐNG nhau (bytes).
    """
    return bytes(buf[:SLOT_HEADER_V2_BYTES])


# ---- Reader registry (P-3 / P1-2): reader_count là DẪN XUẤT từ số ô active ----

def _registry_entry(buf, idx: int) -> tuple[int, int, int]:
    """(reader_pid, reader_create_time_ns, reader_lease_ns) tại ô idx. pid==0 = ô trống."""
    return struct.unpack_from(READER_ENTRY_FMT, buf, reader_entry_offset(idx))


def _registry_set(buf, idx: int, pid: int, ct: int, lease_ns: int) -> None:
    struct.pack_into(READER_ENTRY_FMT, buf, reader_entry_offset(idx), pid, ct, lease_ns)


def _registry_clear(buf, idx: int) -> None:
    _registry_set(buf, idx, 0, 0, 0)


def _registry_find_free(buf) -> Optional[int]:
    for i in range(MAX_READERS):
        if _registry_entry(buf, i)[0] == 0:
            return i
    return None


def _registry_find(buf, pid: int, ct: int) -> Optional[int]:
    for i in range(MAX_READERS):
        p, c, _ = _registry_entry(buf, i)
        if p == pid and c == ct:
            return i
    return None


def _registry_count(buf) -> int:
    return sum(1 for i in range(MAX_READERS) if _registry_entry(buf, i)[0] != 0)


def _write_reader_count(buf, n: int) -> None:
    struct.pack_into(COUNT_FMT, buf, OFFSET_READER_COUNT, n)


def _read_reader_count(buf) -> int:
    return struct.unpack_from(COUNT_FMT, buf, OFFSET_READER_COUNT)[0]


def _reap_dead_readers(buf, liveness_fn, obs=None, ring_name: str = "", slot_idx: int = -1) -> int:
    """Xoá các ô reader CHẾT (lease quá hạn VÀ liveness==DEAD). GỌI DƯỚI LOCK. Trả reader_count mới.

    KHÔNG xoá reader còn-hiệu-lực (lease chưa hết) hoặc còn sống/unknown → giải R-2.2.
    """
    now = time.monotonic_ns()
    for i in range(MAX_READERS):
        pid, ct, lease = _registry_entry(buf, i)
        if pid != 0 and now >= lease and liveness_fn(pid, ct) is Liveness.DEAD:
            _registry_clear(buf, i)
            if obs is not None:
                obs.emit("shm_reader_reaped", ring_name=ring_name, slot=slot_idx,
                         owner_pid=pid, owner_create_time_ns=ct)
    n = _registry_count(buf)
    _write_reader_count(buf, n)
    return n


def _reader_protects_slot(buf, liveness_fn) -> bool:
    """True nếu có ≥1 reader CÒN HIỆU LỰC (lease chưa hết HOẶC còn sống/unknown) → KHÔNG được quarantine slot."""
    now = time.monotonic_ns()
    for i in range(MAX_READERS):
        pid, ct, lease = _registry_entry(buf, i)
        if pid == 0:
            continue
        if now < lease:
            return True
        if liveness_fn(pid, ct) is not Liveness.DEAD:
            return True
    return False


def _write_header(
    buf, state: int, gen: int, pid: int,
    create_time_ns: int = 0, lease_deadline_ns: int = 0,
) -> None:
    """Ghi header v2. GỌI DƯỚI LOCK.

    Thứ tự: identity (gen, pid, create_time) + lease TRƯỚC → `state` GHI CUỐI (authority — Req 7.5/P1-1).
    """
    struct.pack_into(U64_FMT, buf, OFFSET_GENERATION, gen)
    struct.pack_into(U64_FMT, buf, OFFSET_OWNER_PID, pid)
    struct.pack_into(U64_FMT, buf, OFFSET_OWNER_CREATE_TIME_NS, create_time_ns)
    struct.pack_into(U64_FMT, buf, OFFSET_LEASE_DEADLINE_NS, lease_deadline_ns)
    struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(state))


class ShmRingBuffer:
    """Per-slot lock variant SHM ring buffer.

    Architecture:
        Each slot = (meta SHM, data SHM) pair + 1 multiprocessing.Lock.
        Locks are passed cross-process via Process(args=...).

    Lifecycle:
        - Parent (creator) calls __init__(create=True).
        - Child processes call __init__(create=False, slot_locks=parent.slot_locks_for_children).
        - cleanup_all() unlinks all SHM segments. Parent only.
    """

    def __init__(
        self,
        name: str,
        n_slots: int,
        height: int,
        width: int,
        channels: int = 3,
        *,
        create: bool,
        slot_locks: Optional[list[mp.synchronize.Lock]] = None,
        liveness_fn: Callable[[int, int], Liveness] = owner_liveness,
        obs: Optional[ObservabilityHook] = None,
        ring_epoch: int = 1,
        rebuild_threshold: Optional[int] = None,
    ):
        self.name = name
        self.n_slots = n_slots
        self.height = height
        self.width = width
        self.channels = channels
        self._liveness_fn = liveness_fn   # tiêm được để test recovery (mặc định psutil)
        self._obs = obs if obs is not None else ObservabilityHook()   # mặc định no-op (P-2)
        self._writer_registered = False   # intra-process guard cho register_writer (Req 5.1)
        # REBUILD_THRESHOLD (Task 10): số slot quarantine để phát rebuild_requested. Default thận trọng
        # = nửa số slot (làm tròn lên, tối thiểu 1). 🔴 cần tuning theo SLA production thật.
        self._rebuild_threshold = rebuild_threshold if rebuild_threshold is not None else max(1, (n_slots + 1) // 2)
        self._frame_bytes = height * width * channels  # uint8
        self._meta_shms: list[shared_memory.SharedMemory] = []
        self._data_shms: list[shared_memory.SharedMemory] = []
        self._ctrl_shm: Optional[shared_memory.SharedMemory] = None

        # Locks: parent creates, children receive via args.
        if slot_locks is not None:
            if len(slot_locks) != n_slots:
                raise ValueError(
                    f"slot_locks length {len(slot_locks)} != n_slots {n_slots}"
                )
            self._slot_locks = slot_locks
        elif create:
            self._slot_locks = [mp.Lock() for _ in range(n_slots)]
        else:
            raise RuntimeError(
                "create=False requires slot_locks from parent process."
            )

        # Ring-level control segment (self-describing, fail-fast attach). Tạo/attach TRƯỚC slot:
        # attach sai magic/version/header_size/max_readers → raise NGAY, không đụng slot rác.
        ctrl_name = f"{name}_ctrl"
        if create:
            ctrl = shared_memory.SharedMemory(name=ctrl_name, create=True, size=CTRL_SEGMENT_BYTES)
            ctrl.buf[:RING_CONTROL_BYTES] = pack_ring_control()
            struct.pack_into(U64_FMT, ctrl.buf, OFFSET_RING_EPOCH, ring_epoch)   # P0-3: ghi epoch ring
            # writer registry (offset 16..39) = 0 do zero-init → "chưa có writer".
        else:
            ctrl = shared_memory.SharedMemory(name=ctrl_name)
            check_ring_control(bytes(ctrl.buf[:RING_CONTROL_BYTES]))   # fail-fast nếu mismatch
        self._ctrl_shm = ctrl

        # Allocate (or attach to) SHM segments.
        for i in range(n_slots):
            meta_name = f"{name}_meta_{i}"
            data_name = f"{name}_data_{i}"
            if create:
                meta = shared_memory.SharedMemory(
                    name=meta_name, create=True, size=SLOT_HEADER_BYTES,
                )
                data = shared_memory.SharedMemory(
                    name=data_name, create=True, size=self._frame_bytes,
                )
                # Initialize header to FREE state, gen=0 (các field v2 khác = 0 do zero-init).
                _write_header(meta.buf, SlotState.FREE, 0, 0)
            else:
                meta = shared_memory.SharedMemory(name=meta_name)
                data = shared_memory.SharedMemory(name=data_name)
            self._meta_shms.append(meta)
            self._data_shms.append(data)

    def slot_lock(self, slot_idx: int) -> mp.synchronize.Lock:
        return self._slot_locks[slot_idx]

    def peek_state(self, slot_idx: int) -> int:
        """Đọc trường `state` (4B @offset0) LOCK-FREE atomic (x86-64 aligned ≤8B store atomic).

        Dùng để bỏ qua slot QUARANTINED (terminal) TRƯỚC khi acquire lock — không bao giờ đụng
        lock có thể đã poison. Sticky: QUARANTINED không tự revert nên peek an toàn.
        """
        return struct.unpack_from(STATE_FMT, self._meta_shms[slot_idx].buf, OFFSET_STATE)[0]

    def _quarantined_count(self) -> int:
        return sum(1 for i in range(self.n_slots) if self.peek_state(i) == SlotState.QUARANTINED)

    def _healthy_slots(self) -> int:
        return self.n_slots - self._quarantined_count()

    @property
    def ring_epoch(self) -> int:
        """Epoch hiện tại của ring (P0-3). Reader so với ref.ring_epoch để phát hiện stale sau switchover."""
        return struct.unpack_from(U64_FMT, self._ctrl_shm.buf, OFFSET_RING_EPOCH)[0]

    def _read_writer(self) -> tuple[int, int]:
        """Đọc (writer_pid, writer_create_time_ns) từ control segment. (0,0) = chưa có writer."""
        ctrl = self._ctrl_shm.buf
        pid = struct.unpack_from(U64_FMT, ctrl, OFFSET_WRITER_PID)[0]
        ct = struct.unpack_from(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS)[0]
        return pid, ct

    def register_writer(self, pid: Optional[int] = None, create_time_ns: Optional[int] = None) -> None:
        """Đăng ký writer DUY NHẤT của ring (Req 5 / P1-3). Gọi ở composition-root lúc setup.

        - Gọi >1 lần trong process này → SingleWriterViolation (Req 5.1).
        - Ring đã có writer ALIVE (create_time khớp) → reject (Req 5.3).
        - Writer cũ DEAD → emit `shm_ring_rebuild_requested` + reject (KHÔNG takeover im lặng — Req 5.4).
        - UNKNOWN → reject (không claim khi không chắc).
        - Trống → claim (ghi pid/create_time/lease vào control segment).

        Giả định: registration ở startup (composition root điều phối), KHÔNG đăng ký đồng thời từ nhiều
        process cùng một micro-giây. Tái-đăng-ký (worker chết → worker mới) được bảo vệ bằng liveness.
        """
        if pid is None or create_time_ns is None:
            pid, create_time_ns = current_identity()
        if self._writer_registered:
            raise SingleWriterViolation("register_writer() gọi >1 lần trong process này (Req 5.1)")

        cur_pid, cur_ct = self._read_writer()
        if cur_pid != 0:
            liveness = self._liveness_fn(cur_pid, cur_ct)
            if liveness is Liveness.ALIVE:
                raise SingleWriterViolation(f"ring đã có writer còn sống pid={cur_pid} (Req 5.3)")
            if liveness is Liveness.UNKNOWN:
                raise SingleWriterViolation(f"writer hiện tại pid={cur_pid} trạng thái UNKNOWN — không claim")
            # DEAD → KHÔNG takeover im lặng; yêu cầu rebuild (Req 5.4)
            self._obs.emit("shm_ring_rebuild_requested", ring_name=self.name,
                           reason="writer_dead", dead_writer_pid=cur_pid)
            raise SingleWriterViolation(f"writer cũ pid={cur_pid} đã chết — cần rebuild ring, KHÔNG takeover")

        ctrl = self._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, pid)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, create_time_ns)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_LEASE_NS, time.monotonic_ns() + WRITE_LEASE_NS)
        self._writer_registered = True

    def quarantine_poisoned_slot(self, slot_idx: int) -> bool:
        """Cố quarantine 1 slot NGHI poison (gọi khi acquire-lock timeout — KHÔNG có lock).

        Quy tắc an toàn (design §Error Handling, Property 3/4, P1-1, R-2.2):
        - **WRITING**: owner = writer (owner_pid@16). Quarantine khi owner DEAD VÀ lease quá hạn.
        - **READING**: KHÔNG dùng owner_pid đơn lẻ (đa reader) → quét reader_registry; chỉ quarantine khi
          KHÔNG còn reader nào còn-hiệu-lực (mọi ô đều lease-quá-hạn VÀ DEAD). Còn reader sống → KHÔNG quarantine.
        - Double-snapshot TOÀN header (P1-1): 2 lần liên tiếp phải GIỐNG (bytes) mới hành động.
        - QUARANTINED là TERMINAL (atomic 4B). KHÔNG đụng lock (có thể đã poison).
        - now/lease so monotonic_ns: system-wide/boot → cross-process OK; cộng điều kiện DEAD nên robust.

        Trả True nếu vừa quarantine; False nếu không.
        """
        buf = self._meta_shms[slot_idx].buf
        if struct.unpack_from(STATE_FMT, buf, OFFSET_STATE)[0] == SlotState.QUARANTINED:
            return False   # đã terminal

        snap1 = _full_snapshot(buf)
        snap2 = _full_snapshot(buf)
        if snap1 != snap2:
            return False   # torn / đang đổi → KHÔNG quarantine, thử lại sau (P1-1)

        state = struct.unpack_from(STATE_FMT, buf, OFFSET_STATE)[0]
        now = time.monotonic_ns()

        if state in (SlotState.WRITING, SlotState.READY):
            # WRITING/READY: owner = writer (owner_pid@16, set khi mark WRITING/READY). Quarantine khi DEAD+lease quá hạn.
            owner_pid, owner_create_time_ns = _read_owner(buf)
            if now < _read_lease(buf):
                return False   # còn trong lease → owner có thể đang bận hợp lệ
            liveness = self._liveness_fn(owner_pid, owner_create_time_ns)
            if liveness is Liveness.UNKNOWN:
                self._obs.emit("shm_owner_liveness_unknown", ring_name=self.name, slot=slot_idx,
                               state=int(state), owner_pid=owner_pid, owner_create_time_ns=owner_create_time_ns)
                return False
            if liveness is not Liveness.DEAD:
                return False   # ALIVE → KHÔNG quarantine
        elif state == SlotState.READING:
            if _reader_protects_slot(buf, self._liveness_fn):
                return False   # còn ≥1 reader sống/còn-lease → KHÔNG quarantine (R-2.2)
        else:
            return False       # FREE/DONE/khác → không phải slot bị giữ

        struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.QUARANTINED))  # atomic 4B, terminal
        q = self._quarantined_count()
        self._obs.emit("shm_slot_quarantined", ring_name=self.name, slot=slot_idx, state=int(state),
                       quarantined_count=q, healthy_slots=self.n_slots - q)
        self._obs.emit("shm_ring_capacity_degraded", ring_name=self.name,
                       quarantined_count=q, healthy_slots=self.n_slots - q)
        if q >= self._rebuild_threshold:
            # Task 10: quá ngưỡng → yêu cầu control-plane rebuild (KHÔNG tự rebuild ở per-slot).
            self._obs.emit("shm_ring_rebuild_requested", ring_name=self.name, reason="threshold",
                           quarantined_count=q, threshold=self._rebuild_threshold, ring_epoch=self.ring_epoch)
        return True

    @property
    def slot_locks_for_children(self) -> list[mp.synchronize.Lock]:
        return self._slot_locks

    def cleanup_all(self) -> None:
        """Close + unlink all SHM segments (gồm ctrl). Call from creator process only."""
        segments = list(self._meta_shms) + list(self._data_shms)
        if self._ctrl_shm is not None:
            segments.append(self._ctrl_shm)
        for shm in segments:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self._meta_shms.clear()
        self._data_shms.clear()
        self._ctrl_shm = None

    def close(self) -> None:
        """Đóng SHM handle của process NÀY (KHÔNG unlink) — dùng cho consumer rời ring khi switchover epoch.

        Teardown quyết định B (sub-spec shm-ring-epoch-switchover): OS ref-count handle → segment giải phóng
        khi HANDLE CUỐI đóng. Consumer chỉ `close()` (không unlink, vì không phải creator). Creator muốn xoá
        hẳn dùng `cleanup_all()`. Sau `close()` ring object không dùng lại được.
        """
        segments = list(self._meta_shms) + list(self._data_shms)
        if self._ctrl_shm is not None:
            segments.append(self._ctrl_shm)
        for shm in segments:
            try:
                shm.close()
            except Exception:
                pass
        self._meta_shms.clear()
        self._data_shms.clear()
        self._ctrl_shm = None

    def reset_for_reuse(self, new_epoch: int) -> bool:
        """Reset ring để TÁI DÙNG cho epoch mới (H2 ring-pool, K-012). CREATOR-only. Trả True nếu reset,
        False nếu BỊ CHẶN vì ring chưa drain (còn reader hiệu lực — Fix A, K-015).

        Dùng khi supervisor tái dùng một pool ring cho switchover: xoá MỌI slot về FREE (gồm QUARANTINED —
        đúng mục đích rebuild), xoá reader registry + writer registry, rồi bump `ring_epoch` (đơn điệu, GHI
        CUỐI). Sau reset: writer mới `register_writer()` + ghi từ đầu được; ref epoch cũ thành stale (ring_epoch
        đổi → reader trả None). KHÔNG cấp phát SHM/lock mới (đó là điểm mấu chốt H2 — giải K-012 bằng né
        cấp-phát-động; lock giữ nguyên, mọi worker đã thừa kế từ startup).

        DRAIN-BEFORE-REUSE nay được CƯỠNG CHẾ (Fix A, K-015): reap reader chết trước; nếu còn reader hiệu lực
        ở bất kỳ slot → REFUSE (return False, chưa đụng gì) + emit `shm_reset_blocked_active_readers`. KHÔNG
        còn dựa contract ngầm. acquire lock best-effort (không bị chặn bởi lock của owner đã chết).

        ⚠️ INVARIANT AN-TOÀN SỐNG-CÒN (audit K-026 — làm EXPLICIT, đừng phá): giữa pass-guard và pass-clear có
        cửa sổ TOCTOU (release lock slot rồi acquire lại). Cửa sổ này CHỈ an toàn vì CALLER (RingPool.activate)
        chỉ reset ring KHÔNG-hiện-hành: `pool.activate(N)` reset `pool[N%K]` (epoch N-K), còn control-plane vẫn
        trỏ epoch N-1 = `pool[(N-1)%K]`. Với `pool_size >= 2` (RingPool cưỡng chế), ring-reset ≠ ring-hiện-hành
        → KHÔNG reader mới nào (đi theo control-plane) tới ring đang reset trong cửa sổ đó. NẾU ai đó gọi
        `reset_for_reuse` lên ring ĐANG published khi có reader → TOCTOU thành torn-frame. → CHỈ gọi qua
        RingPool (pool_size>=2), TUYỆT ĐỐI không reset ring hiện hành."""
        if self._ctrl_shm is None:
            raise RuntimeError("reset_for_reuse: ring đã đóng / không phải creator")
        cur = self.ring_epoch
        if new_epoch <= cur:
            raise ValueError(f"ring_epoch phải đơn điệu tăng: new={new_epoch} <= cur={cur}")

        # 0) DRAIN GUARD (Fix A, K-015): CƯỠNG CHẾ drain-before-reuse (không dựa contract ngầm).
        # Reap reader chết trước, rồi nếu còn reader CÒN HIỆU LỰC ở bất kỳ slot → KHÔNG reset (tránh torn
        # frame: reset xoá reader_count vô điều kiện sẽ bỏ qua bảo vệ mà reader copy-ngoài-lock đang dựa vào).
        # Refuse toàn phần (chưa đụng gì) + emit → caller hoãn switchover, thử lại sau (defer+retry).
        for i in range(self.n_slots):
            lock = self._slot_locks[i]
            acquired = lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S)
            try:
                buf = self._meta_shms[i].buf
                _reap_dead_readers(buf, self._liveness_fn, self._obs, self.name, i)
                if _reader_protects_slot(buf, self._liveness_fn):
                    self._obs.emit("shm_reset_blocked_active_readers", ring_name=self.name,
                                   slot=i, new_epoch=new_epoch, reader_count=_read_reader_count(buf))
                    return False   # chưa drain → KHÔNG reset (an toàn); caller retry lần sau
            finally:
                if acquired:
                    lock.release()

        # 1) Xoá mọi slot về FREE (gồm QUARANTINED) + reader registry + count (best-effort lock).
        for i in range(self.n_slots):
            lock = self._slot_locks[i]
            acquired = lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S)
            try:
                buf = self._meta_shms[i].buf
                for r in range(MAX_READERS):
                    _registry_clear(buf, r)
                _write_reader_count(buf, 0)
                _write_header(buf, SlotState.FREE, 0, 0)   # state ghi CUỐI, gen=0
            finally:
                if acquired:
                    lock.release()

        # 2) Xoá writer registry (control segment) → ring "chưa có writer".
        ctrl = self._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, 0)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, 0)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_LEASE_NS, 0)

        # 3) Bump ring_epoch — GHI CUỐI (authority): bên khác thấy epoch mới = ring đã reset xong.
        struct.pack_into(U64_FMT, ctrl, OFFSET_RING_EPOCH, new_epoch)
        self._writer_registered = False
        self._obs.emit("shm_ring_reset_for_reuse", ring_name=self.name, new_epoch=new_epoch)
        return True


class ShmFrameWriter:
    """Camera-side SHM writer.

    Strategy: round-robin slot scan, write to first FREE/DONE slot.
    NEVER overwrites READY (would silently drop).

    INVARIANT (F-4): generation là writer-local → 1 writer/ring. KHÔNG tạo 2 writer trên cùng ring.
    """

    def __init__(self, ring: ShmRingBuffer):
        self._ring = ring
        self._next_slot = 0
        self._next_generation = 1
        # Định danh (pid, create_time_ns) cache 1 lần — không đổi trong đời process; tránh gọi psutil mỗi frame.
        self._pid, self._create_time_ns = current_identity()
        self._ring_epoch = ring.ring_epoch   # stamp vào mọi ref để reader phát hiện stale (P0-3)

    def write(self, frame: np.ndarray) -> Optional[ShmFrameRefData]:
        """Write frame to next available slot.

        Returns ShmFrameRefData on success, None if all slots busy.
        """
        if frame.shape != (self._ring.height, self._ring.width, self._ring.channels):
            raise ValueError(
                f"Frame shape mismatch: got {frame.shape}, "
                f"expected ({self._ring.height}, {self._ring.width}, {self._ring.channels})"
            )
        # Hardening (brief #05 F-6): ring data buffer là uint8. dtype khác → np.copyto ép/cắt
        # ÂM THẦM → fail-fast thay vì hỏng lặng lẽ.
        if frame.dtype != np.uint8:
            raise ValueError(f"Frame dtype must be uint8, got {frame.dtype}")

        for attempt in range(self._ring.n_slots):
            slot_idx = (self._next_slot + attempt) % self._ring.n_slots

            # Bước 0 — lock-free peek: slot QUARANTINED là TERMINAL → bỏ qua, KHÔNG đụng lock (có thể poison).
            if self._ring.peek_state(slot_idx) == SlotState.QUARANTINED:
                continue

            lock = self._ring.slot_lock(slot_idx)

            if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
                # Acquire timeout → nghi lock poison → emit + thử recovery (quarantine nếu owner DEAD + lease quá hạn).
                self._ring._obs.emit("shm_slot_lock_timeout", ring_name=self._ring.name, slot=slot_idx)
                self._ring.quarantine_poisoned_slot(slot_idx)
                continue   # skip slot pass này (quarantine hay không, không dùng slot nghi ngờ)

            try:
                buf = self._ring._meta_shms[slot_idx].buf
                state, gen, _pid = _read_header(buf)

                # Available: FREE/DONE VÀ không còn reader pin (Req 3.6). NOT READY/READING (drop/đang đọc).
                if state not in (SlotState.FREE, SlotState.DONE) or _read_reader_count(buf) != 0:
                    continue

                # Mark WRITING.
                new_gen = self._next_generation
                self._next_generation += 1
                _write_header(
                    self._ring._meta_shms[slot_idx].buf,
                    SlotState.WRITING, new_gen, self._pid,
                    self._create_time_ns, time.monotonic_ns() + WRITE_LEASE_NS,
                )
            finally:
                lock.release()

            # Write data outside lock — slot is in WRITING, no one else touches.
            arr = np.ndarray(
                (self._ring.height, self._ring.width, self._ring.channels),
                dtype=np.uint8,
                buffer=self._ring._data_shms[slot_idx].buf,
            )
            np.copyto(arr, frame)

            # Commit READY.
            if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
                return None   # ERRATA E-15: owner=self còn sống nên KHÔNG quarantine; slot kẹt WRITING, caller xử lý
            try:
                _write_header(
                    self._ring._meta_shms[slot_idx].buf,
                    SlotState.READY, new_gen, self._pid,
                    self._create_time_ns, time.monotonic_ns() + WRITE_LEASE_NS,
                )
            finally:
                lock.release()

            self._next_slot = (slot_idx + 1) % self._ring.n_slots
            return ShmFrameRefData(
                ring_name=self._ring.name,
                slot=slot_idx,
                generation=new_gen,
                height=self._ring.height,
                width=self._ring.width,
                channels=self._ring.channels,
                ring_epoch=self._ring_epoch,
            )

        return None  # all slots busy → caller backpressures


class ShmFrameReader:
    """Reader side: pin slot, copy frame, mark DONE."""

    def __init__(self, ring: ShmRingBuffer):
        self._ring = ring
        # Định danh reader (pid, create_time_ns) cache 1 lần.
        self._pid, self._create_time_ns = current_identity()

    def read(self, slot_idx: int, expected_gen: int, *, ring_epoch: Optional[int] = None) -> Optional[np.ndarray]:
        """Pin slot (đa-reader qua registry), copy frame, unpin.

        Trả frame copy; None nếu gen mismatch (ABA) / slot không ở READY|READING / quarantined / không pin được
        / ring_epoch không khớp (stale sau switchover — P0-3). Raise ReaderRegistryFull nếu đầy.
        """
        # Stale-ref check (P0-3): ref cầm epoch cũ → ring đã switchover → KHÔNG đọc ring mới.
        if ring_epoch is not None and ring_epoch != self._ring.ring_epoch:
            return None

        lock = self._ring.slot_lock(slot_idx)

        # Bước 0 — lock-free peek: slot QUARANTINED (terminal) → KHÔNG đọc, không đụng lock.
        if self._ring.peek_state(slot_idx) == SlotState.QUARANTINED:
            return None

        # PIN: ghi 1 ô registry, reader_count = số ô active (dẫn xuất), state=READING.
        if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
            self._ring._obs.emit("shm_slot_lock_timeout", ring_name=self._ring.name, slot=slot_idx)
            self._ring.quarantine_poisoned_slot(slot_idx)
            return None
        try:
            buf = self._ring._meta_shms[slot_idx].buf
            state, gen, _pid = _read_header(buf)
            # Đa-reader: cho pin khi READY (reader đầu) HOẶC READING (reader thứ N). Gen phải khớp (ABA).
            if gen != expected_gen or state not in (SlotState.READY, SlotState.READING):
                return None
            _reap_dead_readers(buf, self._ring._liveness_fn, self._ring._obs, self._ring.name, slot_idx)
            free_idx = _registry_find_free(buf)
            if free_idx is None:
                self._ring._obs.emit("shm_reader_registry_full", ring_name=self._ring.name,
                                     slot=slot_idx, reader_count=_registry_count(buf))
                raise ReaderRegistryFull(
                    f"slot {slot_idx}: registry đầy (MAX_READERS={MAX_READERS})"
                )
            _registry_set(buf, free_idx, self._pid, self._create_time_ns,
                          time.monotonic_ns() + READ_LEASE_NS)
            _write_reader_count(buf, _registry_count(buf))
            struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.READING))  # state ghi cuối
        finally:
            lock.release()

        # COPY (ngoài lock — slot đang READING, writer không tái dùng khi reader_count>0).
        arr = np.ndarray(
            (self._ring.height, self._ring.width, self._ring.channels),
            dtype=np.uint8,
            buffer=self._ring._data_shms[slot_idx].buf,
        )
        frame_copy = arr.copy()

        # UNPIN: xoá ô của mình; reader_count==0 → DONE, còn reader → giữ READING.
        if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
            # Không unpin được; frame đã copy xong. Ô registry của mình còn lại → reader chết sau sẽ bị reap.
            return frame_copy
        try:
            buf = self._ring._meta_shms[slot_idx].buf
            ridx = _registry_find(buf, self._pid, self._create_time_ns)
            if ridx is not None:
                _registry_clear(buf, ridx)
            count = _registry_count(buf)
            _write_reader_count(buf, count)
            if count == 0:
                # reader cuối → clear owner/lease + DONE (DONE = không ai giữ; state ghi cuối).
                struct.pack_into(U64_FMT, buf, OFFSET_OWNER_PID, 0)
                struct.pack_into(U64_FMT, buf, OFFSET_OWNER_CREATE_TIME_NS, 0)
                struct.pack_into(U64_FMT, buf, OFFSET_LEASE_DEADLINE_NS, 0)
                struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.DONE))
        finally:
            lock.release()

        return frame_copy

    def read_ref(self, ref: ShmFrameRefData) -> Optional[np.ndarray]:
        """Đọc theo ShmFrameRefData — tự kiểm `ring_epoch` (stale-ref P0-3) + (slot, generation)."""
        return self.read(ref.slot, ref.generation, ring_epoch=ref.ring_epoch)
