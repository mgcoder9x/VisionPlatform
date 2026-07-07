"""SyncLinearExecutor - linear pipeline runner."""
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.stage_contract import IStage, StageStatus, ExecutionResult


class SyncLinearExecutor:
    """Run packet through stages linearly. Stop on first non-SUCCESS."""

    def __init__(self, stages: list[IStage]):
        self._stages = list(stages)
        self._setup_done: list[IStage] = []   # R3: chỉ teardown stage đã setup THÀNH CÔNG

    def setup_all(self) -> None:
        """Setup tuần tự. Nếu 1 stage setup LỖI → rollback (teardown ngược các stage đã setup) rồi raise."""
        self._setup_done = []
        for s in self._stages:
            try:
                s.setup()
            except Exception:
                # R3 (ERRATA E-16): setup lỗi nửa chừng → dọn các stage đã mở rồi mới ném lên.
                self.teardown_all()
                raise
            self._setup_done.append(s)

    def teardown_all(self) -> None:
        # R3: chỉ teardown các stage ĐÃ setup (tránh gọi teardown lên stage chưa khởi tạo).
        for s in reversed(self._setup_done):
            try:
                s.teardown()
            except Exception:
                pass
        self._setup_done = []

    # Context manager (ERRATA E-14, Risk 4): đảm bảo teardown tự động kể cả khi raise giữa chừng.
    # `with SyncLinearExecutor([...]) as ex: ...` → setup_all() lúc vào, teardown_all() lúc ra.
    def __enter__(self) -> "SyncLinearExecutor":
        self.setup_all()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown_all()
        return False  # KHÔNG nuốt exception của thân `with`

    def execute(self, packet: MediaPacket) -> ExecutionResult:
        """Drive packet qua chuỗi stage. Giữ đầy đủ trạng thái (PROCESSED/SKIPPED/ERROR/CANCELLED)."""
        current = packet
        for stage in self._stages:
            result = stage.process(current)
            if result.status == StageStatus.SUCCESS:
                current = result.packet
            else:
                return ExecutionResult.from_stage_result(result)
        return ExecutionResult.processed(current)
