# Kịch bản pitching Day 13 — khoảng 6 phút

Đây là dàn ý để **học viên tập và diễn đạt lại bằng lời của mình**, không phải lời thoại bắt buộc học thuộc. Chỉ nói số liệu đã có evidence; không gọi fake LLM là model thật và không tuyên bố đạt điểm tuyệt đối trước khi được chấm.

## 1. Chuẩn bị trước khi trình bày

Trong PowerShell tại thư mục repo, chạy API trên cổng 8001 nếu cổng 8000 đang có tiến trình khác:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --env-file .env
```

Mở sẵn các tab sau, theo thứ tự:

1. `http://127.0.0.1:8001/chat-demo` — UI chat tương tác thật với API `/chat`.
2. `http://127.0.0.1:8001/dashboard` — sáu panel lấy từ log JSONL.
3. `http://127.0.0.1:8001/diagnostics/logs/req-75c5179d` — log của request challenge.
4. `http://127.0.0.1:8001/diagnostics/trace/4e86a88524e80a4b0a8e29bc6ce8887a` — waterfall đọc live từ Langfuse API.
5. Giao diện Langfuse project `day13-k4-l3a-2A202602760`: trace list và Prompt Management → `day13-chat`.
6. Ảnh `submission/evidence/12-incident-metric.png` nếu dashboard live đã vượt khỏi cửa sổ 60 phút của incident.

Chạy các cổng kiểm tra trước demo hoặc để sẵn output:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\validate_logs.py
.\.venv\Scripts\python.exe scripts\validate_dashboard.py
.\.venv\Scripts\python.exe scripts\analyze_challenge.py
```

Không mở `.env`, trang API keys hay nội dung `config/challenge.json` trước khán giả. Nếu script `check_submission.py` còn báo thiếu ảnh `06`–`10`, không trình bày nó như một cổng đã pass.

## 2. Lời nói và thao tác

| Mốc | Thao tác trên màn hình | Gợi ý lời trình bày |
|---|---|---|
| 0:00–0:35 — Mở đầu | Mở Chat demo; chỉ menu Dashboard và trạng thái API + tracing. | “Mục tiêu lab không phải làm chatbot thông minh hơn, mà là biến một AI API hộp đen thành hệ thống biết **triệu chứng gì, request nào, span nào** gây sự cố. Em đi theo Metrics → Logs → Traces.” |
| 0:35–1:25 — Tạo request | Chọn feature `monitoring`, bấm gợi ý **Metrics → Logs → Traces**, rồi **Gửi**. Chờ câu trả lời và panel bên phải hiện ID. | “Đây là UI thật gọi `/chat`; backend dùng **FakeLLM theo đề**, nên câu trả lời/token/cost là mô phỏng. Nhưng request, structured log và Langfuse trace được tạo thật. Agent latency là thời gian trong agent; browser round trip là thời gian người dùng chờ.” |
| 1:25–2:10 — Nối log và trace | Chỉ `correlation ID`, `trace ID`; bấm **Mở log**, rồi **Mở trace**. Nếu trace mới chưa hiện, refresh sau vài giây hoặc dùng trace challenge đã mở sẵn. | “Correlation ID là chìa khóa để tìm dòng log của một HTTP request. Trace ID đưa em tới waterfall của request đó. Log trả lời *request nào*; trace trả lời *bước nào*.” |
| 2:10–3:25 — Challenge chính thức | Mở evidence `12`, sau đó tab log `req-75c5179d` và trace `4e86a88524e80a4b0a8e29bc6ce8887a`. Chỉ rõ root, retriever và generation. | “Với cùng 5 query, P95 agent trước injection là **1864 ms**, sau `rag_slow` là **2654 ms**; **5/5** vượt ngưỡng challenge **2000 ms**. Log chỉ ra `req-75c5179d`, latency **2653 ms**. Trace cùng ID cho thấy retrieval **2501 ms** trong khi generation chỉ **152 ms**: retrieval là nút thắt. Trong code, nhánh incident gọi `time.sleep(2.5)`; lời gọi đồng bộ trong endpoint async còn làm các request concurrent xếp hàng.” |
| 3:25–4:15 — Hành động xử lý | Chỉ trạng thái incident đã tắt trong `/health` hoặc report; mở dashboard/screenshot. | “Em đã tắt incident sau workload. Với hệ thống thật, hướng sửa là bỏ delay, đưa retrieval blocking sang async hoặc threadpool có timeout/circuit breaker, rồi đo lại cả P95 trong agent và end-to-end. Ngưỡng **2000 ms của challenge** khác đường **3000 ms của SLO dashboard**; em không đánh đồng hai ngưỡng.” |
| 4:15–5:00 — Prompt & vận hành | Trong Langfuse mở `day13-chat`, chỉ v1/v2 và labels; hoặc dùng evidence `09`–`10`. | “Prompt có ba biến `feature`, `docs`, `message`. v1 mang `baseline`/`production`, v2 mang `candidate`; em đã promote production lên v2 rồi rollback về v1 và xác nhận bằng trace ID. Model label trong trace là metadata của fake LLM, không có phí nhà cung cấp thật.” |
| 5:00–5:40 — SLO, alert, bonus | Mở dashboard; nhắc `config/slo.yaml`, `config/alert_rules.yaml` và evidence cost. | “SLO định nghĩa 99,5% request thành công trong ≤3000 ms trên 28 ngày, tức budget 0,5% hay 50 bad requests/10.000. Ba alert theo triệu chứng là latency, error rate và cost, có owner/duration/runbook. Bonus concise giảm **38,93% cost mô phỏng** trên cùng 10 input mà vẫn qua guardrail quality.” |
| 5:40–6:00 — Kết | Hiện output tests/validator hoặc evidence `01`–`03`. | “Sau triển khai, tests pass, log validator 100/100 và dashboard contract 6/6. Điểm thực tế vẫn phụ thuộc evidence runtime, report cá nhân và chấm của Lab Coach.” |

## 3. Các thao tác phải tập trước

1. Trong Chat demo, bấm một câu mẫu rồi **Gửi**; đợi response hiện đủ latency, token, cost và ID. Nếu muốn kể chuyện refund, dùng gợi ý **Refund policy** thay vì câu monitoring.
2. Bấm **Mở log** và đọc cùng một `correlation_id` ở `request_received` và `response_sent`. Không cần đọc mọi trường JSON; chỉ nêu timestamp, feature, latency, trace ID.
3. Bấm **Mở trace**. Trace mới có thể chưa được Langfuse ingest ngay; chờ vài giây và refresh. Để đảm bảo demo, luôn chuẩn bị trace challenge cố định nêu trên.
4. Trên waterfall, chỉ vào ba observation: root `lab-agent-run` → child `retrieval` và child `fake-llm-generation`. So thời lượng để chứng minh root cause.
5. Với incident chính thức, dùng evidence `12`–`14`. Không cần bật lại challenge để “tạo số đẹp”; log và trace đã có. Nếu dashboard 60 phút đã qua, nói rõ đây là ảnh lúc sự cố và mở `scripts/analyze_challenge.py` để tái tính từ log.
6. Kết thúc bằng tests/validators và nhắc rằng UI chat là **phần demo thêm**, không thay bằng chứng CP2 trên Langfuse.

## 4. Trả lời nhanh khi được hỏi

- **Vì sao dùng FakeLLM?** Repo starter quy định vậy; mục tiêu là monitoring/LLMOps, không phải tích hợp provider. Token/cost là ước lượng nhất quán để quan sát, không phải hóa đơn thật.
- **Correlation ID khác Trace ID?** Correlation ID do middleware gán cho HTTP request và xuất hiện trong log/trace metadata; Trace ID là ID waterfall của Langfuse.
- **Vì sao nhìn average latency là chưa đủ?** Một nhóm request chậm ở đuôi phân phối có thể bị trung bình che khuất; P95 cho thấy trải nghiệm tail latency.
- **Vì sao P95 2654 ms là incident dù dashboard có đường 3000 ms?** Challenge đặt ngưỡng riêng 2000 ms; 5/5 request vượt ngưỡng đó. Đường 3000 ms là SLO cấu hình của dashboard. Browser round trip concurrent còn cao hơn agent latency vì xếp hàng.
- **Vì sao biết retrieval là root cause?** Cùng một request `req-75c5179d`, log ghi chậm; trace cho thấy retrieval 2501 ms trên tổng agent 2653 ms, còn generation 152 ms. Nhánh `rag_slow` trong code đúng là delay 2,5 giây.
- **PII được bảo vệ ở đâu?** Processor scrub duyệt mọi chuỗi lồng nhau trước khi ghi file/render JSON; trace không capture raw input/output. Demo chỉ dùng dữ liệu giả.
- **Validator 100/100 có nghĩa là đạt 100 điểm?** Không. Còn phải có ảnh Langfuse, incident cùng ID, report do học viên tự viết và đúng URL/SHA nộp.

## 5. Phương án dự phòng

- **Cổng 8000 bận:** dùng 8001 và sửa URL tab cho đúng cổng; không tự tắt tiến trình không biết của ai.
- **Trace mới chưa hiện:** dùng trace challenge cố định hoặc ảnh Langfuse `14-incident-trace.jpg`, sau đó refresh Langfuse.
- **Dashboard không còn dữ liệu sự cố:** dùng ảnh `12-incident-metric.png` và output `analyze_challenge.py`, giải thích cửa sổ dashboard chỉ 60 phút.
- **Langfuse UI chậm/không đăng nhập được:** trình bày evidence text/ảnh đã lưu; không tạo ảnh giả và không lộ key.
- **Hết thời gian:** ưu tiên ba bước metric → log → trace và kết luận root cause; bonus chỉ nói nếu còn thời gian.
