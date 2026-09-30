# K4-L3A — Lab Day 13: Monitoring & LLMOps

> - **Loại repository:** đề bài/starter dành riêng cho lớp K4-L3A
> - **Hình thức làm bài:** cá nhân
> - **Thời gian trên lớp:** 14:00–18:00 (240 phút)
> - **Deadline mặc định:** 23:59:59 trong ngày học, múi giờ Asia/Ho_Chi_Minh

Bạn sẽ biến một AI API “hộp đen” thành hệ thống có thể trả lời ba câu hỏi: **hệ thống có vấn đề gì, request nào bị ảnh hưởng và bước nào là nguyên nhân**. Quy trình điều tra đúng theo slide là **Metrics → Logs → Traces**:

1. Metrics cho biết triệu chứng và khoảng thời gian.
2. Logs giúp tìm request cụ thể qua `correlation_id`.
3. Trace của request đó cho biết span nào chậm hoặc lỗi.

Repo dùng fake LLM nên không cần API key mô hình trả phí. Mỗi học viên tự tạo một project Langfuse riêng để quan sát trace và quản lý prompt version; không dùng project/key dùng chung.

## Kết quả cần đạt

Sau lab, bạn có thể:

- tạo structured log dạng JSON, truyền correlation ID và che PII trước khi ghi log;
- đo latency P50/P95/P99, TTFT, traffic, error, token, cost, retrieval success và quality proxy;
- tạo ít nhất 10 traces trên Langfuse, có span tree đọc được và metadata không chứa PII;
- liên kết trace với prompt name/label/version và chứng minh được một lần rollback;
- dựng dashboard 6 panel, định nghĩa một SLO cùng error budget và ba alert có runbook;
- viết incident note có chuỗi bằng chứng metric → log → trace.

## Sản phẩm phải nộp

- Source đã hoàn thiện các `TODO` bắt buộc.
- `submission/REPORT.md` đã điền và evidence đặt trong `submission/evidence/`.
- Kết quả tests, log validator và dashboard validator trên commit cuối.
- Ảnh dashboard có dữ liệu; ít nhất 10 trace IDs; một trace waterfall; prompt v1/v2 và evidence rollback.
- Một SLO/error budget, ba alert symptom-based có `duration`, kênh Slack và runbook.

## Bắt đầu nhanh

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Tự đăng ký/đăng nhập [Langfuse Cloud](https://cloud.langfuse.com), tạo project riêng tên `day13-k4-l3a-<MSSV>`, rồi vào **Project Settings → API Keys** để tạo key pair. Điền key của chính project đó vào `.env`:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

Không chia sẻ key và không chụp màn hình trang hiển thị secret. Xem các bước chi tiết tại [docs/SETUP.md](docs/SETUP.md).

> **Phân biệt evidence:** structured logs nằm ở terminal/`data/logs.jsonl`; Langfuse hiển thị traces/observations và prompt versions. Học viên phải tự chạy workload, tự tạo cả log lẫn trace rồi chụp evidence của mình.

Chạy API ở terminal thứ nhất:

```bash
uvicorn app.main:app --reload --env-file .env
```

Mở `http://127.0.0.1:8000/chat-demo` (hoặc đổi sang cổng 8001 nếu bạn chạy
server riêng ở cổng đó) để demo hội thoại bằng UI. Trang này gọi
chính API `/chat`, hiển thị agent latency, browser round trip, token/cost mô phỏng,
correlation ID và trace ID; từ đó mở log, trace hoặc dashboard. Đây là UI hỗ trợ
pitching, không thay thế các evidence và checkpoint bắt buộc. Không nhập PII thật.

Chạy baseline ở terminal thứ hai:

```bash
python scripts/load_test.py
python scripts/validate_logs.py
python scripts/validate_dashboard.py
python -m pytest -q
```

Baseline log chưa đạt là bình thường vì các `TODO` của CP1 chưa được làm. Ghi lại kết quả baseline vào `submission/REPORT.md` trước khi sửa.

## Lộ trình 14:00–18:00 (240 phút)

| Mốc | Thời gian | Việc chính | Hoàn thành khi |
|---|---:|---|---|
| CP0 | 14:00–14:30 (0–30 phút) | Setup, chạy API và baseline | `/health` trả `ok: true`, log được tạo |
| CP1 | 14:30–15:20 (30–80 phút) | Correlation ID, structured log, PII | `validate_logs.py` đạt ít nhất 80/100 |
| CP2 | 15:20–16:40 (80–160 phút) | Trace, prompt, dashboard, SLO/alert | có span tree; dashboard validator đạt 6/6 |
| CP3 | 16:40–17:30 (160–210 phút) | Điều tra challenge K4-L3A | có metric, log và trace cùng một request |
| CP4 | 17:30–18:00 (210–240 phút) | Report, evidence và kiểm tra cuối | tests/validators chạy xong trên commit nộp |

Chi tiết từng checkpoint nằm trong [docs/CHECKPOINTS.md](docs/CHECKPOINTS.md).

## Các phần cần làm

### CP1 — Logging và PII

- `app/middleware.py`: xóa context cũ; nhận `x-request-id` hoặc sinh `req-<8-hex>`; bind ID; trả ID và response time trong header.
- `app/main.py`: bind `user_id_hash`, `session_id`, `feature`, `model`, `env` trước log `request_received`.
- `app/logging_config.py`: chạy PII scrubber trước bước ghi file/render JSON.
- `app/pii.py`: hoàn thiện pattern và tests cho email, điện thoại Việt Nam, CCCD và thẻ thanh toán.

`validate_logs.py` đọc toàn bộ `data/logs.jsonl`. Sau khi lưu baseline, hãy xóa hoặc đổi tên log cũ, khởi động lại API rồi đo lại để không bị tính các dòng chưa scrub.

### CP2 — Tracing, prompt và dashboard

Starter dùng Langfuse Python SDK v4 và mới tạo root observation cho `LabAgent.run`. Bạn cần thêm child observation cho:

- retrieval: loại `retriever` hoặc `span`;
- LLM call: loại `generation`, có model, prompt, `input_tokens`, `output_tokens` và cost.

Không capture raw prompt/output chứa PII. Correlation ID phải xuất hiện trong trace metadata để nối trace với log.

Dashboard dùng `data/logs.jsonl` làm nguồn chuẩn và giữ đúng 6 panel trong `config/dashboard.yaml`. Panel latency phải có P50/P95/P99 và TTFT; panel errors phải thể hiện cả retrieval success. Sau đó hoàn thiện:

- `config/slo.yaml`: giải thích hoặc điều chỉnh SLO, tính error budget;
- `config/alert_rules.yaml`: ba alert symptom-based, có duration, severity, owner, Slack channel và runbook;
- `docs/alerts.md`: cách kiểm tra và mitigation cho từng alert.

### CP3 — Challenge chính thức

Chỉ chạy khi Lab Coach thông báo mở challenge của K4-L3A. Tại CP3, Lab Coach gửi riêng file đúng lớp; lưu file đó tại `config/challenge.json`. File này đã được `.gitignore` và **không được** force-add/commit/push:

```bash
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
python scripts/inject_incident.py --disable
python scripts/analyze_challenge.py
```

Điều tra theo thứ tự:

1. Xem dashboard để xác định metric xấu và khoảng thời gian.
2. Lọc `data/logs.jsonl`, lấy một `correlation_id` của request bất thường.
3. Tìm trace có cùng `correlation_id`, rồi so sánh các span.
4. Ghi root cause, fix action và preventive measure vào `submission/REPORT.md`.

Nếu cổng 8000 đã có API khác, chạy server lab trên 8001 và đặt
`$env:LAB_BASE_URL='http://127.0.0.1:8001'` trong PowerShell trước khi chạy
`inject_incident.py`/`load_test.py`. Có thể mở `/diagnostics/logs/{correlation_id}`
và `/diagnostics/trace/{trace_id}` trên loopback để xem log đã scrub và metadata
trace đọc live từ Langfuse; hai view này không thay thế ảnh Langfuse UI của CP2.

Không tự tạo, sửa, chia sẻ hoặc lấy `config/challenge.json` từ lớp khác. Nếu chưa nhận file riêng, tiếp tục practice bằng tham số `--scenario`; không chạy challenge chính thức.

## Kiểm tra trước khi nộp

```bash
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
git status --short
git log -1 --oneline
```

- [ ] Không có `.env`, secret, `.venv/`, PII thô hoặc evidence của học viên/lớp khác.
- [ ] `submission/REPORT.md` đã đủ; mọi ảnh dùng đường dẫn tương đối và mở được.
- [ ] Bạn demo và giải thích được luồng Metrics → Logs → Traces → Root cause.

## Tên repo bài nộp

Repo này là **repo đề bài**, nên tên chính thức là `K4-L3A-Day13-Monitoring-LLMOps` (mẫu `K4-L3A-TenBai`). Repo bài nộp cá nhân dùng mẫu:

```text
K4-L3-DAY13-HoVaTen-MSSV-Monitoring-LLMOps
```

Ví dụ: `K4-L3-DAY13-NguyenVanAn-123456-Monitoring-LLMOps`. Mỗi học viên nộp URL repo cá nhân và commit SHA cuối trên VLearn LMS/Codelabs. Xem đầy đủ tại [docs/SUBMISSION.md](docs/SUBMISSION.md).

Không push bài làm trực tiếp lên repo đề bài và không dùng chung repo bài nộp với học viên khác.

## Chạy bản triển khai trong repository cá nhân

Sau khi điền key Langfuse của project cá nhân vào `.env`, chạy API và mở
`http://127.0.0.1:8000/dashboard`. Dashboard đọc `data/logs.jsonl`, hiển thị đúng
6 panel trong cửa sổ 60 phút và refresh mỗi 30 giây. Để chạy thêm một API mà
không chiếm cổng 8000, dùng `--port 8001` và đặt
`LAB_BASE_URL=http://127.0.0.1:8001` trước khi gọi các script load/incident.

Các lệnh kiểm tra và bonus:

```powershell
python scripts/prompt_workflow.py status
python scripts/inspect_trace.py --recent-hours 2
python scripts/inspect_trace.py --correlation-id req-12345678
python scripts/compare_cost.py
python scripts/audit_log.py query
python scripts/audit_log.py prune
python scripts/check_submission.py --scan-only
python scripts/check_submission.py
```

`prompt_workflow.py bootstrap`, `promote` và `rollback` thay đổi prompt/label
trong project Langfuse đang cấu hình. Chỉ chạy bootstrap khi project chưa có
`day13-chat`; script không ghi đè version có sẵn. Sau đổi label cần khởi động
lại API hoặc đợi cache prompt 60 giây trước khi lấy trace evidence. Lệnh
`inspect_trace.py` dùng Observations API v2, chỉ in metadata an toàn, usage và
cost; không in raw input/output. `FAKE_LLM_STYLE=concise` là chế độ tối ưu cost
mô phỏng, cần restart API để áp dụng. Audit log và backup log baseline được
Git ignore; xem [docs/AUDIT.md](docs/AUDIT.md) để biết schema và retention.

Các ảnh Langfuse cần được chụp trực tiếp từ project của học viên. Challenge
chính thức chỉ chạy khi Lab Coach cấp file riêng cho đúng lớp.

## Tài liệu trong repo

- [SETUP.md](docs/SETUP.md): cài đặt và xử lý lỗi môi trường.
- [CHECKPOINTS.md](docs/CHECKPOINTS.md): đầu ra và cách tự kiểm tra từng mốc.
- [GUIDE.md](docs/GUIDE.md): gợi ý kỹ thuật khi bị kẹt.
- [PROMPT_VERSIONING.md](docs/PROMPT_VERSIONING.md): prompt v1/v2, label và rollback.
- [DASHBOARD_SETUP.md](docs/DASHBOARD_SETUP.md): mapping dữ liệu cho 6 panel.
- [RUBRIC.md](docs/RUBRIC.md), [RULES.md](docs/RULES.md), [SUBMISSION.md](docs/SUBMISSION.md): cách chấm, quy định và cách nộp.
- [grading-evidence.md](docs/grading-evidence.md): checklist nhanh các ảnh/output cần thu thập.
- [REPORT.md](submission/REPORT.md): báo cáo cá nhân duy nhất cần hoàn thiện.
