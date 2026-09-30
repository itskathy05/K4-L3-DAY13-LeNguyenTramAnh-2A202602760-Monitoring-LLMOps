# Bonus audit log

App ghi thao tác bật/tắt incident và request lỗi vào `data/audit.jsonl`, độc lập
với structured log dùng cho dashboard. Schema kiểm tra nằm ở
`config/audit_schema.json`: thời gian UTC, nhãn actor của lab, action, outcome,
correlation ID và details đã scrub. `local-lab-operator` chỉ là nhãn của môi
trường lab, không phải danh tính đã xác thực.

Retention là 30 ngày. Lệnh prune mặc định chỉ dự báo số dòng sẽ xóa; `--apply`
mới ghi lại file. Chỉ chạy khi không có API đang ghi vào audit log.

```powershell
python scripts/audit_log.py query --correlation-id req-12345678
python scripts/audit_log.py query --since 2026-09-29T00:00:00Z
python scripts/audit_log.py prune
python scripts/audit_log.py prune --apply
```

Audit log chứa ID để nối với log/trace, không chứa raw message, prompt, key
hoặc PII. File này được Git ignore; evidence cần chụp output truy vấn đã kiểm
tra không chứa dữ liệu nhạy cảm.
