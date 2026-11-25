# Benchmark & Observability Report — Day 14

**Họ tên:** Lê Thành Đạt

**Ngày chạy:** 25/11/2026

**Môi trường:** Windows, Ubuntu/WSL2; Python 3.12.3; WSL thấy 12 CPU logic và 3,8 GiB RAM. Phần 2–3 đo agent v1/v2 chạy trực tiếp trong WSL trên cổng 8001/8002. Phần 4–5 đo stack Docker Desktop qua Nginx trên cổng 8080. Đây là phép đo local với mock LLM, không phải benchmark URL Railway.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Theo ngưỡng mặc định của `load_test.py`; phần lớn request mock nên hoàn thành dưới 0,5 giây. |
| Error rate `/ask` | ≤ 2% | Mock upstream có lỗi ngẫu nhiên 1% theo mặc định; ngưỡng 2% phát hiện khi lỗi tăng đáng kể. |
| Accuracy trên golden dataset | ≥ 85%, không regression | Ngưỡng CI của Exercise 7.3; baseline 23/23 khiến bất kỳ câu đúng nào bị sai lại đều làm gate fail. Eval cuối còn kiểm ngưỡng 100%. |

SLO theo p95/p99 cho thấy trải nghiệm của nhóm request chậm. Average có thể vẫn thấp khi một phần nhỏ request mất hơn 1,5 giây.

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi hàng là **300 request** đến v2 trước khi sửa knowledge base. Các file JSON nằm trong [`develop/reports/`](06-lab-complete/benchmark-observability/develop/reports/). SLO của từng hàng lấy từ chính trường `slo.passed`.

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 4,59 | 188,3 | 219,4 | 1669,5 | 1,67% | PASS |
| 10 | 35,81 | 188,7 | 222,1 | 1704,7 | 0,67% | PASS |
| 50 | 106,80 | 210,8 | 307,7 | 1705,1 | 2,33% | FAIL: error rate |
| 100 | 55,24 | 685,3 | 3727,0 | 3994,2 | 1,00% | FAIL: p95 |

RPS tăng từ 1 đến 50 luồng nhưng **không tuyến tính**; ở 100 luồng còn giảm. Các request tranh tài nguyên của WSL, server và client load test, làm tăng thời gian chờ. Số liệu này chỉ cho thấy hiện tượng ở môi trường đo; cần profiling để xác định nút thắt chính. Exit code 1 ở hai hàng fail là hành vi SLO gate của script, file JSON vẫn được lưu.

### 2.2 Tail latency

Mỗi hàng cũng dùng 300 request, concurrency 20. Để so riêng tác động của `MOCK_SLOW_RATE`, cả ba lần chạy đặt `MOCK_ERROR_RATE=0`; chỉ thay `MOCK_SLOW_RATE` và khởi động lại v2.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 192,8 | 223,7 | 242,2 |
| 0,03 (mặc định) | 255,7 | 232,6 | 1698,8 |
| 0,1 | 325,8 | 1691,6 | 1716,2 |

Từ 0 lên 0,03, p99 nhảy mạnh nhất vì chỉ khoảng 3% request bị thêm 1500 ms, còn p95 vẫn nằm trong nhóm request thường. Ở 0,1, đủ nhiều request chậm để p95 cũng tăng vọt và vi phạm SLO. Average tăng ít hơn percentile đuôi và có thể che giấu trải nghiệm xấu của người dùng.

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Golden dataset có 23 câu. V1 chạy trên cổng 8001; v2 ban đầu và v2 sau sửa KB chạy trên cổng 8002. Các giá trị dưới đây lấy từ `eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau sửa KB |
|---|---:|---:|---:|
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56,3 | 108,8 | 113,4 |
| Tổng cost (USD) | 0,000393 | 0,000758 | 0,000789 |
| Cost / câu đúng (USD) | 0,00039315 | 0,00003607 | 0,00003429 |
| Quality gate của lần eval | FAIL | PASS | PASS; ngưỡng 100%, 0 regression |

| ID sai ở v2 ban đầu | Keyword thiếu trong `eval_v2.json` | Sửa trong `develop/utils/mock_llm.py` |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `jwt`, giải thích JWT có chữ ký và hạn dùng, đối chiếu API key. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry HPA/Kubernetes, nêu ba loại chỉ số scale. |

Sau khi sửa, v2 được **khởi động lại** để nạp KB; lệnh eval cuối dùng `--min-accuracy 1.0 --baseline reports/eval_v2.json` trả exit code 0 và in `Quality gate ... PASS`. Không có câu nào từng đúng bị sai lại. Chạy v1 với baseline v2 và ngưỡng 85% trả exit code 1, ghi nhận 20 regression. Workflow [`.github/workflows/cp7-eval.yml`](.github/workflows/cp7-eval.yml) dùng exit code này để chặn PR khi accuracy dưới 85% hoặc có regression so với baseline 23/23.

V2 dùng khoảng gấp đôi token/câu và tổng cost cao hơn v1, nhưng trả lời đúng nhiều hơn: cost mỗi câu đúng giảm từ 0,00039315 xuống 0,00003607 USD ở v2 ban đầu và 0,00003429 USD sau sửa. Chỉ số này phản ánh tiền bỏ ra cho câu trả lời hữu ích, nên phù hợp hơn cost/câu để so hai phiên bản. Latency eval dao động do mock có request chậm ngẫu nhiên; p95 của 23 câu không nên dùng để kết luận tác động riêng của sửa KB.

## 4. Observability stack (production)

### 4.1 Dashboard và bằng chứng

Chạy Docker Compose với project `k5-day14-observability`: agent, Nginx, Prometheus, Grafana, Jaeger và Locust. `promtool test rules` trả `SUCCESS`. Trong lúc có tải, [dashboard Grafana](screenshots/grafana-dashboard.png) hiển thị traffic 53,3 req/s, error rate 1,02%, p95 975,16 ms và 1 instance up. Bốn ảnh CP8: [Grafana](screenshots/grafana-dashboard.png), [trace chậm](screenshots/jaeger-slow-trace.png), [trace lỗi](screenshots/jaeger-error-trace.png), [hai alert cùng firing](screenshots/prometheus-alert-firing.png). Ảnh lấy từ giao diện thật của stack.

Prometheus scrape `/metrics` trực tiếp từ các agent. Qua Nginx public, `GET /metrics` trả HTTP 404 như cấu hình; không thể dùng endpoint đó từ bên ngoài để đọc metric nội bộ. Tại snapshot khi có ba instance, `sum by (instance) (rate(http_requests_total{route="/ask"}[1m]))` trả **4,661 / 4,499 / 4,590 req/s**: các agent được chia tải gần đều. `sum by (type) (rate(llm_tokens_total[1m]))` trả **1046,88 input / 545,83 output token/s**; input nhiều hơn do có câu hỏi, system prompt và context truy xuất. [Prometheus snapshot](benchmark-results/scale_3_prometheus_snapshot.json) là mẫu tức thời, không đồng nhất với RPS trung bình cả phiên của Locust.

### 4.2 Thí nghiệm cảnh báo

| Thí nghiệm | Cấu hình/tác động | Kết quả quan sát | Thời gian tới firing | Panel phản ánh |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2`, Locust 30 users | `AgentHighErrorRate` firing; giá trị lúc chụp 19,24% | 66,0 giây từ `activeAt` đến lần quan sát firing đầu | Error rate |
| B | `MOCK_SLOW_RATE=0.3`, cùng tải | `AgentHighLatencyP95` firing; p95 lúc chụp 1,929 giây | 126,4 giây từ `activeAt` đến lần quan sát firing đầu | p95 latency |
| C | `LLM_MODEL=mock-llm-large`, Locust 100 users | `LLMCostBurnRateHigh` firing; tốc độ chi phí ước tính 51,79 USD/giờ khi lần đầu quan sát | 142,4 giây từ `activeAt` đến lần quan sát firing đầu | Cost USD/giờ |
| D | `docker pause` một trong ba agent, Locust 30 users | `AgentInstanceDown` firing; một scrape target `down`, hai target còn `up` | 58,3 giây từ lệnh pause đến lần quan sát firing đầu | Instances up / target health |
| E | `AGENT_VERSION=v1`, Locust 30 users | Không có alert firing; `agent_info` là v1 trên cả 3 instance, không có series retrieval mới | Không áp dụng | Bảng version, retrieval hit ratio |

Hai điều kiện A/B được bật đồng thời. Prometheus ghi `activeAt=15:11:42.401817Z` cho cả hai; lần đầu quan sát trạng thái firing là **15:12:48.429704Z** và **15:13:48.808039Z**. Chúng đã vào `pending` khoảng 12 giây trước lần recreate agent thứ hai lúc 15:11:54Z, nên mốc từ lần recreate đó tới firing (**54,4 / 114,7 giây**) ngắn hơn thời gian `for` 1 / 2 phút; không coi đây là phép đo từ điều kiện sạch. [Chuỗi quan sát](benchmark-results/alert_observations_retry.json), [trạng thái cả hai firing](benchmark-results/prometheus-alerts-firing.json) và [ảnh Prometheus Alerts](screenshots/prometheus-alert-firing.png) ghi lại dữ liệu gốc.

Với C, `LLMCostBurnRateHigh` vào `pending` lúc **15:19:12.571502Z** và được quan sát firing lúc **15:21:35.004151Z**. Giá trị PromQL `sum(rate(llm_cost_usd_total{job="agent"}[5m])) * 3600` là 51,79 USD/giờ tại lần quan sát; đây là chi phí *ước tính theo giá mock*, không phải hóa đơn cloud. [JSON trạng thái](benchmark-results/cost-alert-observation.json) và [ảnh alert](screenshots/prometheus-cost-alert.png). Mốc từ khi đổi cấu hình sang lúc firing không được ghi chính xác; bảng dùng `activeAt` do Prometheus cung cấp.

Với D, pause lúc **15:23:23.095634Z**; target `172.19.0.9:8000` chuyển `down`, `AgentInstanceDown` có `activeAt=15:23:32.401817Z` và được quan sát firing lúc **15:24:21.415327Z**. Mốc quan sát gồm thời gian chờ scrape và rule `for: 30s`, không phải thời điểm chuyển trạng thái chính xác giữa hai lần lấy mẫu. [Trạng thái và target health](benchmark-results/instance-down-state.json), [mốc pause](benchmark-results/instance-down-observation.json), [ảnh alert](screenshots/prometheus-instance-down.png). Agent đã được `docker unpause`. Lỗi 504 do Nginx chờ agent bị pause có thể không xuất hiện trong error rate của *agent*, vì agent không hoàn thành xử lý request đó; cần theo dõi thêm 502/504 ở proxy.

Với E, Prometheus thấy `agent_info{version="v1"}` trên **cả 3 instance** và không có series retrieval mới. Ở snapshot cuối, error rate **1,65%**, p95 **224 ms**, **0 alert firing**. Câu hỏi “JWT là gì?” qua Nginx trả **HTTP 200** nhưng câu trả lời chung chung, không giải thích JWT; [response thật](benchmark-results/version-v1-answer.json) và [metric snapshot](benchmark-results/version-v1-observation.json). Quality gate đã đo v1 chỉ **1/23 câu đúng** ở Phần 3. Hạ tầng vẫn có thể trả 200 và các alert hạ tầng không phát hiện câu trả lời kém; cần chạy eval trên golden dataset định kỳ, canary theo version và alert khi accuracy giảm. Alert chi phí của thí nghiệm C còn tồn tại do cửa sổ `rate(...[5m])` trong snapshot đầu của E; nó không phát sinh từ thay đổi version và đã hết ở snapshot cuối.

### 4.3 Debug bằng trace và log

- Trace chậm `a898435cf47d48bbc3ef541a474f17ea`: `POST /ask` **1719,8 ms**, `agent.run` 1717,2 ms, `chat mock-llm-small` **1698,7 ms** (98,8% tổng thời gian), retrieval 18,1 ms. Nút thắt của request này ở mock LLM. [Trace JSON](benchmark-results/jaeger-slow-trace.json) và [ảnh timeline](screenshots/jaeger-slow-trace.png).
- Trace lỗi `3beec86f9a3d7b0cc59eab24ff6f3603`: `POST /ask` **97,7 ms**, `chat mock-llm-small` **78,5 ms** với event `exception` và HTTP 503 giả lập từ upstream. [Trace JSON](benchmark-results/jaeger-error-trace.json) và [ảnh lỗi](screenshots/jaeger-error-trace.png).

Hai dòng JSON lấy từ log agent, ghép đúng `trace_id` với Jaeger, cũng được lưu trong [trace-log-evidence.jsonl](benchmark-results/trace-log-evidence.jsonl):

```json
{"ts": "2026-11-25T14:59:59.430928+00:00", "level": "INFO", "service": "observable-agent", "instance": "00526decb5f5", "event": "llm_call", "trace_id": "a898435cf47d48bbc3ef541a474f17ea", "span_id": "c52f9687832a2d5d", "request_id": "7193af3fae69", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1697.7}
{"ts": "2026-11-25T15:01:22.511052+00:00", "level": "INFO", "service": "observable-agent", "instance": "5edea5b70718", "event": "llm_error", "trace_id": "3beec86f9a3d7b0cc59eab24ff6f3603", "span_id": "f18ad2980303664d", "request_id": "fd0cff1fc40b", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, Locust headless)

Mỗi phép đo dùng **100 users, ramp-up 10 users/giây, 2 phút**, qua Nginx, `AGENT_VERSION=v2`, `mock-llm-small`, lỗi/chậm giả lập mặc định 1%/3%. Dùng hàng `POST /ask` trong CSV cho bảng này; `/health` cũng được Locust gửi nhưng không đại diện cho tác vụ của agent.

| Agent đang chạy | `/ask` requests | RPS `/ask` | p50 (ms) | p95 (ms) | p99 (ms) | Failures `/ask` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5556 | 47,39 | 220 | 1700 | 10000 | 138 (2,48%) |
| 3 | 6553 | 53,98 | 200 | 1300 | 2000 | 94 (1,43%) |

Nguồn: [scale_1_stats.csv](benchmark-results/scale_1_stats.csv), [scale_3_stats.csv](benchmark-results/scale_3_stats.csv) và các file `*_failures.csv`. Một instance có 86 lỗi HTTP 504, 49 lỗi HTTP 503 và 3 lỗi kết nối; ba instance có 94 lỗi HTTP 503. HTTP 503 là lỗi mock LLM có chủ đích; HTTP 504/đứt kết nối ở lần 1 xuất hiện lúc cuối phiên và làm p99 tăng. Vì vậy mức cải thiện p99 từ 10 xuống 2 giây chịu ảnh hưởng của sự cố cuối phiên, không thể quy hết cho việc tăng số instance.

RPS `/ask` tăng **13,9%**, p95 giảm **23,5%**, error rate giảm **1,05 điểm phần trăm**. Scale có cải thiện nhưng không gấp ba: mock LLM vẫn chiếm gần toàn bộ thời gian của trace chậm, các agent có giới hạn CPU 0,5 core, và máy đo/Locust/Nginx dùng chung tài nguyên. Prometheus snapshot ở thời điểm khác cho p95 **1065 ms** so với average **323 ms**; chênh lệch này cho thấy tail latency. RPS và percentile trong bảng lấy từ thống kê toàn phiên Locust, nên không so trực tiếp số tức thời trên dashboard.

## 6. Kết luận

1. RPS không tăng mãi theo concurrency; ở mức 100, p95 vượt SLO rõ rệt.
2. p95/p99 phát hiện request chậm mà average che bớt; cần xem cả tỉ lệ lỗi.
3. Eval trên dataset cố định bắt được hai lỗ hổng kiến thức, còn baseline và exit code giúp ngăn regression trong CI.
4. Metric cho biết mức độ ảnh hưởng, trace chỉ ra span chậm/lỗi, log JSON nối nguyên nhân với cùng `trace_id`; cả ba cần được đọc cùng nhau.
5. Khi dùng thật, nên thêm metric/alert ở Nginx cho 502/504 và kiểm tra synthetic từ ngoài hệ thống, vì request lỗi ở proxy không nhất thiết đi vào metric của agent. Đồng thời theo dõi quality gate định kỳ để phát hiện suy giảm chất lượng mà metric hạ tầng không thấy.
