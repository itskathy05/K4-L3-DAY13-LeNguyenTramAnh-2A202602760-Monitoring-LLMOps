# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Báo cáo đối chiếu source, kết quả kiểm thử và evidence runtime trong project Langfuse cá nhân. Các số liệu mô phỏng của FakeLLM được phân biệt với request, log và trace chạy thật. Mỗi kết luận về incident đều có metric, correlation ID và trace ID để kiểm chứng.

## 1. Thông tin học viên

- **Họ và tên:** Lê Nguyễn Trâm Anh
- **MSSV:** 2A202602760
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/itskathy05/K4-L3-DAY13-LeNguyenTramAnh-2A202602760-Monitoring-LLMOps
- **Commit SHA cuối:** xem SHA nộp trên LMS/Codelabs sau khi hoàn tất artifact.
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`; file gốc do Lab Coach cấp cho K4-L3A đã sao chép nguyên byte vào `config/challenge.json` và được Git ignore.
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602760`.

## 2. Evidence index

Các liên kết dưới đây mở trực tiếp từ repository và nối từng tiêu chí với output hoặc ảnh runtime tương ứng.

| Evidence | Đường dẫn |
|---|---|
| CP0 baseline | [00-cp0-baseline.txt](evidence/00-cp0-baseline.txt) |
| Pytest cuối | [01-pytest.txt](evidence/01-pytest.txt) |
| Log validator | [02-log-validator.txt](evidence/02-log-validator.txt) |
| Dashboard validator | [03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) |
| Structured log | [04-structured-log.png](evidence/04-structured-log.png), [04-structured-log.txt](evidence/04-structured-log.txt) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png), [05-pii-redaction.txt](evidence/05-pii-redaction.txt) |
| Trace list | [06-trace-list.jpg](evidence/06-trace-list.jpg), [06-trace-list.txt](evidence/06-trace-list.txt) |
| Trace waterfall | [07-trace-waterfall.jpg](evidence/07-trace-waterfall.jpg), [07-trace-waterfall.txt](evidence/07-trace-waterfall.txt); ảnh UI ở chế độ Timeline, hiển thị root và hai child cùng thời lượng span. |
| Trace metadata | [08-trace-metadata.jpg](evidence/08-trace-metadata.jpg), [08-trace-metadata.txt](evidence/08-trace-metadata.txt) |
| Prompt versions | [09-prompt-versions.jpg](evidence/09-prompt-versions.jpg), [09-prompt-versions.txt](evidence/09-prompt-versions.txt) |
| Prompt rollback | [10-prompt-rollback.jpg](evidence/10-prompt-rollback.jpg), [10-prompt-rollback.txt](evidence/10-prompt-rollback.txt) |
| Dashboard runtime | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric chính thức | [12-incident-metric.png](evidence/12-incident-metric.png), [12-incident-metric.txt](evidence/12-incident-metric.txt) |
| Incident log chính thức | [13-incident-log.png](evidence/13-incident-log.png), [13-incident-log.txt](evidence/13-incident-log.txt) |
| Incident trace chính thức | [14-incident-trace.jpg](evidence/14-incident-trace.jpg) chụp trực tiếp từ Langfuse, [14-incident-trace.txt](evidence/14-incident-trace.txt) ghi độ chính xác mili giây; [API view](evidence/14-incident-trace-api-view.png) là bằng chứng bổ sung. |
| Bonus cost | [15-cost-comparison.txt](evidence/15-cost-comparison.txt) |
| Bonus audit | [16-audit-demo.txt](evidence/16-audit-demo.txt) |
| Ba incident practice | [17-practice-incidents.txt](evidence/17-practice-incidents.txt) |
| UI chat để pitching (tùy chọn) | [18-chat-demo.png](evidence/18-chat-demo.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | 0 thiếu trường/context, 0 PII leak trên log mới; output cuối ở evidence 02. |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract giữ đúng sáu panel; runtime có ảnh riêng. |
| `pytest` | 22 passed | 36 passed | Có test mới cho context, PII, dashboard, audit, cost, diagnostic views và chat demo UI. |
| Số traces hợp lệ | Chưa xác minh tại CP0 | ≥10 trong workload cá nhân | API v2 đếm 26 root traces trong 2 giờ kiểm tra. |
| Số PII leak | 0 trong validator CP0 | 0 | Mẫu test giả được scrub trước ghi file/trace. |
| Latency P95 / TTFT P95 | Chưa ghi nhận | 2654 ms / 50 ms | Kết quả cửa sổ incident ở evidence 12; đây là thời gian agent nội bộ, không phải HTTP end-to-end. |
| Retrieval success rate | Chưa ghi nhận | 100% | Challenge `rag_slow` làm chậm retrieval nhưng không làm nó thất bại. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware chỉ nhận `x-request-id` khớp `req-<8-hex>`, chuẩn hóa chữ thường; còn lại sinh ID mới. ID được bind vào context và trả qua response body/header, cùng `x-response-time-ms`. Context bị xóa trước/sau request để tránh rò giữa request đồng thời.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `correlation_id`, `env`, `user_id_hash`, `session_id`, `feature`, `model`; response có latency, TTFT, token, cost, quality và trace ID.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` duyệt mọi chuỗi kể cả cấu trúc lồng nhau sau khi format exception nhưng trước file writer/JSON renderer. Trace chỉ ghi metadata an toàn; raw input/output không được capture.
- **Cách kiểm chứng kết quả:** [PII evidence](evidence/05-pii-redaction.txt), test request đồng thời và `validate_logs.py` 100/100. Log CP0, trước challenge và lần challenge đầu được giữ riêng ở các file backup đã Git ignore; validator chỉ đọc log mới sau sửa. Regex điện thoại được điều chỉnh để không che nhầm trace ID hex, có regression test.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** chạy `load_test.py --concurrency 5` với key đang gắn project `day13-k4-l3a-2A202602760`; `inspect_trace.py` đọc Observations API v2, liệt kê 10 trace IDs trong `evidence/06-trace-list.txt`.
- **Cấu trúc root/retrieval/generation observations:** trace `898fbbb9d59c5274d10b866c1c8e0817` có root AGENT `6db7e23eea1f8717`, RETRIEVER `424db21408295245`, GENERATION `a571511ab4d94d67`; hai child cùng trỏ parent root.
- **Cách nối trace với log:** `response_sent` của `req-63892c79` chứa trace ID trên; metadata root/generation có cùng correlation ID. Generation có model, input=28, output=36, cost=0.000624 USD; `raw_io_present=false`.
- **Prompt name:** `day13-chat`, text prompt với biến `feature`, `docs`, `message`.
- **Version/label baseline:** v1=`baseline` và trạng thái cuối `production`.
- **Version/label candidate:** v2=`candidate`.
- **Trace ID của mỗi version:** baseline v1 `898fbbb9d59c5274d10b866c1c8e0817`; candidate v2 `c32f2e15d24a81ac888d1c4aad3f0abe` trên cùng input.
- **Cách promote và rollback `production`:** promote sang v2, xác nhận trace `48166ea6c62854ef10c6dc1270e17c1c` ghi `production`/v2; rollback về v1, xác nhận trace `fd41c08551c210a97df562e213d6b37a` ghi `production`/v1. [Ảnh 09](evidence/09-prompt-versions.jpg) và [ảnh 10](evidence/10-prompt-rollback.jpg) thể hiện trạng thái cuối; hai trace ID là bằng chứng version đã thực sự được dùng trước và sau rollback.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `/dashboard` đọc `data/logs.jsonl`, lấy cửa sổ UTC 60 phút và refresh 30 giây. Sáu panel là latency P50/P95/P99+TTFT, traffic, errors+retrieval, cost, tokens, quality. Panel errors dùng cả `response_sent` để đếm retrieval success vì field `tool_success=true` được ghi ở event này. Ảnh `evidence/11-dashboard-overview.png` có dữ liệu, đơn vị, thời gian và threshold.
- **UI hỗ trợ demo (không phải checkpoint bắt buộc):** `/chat-demo` gọi cùng API `/chat`, hiển thị câu trả lời, agent latency so với browser round trip, token/cost mô phỏng và link tới log/trace theo ID thật. Ảnh giao diện ban đầu ở [evidence 18](evidence/18-chat-demo.png); không dùng nó thay screenshot Langfuse.
- **SLO và lý do chọn:** `config/slo.yaml` giữ mục tiêu 99,5% request thành công trong ≤3000 ms trên cửa sổ 28 ngày, thống nhất với threshold latency trong dashboard. Dashboard hiện dùng `latency_ms` đo thời gian agent nội bộ; số client end-to-end phải lấy từ load tester, đặc biệt khi request đồng thời xếp hàng. Vì vậy không suy rằng SLO end-to-end đạt chỉ từ dashboard.
- **Cách tính error budget:** 100%-99,5%=0,5% tổng request; với 10.000 request là 50 request lỗi hoặc vượt 3000 ms. Không suy thời lượng downtime từ ngân sách request khi lưu lượng biến động.
- **Ba alert và runbook tương ứng:** latency P95 cao, error rate cao và daily cost vượt ngân sách; rule nằm ở `config/alert_rules.yaml`, ba bước điều tra/mitigation ở `docs/alerts.md`. Slack channel là cấu hình dự kiến `#day13-l3a-ops`, chưa có tích hợp gửi thông báo thật.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`, cohort K4, seed 1311, incident `rag_slow`, feature `monitoring`; bản sao `config/challenge.json` có cùng SHA-256 với file Coach và không bị commit.
- **Khoảng thời gian điều tra:** bật incident 2026-09-29 08:25:50 UTC, tắt 08:26:13 UTC; workload 5 query chính thức chạy ở giữa. Ảnh [metric](evidence/12-incident-metric.png), [log](evidence/13-incident-log.png), [trace Langfuse](evidence/14-incident-trace.jpg) cùng sự cố.
- **Triệu chứng từ metrics:** với cùng 5 session, baseline P95 nội bộ 1864 ms và 0/5 vượt ngưỡng riêng của challenge 2000 ms; khi bật `rag_slow`, P95 2654 ms và 5/5 vượt ngưỡng. Dashboard tổng 10 request có P95 2654 ms, TTFT P95 50 ms, error rate 0%, retrieval success 100%. Ngưỡng 2000 ms của challenge khác đường SLO 3000 ms trên dashboard; không gọi đây là vi phạm đường SLO đó. Client wall time cho 5 request đồng thời khoảng 13,3 giây do xếp hàng.
- **Log line và correlation ID liên quan:** `response_sent` lúc 08:25:57.926567 UTC có `correlation_id=req-75c5179d`, `latency_ms=2653`, `tool_success=true`, `trace_id=4e86a88524e80a4b0a8e29bc6ce8887a`; log đầy đủ ở [evidence 13](evidence/13-incident-log.txt).
- **Trace ID và span gây ảnh hưởng:** trace trên chứa root AGENT 2,653 s, child RETRIEVER `retrieval` 2,501 s và child GENERATION 0,152 s; cả ba cùng correlation ID. [Ảnh Langfuse](evidence/14-incident-trace.jpg) hiển thị số làm tròn 2,65/2,50/0,15 s; [Observations API v2](evidence/14-incident-trace.txt) ghi giá trị chính xác đến mili giây.
- **Root cause:** nhánh `rag_slow` trong `app/mock_rag.py` gọi `time.sleep(2.5)` trước khi trả tài liệu. Retrieval chiếm khoảng 94% thời gian agent; generation không gây chậm. Vì `/chat` là async nhưng gọi agent đồng bộ, năm request concurrent còn bị tuần tự hóa, làm client wall time cao hơn latency ghi trong dashboard.
- **Fix action:** đã tắt incident ngay sau workload. Khi xử lý production thật, bỏ delay mô phỏng; chuyển retrieval blocking sang async I/O hoặc threadpool có timeout/circuit breaker, rồi xác nhận lại P95 và client wall latency trên cùng 5 query.
- **Preventive measure:** alert riêng cho retrieval span P95 và tỷ lệ request vượt ngưỡng, test concurrency dưới tải, đo cả HTTP end-to-end latency ngoài agent latency, liên kết log–trace bằng correlation ID và diễn tập rollback.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** triển khai dashboard trực tiếp trên log JSONL theo contract để metric vẫn tái tính được sau khi API khởi động lại. Langfuse tập trung vào cấu trúc span và prompt version; `correlation_id` nối hai nguồn dữ liệu khi điều tra một request.
- **Một lỗi/blocker đã gặp:** API đọc trace cũ của Langfuse trả HTTP 410 với project mới; ngoài ra một lần khởi động API cổng 8000 báo cổng đã được tiến trình hiện có sử dụng.
- **Cách tìm nguyên nhân và xử lý:** kiểm tra HTTP status 410, chuyển script đọc sang Observations API v2; kiểm tra cổng đang dùng, chạy runtime riêng ở cổng 8001 và xác nhận `/health` trước khi tạo workload.
- **Cách hiểu luồng Metrics → Logs → Traces:** challenge chính thức làm 5/5 request vượt 2000 ms; log khoanh vùng `req-75c5179d`; trace cùng ID chỉ ra retrieval 2,501 s trong root 2,653 s. Practice `tool_fail` vẫn có ở [evidence 17](evidence/17-practice-incidents.txt) nhưng không dùng thay challenge.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** version/label làm rõ request đã dùng prompt nào và rollback được; token/cost phát hiện tăng độ dài câu trả lời dù traffic không tăng; SLO/error budget lượng hóa tác động tới người dùng. Cost ở repo là mô phỏng của fake LLM.
- **Bonus đã triển khai:** cùng 10 input, concise giảm cost mô phỏng 38,93% với quality mean 0,86 ≥ 0,75 (`evidence/15-cost-comparison.txt`); CI/scan trong `.github/workflows/verify.yml` và `scripts/check_submission.py`; audit có schema, retention 30 ngày, truy vấn mẫu (`evidence/16-audit-demo.txt`). Bonus tối đa 10 dù có ba hạng mục.
- **Điều quan trọng nhất đã học:** P95 chỉ cho thấy có triệu chứng; log khoanh vùng request, còn thời lượng của child span mới xác định được bước gây chậm. Việc giữ cùng `correlation_id` từ HTTP response đến log và trace giúp kiểm tra kết luận thay vì suy đoán từ một biểu đồ tổng hợp.
- **Phạm vi đo và bước nộp còn lại:** dashboard đo agent latency trên dữ liệu lab, chưa có lịch sử 28 ngày để xác nhận SLO dài hạn; token/cost là ước lượng của FakeLLM. Ảnh incident trace đã chụp trực tiếp trên Langfuse; view local đọc API v2 được giữ riêng để đối chiếu số liệu. Cần commit/push artifact và nộp URL cùng SHA cuối trên LMS/Codelabs.

## 9. Khả năng tái hiện và đối chiếu artifact

Trên cây source dùng để tạo báo cáo, `python -m pytest -q` đạt 36 tests pass; `validate_logs.py` đạt 100/100 trên 51 log records với 0 PII leak; `validate_dashboard.py` đạt 6/6. Kết quả lệnh được lưu ở evidence 01–03. Bộ kiểm tra submission cũng xác nhận các liên kết evidence và scan credential/PII ở phần văn bản. `.env`, log runtime, audit log và file challenge chính thức đều được Git ignore. URL repository ở mục 1 là địa chỉ nộp; SHA của commit chứa toàn bộ artifact được ghi trên LMS/Codelabs để tránh tự tham chiếu SHA trong chính file báo cáo.
