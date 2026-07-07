"""Composition root: profile demo cho Step 04.

Wire: source → BrightnessStage → DarkFilterStage → print event.
Single process, sync executor.
"""
from __future__ import annotations
import argparse
import sys
import time

from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.stages.brightness_stage import BrightnessStage
from vision_platform.runtime.stages.dark_filter_stage import DarkFilterStage


def main() -> int:
    parser = argparse.ArgumentParser(prog="vision_platform.profiles.demo_pipeline")
    parser.add_argument("--source", choices=["fake", "noise"], default="fake")
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--threshold", type=float, default=50.0,
                        help="Brightness threshold for DarkFilterStage")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args()

    # ===== Composition root: chỗ DUY NHẤT chọn cụ thể adapter. =====
    if args.source == "fake":
        from vision_platform.adapters.fake_frame_source import FakeFrameSource
        source = FakeFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    elif args.source == "noise":
        from vision_platform.adapters.noise_frame_source import NoiseFrameSource
        source = NoiseFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    else:
        parser.error(f"Unknown source: {args.source}")

    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=args.threshold),
    ])

    # ===== Run loop =====
    seq = 0
    n_processed = 0
    n_skipped = 0
    n_stage_error = 0
    n_cancelled = 0
    n_eof = 0
    n_error = 0

    # Context manager (R2#04 / ERRATA E-16): `with source, executor:` tự setup lúc vào +
    # teardown lúc ra (kể cả khi raise). Thứ tự ra: executor.teardown_all() → source.teardown().
    with source, executor:
        while True:
            r = source.read()

            if r.status == ReadStatus.EOF:
                n_eof += 1
                break

            if r.status == ReadStatus.ERROR:
                n_error += 1
                print(f"[seq={seq}] source ERROR: {r.error}", file=sys.stderr)
                continue

            if not r.has_data:
                continue

            packet = MediaPacket(
                packet_id=f"pkt_{seq}",
                source_id=source.source_id,
                media_ref=InMemoryArrayRef.from_copy(r.data),
                capture_time_ns=time.monotonic_ns(),
            )
            seq += 1

            result = executor.execute(packet)

            if result.status == StageStatus.SUCCESS:
                n_processed += 1
                final = result.packet
                print(
                    f"[seq={seq:03d}] brightness={final.artifacts['brightness']:.2f} "
                    f"shape={final.media_ref.array.shape}"
                )
            elif result.status == StageStatus.SKIPPED:
                n_skipped += 1
            elif result.status == StageStatus.ERROR:
                n_stage_error += 1
                print(
                    f"[seq={seq:03d}] stage ERROR in '{result.failed_stage}': "
                    f"{result.error_type}: {result.error_message}",
                    file=sys.stderr,
                )
            else:  # CANCELLED
                n_cancelled += 1

    # ===== Summary =====
    print("\n=== Demo summary ===", file=sys.stderr)
    print(f"  Processed: {n_processed}", file=sys.stderr)
    print(f"  Skipped (filter):  {n_skipped}", file=sys.stderr)
    print(f"  Stage errors: {n_stage_error}", file=sys.stderr)
    print(f"  Cancelled: {n_cancelled}", file=sys.stderr)
    print(f"  EOF: {n_eof}", file=sys.stderr)
    print(f"  Source errors: {n_error}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
