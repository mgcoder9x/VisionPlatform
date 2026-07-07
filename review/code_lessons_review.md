# Code Lessons Review - Tham dinh lai bai #01 -> #04

> Cap nhat boi Codex, 2026-06-24.  
> Pham vi nguoi dung yeu cau: `code-lessons/01-skeleton-layout`, `02-data-objects`, `03-port-adapters`, `04-pipeline`, `_TEMPLATE-lesson.md`, `00-INDEX.md`, `00-LESSON-RULES.md`.  
> Gioi han thao tac: **chi sua file review nay**. Khong sua code, khong sua lesson, khong sua diagram.

## Ket luan ngan

Review cu **chua du chinh xac** vi phan quyet "Fidelity: 100% khop byte-by-byte" la qua manh so voi thuc te hien tai.

Phan dung:

- He thong bai hoc co chat luong su pham cao: co vong cung van-de-truoc-giai-phap, chia mau nho, co phan "khong co thi sao", vi von, tu kiem, moc on.
- Code nen hien tai dang xanh: `pytest -q` cho **86 passed, 1 skipped**; `lint-imports` cho **5 kept, 0 broken**.
- Cac sua quan trong sau review truoc da phan anh trong code va nhieu lesson: `MediaPacket` pickle, `StageResult.error_traceback` dang chuoi, context manager cho `IFrameSource`/adapter, demo pipeline dung `with source, executor:`.

Phan sai hoac thieu:

- Nhieu block `## 3. Code that` la **excerpt co `...` / bo qua doan giua**, khong phai quote nguyen van byte-by-byte.
- Nhieu anh `.svg` dang duoc nhung trong markdown nhung **file SVG chua ton tai** o bai #02/#03/#04.
- Nhieu so lieu test trong lesson la so cu (`30 passed`, `13 passed`, `64 passed`) trong khi baseline hien tai da doi.
- `00-INDEX.md` dung bieu tuong hoan thanh de noi "da viet du", nhung cung ghi "cho Feynman"; ve luat cong hieu, can tach ro "da viet" voi "nguoi hoc da dau cong".

## Bang phan quyet

| Hang muc | Phan quyet | Muc do |
|---|---|---|
| Chat luong su pham tong the | Tot, nen giu huong | Cao |
| Dong bo hanh vi code voi test hien tai | Tot, da verify bang test | Cao |
| Claim "quote nguyen van / byte-by-byte 100%" | **Khong dung** | P0 |
| Anh nhung trong bai hoc | **Dang gay o #02/#03/#04 do thieu SVG** | P0 |
| Bang chung test trong lesson | Mot phan da cu | P1 |
| Trang thai Feynman trong index | De gay hieu nham | P1 |
| Review cu co du sau khong | Chua du, can thay bang review nay | P1 |

## Evidence da tu kiem

- Doc `review/code_lessons_review.md` cu.
- Doc `code-lessons/00-LESSON-RULES.md`, `_TEMPLATE-lesson.md`, `00-INDEX.md`.
- Doc/scan toan bo markdown trong 4 folder lesson.
- Kiem cau truc heading: **32/32 file mau** (`01-*` den `09-*`) co du 14 muc theo template. `00-cau-chuyen.md` va `00-muc-luc.md` la file dieu huong nen khong ap template 14 muc.
- Kiem code block trong section `## 3. Code that` bang script heuristic:
  - 18 block la substring exact trong source.
  - 15 block khong exact, chu yeu vi co `...` hoac la excerpt rut gon.
  - 3 block khong gan path source vi la lenh/TOML snippet/cay thu muc.
- Kiem link file noi bo:
  - #01 co du `.drawio` va `.svg`.
  - #02/#03/#04 co `.drawio` nhung thieu SVG export cho 8 file unique.
- Kiem XML diagram: tat ca `.drawio` va SVG hien co parse XML OK.
- Chay `pytest -q`: **86 passed, 1 skipped**.
- Chay rieng #03: **32 passed, 1 skipped**.
- Chay rieng #04: **16 passed**.
- Chay `lint-imports`: **5 kept, 0 broken**.

## Finding P0-1 - Review cu overclaim "Fidelity 100% byte-by-byte"

Review cu viet:

> "Qua viec doi chieu tung ky tu (byte-by-byte comparison) ... 100% khop."

Ket luan nay **khong giu duoc**.

Vi du da doc tay:

- `code-lessons/02-data-objects/01-dataclass-frozen-bbox.md` co block "Code that" chua `# ... (CoordinateSpace o mau 02) ...`. Day la excerpt co chu thich, khong phai code nguyen van trong `bbox.py`.
- `code-lessons/03-port-adapters/03-fakeframesource-khung.md` bo qua `_source_id` va `read()` bang dong `# ...`.
- `code-lessons/04-pipeline/07-sync-linear-executor.md` bo qua context manager bang `# ... (context manager __enter__/__exit__ -> xem mau 08)`.

Danh gia dung hon:

- **Semantic fidelity phan lon tot**: cac excerpt noi dung dung y va dung hanh vi.
- **Literal fidelity khong dat 100%**: khong duoc goi la byte-by-byte nguyen van.

Khuyen nghi cho luot sua lesson sau:

- Hoac doi tieu de `## 3. Code that (excerpt co chu thich)` cho cac block co `...`.
- Hoac thay cac block do bang quote nguyen van lien tuc tu source.
- Review/Index phai dung nhan "excerpt" neu khong quote full.

## Finding P0-2 - Anh SVG dang bi gay o #02/#03/#04

Markdown dang nhung SVG nhung file khong ton tai:

- `code-lessons/02-data-objects/diagrams/data-bricks-overview.svg`
- `code-lessons/02-data-objects/diagrams/pickle-e11.svg`
- `code-lessons/02-data-objects/diagrams/mediapacket-cow.svg`
- `code-lessons/03-port-adapters/diagrams/port-adapter-hexagonal.svg`
- `code-lessons/03-port-adapters/diagrams/fake-read-flow.svg`
- `code-lessons/03-port-adapters/diagrams/contract-test-matrix.svg`
- `code-lessons/04-pipeline/diagrams/pipeline-flow.svg`
- `code-lessons/04-pipeline/diagrams/stage-status-state.svg`

Tac dong:

- Day khong con la "rui ro drift" tru tuong. Hien tai nguoi hoc mo markdown se thay anh hong o nhieu cho.
- Vi `00-LESSON-RULES.md` dua dual coding/hinh anh vao khung su pham, day la loi trai nghiem hoc that.

Trang thai:

- File `.drawio` nguon co ton tai va XML OK.
- #01 co du `.svg` va XML OK.
- #02/#03/#04 can export SVG khi duoc phep sua lesson/assets.

Khuyen nghi cho luot sua lesson sau:

- Export 8 SVG tu drawio nguon.
- Hoac tam thoi bo nhung `![](...svg)` va chi link `.drawio` neu chua co SVG.
- Cap nhat review cu: khong noi "system hoan toan sach" khi anh dang gay.

## Finding P1-1 - So lieu test trong lesson da cu

Baseline hien tai:

- Full suite: **86 passed, 1 skipped**.
- #03: **32 passed, 1 skipped**.
- #04: **16 passed**.
- Import-linter: **5 kept, 0 broken**.

Nhieu lesson van ghi so cu:

- #03 nhieu file ghi `30 passed, 1 skipped`.
- `code-lessons/03-port-adapters/diagrams/contract-test-matrix.drawio` cung ghi cong thuc `30 passed / 1 skipped`.
- #04 nhieu file ghi `13 passed`.
- `code-lessons/04-pipeline/00-muc-luc.md` ghi `64 passed/1 skipped` va `test_step_04 13 passed`.
- #01/#02 co mot so dong lich su ghi `64 passed/1 skipped`.

Danh gia:

- Neu day la "trang thai luc viet" thi khong phai bug logic.
- Nhung vi lesson tu nhan "da verify" va review cu noi dong bo hien tai, nhung con so cu se lam nguoi hoc nghi bang chung da moi trong khi baseline da doi.

Khuyen nghi:

- Doi wording thanh "tai thoi diem viet bai: ...; baseline hien tai xem `00-INDEX.md`/review".
- Hoac cap nhat tat ca so lieu len baseline moi trong mot luot rieng.

## Finding P1-2 - `00-INDEX.md` co nguy co vuot cong Feynman

`00-INDEX.md` dinh nghia trang thai:

> `✅` = da viet + nguoi hoc tu giai thich lai duoc.

Nhung cac dong bai #01 -> #04 hien ghi dang `✅ da viet du ... - cho Feynman`.

Van de:

- Noi "cho Feynman" nghia la nguoi hoc chua qua cong.
- Dung bieu tuong `✅` co the bi hieu thanh da dau cong hoc, trai voi luat Feynman khat khe.

Khuyen nghi:

- Tach 2 cot: `Trang thai viet bai` va `Trang thai nguoi hoc`.
- Hoac dung nhan ro: `✅ da viet du` + `🔵 cho Feynman`, khong gom vao mot trang thai.

## Finding P1-3 - Bai #04 story chua cap nhat day du E-16

`code-lessons/04-pipeline/01-stagestatus-stageresult.md` da dung code hien tai: `error_traceback` la **chuoi** tu `traceback.format_exc()`, khong giu frame.

Nhung `code-lessons/04-pipeline/00-cau-chuyen.md` van noi giai phap loi la:

> "chi `error_type` + `error_message` chuoi"

Dieu nay thieu mot truong quan trong hien tai:

- `error_traceback: Optional[str]`

Danh gia:

- Khong sai o diem "khong giu Exception object".
- Nhung khong du chinh xac voi design sau E-16: he thong giu traceback dang **string** de debug, va do co rui ro string bloat neu ket qua loi bi tich luy/luu lau.

Khuyen nghi:

- Sua `00-cau-chuyen.md` sau nay thanh: "giu `error_type`, `error_message`, va `error_traceback` dang chuoi; khong giu Exception object/frame".

## Finding P1-4 - Risk `source_id` concurrency trong review cu can noi dung hon

Review cu neu rui ro `itertools.count` khi tao adapter song song.

Can chinh sac thai:

- Code comment noi ro `_fake_source_counter` dam bao unique **trong 1 process**.
- Neu yeu cau la unique toan he thong nhieu process/camera, `fake_0` o process A va `fake_0` o process B co the trung.
- Day la gioi han scope, khong phai bug da verify trong hien tai.

Khuyen nghi:

- Ghi la "unique per process".
- Neu production can global uniqueness, them prefix `process_id`/UUID/profile name khi tao source_id.

## Finding P2-1 - Bai #01 co the lam mo dong thoi gian hoc

#01 noi "van de #01 moi chi dung bo khung rong", nhung bang tong quan lai liet ke cac file ve sau nhu `domain/bbox.py`, `runtime/sync_linear_executor.py`, `profiles/demo_pipeline.py`.

Danh gia:

- Neu doc voi tu cach "giai thich code da build" thi chap nhan duoc.
- Nhung nguoi moi co the bi roi: #01 la skeleton hay la snapshot sau #04?

Khuyen nghi:

- Them mot cau sau nay: "Bang duoi la snapshot hien tai sau khi da build #01-#04; o thoi diem #01 ban dau cac folder nay moi co `__init__.py`."

## Nhung diem review cu noi dung

- #01: dung khi khen cau truc skeleton/src layout/import-linter. #01 co du SVG, diagram XML OK.
- #02: dung khi khen cach day bat bien/CoW/pickle. E-11/E-16 da duoc nhac, nhung fidelity khong phai byte-by-byte.
- #03: dung khi xac nhan Protocol/adapter/context manager hien da co trong code. Contract test hien pass.
- #04: dung khi xac nhan `SyncLinearExecutor` teardown nguoc, context manager, result object. Code hien pass.
- `00-LESSON-RULES.md`: khung su pham tot, dac biet luat "WHY truoc WHAT", "vong cung day", "quote code that", "khong day lesson trong chat".
- `_TEMPLATE-lesson.md`: du 14 muc can thiet.

## Khuyen nghi uu tien neu duoc phep sua lesson/assets sau nay

1. Sua/doi nhan cac block code co `...` de khong tu nhan la quote nguyen van.
2. Export 8 SVG thieu cho #02/#03/#04.
3. Cap nhat so lieu test da cu hoac ghi ro "tai thoi diem viet".
4. Tach trang thai "da viet" va "da qua Feynman" trong `00-INDEX.md`.
5. Cap nhat #04 `00-cau-chuyen.md` de nhac `error_traceback` dang string.
6. Cap nhat `contract-test-matrix.drawio` vi no con ghi cong thuc 30 passed/1 skipped.

## Phan quyet cuoi

`review/code_lessons_review.md` cu **khong du chinh xac** vi qua lac quan va chua bat cac loi tai lieu dang co that.

Phan quyet moi:

- **Code va kien truc nen: dat, da verify.**
- **Su pham: tot, co nen tang manh.**
- **Fidelity tai lieu: chua dat muc "quote nguyen van 100%" nhu review cu tuyen bo.**
- **Do day du cua review cu: chua du, vi bo sot SVG gay, so test cu, trang thai Feynman, va distinction excerpt vs quote.**

## Da verify

- `pytest -q` trong `vision-platform`: **86 passed, 1 skipped**.
- `pytest tests/test_step_03_frame_source_contract.py -q`: **32 passed, 1 skipped**.
- `pytest tests/test_step_04_pipeline.py -q`: **16 passed**.
- `lint-imports`: **5 kept, 0 broken**.
- 32/32 file mau co du 14 heading.
- 8 SVG unique dang bi thieu o #02/#03/#04.
- Tat ca `.drawio` va SVG hien co parse XML OK.

## Chua verify

- Chua render Markdown bang IDE/browser de chup anh visual.
- Chua doi chieu byte-by-byte tung code block bang parser hoan hao; script hien tai la heuristic va da du de bac bo claim "100% byte-by-byte".
- Chua kiem tra Feynman response thuc te cua nguoi hoc.
- Chua sua lesson/assets theo cac khuyen nghi tren vi nguoi dung gioi han chi sua file review nay.
