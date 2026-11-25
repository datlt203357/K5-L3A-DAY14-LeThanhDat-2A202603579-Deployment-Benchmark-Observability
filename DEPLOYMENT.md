# Deployment Information — CP6

## Public URL

https://agent-production-12dcc0d5.up.railway.app

## Platform

- Railway project: `k5-day14-agent`, environment: `production`.
- Service `agent`: mã nguồn từ `06-lab-complete/`, build bằng Dockerfile theo `railway.toml`, trạng thái `SUCCESS`.
- Service `Redis`: trạng thái `RUNNING`, được agent dùng cho rate limit và cost guard.
- [Xem service trong Railway](https://railway.com/project/5b1bd682-cc9c-4fda-b927-3b04ed28377f/service/e2748269-f1db-4754-9aca-901fc0bf190b).

## Environment Variables Set

| Biến | Cách đặt |
|---|---|
| `AGENT_API_KEY` | Key ngẫu nhiên 32 byte, đặt trong Railway; không ghi giá trị vào Git. |
| `REDIS_URL` | Tham chiếu `${{Redis.REDIS_URL}}` tới Redis cùng project. |
| `ENVIRONMENT` | `production`. |
| `PORT` | Railway cấp khi chạy; Dockerfile dùng `${PORT:-8000}`. |

## Test Commands

Đặt `BASE` và `AGENT_API_KEY` trong shell trước khi chạy. Lấy key từ biến môi trường của service Railway; không đưa giá trị thật vào ảnh hoặc repo.

```bash
BASE=https://agent-production-12dcc0d5.up.railway.app
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

Kết quả thực tế ngày **25/11/2026**, theo thứ tự: **200, 200, 401, 200**. Railway CLI báo deployment của agent `SUCCESS`; Redis cũng đang chạy. `GET /health` trả `{"status":"ok","environment":"production"}`.

### PowerShell: gửi câu hỏi có dấu tiếng Việt

Trong Windows PowerShell, chuyển JSON thành byte UTF-8 trước khi gửi để tránh lỗi `There was an error parsing the body`:

```powershell
cd D:\Workspace\AI20K\Lab_Day_14\06-lab-complete
$base = 'https://agent-production-12dcc0d5.up.railway.app'
$key = (railway.cmd variable list --service agent --json | ConvertFrom-Json).AGENT_API_KEY
$json = @{ question = 'Xin chào' } | ConvertTo-Json -Compress
$body = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Method Post -Uri "$base/ask" `
  -Headers @{ 'X-API-Key' = $key } `
  -ContentType 'application/json; charset=utf-8' `
  -Body $body
```

Lệnh này đã được chạy với `Xin chào` và trả **HTTP 200**.

## Screenshots

- [Railway dashboard: `agent` và Redis Online, deployment Successful](screenshots/dashboard.png).
- [Service running: phản hồi `/health` thật](screenshots/running.png).
- [Bốn kết quả kiểm tra HTTP](screenshots/test.png) — ảnh chụp trang tổng hợp kết quả từ request thực tế; [nguồn HTML](screenshots/test-results.html).
- [Trạng thái triển khai](screenshots/status.png) — ảnh chụp trang ghi lại kết quả Railway CLI, không phải dashboard Railway; [nguồn HTML](screenshots/status.html).
