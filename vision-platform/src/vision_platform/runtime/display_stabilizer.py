"""DisplayStabilizer — ổn định hiển thị overlay (web-live-overlay-sync spec Task 3).

Layer: runtime — GIỮ STATE (candidates + confirmed tracks + counter/revision). Thuần (không I/O/clock/
network): clock TIÊM qua tham số `now_ns` mỗi lời gọi (design §OverlayStateStore: clock/wait tiêm được).
KHÔNG import analytics (Property 10). Dùng `domain.greedy_associate` (matching, Property 8) + `domain.ema_box`
(smoothing, Property 9) + DTO `kernel.overlay_view`. 1 instance / 1 source (design §4).

Ngữ nghĩa CHÍNH XÁC (design §Stabilizer exact semantics):
- accepted result: match new↔confirmed (cùng label, IoU-greedy). Matched → missCount=0, EMA, lease refresh,
  trackRevision+=1 (kể cả toạ độ bằng). Unmatched confirmed → missCount+=1, KHÔNG refresh; xóa khi
  missCount>maxMisses HOẶC TimerTick chạm lease (Property 7).
- new-box thừa → match candidate; candidate matched → hitStreak+=1; candidate KHÔNG match kết quả này → XÓA;
  hitStreak>=minHits → promote (displayId="<epoch>:<counter>", counter đơn điệu trong epoch).
- EMPTY = mọi track/candidate unmatched. Discontinuity → clear tất cả ngay + counter reset (epoch mới).
- Per-track lease ĐỘC LẬP: match track khác KHÔNG gia hạn track này (Property 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.display_smoothing import ema_box, greedy_associate
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import DisplayTrack, DisplayView

# reason bounded enum (design: metric label chỉ enum bounded)
REASON_INIT = "INIT"
REASON_UPDATED = "UPDATED"
REASON_TICK_EXPIRE = "TICK_EXPIRE"
REASON_CLEARED = "CLEARED"

# 1 box đầu vào accepted result: (label, box NORMALIZED, confidence)
InputBox = Tuple[str, BBox, float]


@dataclass
class _Confirmed:
    display_id: str
    label: str
    box: BBox
    confidence: float
    track_revision: int
    miss_count: int
    lease_deadline_ns: int


@dataclass
class _Candidate:
    label: str
    box: BBox
    confidence: float
    hit_streak: int
    lease_deadline_ns: int


class DisplayStabilizer:
    def __init__(self, source_epoch: int, config: OverlayConfig) -> None:
        if source_epoch < 1:
            raise ValueError(f"source_epoch >= 1, got {source_epoch}")
        self._epoch = source_epoch
        self._cfg = config
        self._confirmed: dict[str, _Confirmed] = {}
        self._candidates: list[_Candidate] = []
        self._counter = 0       # đơn điệu TRONG epoch (reset khi discontinuity)
        self._revision = 0      # display revision toàn cục (tăng mỗi commit đổi state)

    @staticmethod
    def _ms_ns(ms: int) -> int:
        return ms * 1_000_000

    def _validate_normalized(self, boxes: Sequence[InputBox]) -> None:
        for _lbl, bx, _c in boxes:
            if bx.space is not CoordinateSpace.NORMALIZED:
                raise ValueError(f"stabilizer nhận box NORMALIZED, got {bx.space}")

    def on_accepted_result(self, boxes: Sequence[InputBox], now_ns: int) -> DisplayView:
        """Xử lý MỘT accepted unique result. `boxes` = (label, box NORMALIZED, confidence)."""
        self._validate_normalized(boxes)
        cfg = self._cfg
        disp_lease = self._ms_ns(cfg.displayLeaseMs)
        cand_lease = self._ms_ns(cfg.candidateLeaseMs)
        new_labels = [b[0] for b in boxes]
        new_boxes = [b[1] for b in boxes]

        # 1) match new ↔ confirmed (prev=confirmed, new=new) → (new_idx, conf_idx)
        conf_ids = list(self._confirmed.keys())
        conf_boxes = [self._confirmed[i].box for i in conf_ids]
        conf_labels = [self._confirmed[i].label for i in conf_ids]
        matches = greedy_associate(conf_boxes, new_boxes, cfg.iouThreshold,
                                   prev_labels=conf_labels, new_labels=new_labels)
        matched_new: set[int] = set()
        matched_conf: set[int] = set()
        for new_i, conf_i in matches:
            st = self._confirmed[conf_ids[conf_i]]
            st.box = ema_box(st.box, new_boxes[new_i], cfg.emaAlpha)   # EMA (Property 9)
            st.confidence = boxes[new_i][2]
            st.miss_count = 0
            st.track_revision += 1                                     # bump kể cả toạ độ bằng
            st.lease_deadline_ns = now_ns + disp_lease                 # refresh lease CHỈ track này
            matched_new.add(new_i)
            matched_conf.add(conf_i)

        # 2) unmatched confirmed → miss (Property 7); xóa khi vượt maxMisses
        for idx, cid in enumerate(conf_ids):
            if idx in matched_conf:
                continue
            st = self._confirmed[cid]
            st.miss_count += 1
            if st.miss_count > cfg.maxMisses:
                del self._confirmed[cid]

        # 3) new thừa (chưa khớp confirmed) → match candidates
        leftover = [i for i in range(len(new_boxes)) if i not in matched_new]
        cand_boxes = [c.box for c in self._candidates]
        cand_labels = [c.label for c in self._candidates]
        lo_boxes = [new_boxes[i] for i in leftover]
        lo_labels = [new_labels[i] for i in leftover]
        cmatches = greedy_associate(cand_boxes, lo_boxes, cfg.iouThreshold,
                                    prev_labels=cand_labels, new_labels=lo_labels)
        matched_cand: set[int] = set()
        matched_lo: set[int] = set()
        for lo_i, cand_i in cmatches:
            cand = self._candidates[cand_i]
            cand.box = new_boxes[leftover[lo_i]]      # candidate dùng box mới nhất (chưa smoothing)
            cand.confidence = boxes[leftover[lo_i]][2]
            cand.hit_streak += 1
            cand.lease_deadline_ns = now_ns + cand_lease
            matched_cand.add(cand_i)
            matched_lo.add(lo_i)

        # 4) candidate KHÔNG match result này → XÓA (design)
        self._candidates = [c for ci, c in enumerate(self._candidates) if ci in matched_cand]

        # 5) new thừa chưa match candidate → candidate MỚI (hitStreak=1)
        for lo_i in range(len(leftover)):
            if lo_i in matched_lo:
                continue
            i = leftover[lo_i]
            self._candidates.append(_Candidate(
                label=new_labels[i], box=new_boxes[i], confidence=boxes[i][2],
                hit_streak=1, lease_deadline_ns=now_ns + cand_lease))

        # 6) promotion pass: hitStreak>=minHits → confirmed (displayId đơn điệu trong epoch)
        survivors: list[_Candidate] = []
        for cand in self._candidates:
            if cand.hit_streak >= cfg.minHits:
                self._counter += 1
                did = f"{self._epoch}:{self._counter}"
                self._confirmed[did] = _Confirmed(
                    display_id=did, label=cand.label, box=cand.box, confidence=cand.confidence,
                    track_revision=0, miss_count=0, lease_deadline_ns=now_ns + disp_lease)
            else:
                survivors.append(cand)
        self._candidates = survivors

        self._revision += 1
        return self._view(REASON_UPDATED)

    def on_tick(self, now_ns: int) -> DisplayView:
        """TimerTick: xóa confirmed/candidate đã quá hạn lease (Property 5/13). Không đổi → no-op (không tăng revision)."""
        changed = False
        for cid in list(self._confirmed.keys()):
            if self._confirmed[cid].lease_deadline_ns <= now_ns:
                del self._confirmed[cid]
                changed = True
        before = len(self._candidates)
        self._candidates = [c for c in self._candidates if c.lease_deadline_ns > now_ns]
        if len(self._candidates) != before:
            changed = True
        if changed:
            self._revision += 1
        return self._view(REASON_TICK_EXPIRE)

    def on_discontinuity(self, new_source_epoch: int) -> DisplayView:
        """Source discontinuity: clear tất cả NGAY + reset counter theo epoch mới (design §3)."""
        if new_source_epoch <= self._epoch:
            raise ValueError(f"epoch mới ({new_source_epoch}) phải > hiện tại ({self._epoch})")
        self._epoch = new_source_epoch
        self._confirmed.clear()
        self._candidates.clear()
        self._counter = 0
        self._revision += 1
        return self._view(REASON_CLEARED)

    def _view(self, reason: str) -> DisplayView:
        tracks = tuple(
            DisplayTrack(displayId=st.display_id, trackRevision=st.track_revision, label=st.label,
                         box=st.box, leaseDeadlineNs=st.lease_deadline_ns, missCount=st.miss_count,
                         confidence=st.confidence)
            for st in sorted(self._confirmed.values(), key=lambda s: s.display_id)
        )
        return DisplayView(revision=self._revision, reason=reason, tracks=tracks)

    # đọc trạng thái (test/debug)
    @property
    def display_revision(self) -> int:
        """Revision hiển thị hiện tại (tăng mỗi commit đổi state) — store dùng để biết tick có đổi gì không."""
        return self._revision

    def next_expiry_ns(self) -> "int | None":
        """Deadline lease SỚM NHẤT (confirmed + candidate) — scheduler chờ tới đây, tránh busy-poll.
        None nếu không có gì hết hạn."""
        deadlines = [s.lease_deadline_ns for s in self._confirmed.values()]
        deadlines += [c.lease_deadline_ns for c in self._candidates]
        return min(deadlines) if deadlines else None

    @property
    def confirmed_count(self) -> int:
        return len(self._confirmed)

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def epoch(self) -> int:
        return self._epoch
