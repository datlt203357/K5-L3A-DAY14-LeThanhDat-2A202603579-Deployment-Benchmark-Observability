# Day 14 — Mission Answers

Ngày thực hiện: 25/11/2026. Các phép thử Python chạy trong Ubuntu/WSL2 (Python 3.12.3); Docker chạy qua Docker Desktop. Agent trong lab dùng mock LLM nên nội dung câu trả lời có thể thay đổi giữa các lần gọi. Các mã HTTP và số đo dưới đây lấy từ lần chạy thực tế.

## Part 1 — Localhost vs Production (CP1)

### Exercise 1.1 — Anti-patterns trong bản develop

1. `OPENAI_API_KEY` được viết trực tiếp trong `01-localhost-vs-production/develop/app.py`. Nếu dùng key thật rồi push repo công khai, người khác có thể lấy và sử dụng key. Bản production đọc `OPENAI_API_KEY` từ môi trường trong `config.py`.
2. `DATABASE_URL` chứa tên đăng nhập và mật khẩu trong code. Đây cũng là secret cần chuyển sang cấu hình bên ngoài repo.
3. `DEBUG=True`, `MAX_TOKENS=500` và `port=8000` cố định trong code. Khi deploy, nền tảng có thể cấp port hoặc cấu hình khác; bản production đọc các giá trị từ biến môi trường.
4. Handler dùng `print()` thay vì log có cấu trúc. Khó tìm và lọc sự kiện theo trường khi có nhiều instance; bản production dùng logging và đưa thông tin sự kiện vào log.
5. Handler in cả `OPENAI_API_KEY` ra log. Ngay cả khi key không nằm trong Git, người được xem log vẫn có thể đọc được key; bản production không log secret.
6. Bản develop không có `/health` hoặc `/ready`, nên nền tảng không có tín hiệu rõ ràng về việc process còn sống và đã sẵn sàng nhận traffic.
7. `host="localhost"` chỉ nhận kết nối nội bộ; trong container, ứng dụng cần bind `0.0.0.0` để Nginx hoặc cổng được publish kết nối được.
8. `reload=True` là chế độ dành cho phát triển. Bản production điều khiển reload bằng `DEBUG` và có lifecycle để khởi tạo, dọn dẹp khi tắt.

### Exercise 1.2 — Chạy bản develop

```text
POST /ask?question=Hello → HTTP 200
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

`question` của bản develop là query parameter. Gửi JSON body theo lệnh cũ trong `CODE_LAB.md` sẽ nhận 422.

### Exercise 1.3 — So sánh

| Tính năng | Develop | Production | Vì sao quan trọng? |
|---|---|---|---|
| Config/port | Giá trị cố định trong code | Đọc từ biến môi trường | Chạy cùng mã nguồn ở local và cloud với cấu hình khác nhau. |
| Secret | Có key và database URL trong code, còn in key ra log | Đọc key từ môi trường, không log key | Giảm nguy cơ lộ thông tin truy cập. |
| Host | `localhost` | `0.0.0.0` | Cho phép container nhận kết nối qua mạng Docker. |
| Logging | `print()` | Logging với trường sự kiện | Thu thập và lọc log thuận tiện hơn. |
| Health/readiness | Không có | Có `/health`, `/ready` | Nền tảng biết process còn sống và có nên gửi traffic vào không. |
| Shutdown | Không có lifecycle riêng | Có startup/shutdown trong `lifespan` | Dọn dẹp tài nguyên và xử lý quá trình tắt. |

Kết quả kiểm tra bản production:

```text
GET /health → HTTP 200, "status":"ok"
GET /ready  → HTTP 200, "ready":true
POST /ask với JSON {"question":"Hello"} → HTTP 200
```

## Part 2 — Docker (CP2)

### Exercise 2.1 — Đọc Dockerfile develop

1. Base image: `python:3.11`.
2. Working directory bên trong container: `/app` (`WORKDIR /app`).
3. `COPY requirements.txt` đứng trước `COPY app.py` để Docker có thể dùng lại layer cài dependencies khi chỉ sửa code ứng dụng.
4. `CMD` cung cấp lệnh mặc định khi chạy container và có thể bị thay thế bằng đối số của `docker run`. `ENTRYPOINT` xác định chương trình chính; đối số khi chạy thường được nối vào chương trình đó. Dockerfile develop dùng `CMD ["python", "app.py"]`.

### Exercise 2.2–2.3 — Build, chạy và đo image

Build hai image từ gốc repo bằng Dockerfile tương ứng. Container develop trả:

```text
POST /ask?question=What%20is%20Docker%3F → HTTP 200
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Đo bằng `docker image inspect --format '{{.Size}}'`:

| Image | Byte | MiB |
|---|---:|---:|
| `my-agent:develop` | 426319930 | 406,6 |
| `my-agent:advanced` | 57409034 | 54,7 |

Mức giảm theo số byte: **86,5%** = `(develop − advanced) / develop × 100`. Stage builder của image advanced cài build tools và Python dependencies; stage runtime bắt đầu từ `python:3.11-slim` sạch, chỉ chép packages và mã cần chạy, rồi dùng user không phải root. Các công cụ build không nằm trong image cuối.

### Exercise 2.4 — Docker Compose

```text
Client → Nginx (:80) → agent (:8000)
                         ├─ Redis (:6379), cấu hình cache/state
                         └─ Qdrant (:6333), cấu hình vector database
```

`docker compose ps` cho thấy `agent`, `nginx`, `redis`, `qdrant` đều chạy; `agent`, `redis`, `qdrant` báo healthy. Kết quả qua Nginx:

```text
GET /health → HTTP 200, {"status":"ok", ..., "version":"2.0.0"}
POST /ask với {"question":"Explain microservices"} → HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Trong ví dụ này, agent mock chưa thực sự truy vấn Redis hoặc Qdrant để tạo câu trả lời; Compose minh họa cách các service được nối mạng và khởi động cùng nhau. Stack đã được dừng sau khi kiểm tra.

## Part 3 — Cloud Deployment (CP6)

### Exercise 3.1 — Railway

Đã triển khai agent trong `06-lab-complete/` bằng Dockerfile và `railway.toml` lên project Railway `k5-day14-agent` (environment `production`). Service `agent` và `Redis` đều chạy; `AGENT_API_KEY` được tạo ngẫu nhiên và đặt trên Railway, `REDIS_URL` tham chiếu `${{Redis.REDIS_URL}}` trong cùng project. Không lưu giá trị key vào repo.

- URL public: https://agent-production-12dcc0d5.up.railway.app
- Ảnh: [service đang chạy](screenshots/running.png), [kết quả kiểm tra](screenshots/test.png), [bản ghi trạng thái Railway CLI](screenshots/status.png).
- Kết quả 4 request thực tế: `GET /health` → **200**; `GET /ready` → **200**; `POST /ask` không có key → **401**; `POST /ask` có key hợp lệ → **200**. `GET /ready` trả 200 cho thấy agent kết nối Redis thành công.
- Chi tiết cấu hình và lệnh kiểm tra: [DEPLOYMENT.md](DEPLOYMENT.md).

### Exercise 3.2 — So sánh Railway và Render

`railway.toml` của agent chọn Dockerfile để build và đặt `/health` làm health check; ứng dụng vẫn nhận cổng qua biến `PORT` do nền tảng cấp. Redis được tạo như service riêng và `REDIS_URL` được nối qua biến môi trường trên Railway.

Blueprint `render.yaml` ở `03-cloud-deployment/render/` mô tả cả web service, cách build/start, region, plan, auto deploy, biến môi trường và Redis trong một file. Vì vậy Render Blueprint khai báo nhiều tài nguyên cùng lúc, còn cấu hình Railway hiện tại tập trung vào cách build và kiểm tra một service; Redis và secret được quản lý ở project/dashboard. `06-lab-complete/render.yaml` mới là mẫu hướng dẫn, chưa dùng để deploy.

### Exercise 3.3 — Cloud Run CI/CD

1. Khi pipeline được kích hoạt, `cloudbuild.yaml` cài dependencies và chạy `pytest`; chỉ khi test qua mới build Docker image với tag commit SHA và `latest`.
2. Cloud Build đẩy image lên Container Registry, rồi triển khai tag commit SHA lên Cloud Run ở `asia-southeast1`.
3. Lệnh deploy đặt giới hạn instance, CPU, RAM, timeout và lấy `OPENAI_API_KEY` từ Secret Manager.
4. `service.yaml` mô tả cấu hình service: cổng 8000, concurrency, tài nguyên, secret, `/health` cho liveness và `/ready` cho startup. Bài này chỉ phân tích pipeline, không triển khai GCP.

## Part 4 — API Security (CP3)

### Exercise 4.1 — API key

`04-api-gateway/develop/app.py` lấy `AGENT_API_KEY` từ môi trường. `APIKeyHeader` đọc `X-API-Key`, `verify_api_key` kiểm tra và được gắn vào `/ask` qua `Depends`. Thiếu key trả 401; key sai trả 403 trong ví dụ này. Để đổi key, đặt giá trị `AGENT_API_KEY` mới cho service rồi khởi động lại, đồng thời cập nhật client; không ghi key thật vào Git.

Lệnh `curl -i` với key bị thiếu:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Lệnh `curl -i` với key đúng:

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

### Exercise 4.2 — JWT

`POST /auth/token` với tài khoản demo `student` / `demo123` trả 200 và JWT. Client gửi token bằng `Authorization: Bearer <token>`; server kiểm chữ ký, hạn dùng và đọc `sub`, `role` trước khi xử lý `/ask`. Token đã được ẩn khỏi báo cáo. Request đầu tiên với token hợp lệ trả:

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Test 1","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

### Exercise 4.3 — Rate limiting

`rate_limiter.py` dùng **sliding window** 60 giây, lưu timestamp trong `deque` theo user. Tài khoản user có 10 request/phút, admin có 100 request/phút; admin được một hạn mức cao hơn chứ không bỏ qua kiểm tra. Vòng lặp 20 request thực tế: lần 1–10 trả 200, lần 11–20 trả 429. Phản hồi `curl -i` ở lần 11:

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Giới hạn này nằm trong RAM của process ví dụ, nên không chia sẻ giữa nhiều worker và mất khi khởi động lại. CP5 yêu cầu chuyển state rate limit sang Redis.

### Exercise 4.4 — Cost guard

Trong `cost_guard.py`, ứng dụng kiểm ngân sách trước khi gọi mock LLM. Sau câu trả lời, ứng dụng ước tính input/output tokens, nhân với giá tương ứng và ghi thêm chi phí. Bản demo dùng ngân sách **1 USD/ngày mỗi user** và **10 USD/ngày toàn hệ thống**, lưu trong RAM; khi user hết ngân sách sẽ trả 402. Rate limit chặn tần suất gọi trong một khoảng ngắn, còn cost guard chặn tổng chi tiêu ngay cả khi request được gửi chậm.

Đối với bài Part 6, state cần lưu ở Redis để dùng chung giữa worker/instance và còn hiệu lực sau restart. Bản code ví dụ Part 4 chỉ để quan sát cơ chế; không thay nó bằng lời giải Part 6.

## Part 5 — Scaling & Reliability (CP4)

### Exercise 5.1 — Liveness và readiness

Ở bản develop, `GET /health` trả 200 với `status=ok`, uptime và thông tin memory; `GET /ready` trả 200 với `ready=true`. Liveness trả lời “process còn hoạt động không?”; readiness trả lời “instance đã sẵn sàng nhận request chưa?”. Khi chưa sẵn sàng, `/ready` có thể trả 503 để load balancer tạm ngừng gửi traffic mà không cần coi process đã chết.

### Exercise 5.2 — Graceful shutdown

Gửi `POST /ask?question=Long%20task`, sau 0,5 giây gửi SIGTERM. Request đang xử lý vẫn trả **HTTP 200**. Log thực tế cho thấy `Shutting down`, sau đó `POST /ask ... 200 OK`, `Graceful shutdown initiated`, `Shutdown complete` và `Finished server process`. Điều này chứng minh request thử nghiệm không bị cắt ngang khi process tắt.

### Exercise 5.3–5.5 — Stateless, load balancing

Chạy Compose với **3 agent**, **1 Redis** và **1 Nginx** ở cổng 8080. `test_stateless.py` gửi 5 câu hỏi trong cùng một session. Kết quả:

```text
Total requests: 5
Instances used: {'instance-be2b59', 'instance-73a6a3', 'instance-b945ba'}
Total messages: 10
Session history preserved across all instances via Redis!
```

Mỗi agent có RAM riêng. Nếu history chỉ nằm trong RAM, một request được Nginx chuyển sang instance khác sẽ không thấy hội thoại trước đó. Ở bản production mẫu, `session_id` trỏ tới dữ liệu lưu trong Redis; ba instance đều đọc/ghi cùng session, nên history vẫn có đủ 5 câu hỏi và 5 câu trả lời. `GET /health` qua Nginx trả **HTTP 200**, `storage=redis`, `redis_connected=true`. Stack đã được dừng sau khi kiểm tra.

## Part 6 — Final Project (CP5)

Hoàn thiện bản khung trong `06-lab-complete/`: cấu hình từ biến môi trường; xác thực `X-API-Key`; `/health` và `/ready`; rate limit sliding window nguyên tử và cost guard trong Redis; log JSON; FastAPI lifespan cho shutdown; Dockerfile multi-stage; Compose agent + Redis; `.dockerignore`; cấu hình Railway. Không sửa `check_production_ready.py`.

`/health` chỉ kiểm tra process nên vẫn trả 200 khi Redis mất kết nối. `/ready` ping Redis và trả 503 khi Redis không sẵn sàng, để nền tảng ngừng chuyển traffic vào instance đó. API key được kiểm tra trước rate limit; Redis lưu timestamp request và chi phí theo ngày để nhiều worker dùng chung. Khi Redis không dùng được, `/ask` trả 503 thay vì tiếp tục xử lý mà không kiểm soát giới hạn.

Chạy `python check_production_ready.py` trong Ubuntu/WSL2, từ `06-lab-complete/`, với Docker Desktop đang chạy. Phần output **📋 Checklist Deliverable** của lần chấm đầy đủ:

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Chi tiết đo được: image **63 MB**; `RATE_LIMIT_PER_MINUTE=5` thì 5 request thành công rồi nhận 429, state vẫn còn sau restart; ngân sách thử rất nhỏ nhận 402; 12 dòng log của app đều là JSON hợp lệ; request đang chạy vẫn trả 200 sau SIGTERM; `docker stop` thoát mã 0 trong **1,0 giây**.

Kiểm tra thêm bằng `docker compose -p k5-day14-final up -d --build` với key thử cục bộ: `GET /health` → 200 (`environment=staging`), `GET /ready` → 200, `POST /ask` có key → 200 và báo `input_tokens=6`, `output_tokens=32`, `cost_usd=0.0000201`. Stack đã được dừng; file `.env` thử nghiệm đã được xóa.

## Part 7 — Benchmark & Observability, Bước 1 (CP7)

### Exercise 7.1 — Metrics của agent

Chạy agent v1 ở `localhost:8001` và v2 ở `localhost:8002` trong WSL2. Sau khi eval v2 đã sửa KB, `GET /metrics` cho thấy:

```text
http_requests_total{method="POST",route="/ask",status="200"} 23.0
http_request_duration_seconds_bucket{le="0.5",method="POST",route="/ask"} 21.0
agent_in_flight_requests 0.0
llm_tokens_total{model="mock-llm-small",type="input"} 1726.0
agent_question_length_chars_count 23.0
```

`http_requests_total` là Counter; `agent_in_flight_requests` là Gauge; `http_request_duration_seconds` và metric mới `agent_question_length_chars` là Histogram. Đã thêm Histogram độ dài câu hỏi và gọi `observe(len(body.question))` trong `/ask`. Độ dài có nhiều giá trị nên dùng bucket, không tạo label cho từng độ dài. Middleware dùng `route.path` (mẫu `/ask`) làm label; nếu dùng URL thật, bot quét hàng nghìn đường dẫn lạ sẽ tạo hàng nghìn chuỗi time series và làm Prometheus tốn RAM.

### Exercise 7.2 — Load test và SLO

Chạy 300 request cho mỗi mức concurrency 1, 10, 50, 100; lưu bốn file `load_v2_c*.json`. RPS lần lượt **4,59 / 35,81 / 106,80 / 55,24**; p95 lần lượt **219,4 / 222,1 / 307,7 / 3727,0 ms**. Mức 50 fail SLO vì error rate **2,33% > 2%**; mức 100 fail vì p95 **3727 > 500 ms**. RPS không tăng tuyến tính và giảm ở mức 100 khi client/server tranh tài nguyên.

So sánh `MOCK_SLOW_RATE=0 / 0,03 / 0,1` với 300 request, concurrency 20, `MOCK_ERROR_RATE=0`: average **192,8 / 255,7 / 325,8 ms**; p95 **223,7 / 232,6 / 1691,6 ms**; p99 **242,2 / 1698,8 / 1716,2 ms**. Một ít request chậm làm p99 tăng mạnh trước khi average hoặc p95 đổi nhiều; khi tỷ lệ chậm lên 10%, p95 cũng vượt SLO. Bảng đủ p50/p95/p99, error rate và file nguồn ở [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).

### Exercise 7.3 — Eval và quality gate

Trên 23 câu golden dataset: v1 đúng **1/23 (4,35%)**; v2 ban đầu **21/23 (91,30%)**; sau khi bổ sung KB cho `security-02` (JWT: token, hết hạn, chữ ký) và `scaling-03` (HPA: CPU, memory, custom metrics), v2 đúng **23/23 (100%)**, không regression. Đã dừng và chạy lại v2 trước eval cuối. `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` trả exit code 0 và `Quality gate ... PASS`; chạy v1 với baseline v2 và ngưỡng 85% trả exit code 1, có 20 regression.

V2 sau sửa có cost mỗi câu đúng **$0,00003429**, thấp hơn v1 **$0,00039315** dù tổng cost/token cao hơn, vì gần như toàn bộ câu trả lời v1 không đạt. [Workflow quality gate](.github/workflows/cp7-eval.yml) chạy eval v2 trong CI, đặt ngưỡng 85% và baseline 23/23; exit code 1 của script khiến job fail và chặn merge khi có regression hoặc accuracy dưới ngưỡng.

## Part 7 — Benchmark & Observability, Bước 2 (CP8)

Đã chạy Docker Compose project `k5-day14-observability` với Prometheus, Grafana, Jaeger, Nginx, Locust và agent. Sửa Dockerfile production để runtime dùng cùng virtualenv đã cài dependency trong builder; sau đó agent khởi động và health check thành công. `promtool test rules` trả `SUCCESS`. Qua Nginx, `GET /metrics` trả 404 như yêu cầu bảo vệ metric nội bộ.

Locust headless 100 users, 2 phút trên **1** và **3** agent cho `/ask` lần lượt **47,39 / 53,98 RPS**, p95 **1700 / 1300 ms**, failures **138/5556 / 94/6553**. Bằng chứng nằm trong `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv` và [báo cáo](BENCHMARK_REPORT.md). Tìm được một trace chậm 1719,8 ms với span LLM 1698,7 ms và một trace lỗi upstream 503; log JSON cùng `trace_id` lưu ở `benchmark-results/trace-log-evidence.jsonl`.

Tăng mock error lên 20% và slow lên 30% làm `AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing; ảnh `screenshots/prometheus-alert-firing.png` chụp đồng thời. Chuyển sang `mock-llm-large` làm `LLMCostBurnRateHigh` firing; pause một agent làm `AgentInstanceDown` firing, rồi đã unpause. Chuyển sang v1 khiến cả ba instance báo version v1, metric retrieval không có series mới, nhưng cuối phiên **không có alert firing** dù câu trả lời JWT chung chung. Kết quả này cần quality gate định kỳ, không chỉ SLO hạ tầng. Thời gian, ảnh và giới hạn của từng phép đo ghi trong [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).

## AI log

- Câu hỏi gửi AI: đọc repo và thực hiện các công việc CP1–CP4.
- Hỗ trợ nhận được: đối chiếu hướng dẫn K5, chuẩn bị lệnh chạy, giải thích mã nguồn, viết phần trình bày kết quả.
- Cách tự kiểm tra: chạy app bằng Python trong WSL2; gọi các endpoint và ghi mã HTTP; build và đo hai Docker image bằng `docker image inspect`; chạy hai Docker Compose stack; chạy `test_stateless.py`; xem log SIGTERM. Các số đo và phản hồi ở trên lấy từ các lần chạy này, không lấy từ ví dụ minh họa trong README.
- Câu hỏi gửi AI: đọc hướng dẫn và thực hiện CP5.
- Hỗ trợ nhận được: hoàn thiện các `TODO` của Part 6, nối API với Redis, viết cấu hình Docker/Compose/Railway và ghi kết quả kiểm tra.
- Cách kiểm tra: chạy `check_production_ready.py --static-only`, `--skip-docker` và bản đầy đủ trong WSL2; bản đầy đủ đạt 12/12 và 41/41. Chạy thêm Compose với Redis và gọi `/health`, `/ready`, `/ask`; tất cả trả 200. Các số đo nêu trong Part 6 là output thực tế.
- Câu hỏi gửi AI: đọc các file `.md` và thực hiện CP6.
- Hỗ trợ nhận được: tạo project/service Railway, triển khai `06-lab-complete/`, nối Redis và API key bằng biến môi trường, tạo URL public, viết `DEPLOYMENT.md` và ảnh bằng chứng.
- Cách kiểm tra: Railway CLI báo `agent` và Redis chạy; bốn request tới URL public lần lượt trả 200, 200, 401, 200. `screenshots/test.png` là ảnh chụp trang trình bày các kết quả đã ghi lại; `screenshots/status.png` trình bày trạng thái CLI, không phải ảnh dashboard Railway.
- Câu hỏi gửi AI: đọc hướng dẫn và thực hiện CP7.
- Hỗ trợ nhận được: thêm metric độ dài câu hỏi, chạy load test và eval trên WSL2, sửa hai entry của knowledge base, tạo report và workflow CI.
- Cách kiểm tra: đối chiếu bảng số liệu với 10 file JSON trong `develop/reports/`; eval cuối 23/23 với quality gate PASS, v1 so với baseline v2 trả exit code 1. Các hàng SLO fail vẫn giữ nguyên theo output thực tế.
- Câu hỏi gửi AI: kiểm tra lại môi trường và hoàn tất CP8, gồm observability stack và hồ sơ nộp.
- Hỗ trợ nhận được: sửa Dockerfile production để agent chạy được, điều phối Locust/Prometheus/Jaeger, thu ảnh và log, đối chiếu số liệu với CSV/JSON, điền báo cáo.
- Cách kiểm tra: xác nhận số agent và target Prometheus trước mỗi phép đo; đọc trực tiếp `scale_1_stats.csv` và `scale_3_stats.csv`; khớp `trace_id` trong log với Jaeger API/UI; đọc `/api/v1/alerts` và ảnh Prometheus khi hai alert firing; dùng `promtool test rules`; kiểm tra v1 bằng response và `agent_info`. Ghi rõ lỗi HTTP 504 cuối phiên scale 1 và sự khác nhau giữa mốc `activeAt` với mốc đổi cấu hình, không tự suy ra thời gian chưa đo.
