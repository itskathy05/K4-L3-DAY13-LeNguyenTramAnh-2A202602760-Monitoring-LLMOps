# Alert và runbook Day 13

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `user_latency_p95_high`
- Severity: critical
- Duration: 5 phút
- Kênh thông báo: Slack `#day13-l3a-ops`
- SLI/SLO liên quan: P95 latency ≤ 3000 ms; good request trong 28 ngày.
- Điều kiện và thời gian duy trì: P95 > 3000 ms trong 5 phút, có ít nhất 5 requests trong cửa sổ.
- Ảnh hưởng tới người dùng: trả lời chậm, request có thể vượt ngưỡng SLO.
- Ba bước kiểm tra đầu tiên: (1) xác định phút P95 tăng trên dashboard; (2) lọc log `response_sent` chậm, lấy `correlation_id`; (3) mở trace cùng ID, so thời lượng retrieval và generation.
- Mitigation tạm thời: nếu retrieval chậm, tạm tắt nguồn retrieval lỗi hoặc dùng fallback an toàn; nếu generation chậm, giảm tải và theo dõi lại P95.
- Owner: `student-operator`.

## Alert 2

- Tên: `user_request_error_rate_high`
- Severity: critical
- Duration: 5 phút
- Kênh thông báo: Slack `#day13-l3a-ops`
- SLI/SLO liên quan: error rate ≤ 2%; retrieval success rate ≥ 90%.
- Điều kiện và thời gian duy trì: error rate > 2% trong 5 phút, có ít nhất 5 requests trong cửa sổ.
- Ảnh hưởng tới người dùng: request thất bại, không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên: (1) xem error rate và breakdown; (2) lọc `request_failed` và `error_type`, lấy `correlation_id`; (3) mở trace cùng ID, tìm observation lỗi và kiểm tra retrieval success.
- Mitigation tạm thời: chuyển sang tài liệu fallback khi retrieval lỗi, giới hạn request bị ảnh hưởng và kiểm tra lại error rate.
- Owner: `student-operator`.

## Alert 3

- Tên: `user_cost_budget_high`
- Severity: warning
- Duration: 10 phút
- Kênh thông báo: Slack `#day13-l3a-ops`
- SLI/SLO liên quan: daily cost guardrail ≤ 2.5 USD (cost mô phỏng của fake LLM).
- Điều kiện và thời gian duy trì: tổng cost trong 24 giờ > 2.5 USD, kéo dài 10 phút.
- Ảnh hưởng tới người dùng: chi phí phục vụ tăng bất thường, có nguy cơ vượt ngân sách.
- Ba bước kiểm tra đầu tiên: (1) so cost với traffic cùng khoảng thời gian; (2) xem `tokens_in`, `tokens_out` và cost theo log của request tăng mạnh; (3) mở generation observation để kiểm tra token/cost và prompt version.
- Mitigation tạm thời: dùng chế độ trả lời ngắn đã kiểm chứng quality, giới hạn độ dài câu trả lời và theo dõi cost trên cùng workload.
- Owner: `student-operator`.

Các rule ở `config/alert_rules.yaml` là cấu hình và runbook của lab; tên Slack channel là đích dự kiến, không ngụ ý đã có hệ thống gửi thông báo thật.
