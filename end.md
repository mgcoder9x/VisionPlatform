Including Steering Documents

AGENTS.md

00-core-rules.md
Thinking completed
+
→ Chế độ: XÂY (tiếp tục TASK 5 — perf-harness K-014)

Đầu phiên bắt buộc: kiểm tra trạng thái git + drift trước, rồi đọc bộ nhớ. Chạy song song các bước độc lập.

Command
c:\Users\k.…ionPlatform

git status && echo "=====DIFF-STAT=====" && git diff --stat
us && echo "=====DIFF-STAT=====" && git diff --stat                             On branch chore/dev-env-launcher-portable-hooks
Your branch is up to date with 'origin/chore/dev-env-launcher-portable-hooks'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        vision-platform/benchmarks/measure_ring_drop.py

nothing added to commit but untracked files present (use "git add" to track)
=====DIFF-STAT=====
Thinking completed
+
Có 1 file untracked measure_ring_drop.py (VỪA TẠO phiên trước). Chạy drift-check + đọc bộ nhớ song song.

Command
c:\Users\k.…ionPlatform

scripts\vp.cmd check
vp.cmd check                                                                    === [1/3] MEMORY CONSISTENCY (LOG/journal/INDEX/activeContext khớp thực tế) ===
[PASS] C1-LOG: 444 entry, max #440 · dup-LEGACY(bỏ qua)=[90, 91, 95, 96]
[PASS] C2-INDEX-LOGREF: INDEX ghi #440 vs LOG max #440
[PASS] C3-D: 141 ID, max D-141
[PASS] C5-D: khớp INDEX
[PASS] C3-C: 24 ID, max C-024
[PASS] C5-C: khớp INDEX
[PASS] C3-T: 35 ID, max T-035
[PASS] C5-T: khớp INDEX
[PASS] C3-K: 119 ID, max K-119
[PASS] C5-K: khớp INDEX
[PASS] C4-INDEX-TOTAL: INDEX ghi (D141·C24·T35·K119=Σ319) vs THẬT (D141·C24·T35·
K119=Σ319)                                                                      [PASS] C6-ACTIVE-STAMP: có mốc 'Cập nhật lúc'
[PASS] C6-ACTIVE-LATEST: activeContext nhắc #440
[PASS] C7-INDEX-CITES: mọi #N trích ∈ LOG
[PASS] C8-DOC-CODE: 34 Verify-Symbol khớp code
[PASS] C9-GIT: local dong-bo/vuot upstream (behind=0 · ahead=0 · chore/dev-env-l
auncher-portable-hooks@db58665)                                                 
=== [2/3] RULES_VERSION SYNC (mọi mirror + kit khớp) ===
      16  AGENTS.md
      16  GEMINI.md
      16  .github/copilot-instructions.md
      16  .kiro/steering/00-core-rules.md
      16  ai-learning-os-kit/AGENTS.template.md

=== [3/3] SELF-TEST checker (guard chống regex-rot — checker phải BẮT được drift
) ===                                                                           [PASS] self:baseline-clean-PASS
[PASS] self:C1-catch-dup
[PASS] self:C2-catch-header-mismatch
[PASS] self:C4-catch-wrong-total
[PASS] self:C5-catch-orphan
[PASS] self:C6-catch-missing-stamp
[PASS] self:C6-catch-stale-pointer
[PASS] self:C7-catch-phantom-cite
[PASS] self:C8-clean-PASS
[PASS] self:C8-catch-missing-symbol
[PASS] self:C8-catch-missing-file
[PASS] self:C9-catch-behind
[PASS] self:C9-no-upstream-SKIP-PASS
[PASS] self:C9-unavailable-SKIP-PASS

DRIFT-CHECK: PASS — bản ghi nhất quán.
Read file(s)

activeContext.md

measure_ring_drop.py
Thinking completed
+
Drift PASS · frontier #440 · harness đã viết đầy đủ. Giờ chạy harness thật để lấy số K-014.

Command
c:\Users\k.…on-platform

.venv\Scripts\python.exe -m benchmarks.measure_ring_drop
nv\Scripts\python.exe -m benchmarks.measure_ring_drop                           [ring-drop] fps=30.0 · consume=100.0ms (~10.0/s) · n_slots=8 · 480x640 · 5.0s × 
3 vòng                                                                            vòng  produced  received  drop_full  drop_sup  drop%   cons_fps 
  1     151       50        93         7         66.2    10.0     
  2     151       50        93         7         66.2    10.0     
  3     151       50        93         7         66.2    10.0     
  MEDIAN drop%=66.2 · consumer_fps=10.0
  (drop cao là ĐÚNG cho real-time keep-latest khi consumer<producer: bỏ frame cũ
, giữ mới nhất — box vẫn bám frame mới; đây là số ĐO SLA nguồn, không phải lỗi.)
Thinking completed
+
Số ổn định tuyệt đối qua 3 vòng (variance=0): produced 151 (~30fps×5s ✓), received 50 (10/s×5s ✓), drop 66.2%. Đúng bản chất keep-latest.

Để K-014 có bằng chứng SLA đầy đủ (và tự-kiểm harness đo đúng bản chất, chống số bịa), chạy thêm 2 kịch bản consumer-rate khác — chứng minh quan hệ consumer-rate ↔ drop%.

Command
c:\Users\k.…on-platform

.venv\Scripts\python.exe -m benchmarks.measure_ring_drop --consume-ms 33 && echo ===== && .venv\Scripts\python.exe -m benchmarks.measure_ring_drop --consume-ms 50
&& .venv\Scripts\python.exe -m benchmarks.measure_ring_drop --consume-ms 50     [ring-drop] fps=30.0 · consume=33.0ms (~30.3/s) · n_slots=8 · 480x640 · 5.0s × 3
 vòng                                                                             vòng  produced  received  drop_full  drop_sup  drop%   cons_fps 
  1     151       145       0          5         3.3     29.0     
  2     150       147       0          3         2.0     29.4     
  3     151       148       0          2         1.3     29.6     
  MEDIAN drop%=2.0 · consumer_fps=29.4
  (drop cao là ĐÚNG cho real-time keep-latest khi consumer<producer: bỏ frame cũ
, giữ mới nhất — box vẫn bám frame mới; đây là số ĐO SLA nguồn, không phải lỗi.)=====
[ring-drop] fps=30.0 · consume=50.0ms (~20.0/s) · n_slots=8 · 480x640 · 5.0s × 3
 vòng                                                                             vòng  produced  received  drop_full  drop_sup  drop%   cons_fps 
  1     151       99        44         7         33.8    19.8     
  2     151       99        44         7         33.8    19.8     
  3     150       98        44         7         34.0    19.6     
  MEDIAN drop%=33.8 · consumer_fps=19.8
  (drop cao là ĐÚNG cho real-time keep-latest khi consumer<producer: bỏ frame cũ
, giữ mới nhất — box vẫn bám frame mới; đây là số ĐO SLA nguồn, không phải lỗi.)
Thinking completed
+
Bảng SLA nhất quán hoàn hảo với lý thuyết real-time keep-latest:

consumer rate	drop%	consumer_fps	frame giữ
~30/s (=producer)	2.0%	29.4	~all
~20/s	33.8%	19.8	2/3
~10/s (YOLO-CPU)	66.2%	10.0	1/3
Quan hệ drop% ≈ 1 − consumer_rate/producer_rate xác nhận harness đo đúng bản chất (không nhiễu, không bịa). Điểm SLA cốt lõi: consumer_fps LUÔN = 1000/consume_ms bất kể producer chạy 30fps → chứng minh keep-latest latency-bounded: consumer luôn chạy full tốc độ của nó, không bị backlog kéo chậm, drop = frame cũ bị bỏ (không tích luỹ độ trễ).

Giờ ghi sổ. Đọc journal K-014 + INDEX + LOG tail để bump đúng.

Read file(s)

00-INDEX.md 1 - 31

AI-IMPLEMENTATION-LOG.md 1 - 31
Thinking completed
+
Cần đọc LOG entry #440 (format) + entry K-014 hiện tại trong journal + dòng total/logref của INDEX. Đọc song song.

Command
c:\Users\k.…ionPlatform

.venv\Scripts\python.exe -c "import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8'); t=open('AI-IMPLEMENTATION-LOG.md',encoding='utf-8').read(); i=t.rfind('## Entry #440'); print(t[i:] if i>0 else t[-3000:])"
('## Entry #440'); print(t[i:] if i>0 else t[-3000:])"                          .venv\Scripts\python.exe: The module '.venv' could not be loaded. For more infor
mation, run 'Import-Module .venv'.                                              
Thinking completed
+
Command

vision-platform\.venv\Scripts\python.exe -c "import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8'); t=open('AI-IMPLEMENTATION-LOG.md',encoding='utf-8').read(); i=t.rfind('Entry #440'); print(t[i-2:])"
Command
c:\Users\k.…ionPlatform

vision-platform\.venv\Scripts\python.exe -c "import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8'); t=open('AI-IMPLEMENTATION-LOG.md',encoding='utf-8').read(); i=t.rfind('Entry #440'); print(t[i-2:])"
'utf-8').read(); i=t.rfind('Entry #440'); print(t[i-2:])"                       # Entry #440 — 2026-07-18 — Hardening kiến trúc: +import-linter contract `layers
` (F1.4) + đính chính comment (F1.5) — Kiro-Opus                                
**Bối cảnh:** Chờ user chốt GPU target → làm bước hardening kiến trúc verify-đượ