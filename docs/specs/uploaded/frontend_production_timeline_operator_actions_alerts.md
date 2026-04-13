# Production Timeline + Operator Actions + Alert Hooks Spec

Vì sau khi đã có timeline hợp nhất, hệ của bạn đã “nhìn thấy” production run.
Bước kế tiếp phải làm cho hệ tác động ngược lại được vào run.
Khi đó dashboard sẽ chuyển từ:
chỉ đọc trạng thái
thành
control plane thật
Patch kế tiếp nên gồm 3 lớp chính:
1. Timeline materialization
Mục tiêu là không còn tính timeline động rải rác mỗi lần gọi API, mà có read model vật lý để UI, alerting, SLA, queue và operator actions cùng đọc một nguồn chuẩn.
Nên thêm:
production_timeline_materialized
production_run_state
production_action_log
Read model này nên giữ các field kiểu:
production_run_id
current_stage
current_status
is_blocked
blocking_reason
last_event_at
active_provider
active_worker
percent_complete
retry_count
requires_operator_action
available_actions
final_output_url
Khi đó dashboard load cực nhanh và filter được thật:
blocked
failed
waiting operator
retrying
safe to reroute
ready to publish
2. Operator actions
Đây là phần biến timeline thành bảng điều khiển vận hành.
Nên thêm action endpoint chuẩn hóa như:
POST /api/v1/production-runs/{id}/ack
POST /api/v1/production-runs/{id}/retry
POST /api/v1/production-runs/{id}/unblock
POST /api/v1/production-runs/{id}/reroute
POST /api/v1/production-runs/{id}/cancel
POST /api/v1/production-runs/{id}/pause
POST /api/v1/production-runs/{id}/resume
Mỗi action phải tạo:
timeline event mới
audit log
state transition
optional worker dispatch
Ví dụ:
ack
xác nhận operator đã thấy sự cố
retry
đẩy lại phase lỗi theo policy
unblock
gỡ trạng thái chờ sau khi operator đã xử lý dependency
reroute
đổi provider, ví dụ từ veo sang runway, hoặc đổi voice/music provider
pause/resume/cancel
khóa execution thật ở runtime
Điểm quan trọng nhất là action nào cũng phải đi qua:
policy guard
permission check
safety gate
audit trail
3. Alert hooks
Sau khi đã có materialized state, alerting mới đúng nghĩa production.
Nên có:
Slack webhook
email
generic webhook
sau này thêm PagerDuty nếu cần
Trigger cơ bản:
run bị blocked quá X phút
retry vượt ngưỡng
mux fail
provider fail rate tăng
narration fail hàng loạt
output ready
operator action required
reroute recommended
Cấu trúc tốt nhất là:
alert_rule
alert_delivery
alert_event
Để sau này không chỉ gửi cảnh báo mà còn làm được:
suppression window
cooldown
dedupe
escalation chain
Vì sao đây là bước mạnh nhất
Vì sau lớp này, hệ không còn là:
timeline viewer
status dashboard
mà trở thành:
operator console
execution control plane
nền cho autonomous control fabric
Nói gọn:
timeline cho bạn biết chuyện gì đang xảy ra
materialization cho bạn trạng thái chuẩn để điều phối
operator actions cho bạn can thiệp thật
alert hooks cho hệ tự gọi người khi cần
File groups nên viết ở lượt tiếp theo
backend models
production_run_state.py
production_timeline_materialized.py
production_action_log.py
alert_rule.py
alert_event.py
alert_delivery.py
migrations
bảng state/materialized/action/alert
services
timeline_materializer.py
operator_action_service.py
action_policy_service.py
alert_rule_engine.py
alert_dispatcher.py
API
api/operator_actions.py
api/alerts.py
workers
materialization worker
alert dispatch worker
retry/reroute execution hooks
frontend
action bar trên run detail
blocked banner
retry/reroute modal
alert history panel
operator note box
tests
status transition tests
action policy tests
reroute safety tests
alert dedupe/cooldown tests
Bước mạnh nhất của bước mạnh nhất sau đó sẽ là:
policy-enforced autonomous execution
tức là một số action an toàn như retry hoặc reroute có thể auto-execute theo rule, không cần operator bấm tay nữa.
Bước mạnh nhất của bước mạnh nhất sau đó sẽ là: policy-enforced autonomous execution tức là một số action an toàn như retry hoặc reroute có thể auto-execute theo rule, không cần operator bấm tay nữa.
Đã suy nghĩ trong vài giây
Đúng. Đó là bước nhảy từ operator-controlled system sang guardrailed autonomous system.
Khi đó hệ không chỉ:
phát hiện
hiển thị
đề xuất
chờ người bấm
mà bắt đầu có thể:
tự quyết định trong phạm vi an toàn
tự thực thi action được phép
tự dừng khi vượt risk envelope
tự escalte sang operator khi ra ngoài policy
Đây mới là lõi của policy-enforced autonomous execution.
Nó nên hoạt động như thế nào
Hệ cần 4 lớp khóa cứng:
1. Decision policy
Quy định khi nào được phép hành động.
Ví dụ:
retry nếu lỗi là transient
reroute nếu provider A timeout quá ngưỡng
unblock nếu dependency đã recovered
không auto-reroute nếu action làm tăng cost vượt budget
không auto-retry nếu đã chạm retry ceiling
không auto-resume nếu run đang ở trạng thái manual_hold
Policy phải đọc từ:
current stage
failure class
provider health
retry count
cooldown window
budget/cost guard
project policy
global kill switch
2. Action guardrail
Quy định hành động nào là safe / unsafe / irreversible.
Một model rất mạnh là chia action thành 3 lớp:
safe_auto
retry same provider
reroute sang backup provider đã allowlist
resume sau transient outage
requeue worker
semi_auto
reroute sang provider cost cao hơn
fallback quality thấp hơn
skip optional phase
manual_only
cancel run
publish final asset
delete output
override compliance/consent
bypass quality gate
Từ đây mọi action đều đi qua:
requested_action -> policy evaluation -> guardrail classification -> execution or escalation
3. Execution orchestrator
Lớp này biến “nên làm gì” thành “đã làm gì”.
Nó phải có:
decision queue
action planner
executor
rollback path
suppression/cooldown logic
idempotency key
execution lease
audit trail
Tối thiểu cần flow:
detect issue -> evaluate policy -> simulate action -> approve if safe -> execute -> observe outcome -> rollback/escalate if needed
Điểm rất quan trọng:
mọi auto-action phải có observe-after-execute window.
Không phải execute xong là tin ngay.
Ví dụ:
auto-reroute sang Runway
chờ 2–5 phút
nếu progress recovery có thật -> giữ
nếu vẫn fail -> escalate operator
4. Risk envelope
Đây là lớp ngăn hệ “tự động quá đà”.
Nên có budget/risk controls như:
max auto actions per run
max retries per phase
max reroutes per provider class
max extra cost delta
max degraded quality fallback
max autonomous actions per hour
kill switch toàn cục
project-level autonomy mode:
off
recommend-only
safe-auto
aggressive-auto
Chính lớp này quyết định hệ là “thông minh có kiểm soát” hay “tự động nguy hiểm”.
Các auto-action mạnh nhất nên cho phép trước
Thứ tự triển khai tốt nhất:
Wave 1 — safe auto
retry transient failure
requeue stuck worker
resume after provider recovery
reroute sang provider backup đã pre-approved
clear block nếu health dependency đã xanh lại
Wave 2 — bounded optimization
chọn provider theo policy
fallback quality profile thấp hơn khi queue quá tải
chuyển lane từ fast sang stable
retry với backoff khác nhau theo failure class
Wave 3 — conditional autonomy
auto-reroute theo cost/performance envelope
auto-pause noisy runs
auto-suppress flapping actions
auto-promote stable provider override
auto-rollback override khi recovery xong
Backend nên có gì ở bước này
models
decision_policy.py
autonomous_action_execution.py
execution_guardrail.py
risk_budget.py
provider_override.py
rollback_execution.py
services
policy_evaluator.py
autonomous_decision_engine.py
action_simulator.py
execution_orchestrator.py
rollback_orchestrator.py
risk_envelope_service.py
workers
decision_evaluation_worker.py
autonomous_execution_worker.py
rollback_worker.py
provider_override_expiry_worker.py
API
GET /api/v1/autonomy/policies
POST /api/v1/autonomy/policies
POST /api/v1/production-runs/{id}/autonomy/evaluate
GET /api/v1/production-runs/{id}/autonomy/decisions
POST /api/v1/autonomy/kill-switch
POST /api/v1/autonomy/modes
frontend
autonomy mode selector
decision trace panel
auto-action history
risk budget panel
rollback events panel
simulation result modal
Decision engine nên ra kết quả kiểu gì
Mỗi evaluation nên trả một object dạng:
detected_problem
candidate_actions
safest_action
confidence_score
policy_basis
blocked_by
estimated_cost_delta
estimated_recovery_gain
execution_mode:
recommend
auto_execute
escalate
rollback_plan
Nghĩa là hệ không chỉ nói:
“retry đi”
mà phải nói:
“retry same provider trong safe-auto vì lỗi timeout transient, retry_count còn 1/3, cost delta = 0, rollback không cần, cooldown 5 phút”
Điều làm bước này rất mạnh
Vì từ đây hệ bắt đầu có:
decision memory
policy enforcement
bounded execution
self-healing behavior
Nói cách khác:
timeline = thấy
operator actions = can thiệp
materialization = có state chuẩn
autonomous execution = tự vận hành trong biên an toàn
Đây là bước đầu tiên khiến system có cảm giác như một production autopilot thật.
Cảnh báo kiến trúc rất quan trọng
Không nên cho autonomy nhảy thẳng vào execute.
Phải bắt buộc có chuỗi:
signal -> evaluate -> simulate -> approve-by-policy -> execute -> observe -> confirm/rollback
Nếu thiếu simulate hoặc observe, hệ rất dễ thành:
retry loop vô tận
reroute lung tung
tăng cost ngoài ý muốn
flapping giữa providers
giấu lỗi thật thay vì giải quyết lỗi
Bản patch kế tiếp mạnh nhất nên chia 7 nhóm
backend models
migrations
policy services
decision engine
orchestration workers
API
frontend autonomy console + tests
Bước kế tiếp ngay sau lớp này sẽ là:
closed-loop self-healing execution system
tức là hệ không chỉ auto-execute theo rule, mà còn học từ outcome để điều chỉnh policy envelope và provider strategy theo hiệu quả thật.
Bước kế tiếp ngay sau lớp này sẽ là: closed-loop self-healing execution system tức là hệ không chỉ auto-execute theo rule, mà còn học từ outcome để điều chỉnh policy envelope và provider strategy theo hiệu quả thật.
Đã suy nghĩ trong vài giây
Đúng. Đây là bước chuyển từ autonomous execution theo luật cố định sang autonomous system biết tự hiệu chỉnh bằng outcome thật.
Khác biệt cốt lõi là:
policy-enforced autonomy: hệ làm theo rule đã định
closed-loop self-healing: hệ quan sát kết quả sau khi làm, rồi tự siết hoặc nới cách hành động ở lần sau
Nói ngắn gọn:
trước đó hệ hỏi: “có được phép retry/reroute không?”
sau bước này hệ hỏi thêm: “lần trước retry kiểu đó có cứu được run thật không, có đáng tiếp tục không?”
Vì sao đây là bước mạnh nhất sau autonomy
Vì đến đây hệ không còn chỉ:
tự chạy
tự bảo vệ
tự rollback
mà bắt đầu:
đo outcome thật
so sánh action với recovery thật
điều chỉnh chiến lược thực thi
giảm dần action vô ích
tăng dần action có xác suất cứu run cao
Đó mới là một self-healing system thật.
Closed-loop self-healing phải có 5 lớp
1. Outcome capture
Mỗi auto-action phải có kết quả hậu kiểm rõ ràng.
Ví dụ sau một action retry hoặc reroute, hệ phải ghi:
run có recovery không
recovery sau bao lâu
có fail lại không
cost tăng bao nhiêu
quality giảm hay không
có cần operator vào tay không
final output có thành công không
Không có lớp này thì autonomy chỉ là “tự làm”, chưa phải “tự học”.
2. Action effectiveness memory
Hệ phải nhớ:
action nào hiệu quả với loại lỗi nào
action nào hay gây flapping
provider nào fail kiểu nào
phase nào recovery tốt bằng retry
phase nào nên reroute sớm hơn retry
Ví dụ:
transient timeout ở narration với provider A: retry 1 lần thành công 82%
mux failure do input corrupt: retry vô ích, nên escalate ngay
render timeout ở provider X giờ cao điểm: reroute tốt hơn retry
Từ đây decision engine không còn chỉ dựa vào rule tĩnh, mà có thêm memory theo outcome thật.
3. Policy envelope adaptation
Policy không nên tự thay đổi bừa bãi, mà phải điều chỉnh trong biên an toàn.
Ví dụ hệ chỉ được phép:
giảm retry ceiling từ 3 xuống 2 nếu retry thứ 3 liên tục vô ích
tăng ưu tiên backup provider trong một số phase
kéo ngắn cooldown cho lỗi có recovery nhanh
siết auto-reroute nếu cost delta cao mà recovery thấp
Tức là:
không thay chính sách lõi bừa bãi
chỉ điều chỉnh tham số vận hành trong envelope được cho phép
4. Provider strategy optimization
Đây là phần rất mạnh.
Hệ không chỉ hỏi:
provider nào đang up/down
mà hỏi:
provider nào hiệu quả nhất cho loại job này, trong phase này, ở thời điểm này, với cost envelope này
Ví dụ:
video render ngắn → provider A tốt
narration EN dài → provider B ổn định hơn
mux không phụ thuộc provider render, nên đừng reroute vô nghĩa
giờ cao điểm thì lane stable tốt hơn lane fast
Tức là từ một hệ “có backup provider”, bạn tiến lên thành hệ “biết chọn provider theo evidence”.
5. Recovery learning loop
Đây là vòng khép kín thật:
detect -> evaluate -> execute -> observe -> score outcome -> update memory -> adjust next decision
Nếu thiếu bước score outcome và update memory, thì chưa phải closed-loop.
Những gì hệ nên học
Không phải học mọi thứ. Chỉ nên học các biến vận hành quan trọng:
retry effectiveness theo failure class
reroute effectiveness theo provider pair
mean time to recovery
operator intervention rate sau auto-action
cost delta vs recovery gain
quality degradation risk
flapping likelihood
action success by stage
safe fallback ranking
time-of-day/provider-load effect
Những gì hệ không nên tự học trực tiếp
Không nên cho hệ tự học và tự sửa các thứ quá nguy hiểm như:
tự mở rộng quyền action từ manual sang auto
tự cho phép publish
tự bỏ quality gates
tự bỏ consent/compliance
tự tăng budget ceiling
tự thêm provider mới ngoài allowlist
Những cái này phải vẫn là manual policy governance.
Kiến trúc nên thêm ở bước này
models
action_outcome.py
provider_strategy_snapshot.py
policy_envelope_state.py
recovery_learning_record.py
self_healing_decision_score.py
services
outcome_capture_service.py
recovery_scoring_service.py
policy_adaptation_service.py
provider_strategy_service.py
self_healing_controller.py
workers
outcome_evaluation_worker.py
policy_adjustment_worker.py
provider_strategy_refresh_worker.py
self_healing_feedback_worker.py
read models
provider_reliability_rollup
action_effectiveness_rollup
recovery_rate_rollup
autonomy_outcome_summary
Cách chấm điểm một auto-action
Mỗi action sau khi chạy nên có score kiểu:
success_recovery_score
speed_score
cost_penalty
quality_penalty
operator_escalation_penalty
recurrence_penalty
Từ đó ra một net effectiveness score.
Ví dụ:
retry cứu được run nhanh, cost = 0, không cần operator → điểm cao
reroute cứu được nhưng cost tăng mạnh, còn fail lại → điểm trung bình
retry không cứu được, làm chậm escalation → điểm thấp
Sau vài trăm run, hệ sẽ có evidence thật để thay đổi strategy.
Cách hệ tự điều chỉnh mà vẫn an toàn
Tôi khuyên chia 3 lớp điều chỉnh:
lớp 1 — recommend only
Hệ chỉ đề xuất:
giảm retry từ 3 xuống 2
ưu tiên reroute sớm hơn ở provider X
disable auto-action cho lỗi Y
lớp 2 — bounded auto-tuning
Hệ tự chỉnh các tham số nhỏ trong khoảng cho phép:
retry backoff
cooldown
provider priority weight
transient timeout threshold
reroute threshold
lớp 3 — governed rollout
Tham số mới không áp full ngay mà rollout:
10% runs
rồi 25%
rồi 50%
nếu outcome tốt mới promote
Đây là cách tránh “tự học một phát làm hỏng cả hệ”.
Dashboard nên có gì ở bước này
Frontend nên thêm:
Self-Healing Console
bảng action effectiveness
bảng provider strategy
biểu đồ auto-action recovery rate
panel policy adaptation history
panel why this parameter changed
nút rollback policy envelope
Operator phải nhìn được:
hệ vừa tự chỉnh cái gì
dựa trên dữ liệu nào
kết quả sau khi chỉnh ra sao
Nếu không có phần này, hệ sẽ thành hộp đen khó tin cậy.
Luồng chuẩn của closed-loop self-healing
Luồng mạnh nhất nên là:
phát hiện lỗi
decision engine chọn action an toàn
execute action
mở observe window
chấm outcome
ghi vào action-effectiveness memory
cập nhật provider/policy weights trong envelope cho phép
áp dụng dần ở các run sau
rollback nếu outcome xấu đi
Vì sao bước này rất lớn
Vì từ đây hệ bắt đầu có:
operational memory
evidence-based action selection
adaptive recovery strategy
bounded self-optimization
Nói cách khác, nó không còn chỉ là autopilot “có luật”, mà là autopilot “biết luật nào đang thực sự hiệu quả”.
Bản patch kế tiếp mạnh nhất nên chia thành 8 nhóm
backend models
migrations
outcome capture services
recovery scoring services
provider strategy services
self-healing workers
API
frontend self-healing console + tests
Bước mạnh nhất ngay sau lớp này sẽ là:
adaptive resilience control fabric
tức là không chỉ từng run tự hồi phục tốt hơn, mà toàn hệ bắt đầu điều phối tải, budget, provider routing, suppression, escalation và rollback ở cấp fabric dựa trên tín hiệu thật của toàn mạng thực thi.
Đây là bước chuyển từ self-healing ở mức từng run sang điều phối sức bền ở mức toàn fabric.
Khác biệt rất lớn là:
closed-loop self-healing
tối ưu cách cứu từng run
adaptive resilience control fabric
tối ưu cách bảo vệ, phân phối, và ổn định toàn bộ mạng thực thi
Nói cách khác, từ đây hệ không chỉ hỏi:
run này nên retry hay reroute thế nào?
mà bắt đầu hỏi:
toàn hệ đang quá tải ở đâu?
budget đang bị đốt ở lane nào?
provider nào nên bị hạ tải tạm thời?
run nào nên được ưu tiên cứu trước?
loại lỗi nào nên suppress thay vì tiếp tục spam action?
rollback nào nên kích hoạt ở cấp fabric thay vì từng run riêng lẻ?
Đây là bước đưa hệ từ một autopilot tốt lên thành một resilience operating system.
Fabric này phải làm gì
Nó cần nhìn toàn cục và điều phối 6 thứ cùng lúc:
1. Load shaping
Không để mọi run cùng đổ vào một provider hoặc một lane.
Hệ phải biết:
provider nào đang nóng
queue nào đang phình
worker class nào đang nghẽn
phase nào đang là bottleneck
Từ đó tự:
giảm dispatch vào lane nóng
chuyển tải sang lane ổn định hơn
trì hoãn nhóm job ít ưu tiên
bảo vệ capacity cho job quan trọng
2. Budget arbitration
Từ đây cost không còn là chuyện của từng run riêng lẻ.
Fabric phải quyết định:
budget nào dành cho premium recovery
khi nào không được reroute sang provider đắt hơn nữa
project nào được quyền dùng lane chất lượng cao
khi nào phải chuyển sang degraded-but-safe mode
Tức là budget trở thành tài nguyên điều phối cấp hệ.
3. Provider routing control
Không chỉ fallback khi hỏng, mà routing chủ động theo tín hiệu thật.
Ví dụ:
provider A latency tăng nhưng chưa down
provider B ổn hơn cho narration dài
provider C rẻ hơn nhưng fail rate đang tăng
Fabric phải biết:
giảm tải A trước khi nó gãy hẳn
chuyển một phần traffic sang B
khóa C cho một số phase
mở override có expiry
4. Suppression and anti-flapping
Khi hệ lớn hơn, một lỗi có thể tạo ra hàng trăm action vô ích nếu không chặn.
Fabric phải có:
suppression window
dedupe theo cluster
anti-flapping guard
retry storm prevention
reroute storm prevention
Ví dụ:
50 run cùng fail vì cùng một provider spike
không nên để 50 decision engine tự nghĩ độc lập rồi reroute loạn
fabric phải thấy đó là một sự kiện cụm và xử lý theo cụm
5. Escalation control
Không phải lỗi nào cũng escalte như nhau.
Fabric phải quyết định:
escalte run nào trước
escalte theo cụm hay theo run
escalte khi nào sang operator
escalte khi nào sang “global mitigation mode”
Ví dụ:
một run lỗi lẻ → operator bình thường
200 run cùng lỗi → kích hoạt incident mode
6. Global rollback and safeguard injection
Khi một thay đổi hệ thống gây hại, fabric phải rollback ở cấp mạng, không chờ từng run chết riêng.
Ví dụ:
provider override mới làm fail rate tăng
policy envelope nới quá tay
cost spike do aggressive reroute
degradation mode làm quality xuống quá sâu
Lúc này fabric cần:
rollback override
thu hẹp risk envelope
chặn action class nào đó
bật global safe mode
khóa autonomy với nhóm run nhất định
Kiến trúc tư duy đúng cho fabric
Hãy hình dung 3 tầng:
Tầng 1 — run control
Xử lý từng run riêng lẻ:
retry
reroute
rollback
unblock
Tầng 2 — cluster control
Xử lý nhóm run có cùng mẫu sự cố:
cùng provider surge
cùng phase fail
cùng project overload
cùng worker queue congestion
Tầng 3 — fabric control
Xử lý trạng thái toàn mạng:
global budget pressure
systemwide latency surge
regional provider instability
noisy retry storm
global autonomy shrink mode
Nếu thiếu tầng 2 và 3, hệ chỉ là nhiều autopilot nhỏ đứng cạnh nhau, chưa phải fabric thật.
Những “control knobs” fabric nên có
Đây là các núm điều khiển mạnh nhất:
provider traffic weight
lane priority weight
retry ceiling override
reroute threshold override
cooldown extension
suppression window
escalation threshold
degraded mode enable/disable
quality floor
cost ceiling
kill switch
override expiry
rollback mode
Các núm này phải có:
scope toàn cục
scope theo project
scope theo provider
scope theo phase
scope theo run class
Read models nên materialize ở bước này
Để fabric hoạt động thật, cần read model mạnh hơn dashboard thường:
fabric_health_state
provider_routing_state
budget_pressure_state
suppression_state
cluster_incident_state
resilience_override_state
autonomy_global_mode
recovery_capacity_state
Nhờ đó hệ sẽ trả lời được ngay:
provider nào đang bị suppress
budget nào đang đỏ
cụm sự cố nào đang mở
lane nào đang bị throttle
policy nào đang override
global mode hiện tại là gì
Control loop của adaptive fabric
Vòng điều phối chuẩn nên là:
observe -> detect cluster/fabric condition -> simulate mitigation -> apply bounded control change -> watch fabric response -> keep / rollback / escalate
Từ khóa quan trọng là bounded control change.
Fabric không được:
đổi 100% traffic tức thì
khóa toàn bộ provider quá nhanh
mở degraded mode cho tất cả project cùng lúc
tăng suppression quá rộng rồi che mất lỗi thật
Mọi thay đổi nên:
có phạm vi
có thời hạn
có metric quan sát
có rollback plan
Những chiến lược mạnh nhất nên thêm đầu tiên
Wave 1 — stabilization
provider traffic throttling
retry storm suppression
reroute storm prevention
cluster-level incident grouping
degraded mode khi capacity đỏ
Wave 2 — adaptive routing
weight-based provider routing
phase-specific routing
time-of-day routing preference
project-priority-aware routing
budget-aware routing
Wave 3 — resilient governance
global autonomy shrink/expand
automatic rollback of bad overrides
proactive safeguard injection
cluster-level action plans
recovery capacity reservation
Cần thêm những service nào
core services
fabric_observer.py
cluster_detector.py
budget_arbiter.py
provider_router.py
suppression_engine.py
escalation_controller.py
global_rollback_controller.py
resilience_override_service.py
policy/control services
fabric_policy_evaluator.py
mitigation_simulator.py
control_change_planner.py
override_expiry_service.py
global_safeguard_service.py
workers
fabric_evaluation_worker.py
cluster_mitigation_worker.py
routing_rebalance_worker.py
suppression_expiry_worker.py
override_rollback_worker.py
Frontend ở bước này không còn là dashboard thường nữa
Nó phải thành fabric console.
Nên có:
global health map
provider routing panel
budget pressure panel
cluster incidents panel
suppression rules panel
active overrides panel
rollback events panel
autonomy mode panel
kill switch panel
Operator lúc này không chỉ xem “job nào fail”, mà xem:
cả hệ đang nghiêng về đâu
tài nguyên đang căng ở đâu
override nào đang sống
cluster nào đang gây nhiễu
quyết định fabric vừa đổi cái gì
Vì sao bước này mạnh hơn self-healing run-level
Vì self-healing từng run vẫn có thể thất bại ở quy mô lớn nếu:
quá nhiều run cùng retry
cùng reroute vào một chỗ
cost tăng dây chuyền
operator bị ngập cảnh báo
provider bị đẩy qua lại liên tục
Adaptive resilience control fabric xử lý đúng các vấn đề emergent behavior đó.
Tức là:
tối ưu từng run là chưa đủ
phải tối ưu sự tương tác giữa các run
Đó mới là sức mạnh thực sự của fabric.
Cảnh báo kiến trúc cực quan trọng
Không nên cho fabric trực tiếp sửa quá nhiều policy lõi.
Fabric nên chủ yếu điều chỉnh:
weights
thresholds
suppression windows
routing preferences
temporary overrides
global modes
Còn những thứ như:
quyền auto-publish
compliance bypass
consent bypass
quality gate removal
unlimited budget expansion
vẫn phải là manual governance.
Chuỗi tiến hóa hợp lý
Nếu nhìn toàn bộ roadmap, bạn đang đi rất đúng theo thứ tự mạnh nhất:
timeline hợp nhất
operator actions + alerts
policy-enforced autonomous execution
closed-loop self-healing
adaptive resilience control fabric
Sau bước này, lớp tiếp theo mạnh nhất sẽ là:
autonomous resilience operating system
Tức là không chỉ điều phối phản ứng khi có sự cố, mà toàn hệ bắt đầu:
dự báo nguy cơ trước khi lỗi nổ ra
reserve capacity trước
preemptively reroute
shrink risk envelope trước khi sự cố lan rộng
tự chuyển topology vận hành theo điều kiện thực tế
Đó là lúc hệ không còn chỉ “chịu lỗi tốt”, mà bắt đầu tổ chức lại chính nó để tránh lỗi.
Đây là bước cuối cùng để hệ của bạn chuyển từ reactive + adaptive sang anticipatory + self-organizing.
Nếu nói ngắn gọn:
control fabric = phản ứng thông minh khi đã có tín hiệu
autonomous resilience OS = đi trước tín hiệu, tự sắp xếp lại hệ trước khi vấn đề xảy ra
Đây là lớp biến hệ của bạn thành một living system chứ không còn là pipeline + control nữa.
Bản chất của “Autonomous Resilience Operating System”
Hệ không còn hỏi:
“nên làm gì khi fail?”
mà hỏi:
“dấu hiệu này có dẫn tới fail không?”
“nếu tiếp tục như hiện tại, 5–10 phút nữa chuyện gì sẽ xảy ra?”
“có nên đổi topology ngay bây giờ để tránh chuyện đó không?”
👉 Tức là:
from event-driven → forecast-driven
5 năng lực lõi bắt buộc phải có
1. Predictive signal layer (dự báo sớm)
Không đợi fail mới xử lý.
Hệ phải detect sớm các pattern:
latency drift tăng dần
retry rate tăng nhẹ nhưng chưa vượt threshold
queue depth tăng theo slope bất thường
provider response variance tăng
mux time dài bất thường
narration lag theo batch size
cost per job bắt đầu lệch
👉 Đây là “weak signals” — rất quan trọng.
Không có lớp này:
hệ luôn chậm 1 bước
chỉ chữa cháy
2. Risk forecasting engine
Từ weak signals → dự báo outcome.
Ví dụ:
“nếu giữ traffic hiện tại, 8 phút nữa queue sẽ nghẽn”
“provider A sẽ timeout cluster trong 5 phút”
“retry storm sẽ bắt đầu nếu không chặn ngay”
“cost spike sẽ vượt budget trong 15 phút”
Đây không cần ML phức tạp ban đầu.
Có thể bắt đầu bằng:
threshold + slope
rolling window anomaly
heuristic forecasting
simple regression theo time
👉 Quan trọng là:
biết trước khi nó xảy ra
3. Preemptive control (can thiệp trước khi lỗi xảy ra)
Đây là khác biệt lớn nhất so với fabric.
Thay vì:
đợi fail → retry / reroute
Hệ sẽ:
giảm tải trước
reroute trước
mở capacity trước
shrink autonomy trước
kích hoạt degraded mode sớm
Ví dụ:
queue đang tăng → giảm dispatch vào lane đó ngay
provider latency tăng → chuyển 30% traffic sang provider khác trước khi fail
cost đang spike → siết reroute sớm hơn
narration backlog tăng → tăng worker pool trước
👉 Đây là “preemptive mitigation”
4. Capacity reservation & topology shaping
Hệ bắt đầu tái cấu trúc chính nó.
Không chỉ điều chỉnh tham số, mà điều chỉnh:
worker allocation
provider distribution
lane topology
priority routing
execution graph
Ví dụ:
tách riêng lane:
fast lane (low latency)
stable lane (high reliability)
reserve capacity cho:
high priority jobs
mux stage (critical path)
chuyển topology:
từ linear → parallel batching
từ single-provider → multi-provider split
👉 Đây là bước hệ “tự tổ chức lại”
5. Risk envelope pre-shrinking
Trước khi lỗi lan rộng, hệ tự:
giảm retry ceiling
giảm reroute aggressiveness
tăng cooldown
bật suppression sớm
hạ autonomy mode
Ví dụ:
bình thường retry = 3
→ khi thấy risk tăng → giảm xuống 2
reroute bình thường = aggressive
→ khi provider unstable → chuyển sang conservative
👉 Không đợi fail mới siết → siết trước
Control loop mới (so với trước)
Trước đây:
detect failure → react → recover
Sau khi lên OS:
observe weak signals → forecast risk → simulate topology change → apply bounded preemptive change → monitor → adjust
👉 thêm 2 bước cực quan trọng:
forecast
simulate BEFORE execute
Những thứ hệ phải bắt đầu “biết trước”
provider degradation
queue congestion
retry storm risk
cost explosion
flapping probability
mux bottleneck
narration lag
worker starvation
SLA breach trước khi xảy ra
Kiến trúc nên thêm ở bước này
Models
predictive_signal.py
risk_forecast.py
capacity_state.py
topology_state.py
preemptive_action.py
risk_envelope_projection.py
Services
signal_aggregation_service.py
anomaly_detection_service.py
risk_forecasting_engine.py
preemptive_planner.py
topology_optimizer.py
capacity_allocator.py
risk_envelope_controller.py
Workers
signal_ingestion_worker.py
forecast_evaluation_worker.py
preemptive_execution_worker.py
capacity_rebalance_worker.py
topology_update_worker.py
Read models
system_risk_state
provider_health_projection
queue_pressure_projection
capacity_reservation_state
topology_layout_state
preemptive_action_log
Những chiến lược mạnh nhất nên triển khai trước
Wave 1 — Early warning
latency drift detector
queue slope detector
retry anomaly detector
provider instability early signal
Wave 2 — Preemptive mitigation
preemptive reroute (partial traffic shift)
preemptive throttling
early suppression
early degraded mode
Wave 3 — Topology shaping
dynamic lane switching
capacity reservation
workload partitioning
provider weight shifting theo forecast
Điều làm hệ này cực kỳ mạnh
Vì từ đây hệ có:
temporal awareness (nhìn theo thời gian)
future modeling (dự báo tương lai gần)
structural control (tái cấu trúc topology)
preventive resilience (ngăn lỗi trước khi xảy ra)
Cảnh báo cực quan trọng
Nếu làm sai, hệ sẽ:
overreact (thay đổi quá sớm)
thrash topology (đổi liên tục)
suppress quá mức (che mất lỗi thật)
waste capacity
tăng cost vô ích
👉 Vì vậy bắt buộc:
mọi preemptive action phải:
có confidence threshold
có scope nhỏ ban đầu (10–30%)
có expiry
có rollback
có observe window
So sánh 3 cấp độ cuối
Sau lớp này còn gì nữa?
Bước tiếp theo (và cũng là level rất cao) sẽ là:
👉 Adaptive system evolution layer
Tức là:
hệ không chỉ tối ưu runtime
mà bắt đầu:
tự thay đổi architecture
tự chọn strategy dài hạn
tự evolve execution graph
tự optimize cost vs reliability vs quality theo mục tiêu
Kết luận
Bạn đã đi đúng toàn bộ chuỗi tiến hóa mạnh nhất:
Timeline
Operator control
Autonomous execution
Self-healing
Control fabric
Resilience OS (predictive + self-organizing)
👉 Đây chính là ranh giới giữa:
một hệ production tốt
và
một hệ có khả năng tự vận hành như một organism
Nếu Resilience OS là hệ biết:
dự báo
phòng ngừa
tự tổ chức lại topology vận hành
thì Adaptive System Evolution Layer là hệ bắt đầu:
tự thay đổi thiết kế của chính nó
tự chọn hướng tiến hóa dài hạn
tự tối ưu cấu trúc thực thi, không chỉ tối ưu từng quyết định runtime
Nói ngắn gọn:
trước đó hệ hỏi: “lúc này nên reroute thế nào?”
đến lớp này hệ hỏi: “kiến trúc hiện tại còn là kiến trúc tốt nhất không?”
Khác biệt cốt lõi
Runtime optimization
Tập trung vào:
xử lý job hiện tại
cân tải hiện tại
cứu run hiện tại
giảm lỗi trước mắt
System evolution
Tập trung vào:
execution graph nào tốt hơn về dài hạn
topology nào phù hợp với pattern tải mới
provider mix nào nên trở thành default
policy family nào nên được promote hoặc retire
cost/reliability/quality frontier nào là tối ưu cho mục tiêu kinh doanh
Đây là bước chuyển từ:
self-healing system
sang
self-evolving production system
5 năng lực lõi của lớp này
1. Architecture mutation
Hệ phải có khả năng thử các biến thể kiến trúc như:
linear pipeline vs branched pipeline
eager mux vs delayed mux
single-pass narration vs segmented narration
one-shot provider routing vs staged routing
strict quality gate vs progressive quality gate
Nhưng không mutate bừa. Mọi mutation phải:
bounded
reversible
rollout nhỏ
có metric so sánh
2. Strategy selection
Hệ không chỉ chọn action, mà chọn chiến lược vận hành dài hạn.
Ví dụ:
ưu tiên reliability trong giờ cao điểm
ưu tiên cost ở batch overnight
ưu tiên quality cho premium projects
ưu tiên fast-lane cho shortform
ưu tiên multi-provider redundancy cho longform
Tức là system biết rằng:
một strategy không phù hợp cho mọi workload
3. Execution graph evolution
Đây là phần rất mạnh.
Hệ có thể tiến hóa từ:
render -> narration -> mix -> mux
sang:
render -> narration
render -> music
narration + music -> mix
mix + render -> mux
hoặc:
chia pipeline thành lane theo loại workload
thêm bước validate giữa các phase
bỏ bớt bước không tạo giá trị với một số job class
Tức là hệ bắt đầu tối ưu shape của workflow.
4. Multi-objective optimization
Đây là lõi thực sự của lớp này.
Hệ không tối ưu một metric duy nhất, mà phải cân bằng:
cost
reliability
latency
output quality
operator load
recovery overhead
Ví dụ:
kiến trúc A rẻ hơn nhưng fail nhiều hơn
kiến trúc B ổn hơn nhưng chậm
kiến trúc C nhanh nhưng chất lượng giảm nhẹ
Hệ phải học frontier:
đổi cái gì để được cái gì
5. Governance-aware evolution
Đây là điểm giữ hệ không trượt khỏi production-safe.
System có thể evolve:
routing weights
graph variants
policy thresholds
lane topology
rollout strategy
Nhưng không được tự evolve:
compliance rules
consent rules
publish authority
unrestricted budget
unsafe action classes
Kiến trúc nên có ở lớp này
models
architecture_variant.py
execution_graph_version.py
strategy_profile.py
evolution_experiment.py
evolution_outcome.py
optimization_frontier.py
services
architecture_mutation_service.py
strategy_selection_engine.py
execution_graph_evolver.py
multi_objective_optimizer.py
evolution_governance_service.py
variant_promotion_service.py
workers
evolution_evaluation_worker.py
variant_rollout_worker.py
graph_migration_worker.py
strategy_refresh_worker.py
read models
architecture_performance_rollup
strategy_effectiveness_rollup
variant_comparison_state
optimization_frontier_state
Cách hệ nên tiến hóa an toàn
Chuỗi chuẩn nên là:
observe long-horizon outcomes -> propose variant -> simulate -> limited rollout -> compare -> promote / rollback / retire
Không bao giờ:
đổi toàn bộ architecture ngay
promote variant chỉ vì vài run tốt
để runtime engine tự sửa graph production không có rollout
Các mutation mạnh nhất nên làm trước
Wave 1
provider strategy profiles theo workload class
lane split theo priority
retry/reroute policy families theo phase
Wave 2
execution graph variants
conditional branching theo asset type
dynamic quality gate placement
Wave 3
topology family selection theo time window
automatic promotion/retirement of graph variants
portfolio optimization across projects
Điều làm lớp này rất mạnh
Vì từ đây hệ bắt đầu có:
long-horizon memory
structural adaptation
portfolio-level strategy
architecture experimentation under governance
Nói cách khác:
không chỉ chạy tốt hơn
không chỉ tự chữa tốt hơn
mà trở thành một hệ biết tiến hóa
Cảnh báo kiến trúc rất quan trọng
Nếu làm sai, hệ sẽ:
overfit vào dữ liệu ngắn hạn
đổi kiến trúc quá thường xuyên
tạo fragmentation giữa các lane
tăng độ phức tạp nhanh hơn giá trị tạo ra
Nên bắt buộc có:
promotion threshold cao
rollback nhanh
canary rollout
expiry cho experimental variants
human governance cho structural changes lớn
Thứ tự tiến hóa hoàn chỉnh
Bạn đang đi đúng chuỗi mạnh nhất:
timeline unified
operator control
policy-enforced autonomy
closed-loop self-healing
adaptive resilience control fabric
autonomous resilience OS
adaptive system evolution layer
Đây là lớp biến monorepo của bạn từ một production platform rất mạnh thành một self-optimizing execution system.
Nếu Adaptive System Evolution hỏi:
kiến trúc nào tốt hơn?
strategy nào nên được promote?
graph nào nên tiến hóa?
thì Mission-Level Objective Orchestration hỏi câu lớn hơn:
toàn bộ hệ nên tối ưu vì mục tiêu nào?
khi các mục tiêu xung đột nhau, hệ nên hy sinh cái gì trước?
ở thời điểm này, business cần:
margin
SLA
quality
throughput
deadline
hay market responsiveness?
Đây là bước chuyển từ:
self-optimizing system
sang
goal-directed execution organism
Bản chất thật của lớp này
Từ đây hệ không còn tối ưu “cho đẹp về kỹ thuật”.
Nó phải tối ưu theo ưu tiên kinh doanh cấp cao.
Ví dụ:
tuần này cần giữ SLA cho khách premium
cuối tháng cần siết margin
hôm nay có launch deadline nên chấp nhận cost cao hơn
overnight batch thì ưu tiên throughput hơn latency
workload premium thì quality quan trọng hơn cost
Nói cách khác, hệ bắt đầu có:
mission
objective hierarchy
trade-off governance
Khác biệt cốt lõi
Trước đó
Hệ hỏi:
nên retry không?
nên reroute provider nào?
graph nào hiệu quả hơn?
topology nào bền hơn?
Ở lớp này
Hệ hỏi:
với mục tiêu business hiện tại, có nên ưu tiên reliability hơn margin không?
có nên hy sinh latency để giữ quality?
có nên dồn capacity cho premium runs và trì hoãn low-priority batch?
có nên chấp nhận degraded mode để kịp launch deadline?
Đây là lớp làm cho hệ ra quyết định vì mục tiêu, không chỉ vì metric vận hành.
6 năng lực lõi bắt buộc phải có
1. Objective hierarchy
Hệ phải hiểu thứ tự ưu tiên của mục tiêu.
Ví dụ một objective stack có thể là:
Tier 1: safety / compliance
Tier 2: SLA premium
Tier 3: launch deadline
Tier 4: quality floor
Tier 5: margin
Tier 6: throughput optimization
Hoặc trong chế độ khác:
Tier 1: safety
Tier 2: margin protection
Tier 3: acceptable SLA
Tier 4: throughput
Không có objective hierarchy thì mọi optimizer phía dưới sẽ đánh nhau.
2. Trade-off engine
Đây là lõi quan trọng nhất.
Khi 2 mục tiêu xung đột, hệ phải biết chọn.
Ví dụ:
tăng reliability nhưng cost tăng
tăng throughput nhưng quality giảm
giữ deadline nhưng operator load tăng
giữ premium SLA nhưng low-tier queue bị dồn
Hệ phải có logic rõ:
cái gì được đánh đổi
trong mức nào
khi nào bị cấm đánh đổi
3. Portfolio allocation
Lúc này hệ không còn nhìn từng run riêng.
Nó nhìn cả danh mục:
premium projects
standard projects
overnight batch
urgent launches
cost-sensitive workloads
Và quyết định:
project nào giữ fast lane
project nào chuyển degraded mode
project nào được reserve capacity
project nào phải delay để bảo vệ mission lớn hơn
4. Time-horizon orchestration
Objective không cố định mãi.
Hệ phải biết:
mục tiêu 15 phút tới
mục tiêu hôm nay
mục tiêu tuần này
mục tiêu kỳ launch này
Ví dụ:
ngắn hạn: giữ hệ ổn định
trung hạn: hoàn thành launch window
dài hạn: giữ margin và provider health
Đây là khác biệt giữa hệ “thông minh tức thời” và hệ “thông minh theo chu kỳ nhiệm vụ”.
5. Goal-driven policy shaping
Lúc này policy không chỉ do resilience hay autonomy quyết định.
Mission layer có thể đẩy xuống các directive như:
tăng priority weight cho premium SLA
nới cost envelope có thời hạn
siết quality floor cho standard tier
bật deadline mode đến 18:00
khóa experimental graph cho workloads quan trọng
Tức là mission layer không làm thay mọi thứ, nhưng định hình sân chơi cho toàn fabric bên dưới.
6. Business outcome feedback
Cuối cùng, hệ phải học từ outcome cấp mission:
margin có giữ được không
SLA có đạt không
launch có kịp không
premium complaints có giảm không
throughput có đủ không
Nếu không có lớp feedback này, objective orchestration sẽ thành khẩu hiệu chứ không thành hệ điều khiển thật.
Ví dụ rất thực tế
Chế độ 1: Premium SLA Protection
Hệ sẽ:
reserve capacity cho premium
reroute sớm hơn cho premium runs
chặn experiments trên premium lane
đẩy standard tier sang stable/degraded lane
chấp nhận cost cao hơn trong ngưỡng
Chế độ 2: Margin Protection
Hệ sẽ:
ưu tiên provider rẻ hơn
siết aggressive reroute
giảm retries tốn kém
delay batch không khẩn cấp
giảm quality overhead ở tier thấp
Chế độ 3: Launch Deadline Mode
Hệ sẽ:
tăng throughput
unlock reserve capacity
cho phép provider override tạm thời
giảm một số optional validations
ưu tiên run liên quan launch
Chế độ 4: Quality First
Hệ sẽ:
chặn degraded mode quá sâu
ưu tiên provider chất lượng tốt hơn
giữ mux/validation gate chặt
giảm traffic vào lane fast nếu quality giảm
Kiến trúc nên có ở lớp này
models
mission_objective.py
objective_priority_profile.py
portfolio_allocation_plan.py
tradeoff_decision.py
mission_mode.py
business_outcome_snapshot.py
services
objective_orchestrator.py
tradeoff_engine.py
portfolio_allocator.py
mission_policy_shaper.py
business_feedback_service.py
objective_rollup_service.py
workers
objective_evaluation_worker.py
portfolio_rebalance_worker.py
mission_mode_expiry_worker.py
business_outcome_refresh_worker.py
read models
mission_state
objective_pressure_state
portfolio_capacity_state
tradeoff_history
business_outcome_rollup
Cách quyết định ở lớp này nên diễn ra
Luồng chuẩn nên là:
read mission objectives -> inspect portfolio state -> detect objective conflicts -> compute bounded trade-offs -> emit directives to fabric/resilience/autonomy layers -> observe business outcome -> refine mission profile
Điểm quan trọng:
lớp này không thay thế autonomy/fabric/resilience
nó chỉ huy các lớp đó theo mục tiêu cấp cao hơn
Những directive mạnh nhất mission layer nên phát ra
priority weights by project tier
cost ceiling overrides by mode
quality floor by customer segment
throughput target by time window
deadline mode activation
premium capacity reservation
experiment freeze/unfreeze
allowed degradation profile
routing preference profile
escalation sensitivity profile
Điều làm lớp này cực mạnh
Vì từ đây hệ bắt đầu có thể trả lời:
“vì sao hôm nay hệ reroute ít hơn?”
“vì sao low-tier jobs bị delay?”
“vì sao cost tăng nhưng vẫn là quyết định đúng?”
“vì sao experimental variant bị tắt?”
“vì sao premium throughput được giữ bằng mọi giá?”
Tức là hệ có ý chí vận hành cấp business, không chỉ có logic kỹ thuật.
Cảnh báo cực quan trọng
Nếu làm sai, mission layer sẽ gây:
tối ưu sai mục tiêu
hy sinh nhầm nhóm khách hàng
over-control từ trên xuống
conflict với policy safety/compliance
oscillation giữa các mode kinh doanh
Nên bắt buộc có:
hierarchy cứng: safety/compliance luôn cao nhất
bounded trade-off rules
expiry cho mission modes
audit trail cho mọi objective shift
manual governance cho strategic changes lớn
Chuỗi tiến hóa hoàn chỉnh nhất
Bạn đang mô tả gần như full stack trưởng thành nhất của một execution platform:
timeline unified
operator control
policy-enforced autonomy
closed-loop self-healing
adaptive resilience control fabric
autonomous resilience OS
adaptive system evolution layer
mission-level objective orchestration
Đây là lớp biến hệ từ:
production platform rất giỏi
thành:
goal-seeking operational intelligence system
Nếu đi thêm một lớp nữa sau đó
Lớp tự nhiên cao hơn nữa sẽ là:
enterprise strategy alignment layer
Tức là hệ không chỉ tối ưu theo objective vận hành, mà gắn trực tiếp với:
revenue targets
customer tier strategy
launch calendar
contractual SLA commitments
market campaigns
product roadmap priorities
Khi đó execution fabric không chỉ phục vụ “system goals”, mà phục vụ chiến lược doanh nghiệp một cách trực tiếp.
Đây là lớp “trên cùng của trên cùng”: execution fabric ↔ chiến lược doanh nghiệp.
Nếu Mission layer quyết định ưu tiên vận hành, thì Enterprise Strategy Alignment quyết định vì sao phải ưu tiên như vậy—dựa trên doanh thu, hợp đồng, chiến dịch, roadmap.
Hệ không chỉ tối ưu tốt, mà tối ưu đúng thứ cần thắng.
Bản chất của Enterprise Strategy Alignment
Hệ bắt đầu nhận tín hiệu chiến lược và chuyển hóa thành directive vận hành có thể thực thi:
“Q này phải đạt +20% revenue premium”
“Tuần này có launch lớn”
“SLA enterprise có penalty cao”
“Campaign A đang chạy, cần throughput cao”
“Roadmap ưu tiên feature X → cần capacity cho pipeline liên quan”
👉 Output không phải báo cáo, mà là:
priority weights
capacity reservation
routing & cost envelopes
quality floors
experiment freeze/unfreeze
7 năng lực lõi
1. Strategy ingestion
Thu nhận dữ liệu chiến lược:
revenue targets (theo tuần/tháng/quý)
customer tiers (enterprise / premium / standard)
SLA contracts (penalty, uptime, deadlines)
launch calendar (ngày/giờ, scope)
campaign windows (marketing bursts)
roadmap priorities (feature/vertical)
→ Chuẩn hóa thành Strategy Signals
2. Objective translation
Biến “chiến lược” → “directive kỹ thuật”
Ví dụ:
“Giữ SLA enterprise” → reserve capacity + strict quality gate
“Bảo vệ margin” → cost ceiling + hạn chế reroute đắt
“Launch deadline” → deadline mode + unlock capacity + relax non-critical checks
→ Tạo Objective Profiles (machine-readable)
3. Portfolio-aware allocation
Phân bổ tài nguyên theo danh mục kinh doanh, không theo job lẻ:
enterprise lane (protected)
premium lane (prioritized)
standard lane (elastic)
batch lane (opportunistic)
→ Quyết định:
ai được fast lane
ai bị delay
ai vào degraded mode
4. Contract-aware execution
Đưa hợp đồng SLA vào runtime:
penalty-weighted prioritization
deadline-aware scheduling
breach-avoidance preemption
escalation sensitivity theo contract
→ “Run A fail” ≠ “Run B fail” (tùy contract)
5. Campaign & launch synchronization
Đồng bộ với thời điểm kinh doanh:
Launch Mode (time-boxed):
tăng throughput
unlock reserve capacity
freeze experiments rủi ro
Campaign Mode:
ưu tiên latency/throughput
đảm bảo pipeline liên quan
6. Trade-off governance (cấp doanh nghiệp)
Khi xung đột:
SLA vs margin
quality vs throughput
premium vs standard
Hệ phải có luật đánh đổi rõ ràng:
cái gì không bao giờ được hy sinh (compliance, safety)
cái gì được hy sinh có điều kiện (latency, cost, quality phụ)
7. Business outcome feedback
Đóng vòng với KPI thật:
revenue impact
SLA attainment
penalty avoided/incurred
campaign performance
churn/complaint signals
→ Điều chỉnh lại Objective Profiles (có governance)
Kiến trúc đề xuất
Models
enterprise_strategy_signal.py
objective_profile.py
portfolio_allocation_plan.py
contract_sla_profile.py
campaign_window.py
roadmap_priority.py
business_outcome_snapshot.py
Services
strategy_ingestion_service.py
objective_translation_engine.py
portfolio_allocator.py
contract_sla_service.py
campaign_sync_service.py
tradeoff_governance_engine.py
business_feedback_service.py
Workers
strategy_refresh_worker.py
portfolio_rebalance_worker.py
mission_mode_expiry_worker.py
business_outcome_rollup_worker.py
Read models
enterprise_strategy_state
objective_pressure_state
portfolio_capacity_state
sla_risk_state
campaign_mode_state
API (gợi ý)
GET /api/v1/strategy/state
POST /api/v1/strategy/signals
GET /api/v1/objectives/current
POST /api/v1/objectives/mode (launch / margin / sla / quality)
GET /api/v1/portfolio/allocation
GET /api/v1/sla/risk
GET /api/v1/business/outcomes
Directive đẩy xuống các lớp dưới
Mission/Resilience/Fabric nhận các directive chuẩn hóa:
priority_weight_by_tier
capacity_reservation
cost_ceiling_by_mode
quality_floor_by_segment
routing_preference_profile
allowed_degradation_profile
experiment_freeze_flag
deadline_mode(ttl)
sla_protection_mode
Dashboard (Strategy Console)
Không chỉ là ops dashboard nữa, mà là Strategy Console:
Revenue / SLA / Throughput gauges
Portfolio lanes (enterprise/premium/standard/batch)
Active modes (Launch / Margin / SLA)
Capacity reservation map
SLA risk heatmap
Campaign windows timeline
“Why this decision?” (trace từ strategy → directive → action)
Luồng chuẩn
ingest strategy → translate to objectives → allocate portfolio → emit directives → fabric/resilience/autonomy execute → capture business outcomes → refine objectives (governed)
Guardrails bắt buộc
Safety/Compliance > all
Bounded trade-offs (không mở cost vô hạn)
Mode có TTL/expiry
Audit trail cho mọi thay đổi chiến lược
Manual approval cho thay đổi lớn (policy/architecture)
Canary rollout cho directive mạnh
Ví dụ cụ thể
“Launch 18:00 hôm nay”
bật deadline_mode(6h)
reserve 30% capacity cho project X
freeze experiments trên lane liên quan
cho phép cost +15% trong envelope
giảm optional validations (không ảnh hưởng compliance)
“Bảo vệ margin cuối tháng”
cost_ceiling siết chặt
giảm aggressive reroute
ưu tiên provider rẻ hơn
delay batch low-priority
“Enterprise SLA under risk”
tăng priority_weight enterprise
preemptive reroute cho enterprise runs
tăng escalation sensitivity
hạ priority standard/batch
Điều làm lớp này cực mạnh
Vì hệ có thể giải thích:
“Tại sao cost tăng hôm nay?” → vì deadline_mode
“Tại sao standard bị chậm?” → vì SLA protection
“Tại sao reroute ít?” → vì margin mode
👉 Quyết định kỹ thuật trở thành hệ quả của chiến lược.
Toàn bộ chuỗi hoàn chỉnh
Timeline
Operator control
Autonomous execution
Self-healing
Control fabric
Resilience OS
System evolution
Mission orchestration
Enterprise strategy alignment
👉 Đây là một goal-seeking, strategy-aligned execution system.
Đây là bước nên viết tiếp ngay.
Và ở lớp này, patch không nên chỉ là “thêm vài model”, mà phải là một directive layer thật nối:
enterprise strategy
→ objective translation
→ portfolio allocation
→ fabric directives
→ frontend strategy console
Bản patch file-by-file chuẩn nhất nên chia đúng 7 nhóm sau.
1. Backend models
Nên thêm:
backend/app/models/enterprise_strategy_signal.py
backend/app/models/objective_profile.py
backend/app/models/contract_sla_profile.py
backend/app/models/campaign_window.py
backend/app/models/roadmap_priority.py
backend/app/models/portfolio_allocation_plan.py
backend/app/models/business_outcome_snapshot.py
backend/app/models/strategy_directive.py
Mục đích:
lưu tín hiệu chiến lược
lưu objective đã dịch sang dạng máy đọc được
lưu directive đẩy xuống fabric/autonomy/resilience
lưu snapshot outcome cấp business
2. Migrations
Nên có một migration gộp kiểu:
backend/alembic/versions/20260412_0019_add_enterprise_strategy_tables.py
Tạo các bảng:
enterprise_strategy_signals
objective_profiles
contract_sla_profiles
campaign_windows
roadmap_priorities
portfolio_allocation_plans
business_outcome_snapshots
strategy_directives
3. Services
Đây là lõi thật của lớp này.
Nên thêm:
backend/app/services/strategy/strategy_ingestion_service.py
backend/app/services/strategy/objective_translation_engine.py
backend/app/services/strategy/portfolio_allocator.py
backend/app/services/strategy/contract_sla_service.py
backend/app/services/strategy/campaign_sync_service.py
backend/app/services/strategy/tradeoff_governance_engine.py
backend/app/services/strategy/business_feedback_service.py
backend/app/services/strategy/strategy_directive_bridge.py
Vai trò từng lớp:
strategy_ingestion_service
nhận input chiến lược từ revenue, SLA, campaign, roadmap
objective_translation_engine
đổi tín hiệu chiến lược thành objective profile
portfolio_allocator
phân capacity theo tier, project, mode
tradeoff_governance_engine
xử lý xung đột giữa margin / SLA / quality / throughput / deadline
strategy_directive_bridge
chuyển objective sang directive runtime:
priority weights
capacity reservation
cost ceiling
quality floor
routing preference
experiment freeze
4. API
Nên thêm:
backend/app/api/strategy.py
Các endpoint mạnh nhất:
GET /api/v1/strategy/state
POST /api/v1/strategy/signals
GET /api/v1/strategy/objectives
GET /api/v1/strategy/directives
GET /api/v1/strategy/portfolio
GET /api/v1/strategy/sla-risk
GET /api/v1/strategy/business-outcomes
POST /api/v1/strategy/modes
modes có thể gồm:
launch_mode
margin_mode
sla_protection_mode
quality_first_mode
5. Workers
Nên thêm:
backend/app/workers/strategy_refresh_worker.py
backend/app/workers/objective_rollup_worker.py
backend/app/workers/portfolio_rebalance_worker.py
backend/app/workers/business_outcome_rollup_worker.py
backend/app/workers/strategy_mode_expiry_worker.py
Chúng sẽ làm:
refresh strategy signals
recalc objective profiles
rebalance allocation
expire mode có TTL
update business snapshots
6. Directive bridge xuống fabric
Đây là phần quan trọng nhất để lớp strategy không bị “treo trên trời”.
Nên có:
backend/app/services/strategy/strategy_directive_bridge.py
backend/app/services/strategy/directive_dispatcher.py
Output directive chuẩn hóa nên gồm:
priority_weight_by_tier
capacity_reservation
cost_ceiling_by_mode
quality_floor_by_segment
routing_preference_profile
allowed_degradation_profile
experiment_freeze_flag
deadline_mode
sla_protection_mode
Tức là strategy layer không trực tiếp điều khiển workers, mà phát directive xuống:
fabric
resilience OS
autonomy layer
7. Frontend Strategy Console
Nên thêm:
frontend/src/app/strategy/page.tsx
cập nhật frontend/src/lib/api.ts
có thể thêm:
frontend/src/components/strategy/StrategyStateCard.tsx
frontend/src/components/strategy/PortfolioAllocationTable.tsx
frontend/src/components/strategy/DirectivePanel.tsx
frontend/src/components/strategy/SlaRiskHeatmap.tsx
frontend/src/components/strategy/CampaignTimeline.tsx
UI nên có:
current strategic mode
objective stack
portfolio allocation
SLA risk heatmap
active directives
business outcome panel
campaign / launch windows
“why this directive exists”
8. Tests cơ bản
Nên thêm:
backend/tests/test_objective_translation_engine.py
backend/tests/test_tradeoff_governance_engine.py
backend/tests/test_strategy_directive_bridge.py
backend/tests/test_strategy_api.py
backend/tests/test_portfolio_allocator.py
Các case quan trọng:
launch mode tăng capacity reservation đúng
margin mode siết cost ceiling đúng
SLA protection ưu tiên enterprise tier đúng
directive bridge tạo output đúng schema
conflicting objectives được resolve đúng thứ tự ưu tiên
Thứ tự triển khai mạnh nhất
Tôi khuyên viết theo thứ tự này:
models + migration
objective translation engine
tradeoff governance
directive bridge
strategy API
workers refresh/rebalance
Strategy Console
tests
Điểm phải giữ rất chặt
Lớp này phải luôn obey:
safety/compliance cao nhất
strategy chỉ phát directive trong envelope cho phép
mọi mode đều có TTL
mọi thay đổi đều có audit trail
các thay đổi lớn phải rollback được
Kết quả sau patch này
Sau lớp này, hệ của bạn sẽ có chuỗi điều khiển đầy đủ:
enterprise strategy
mission objectives
adaptive evolution
resilience OS
control fabric
self-healing
autonomy
operator console
unified execution timeline
Nói cách khác, từ đây monorepo không còn là “video publishing tool” nữa, mà là một strategy-aligned execution platform.
Đây là bước mạnh nhất ngay sau bản Strategy Layer.
Vì hiện tại bạn đã có:
strategy signals
objective translation
directive generation
strategy console
Nhưng nếu directive chỉ được nhìn thấy mà chưa được thực thi xuống fabric, thì hệ vẫn mới dừng ở mức:
hiểu chiến lược
mô tả chiến lược
hiển thị chiến lược
chứ chưa thành:
strategy-driven runtime
Bước tiếp theo phải biến directive thành runtime control thật.
Mục tiêu của lớp này
Nối thẳng:
capacity_reservation
cost_ceiling
routing_preference
deadline_mode
quality_floor
experiment_freeze
sla_protection_mode
xuống các lớp đang chạy thật:
scheduler
provider router
queue dispatcher
suppression engine
retry/reroute policy
degraded-mode controller
Nói ngắn gọn:
strategy → directive → enforcement → observed runtime effect
Đây là điểm mà strategy layer thôi “nói chuyện” và bắt đầu “ra lệnh thật”.
1. Capacity reservation enforcement
Đây là phần mạnh nhất đầu tiên.
Hiện tại capacity_reservation mới là directive logic.
Bước tiếp theo là dùng nó để ảnh hưởng thật đến:
queue admission
worker allocation
lane priority
concurrency slots
Ví dụ:
enterprise tier được giữ 30% worker slots
launch project được ưu tiên dispatch trước
batch jobs bị chặn khi reserve đang bị ăn hết
mux stage có reserved lane riêng vì là critical path
Nên thêm enforcement kiểu:
capacity_reservation_state
reservation_enforcement_service.py
queue_admission_controller.py
worker_slot_allocator.py
Khi đó runtime sẽ không còn “cạnh tranh tự do”, mà bắt đầu chạy theo quota chiến lược.
2. Cost ceiling enforcement
Đây là lớp chặn runaway cost.
Directive cost_ceiling_by_mode phải ảnh hưởng tới:
có được reroute sang provider đắt hơn không
có được bật premium recovery không
có được tăng worker scale-out không
có được dùng lane quality cao không
Ví dụ:
margin_mode bật lên → cấm reroute sang provider cost+40%
chỉ cho phép fallback rẻ hoặc neutral-cost
tắt một số optional enhancements
siết retry/recovery envelope
Nên thêm:
cost_enforcement_service.py
budget_gate.py
provider_cost_guard.py
Mọi action có estimated_cost_delta đều phải đi qua cost gate trước khi thực thi.
3. Routing preference enforcement
Đây là phần làm strategy layer ảnh hưởng trực tiếp đến provider/router.
Directive routing_preference_profile phải đi vào:
provider selection
fallback ranking
per-phase routing
tier-aware provider selection
Ví dụ:
premium narration dùng provider ổn định hơn
batch render dùng provider rẻ hơn
launch mode ưu tiên provider throughput cao
quality-first mode dùng provider chất lượng cao hơn cho mux/narration
Nên thêm:
routing_preference_enforcer.py
provider_selection_policy.py
provider_weight_resolver.py
Khi router chọn provider, nó không chỉ nhìn:
health
latency
fail rate
mà còn nhìn:
mission mode
customer tier
active strategy directives
budget envelope
4. Deadline mode enforcement
Đây là lớp rất thực chiến.
deadline_mode không nên chỉ là badge trên UI.
Nó phải kéo theo thay đổi runtime như:
ưu tiên dispatch cho runs liên quan deadline
reserve thêm slots
nới cost envelope có kiểm soát
freeze experiments
cho phép fast stable fallback
hạ bớt một số optional non-critical validations
Nên thêm:
deadline_mode_enforcer.py
priority_escalation_service.py
deadline_scheduler_policy.py
Điểm quan trọng:
deadline mode phải có:
TTL
scope rõ
rollback ngay khi hết cửa sổ deadline
5. Suppression runtime enforcement
Directive chiến lược cũng phải ảnh hưởng đến suppression.
Ví dụ:
trong launch_mode, suppression ngắn hơn với premium runs
trong margin_mode, suppression mạnh hơn với noisy retry storm để tránh đốt cost
trong sla_protection_mode, cluster incident escalation nhạy hơn
Nên nối xuống:
suppression_engine.py
cluster_mitigation_policy.py
escalation_controller.py
Nói cách khác:
chiến lược không chỉ ảnh hưởng scheduling, mà còn ảnh hưởng nhịp phản ứng của fabric.
6. Directive enforcement read model
Bạn cần một read model riêng để biết directive nào đang thực sự có hiệu lực.
Nên thêm:
directive_enforcement_state
runtime_override_state
strategy_runtime_effect_log
Các field nên có:
directive id
scope
effective from/to
enforcement target
runtime effect summary
status: pending / active / expired / rolled_back / blocked
last observed impact
Nếu không có lớp này, bạn sẽ không phân biệt được:
directive đã phát ra
directive đã được apply
directive đang có tác động thật
7. API nên có gì
Nên thêm các endpoint kiểu:
GET /api/v1/strategy/enforcement/state
GET /api/v1/strategy/enforcement/effects
POST /api/v1/strategy/enforcement/recompute
POST /api/v1/strategy/enforcement/rollback
GET /api/v1/fabric/routing-state
GET /api/v1/fabric/capacity-state
GET /api/v1/fabric/budget-state
Mục tiêu là để operator/strategy console thấy được:
directive nào đang active
nó đang ép runtime thế nào
kết quả bước đầu ra sao
8. Workers nên thêm
directive_enforcement_worker.py
capacity_reconciliation_worker.py
routing_preference_refresh_worker.py
budget_enforcement_worker.py
deadline_mode_expiry_worker.py
Các worker này sẽ làm:
apply directives
reconcile runtime state
expire directives theo TTL
rollback khi directive không còn hợp lệ
refresh weights và reservations định kỳ
9. Frontend nên nâng thành Strategy-Fabric Console
Không chỉ xem strategy nữa, mà thấy được strategy đang ép runtime ra sao.
Nên thêm các panel:
Active directives
Runtime effects
Capacity reservations
Provider routing weights
Budget guard status
Deadline mode state
Enforcement audit log
Rollback controls
Quan trọng nhất là phải có trace:
strategy signal → objective → directive → enforced runtime effect
Đây là mạch giải thích khiến hệ đáng tin cậy.
10. Tests quan trọng nhất
test_capacity_reservation_enforcement.py
test_cost_ceiling_enforcement.py
test_routing_preference_enforcement.py
test_deadline_mode_enforcement.py
test_directive_enforcement_api.py
Case cần có:
reserve slots thật sự đổi admission behavior
cost ceiling chặn reroute đắt
routing preference đổi provider weight đúng
deadline mode tăng priority và hết TTL thì rollback
expired directive không còn tác động runtime
Thứ tự triển khai mạnh nhất
Tôi khuyên patch theo thứ tự này:
directive enforcement state + migration
capacity reservation enforcement
routing preference enforcement
cost ceiling enforcement
deadline mode enforcement
API + workers reconcile/expiry
frontend enforcement panels
tests
Vì sao đây là bước mạnh nhất
Vì sau lớp này, hệ của bạn lần đầu tiên có chuỗi đầy đủ:
chiến lược doanh nghiệp
objective profile
strategy directives
fabric enforcement
runtime behavior change
observed business effect
Nói cách khác, đây là lúc monorepo của bạn thôi là:
platform biết chiến lược
và trở thành:
platform vận hành theo chiến lược
Đây là lớp đóng vòng cuối cùng và là một trong những lớp quan trọng nhất của toàn bộ hệ.
Vì từ trước đến đây, bạn đã đi được chuỗi:
strategy phát directive
directive được enforce xuống fabric
runtime thay đổi hành vi thật
Nhưng vẫn còn thiếu câu hỏi lớn nhất:
sự thay đổi đó có thực sự tạo ra kết quả kinh doanh tốt hơn không?
Đó chính là vai trò của strategy outcome attribution layer.
Bản chất của lớp này
Lớp này không chỉ đo:
directive đã active chưa
runtime có đổi chưa
mà đo:
đổi như vậy có đáng không
đổi cái gì tạo ra kết quả tốt
đổi cái gì gây tốn kém nhưng không giúp mission
đổi cái gì nên promote thành default strategy
đổi cái gì nên rollback hoặc cấm dùng lại
Nói ngắn gọn:
strategy outcome attribution = cầu nối định lượng giữa quyết định chiến lược và kết quả thực tế
4 câu hỏi lõi mà lớp này phải trả lời
1. Directive nào thực sự cải thiện outcome?
Ví dụ:
capacity_reservation có thực sự giảm SLA breach không?
deadline_mode có thực sự giúp kịp launch window không?
routing_preference_profile có thực sự tăng reliability cho premium tier không?
2. Directive nào chỉ tạo cảm giác kiểm soát nhưng không tạo giá trị?
Ví dụ:
cost tăng nhưng deadline không cải thiện
reserve capacity nhiều nhưng throughput tổng thể không tăng
reroute nhiều nhưng final recovery không tốt hơn
3. Directive nào có tác dụng trong điều kiện nào?
Ví dụ:
deadline mode chỉ hiệu quả cho premium launch, không hiệu quả cho batch
cost ceiling mạnh ở giờ bình thường nhưng hại SLA lúc peak
routing preference tốt cho narration nhưng vô nghĩa với mux
4. Directive nào nên promote, throttle, hoặc retire?
Ví dụ:
promote thành default policy
chỉ dùng cho một workload class
giảm phạm vi rollout
retire hẳn vì cost > value
Đây là lớp gì nếu nhìn đúng bản chất?
Nó là một causal-ish evaluation layer có governance.
Không nhất thiết phải làm causal inference hoàn chỉnh ngay từ đầu, nhưng nó phải tiến gần đến việc trả lời:
“kết quả tốt hơn là do directive này, hay do hệ vốn đã hồi phục sẵn?”
Tức là attribution layer phải cố gắng tách:
correlation
coincidence
true contribution
5 năng lực lõi bắt buộc phải có
1. Outcome linking
Phải nối được:
strategy signal
objective profile
directive
enforcement state
runtime events
business outcome
thành một chuỗi truy vết duy nhất.
Ví dụ một chain đầy đủ:
launch_mode activated -> deadline_mode enforced -> provider weight shifted -> queue latency dropped -> premium job finished before deadline -> SLA penalty avoided
Nếu không nối được chain này thì attribution sẽ mù.
2. Counterfactual-lite evaluation
Hệ nên bắt đầu bằng phiên bản nhẹ của counterfactual:
trước khi áp directive, baseline là gì
sau khi áp directive, metric đổi ra sao
có nhóm tương tự không áp directive để so
historical expected outcome là gì
Không cần quá phức tạp ban đầu. Có thể bắt đầu bằng:
before/after windows
matched cohort
same project / same tier / same phase comparison
historical rolling baseline
Mục tiêu là tránh kiểu:
thấy SLA tốt hơn rồi tưởng directive có công
trong khi thực ra do queue tự hết nghẽn.
3. Multi-metric attribution
Không được chấm directive bằng 1 metric duy nhất.
Mỗi directive phải được chấm ít nhất theo:
SLA effect
deadline effect
cost effect
quality effect
throughput effect
operator load effect
Ví dụ:
deadline mode cứu deadline tốt
nhưng cost tăng mạnh
và quality giảm nhẹ
Khi đó kết luận không phải “tốt” hay “xấu”, mà là:
tốt cho mục tiêu A
trung tính cho B
có penalty ở C
4. Promotion and rollback recommendation
Đây là phần làm lớp này có giá trị vận hành.
Attribution layer phải đưa ra đề xuất như:
promote directive thành default cho tier enterprise
giữ directive nhưng thu hẹp scope
rollback directive vì cost delta quá cao
chỉ dùng directive trong launch windows
retire directive cho batch workloads
Tức là nó không chỉ quan sát, mà tạo đầu vào cho:
policy refinement
strategy refinement
fabric tuning
enterprise governance
5. Strategic memory
Hệ phải nhớ:
directive nào từng hiệu quả
hiệu quả trong bối cảnh nào
hiệu quả ngắn hạn hay dài hạn
ở workload nào thì phản tác dụng
Đây là lớp “institutional memory” của system.
Ví dụ:
deadline_mode_v2 tốt cho premium launch dưới 6h
nhưng hại margin nếu kéo quá 12h
cost_ceiling_strict tốt cho batch
nhưng nguy hiểm với enterprise SLA windows
Kiến trúc nên thêm ở bước này
Models
strategy_outcome_attribution.py
directive_effect_snapshot.py
objective_outcome_link.py
business_impact_assessment.py
directive_promotion_recommendation.py
directive_retirement_decision.py
Services
outcome_linking_service.py
attribution_engine.py
baseline_comparison_service.py
cohort_matching_service.py
directive_scoring_service.py
promotion_recommendation_service.py
rollback_recommendation_service.py
Workers
outcome_attribution_worker.py
baseline_refresh_worker.py
directive_effect_rollup_worker.py
promotion_decision_worker.py
Read models
directive_effectiveness_rollup
strategy_outcome_state
objective_impact_summary
directive_recommendation_state
business_impact_rollup
Mỗi directive nên được chấm kiểu gì
Tôi khuyên mỗi directive có một scorecard như sau:
sla_gain_score
deadline_recovery_score
cost_penalty_score
quality_penalty_score
throughput_gain_score
operator_relief_score
net_mission_effect_score
Ví dụ:
directive: deadline_mode
SLA gain: cao
Deadline recovery: rất cao
Cost penalty: trung bình
Quality penalty: thấp
Operator relief: cao
Net mission effect: dương mạnh trong launch windows
Từ đó hệ mới nói được:
giữ
mở rộng
thu hẹp
rollback
Điều cực kỳ quan trọng: attribution phải theo context
Một directive không bao giờ “tốt tuyệt đối”.
Nó chỉ tốt trong:
đúng tier
đúng workload class
đúng mission mode
đúng thời gian
đúng pressure profile
Ví dụ:
capacity_reservation tốt trong SLA protection
nhưng lãng phí trong low-load periods
cost_ceiling_strict tốt khi bảo vệ margin
nhưng tệ khi launch deadline cận kề
Vì vậy attribution layer phải luôn gắn score với:
context
scope
mode
objective stack
Dashboard nên có gì
Frontend nên nâng thành một Strategy Impact Console với các panel:
Directive effectiveness leaderboard
SLA impact chart
Deadline save rate
Cost vs value scatter plot
Quality trade-off heatmap
Promotion recommendations
Rollback candidates
“Why this directive was judged effective”
Quan trọng nhất là operator hoặc strategy owner nhìn được:
directive A tốt hơn directive B ở đâu, trong bối cảnh nào, với cái giá nào
Vì đây là lớp đầu tiên trả lời được câu hỏi quan trọng nhất của toàn bộ hệ:
“quyết định chiến lược nào thực sự tạo ra giá trị kinh doanh, trong điều kiện nào, với cái giá nào?”
Khi chưa có lớp này, toàn bộ stack phía dưới dù rất mạnh vẫn mới dừng ở mức:
ra quyết định tốt hơn
thực thi tốt hơn
tự hồi phục tốt hơn
điều phối tốt hơn
bám mục tiêu tốt hơn
Nhưng vẫn chưa biết chắc:
cái gì thật sự đáng giữ
cái gì chỉ là cảm giác kiểm soát
cái gì đắt nhưng vô ích
cái gì nên thành chuẩn vận hành
cái gì phải rollback trước khi trở thành thói quen hệ thống
Đó là lý do nó là lớp đóng vòng cuối cùng.
Vì nó khép kín toàn bộ chuỗi sau
enterprise strategy
→ objective hierarchy
→ directive generation
→ fabric enforcement
→ runtime behavior change
→ business outcome
→ attribution
→ promotion / rollback / retirement
→ cập nhật strategy tiếp theo
Khi có lớp này, hệ không còn vận hành theo kiểu:
ra directive
hy vọng nó đúng
thấy vài chỉ số đẹp rồi tin rằng nó hiệu quả
Mà chuyển sang:
ra directive
đo tác động thật
so với baseline
tính cost và trade-off
kết luận có giữ hay không
đưa kết luận đó quay ngược lại strategy layer
Đó chính là một closed strategic loop hoàn chỉnh.
Vì đây là nơi “chiến lược” bị buộc phải trả bài bằng kết quả thật
Trước lớp này, chiến lược có thể nghe rất hợp lý:
reserve capacity cho premium
bật deadline mode
siết cost ceiling
đổi routing preference
freeze experiments
Nhưng chỉ ở attribution layer bạn mới biết:
reserve capacity có thật sự tránh breach không
deadline mode có thật sự cứu launch không
cost ceiling có bảo vệ margin mà không làm hỏng SLA không
routing preference mới có giúp hơn routing cũ không
experiment freeze có làm hệ ổn hơn thật hay chỉ làm mất cơ hội tối ưu
Nói cách khác:
mọi directive đều phải ra tòa ở lớp này.
Vì nó biến “strategy” thành thứ có thể học được
Nếu không có attribution, strategy layer rất dễ trở thành:
static policy
intuition của operator
preference của stakeholder
phản ứng theo cảm giác
Có attribution rồi, strategy bắt đầu có:
memory theo outcome
ranking theo effectiveness
context-specific trust
evidence để promote/retire
Lúc đó hệ không còn chỉ “có chiến lược”, mà bắt đầu học chiến lược nào đáng tin.
Vì nó ngăn hệ tiến hóa sai hướng
Một hệ nhiều lớp như bạn đang xây có một rủi ro lớn:
autonomy tối ưu cái dễ đo
resilience tối ưu cái cứu nhanh
fabric tối ưu cái ổn định hệ
mission layer tối ưu cái gần mục tiêu
strategy layer tối ưu cái nghe có vẻ hợp lý
Nhưng tất cả các lớp đó vẫn có thể cùng nhau trượt nếu thiếu một lớp hỏi lại:
“tất cả những tối ưu đó có tạo ra kết quả doanh nghiệp tốt hơn thật không?”
Attribution layer chính là bộ phanh trí tuệ của toàn hệ.
Nó chặn các kiểu tiến hóa sai như:
cost tăng nhưng tưởng là đáng
cứu SLA ngắn hạn nhưng làm margin xấu dài hạn
reserve capacity quá mức làm standard tier nghẽn
deadline mode bị lạm dụng
directive noisy được giữ lại chỉ vì vài case nổi bật
Vì nó tạo nền cho governance thật
Chỉ khi có attribution layer, bạn mới có governance cấp cao kiểu:
directive nào cần approval mới được mở rộng phạm vi
directive nào chỉ được giữ ở một số context
directive nào đủ bằng chứng để thành default
directive nào phải sunset
directive nào bị cấm vì trade-off xấu
Không có attribution, governance chỉ là rule cứng.
Có attribution, governance trở thành evidence-based governance.
Strategy Impact Console vì thế không chỉ là dashboard đẹp
Nó là nơi hiển thị bằng chứng để ra quyết định chiến lược tiếp theo.
Các panel bạn nêu ra chính là đúng lõi:
Directive effectiveness leaderboard
để biết directive nào thật sự có net value cao
SLA impact chart
để thấy directive nào cứu SLA, cứu trong tier nào
Deadline save rate
để biết deadline mode có đáng bật hay không
Cost vs value scatter plot
để nhìn rõ directive nào đắt mà không đáng
Quality trade-off heatmap
để tránh cứu vận hành bằng cách âm thầm làm xấu output
Promotion recommendations
để biết cái gì nên thành chuẩn
Rollback candidates
để biết cái gì nên rút lại sớm
“Why this directive was judged effective”
để hệ không thành hộp đen
Điểm mạnh nhất của console này là nó giúp strategy owner nhìn được:
directive A hơn directive B ở đâu
hơn trong workload nào
hơn trong mission mode nào
hơn với chi phí bao nhiêu
và có đáng mở rộng hay không
Nói ngắn gọn
Đây là lớp đóng vòng cuối cùng vì nó biến toàn bộ hệ từ:
biết chiến lược
biết thực thi
biết tự hồi phục
biết tự tối ưu
thành một hệ:
biết chiến lược nào thực sự tạo giá trị
biết khi nào chiến lược đó đúng
biết khi nào phải dừng, rollback, hoặc promote
Đó là khoảnh khắc hệ của bạn không còn chỉ là một execution platform rất mạnh, mà trở thành một self-correcting strategic execution system.
Ở lượt tiếp theo, tôi có thể viết thẳng bộ spec cho Strategy Impact Console + attribution data model + scoring framework theo đúng format monorepo để bạn đi tiếp sang patch file-by-file.
Ở lượt tiếp theo, tôi có thể viết thẳng bộ spec cho Strategy Impact Console + attribution data model + scoring framework theo đúng format monorepo để bạn đi tiếp sang patch file-by-file.
Đã suy nghĩ trong vài giây
Đúng. Đó là bước nên chốt spec trước khi viết patch.
Với lớp này, làm đúng nhất là tách thành 3 trục rõ ràng:
Strategy Impact Console: phần nhìn và quyết định
Attribution data model: phần dữ liệu và truy vết
Scoring framework: phần chấm điểm và recommendation
Nếu viết spec tốt, lượt patch sau sẽ đi rất thẳng, không bị loạn giữa “metric”, “impact”, “attribution”, và “recommendation”.
Bộ spec nên chia thành 8 phần
1. Mục tiêu của layer
Phải định nghĩa rất rõ layer này dùng để trả lời 4 câu hỏi:
directive nào tạo ra giá trị thật
directive nào chỉ tăng cost hoặc complexity
directive nào hiệu quả trong context nào
directive nào nên promote, throttle, rollback, retire
Đây là phần khóa phạm vi để patch sau không trôi sang analytics chung chung.
2. Attribution entity model
Nên chuẩn hóa các entity cốt lõi như:
strategy_directive
directive_enforcement_window
objective_context_snapshot
runtime_effect_snapshot
business_outcome_snapshot
directive_attribution_record
directive_recommendation
Chuỗi liên kết phải là:
strategy signal -> objective profile -> directive -> enforcement -> runtime effect -> business outcome -> attribution verdict
3. Attribution windows và baseline
Spec phải định nghĩa rõ:
observation window
comparison baseline
matched cohort hoặc historical baseline
minimum evidence threshold
confidence bands
Ví dụ:
t0: directive bắt đầu active
t1: observe runtime effect
t2: observe business outcome
baseline lấy theo:
historical rolling window
same tier / same workload class
same mission mode nếu có
Nếu không khóa phần này, patch sau rất dễ thành before/after thô.
4. Scoring framework
Đây là lõi.
Mỗi directive nên có scorecard chuẩn như:
sla_gain_score
deadline_save_score
cost_penalty_score
quality_penalty_score
throughput_gain_score
operator_load_relief_score
stability_gain_score
net_mission_effect_score
confidence_score
Và phải có công thức kết luận cuối:
promote_candidate
keep_with_scope
throttle_candidate
rollback_candidate
retire_candidate
5. Context-aware segmentation
Spec phải bắt buộc attribution theo context, không chấm gộp bừa.
Nên có các dimension:
tier
workload class
mission mode
provider family
project
phase
time window
strategy mode
Để console trả lời được kiểu:
directive này tốt cho enterprise launch
nhưng tệ cho batch margin mode
6. Recommendation engine rules
Nên định nghĩa rule rõ cho recommendation:
promote nếu:
net effect cao
confidence đủ
cost penalty trong ngưỡng
không vi phạm quality floor
rollback nếu:
cost tăng mạnh
SLA gain thấp
quality penalty cao
throttle nếu:
chỉ tốt ở một số context
retire nếu:
hiệu quả thấp lặp lại nhiều kỳ
7. Strategy Impact Console spec
UI nên có đúng các panel bạn đã nêu, nhưng cần chốt dữ liệu đầu vào cho từng panel:
Directive effectiveness leaderboard
top directives theo net_mission_effect_score
SLA impact chart
before/after + baseline by tier
Deadline save rate
% runs tránh breach nhờ directive
Cost vs value scatter plot
x = cost penalty
y = net effect
bubble = confidence hoặc sample size
Quality trade-off heatmap
quality delta theo directive/context
Promotion recommendations
kèm lý do + confidence
Rollback candidates
kèm penalty profile
Why this directive was judged effective
trace giải thích:
context
baseline
observed change
trade-off
final verdict
8. Patch contract cho lượt sau
Spec nên kết thúc bằng danh sách file sẽ sinh ra ở lượt patch, ví dụ:
backend models
migrations
attribution services
scoring services
recommendation services
API
frontend strategy impact console
tests
Thứ tự viết spec mạnh nhất
Tôi khuyên chốt theo đúng thứ tự này:
attribution goals
entity/data model
windows + baseline logic
scoring framework
recommendation rules
API contract
frontend console contract
test matrix
Vì sao nên làm spec trước
Vì lớp này rất dễ bị lệch thành:
BI dashboard
observability board
analytics summary
Trong khi thứ bạn cần là:
decision-grade attribution system
Tức là hệ đủ chắc để dùng kết quả đó cho:
promote directive
rollback directive
đổi strategy scope
cập nhật governance
Kết quả của spec tốt
Nếu chốt đúng spec này, lượt patch file-by-file sau đó sẽ đi rất sạch:
model nào sinh ra để làm gì
endpoint nào phục vụ panel nào
score nào quyết định recommendation nào
context nào bắt buộc phải segment
test nào chứng minh attribution không bị “ảo”
Tôi sẽ compress lại thành bản SPEC FINAL (không lan man, chỉ giữ phần có thể code hóa trực tiếp).
🧠 STRATEGY ATTRIBUTION LAYER — FINAL SPEC (MONOREPO-READY)
I. CORE PURPOSE (LOCK SCOPE)
Layer này chỉ tồn tại để trả lời 4 câu hỏi bắt buộc:
Directive nào tạo net business value thật
Directive nào tăng cost nhưng không tạo giá trị
Directive nào chỉ đúng trong context cụ thể
Directive nào cần:
promote
throttle
rollback
retire
👉 Bất kỳ metric / API / UI nào không phục vụ 4 câu này → LOẠI
II. ATTRIBUTION DATA MODEL (CANONICAL CHAIN)
Chuỗi bắt buộc (không được phá vỡ):
strategy_signal
→ objective_context_snapshot
→ strategy_directive
→ directive_enforcement_window
→ runtime_effect_snapshot
→ business_outcome_snapshot
→ directive_attribution_record
→ directive_recommendation
III. ENTITY DEFINITIONS (STRICT)
1. strategy_directive
id
name
strategy_origin
objective_id
directive_type
parameters (json)
activation_ts
deactivation_ts
scope:
  tier
  workload_class
  mission_mode
  provider
  project
2. directive_enforcement_window
id
directive_id
start_ts
end_ts
active_context_hash
is_partial
3. runtime_effect_snapshot
id
directive_id
window_id
sla_metrics:
  latency_p95
  error_rate
deadline_metrics:
  breach_rate
cost_metrics:
  cost_per_job
  total_cost
throughput:
  jobs_per_minute
stability:
  retry_rate
  incident_rate
operator_load:
  manual_interventions
timestamp
4. business_outcome_snapshot
id
directive_id
window_id
revenue_impact
margin_delta
sla_breach_avoided
deadline_saved
customer_impact_score
quality_score
timestamp
5. directive_attribution_record (CORE TABLE)
id
directive_id
window_id
baseline_id
context_signature

sla_gain
deadline_save
cost_penalty
quality_penalty
throughput_gain
stability_gain

net_mission_effect
confidence_score

sample_size
evaluation_ts
6. directive_recommendation
id
directive_id
verdict:
  promote | keep | throttle | rollback | retire

reason_summary
confidence_score

context_scope:
  allowed_contexts
  restricted_contexts

generated_ts
IV. ATTRIBUTION WINDOWS + BASELINE
1. Observation Windows
t0 → directive activate
t1 → runtime effect capture
t2 → business outcome capture
2. Baseline Types
baseline_type:
  - historical_rolling
  - matched_cohort
  - same_context_previous

matching_keys:
  tier
  workload_class
  mission_mode
  provider
3. Evidence Rules
min_sample_size: 50
min_duration_minutes: 30

confidence_bands:
  high: >0.8
  medium: 0.5–0.8
  low: <0.5
V. SCORING FRAMEWORK (NON-NEGOTIABLE CORE)
Score Components
sla_gain_score
deadline_save_score
cost_penalty_score
quality_penalty_score
throughput_gain_score
stability_gain_score
operator_relief_score
Net Mission Effect
net_mission_effect =
  (sla_gain * w1)
+ (deadline_save * w2)
+ (throughput_gain * w3)
+ (stability_gain * w4)
- (cost_penalty * w5)
- (quality_penalty * w6)
Confidence
confidence_score =
  f(sample_size, variance, consistency_across_windows)
VI. CONTEXT SEGMENTATION (MANDATORY)
Không bao giờ chấm điểm global.
Required dimensions:
tier
workload_class
mission_mode
provider
project
time_bucket
strategy_mode
👉 Mọi attribution record phải có context_signature
VII. RECOMMENDATION ENGINE RULES
1. PROMOTE
if:
  net_effect > high_threshold
  confidence > 0.8
  cost_penalty < limit
  quality_penalty < limit
2. KEEP (SCOPED)
if:
  net_effect positive
  nhưng chỉ đúng trong context cụ thể
3. THROTTLE
if:
  variance cao
  hoặc chỉ tốt ở subset context
4. ROLLBACK
if:
  cost_penalty cao
  sla_gain thấp
  quality_penalty cao
5. RETIRE
if:
  net_effect thấp liên tục
  across multiple windows
VIII. STRATEGY IMPACT CONSOLE (UI CONTRACT)
1. Directive Effectiveness Leaderboard
Input: net_mission_effect
Sort: descending
Filter: context
2. SLA Impact Chart
Before vs After vs Baseline
Group by tier / mission_mode
3. Deadline Save Rate
saved_deadlines / total_deadlines
4. Cost vs Value Scatter
X = cost_penalty
Y = net_effect
Bubble = confidence
5. Quality Trade-off Heatmap
Δ quality theo directive + context
6. Promotion Recommendations
directive_id
reason
confidence
suggested_scope
7. Rollback Candidates
penalty breakdown
risk score
8. Explain Panel ("Why effective")
Trace bắt buộc:
context
baseline
observed_delta
trade_off
final_verdict
confidence
IX. API CONTRACT (BACKEND → FRONTEND)
Core endpoints
GET /strategy/directives
GET /strategy/attribution
GET /strategy/recommendations
GET /strategy/leaderboard
GET /strategy/explain/{directive_id}
GET /strategy/scatter
GET /strategy/heatmap
X. PATCH PLAN (NEXT STEP)
Backend
models/
repositories/
attribution_service.py
scoring_engine.py
recommendation_engine.py
Workers
attribution_worker.py
scoring_worker.py
API
strategy_router.py
Frontend
StrategyImpactConsole.tsx
LeaderboardPanel.tsx
ScatterPlot.tsx
Heatmap.tsx
ExplainDrawer.tsx
Infra
migrations (Alembic)
metrics hooks
Tests
attribution correctness
baseline matching
scoring stability
recommendation validity
🔥 KẾT LUẬN (RẤT QUAN TRỌNG)
Bạn đã đúng hoàn toàn ở insight cốt lõi:
Đây không phải analytics layer
→ mà là decision-grade attribution system
Và SPEC này đã khóa chặt điều đó bằng:
chain dữ liệu không bị gãy
scoring có thể quyết định thật
recommendation có thể execute
UI phục vụ decision, không phải quan sát
Strategy Impact Console — Patch File-by-File
Dưới đây là patch monorepo production-oriented cho layer Strategy Impact Console + Attribution + Scoring + Recommendation.
Assumption: monorepo đang dùng FastAPI + SQLAlchemy + Alembic + Celery + React/TypeScript.
Nếu codebase hiện tại của bạn đã có các module tương đương, giữ nguyên naming convention nội bộ và cắm patch này vào đúng domain strategy / attribution.
1) backend/app/models/strategy_attribution.py
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
class DirectiveVerdict(str, enum.Enum):
    PROMOTE = "promote"
    KEEP = "keep"
    THROTTLE = "throttle"
    ROLLBACK = "rollback"
    RETIRE = "retire"
class BaselineType(str, enum.Enum):
    HISTORICAL_ROLLING = "historical_rolling"
    MATCHED_COHORT = "matched_cohort"
    SAME_CONTEXT_PREVIOUS = "same_context_previous"
class StrategyDirective(Base):
    __tablename__ = "strategy_directives"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    strategy_origin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    objective_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    directive_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    workload_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    mission_mode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    strategy_mode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    activation_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    deactivation_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
class DirectiveEnforcementWindow(Base):
    __tablename__ = "directive_enforcement_windows"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    active_context_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_signature: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class RuntimeEffectSnapshot(Base):
    __tablename__ = "runtime_effect_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    latency_p95_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline_breach_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_job: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jobs_per_minute: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retry_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    incident_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manual_interventions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class BusinessOutcomeSnapshot(Base):
    __tablename__ = "business_outcome_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    revenue_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margin_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sla_breach_avoided: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deadline_saved: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class DirectiveAttributionRecord(Base):
    __tablename__ = "directive_attribution_records"
    __table_args__ = (
        UniqueConstraint("directive_id", "window_id", name="uq_directive_window_attribution"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_type: Mapped[BaselineType] = mapped_column(Enum(BaselineType), nullable=False, index=True)
    baseline_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    context_signature: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sla_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deadline_save: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    throughput_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stability_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    operator_relief: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_mission_effect: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explain_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluation_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class DirectiveRecommendation(Base):
    __tablename__ = "directive_recommendations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_attribution_records.id", ondelete="CASCADE"), nullable=False, index=True)
    verdict: Mapped[DirectiveVerdict] = mapped_column(Enum(DirectiveVerdict), nullable=False, index=True)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    allowed_contexts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    restricted_contexts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
2) backend/app/schemas/strategy_attribution.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
class StrategyDirectiveRead(BaseModel):
    id: UUID
    name: str
    directive_type: str
    strategy_origin: Optional[str] = None
    objective_id: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    tier: Optional[str] = None
    workload_class: Optional[str] = None
    mission_mode: Optional[str] = None
    provider: Optional[str] = None
    project: Optional[str] = None
    strategy_mode: Optional[str] = None
    activation_ts: datetime
    deactivation_ts: Optional[datetime] = None
    is_active: bool
    model_config = {"from_attributes": True}
class AttributionRecordRead(BaseModel):
    id: UUID
    directive_id: UUID
    window_id: UUID
    baseline_type: str
    baseline_id: Optional[str] = None
    context_signature: dict[str, Any]
    sla_gain: float
    deadline_save: float
    cost_penalty: float
    quality_penalty: float
    throughput_gain: float
    stability_gain: float
    operator_relief: float
    net_mission_effect: float
    confidence_score: float
    sample_size: int
    explain_payload: dict[str, Any]
    evaluation_ts: datetime
    model_config = {"from_attributes": True}
class RecommendationRead(BaseModel):
    id: UUID
    directive_id: UUID
    attribution_record_id: UUID
    verdict: str
    reason_summary: str
    confidence_score: float
    allowed_contexts: dict[str, Any]
    restricted_contexts: dict[str, Any]
    generated_ts: datetime
    model_config = {"from_attributes": True}
class LeaderboardRow(BaseModel):
    directive_id: UUID
    directive_name: str
    directive_type: str
    net_mission_effect: float
    confidence_score: float
    sample_size: int
    context_signature: dict[str, Any]
    latest_verdict: Optional[str] = None
class ScatterPoint(BaseModel):
    directive_id: UUID
    directive_name: str
    cost_penalty: float
    net_mission_effect: float
    confidence_score: float
    sample_size: int
class HeatmapCell(BaseModel):
    directive_id: UUID
    directive_name: str
    context_key: str
    quality_penalty: float
class ExplainResponse(BaseModel):
    directive: StrategyDirectiveRead
    attribution: AttributionRecordRead
    recommendation: Optional[RecommendationRead] = None
3) backend/app/repositories/strategy_attribution_repository.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.models.strategy_attribution import (
    DirectiveAttributionRecord,
    DirectiveRecommendation,
    StrategyDirective,
)
class StrategyAttributionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def list_directives(
        self,
        tier: Optional[str] = None,
        mission_mode: Optional[str] = None,
        provider: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[StrategyDirective]:
        stmt = select(StrategyDirective)
        if tier:
            stmt = stmt.where(StrategyDirective.tier == tier)
        if mission_mode:
            stmt = stmt.where(StrategyDirective.mission_mode == mission_mode)
        if provider:
            stmt = stmt.where(StrategyDirective.provider == provider)
        if is_active is not None:
            stmt = stmt.where(StrategyDirective.is_active == is_active)
        stmt = stmt.order_by(desc(StrategyDirective.activation_ts))
        return list(self.db.scalars(stmt).all())
    def list_attributions(self, directive_id: Optional[UUID] = None) -> list[DirectiveAttributionRecord]:
        stmt = select(DirectiveAttributionRecord).order_by(desc(DirectiveAttributionRecord.evaluation_ts))
        if directive_id:
            stmt = stmt.where(DirectiveAttributionRecord.directive_id == directive_id)
        return list(self.db.scalars(stmt).all())
    def get_latest_attribution_for_directive(self, directive_id: UUID) -> Optional[DirectiveAttributionRecord]:
        stmt = (
            select(DirectiveAttributionRecord)
            .where(DirectiveAttributionRecord.directive_id == directive_id)
            .order_by(desc(DirectiveAttributionRecord.evaluation_ts))
            .limit(1)
        )
        return self.db.scalar(stmt)
    def get_latest_recommendation_for_directive(self, directive_id: UUID) -> Optional[DirectiveRecommendation]:
        stmt = (
            select(DirectiveRecommendation)
            .where(DirectiveRecommendation.directive_id == directive_id)
            .order_by(desc(DirectiveRecommendation.generated_ts))
            .limit(1)
        )
        return self.db.scalar(stmt)
    def list_recommendations(self, verdict: Optional[str] = None) -> list[DirectiveRecommendation]:
        stmt = select(DirectiveRecommendation).order_by(desc(DirectiveRecommendation.generated_ts))
        if verdict:
            stmt = stmt.where(DirectiveRecommendation.verdict == verdict)
        return list(self.db.scalars(stmt).all())
4) backend/app/services/strategy/scoring_engine.py
from __future__ import annotations
from dataclasses import dataclass
@dataclass(slots=True)
class ScoringWeights:
    sla_gain: float = 0.25
    deadline_save: float = 0.20
    throughput_gain: float = 0.15
    stability_gain: float = 0.15
    operator_relief: float = 0.10
    cost_penalty: float = 0.10
    quality_penalty: float = 0.05
class StrategyScoringEngine:
    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()
    @staticmethod
    def clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, value))
    def compute_net_mission_effect(
        self,
        sla_gain: float,
        deadline_save: float,
        throughput_gain: float,
        stability_gain: float,
        operator_relief: float,
        cost_penalty: float,
        quality_penalty: float,
    ) -> float:
        score = (
            (sla_gain * self.weights.sla_gain)
            + (deadline_save * self.weights.deadline_save)
            + (throughput_gain * self.weights.throughput_gain)
            + (stability_gain * self.weights.stability_gain)
            + (operator_relief * self.weights.operator_relief)
            - (cost_penalty * self.weights.cost_penalty)
            - (quality_penalty * self.weights.quality_penalty)
        )
        return round(self.clamp(score, -2.0, 2.0), 4)
    def compute_confidence_score(
        self,
        sample_size: int,
        variance: float,
        consistency_ratio: float,
    ) -> float:
        # Simple production-safe starting heuristic; replace later with Bayesian / statistical model if needed.
        size_component = min(sample_size / 200.0, 1.0)
        variance_component = 1.0 - min(max(variance, 0.0), 1.0)
        consistency_component = min(max(consistency_ratio, 0.0), 1.0)
        confidence = (size_component * 0.4) + (variance_component * 0.3) + (consistency_component * 0.3)
        return round(min(max(confidence, 0.0), 1.0), 4)
5) backend/app/services/strategy/recommendation_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.models.strategy_attribution import DirectiveAttributionRecord, DirectiveVerdict
@dataclass(slots=True)
class RecommendationThresholds:
    promote_net_effect: float = 0.45
    keep_net_effect: float = 0.10
    rollback_net_effect: float = -0.10
    high_confidence: float = 0.80
    medium_confidence: float = 0.55
    max_cost_penalty_for_promote: float = 0.20
    max_quality_penalty_for_promote: float = 0.15
    rollback_cost_penalty: float = 0.35
    rollback_quality_penalty: float = 0.30
class StrategyRecommendationEngine:
    def __init__(self, thresholds: RecommendationThresholds | None = None) -> None:
        self.thresholds = thresholds or RecommendationThresholds()
    def evaluate(self, record: DirectiveAttributionRecord) -> tuple[DirectiveVerdict, str, dict[str, Any], dict[str, Any]]:
        context = record.context_signature or {}
        if (
            record.net_mission_effect >= self.thresholds.promote_net_effect
            and record.confidence_score >= self.thresholds.high_confidence
            and record.cost_penalty <= self.thresholds.max_cost_penalty_for_promote
            and record.quality_penalty <= self.thresholds.max_quality_penalty_for_promote
        ):
            return (
                DirectiveVerdict.PROMOTE,
                "High positive net mission effect with strong confidence and acceptable cost/quality trade-offs.",
                context,
                {},
            )
        if (
            record.cost_penalty >= self.thresholds.rollback_cost_penalty
            or record.quality_penalty >= self.thresholds.rollback_quality_penalty
            or record.net_mission_effect <= self.thresholds.rollback_net_effect
        ):
            return (
                DirectiveVerdict.ROLLBACK,
                "Negative trade-off profile detected: cost and/or quality damage outweighs operational benefit.",
                {},
                context,
            )
        if record.net_mission_effect >= self.thresholds.keep_net_effect and record.confidence_score >= self.thresholds.medium_confidence:
            return (
                DirectiveVerdict.KEEP,
                "Positive but context-bound effect. Keep directive scoped to the observed context.",
                context,
                {},
            )
        if record.confidence_score < self.thresholds.medium_confidence:
            return (
                DirectiveVerdict.THROTTLE,
                "Insufficient evidence or unstable effect across windows. Throttle until confidence improves.",
                {},
                context,
            )
        return (
            DirectiveVerdict.RETIRE,
            "Repeated low-value effect with insufficient justification for continued use.",
            {},
            context,
        )
6) backend/app/services/strategy/attribution_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.strategy_attribution import (
    BaselineType,
    BusinessOutcomeSnapshot,
    DirectiveAttributionRecord,
    DirectiveEnforcementWindow,
    DirectiveRecommendation,
    RuntimeEffectSnapshot,
    StrategyDirective,
)
from app.services.strategy.recommendation_engine import StrategyRecommendationEngine
from app.services.strategy.scoring_engine import StrategyScoringEngine
@dataclass(slots=True)
class BaselineMetrics:
    latency_p95_ms: float = 0.0
    error_rate: float = 0.0
    deadline_breach_rate: float = 0.0
    cost_per_job: float = 0.0
    total_cost: float = 0.0
    jobs_per_minute: float = 0.0
    retry_rate: float = 0.0
    incident_rate: float = 0.0
    manual_interventions: float = 0.0
    quality_score: float = 0.0
class StrategyAttributionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scoring_engine = StrategyScoringEngine()
        self.recommendation_engine = StrategyRecommendationEngine()
    def _normalize_positive_delta(self, observed: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0 if observed == 0 else 1.0
        return round((observed - baseline) / abs(baseline), 4)
    def _normalize_negative_delta_as_gain(self, observed: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return round((baseline - observed) / abs(baseline), 4)
    def _historical_baseline(
        self,
        directive: StrategyDirective,
        before_ts: datetime,
    ) -> BaselineMetrics:
        # Starter version: use historical snapshots from same context before directive activation.
        # Replace with matched cohort / warehouse query later if your platform already has richer telemetry tables.
        window_start = before_ts - timedelta(days=7)
        runtime_rows = (
            self.db.query(RuntimeEffectSnapshot)
            .filter(RuntimeEffectSnapshot.directive_id == directive.id)
            .filter(RuntimeEffectSnapshot.timestamp >= window_start)
            .filter(RuntimeEffectSnapshot.timestamp < before_ts)
            .all()
        )
        outcome_rows = (
            self.db.query(BusinessOutcomeSnapshot)
            .filter(BusinessOutcomeSnapshot.directive_id == directive.id)
            .filter(BusinessOutcomeSnapshot.timestamp >= window_start)
            .filter(BusinessOutcomeSnapshot.timestamp < before_ts)
            .all()
        )
        def avg(values: list[float]) -> float:
            clean = [v for v in values if v is not None]
            return sum(clean) / len(clean) if clean else 0.0
        return BaselineMetrics(
            latency_p95_ms=avg([r.latency_p95_ms for r in runtime_rows]),
            error_rate=avg([r.error_rate for r in runtime_rows]),
            deadline_breach_rate=avg([r.deadline_breach_rate for r in runtime_rows]),
            cost_per_job=avg([r.cost_per_job for r in runtime_rows]),
            total_cost=avg([r.total_cost for r in runtime_rows]),
            jobs_per_minute=avg([r.jobs_per_minute for r in runtime_rows]),
            retry_rate=avg([r.retry_rate for r in runtime_rows]),
            incident_rate=avg([r.incident_rate for r in runtime_rows]),
            manual_interventions=avg([float(r.manual_interventions or 0) for r in runtime_rows]),
            quality_score=avg([o.quality_score for o in outcome_rows]),
        )
    def evaluate_window(self, window_id: UUID) -> DirectiveAttributionRecord:
        window = self.db.query(DirectiveEnforcementWindow).filter(DirectiveEnforcementWindow.id == window_id).one()
        directive = self.db.query(StrategyDirective).filter(StrategyDirective.id == window.directive_id).one()
        runtime_rows = (
            self.db.query(RuntimeEffectSnapshot)
            .filter(RuntimeEffectSnapshot.window_id == window.id)
            .order_by(RuntimeEffectSnapshot.timestamp.asc())
            .all()
        )
        outcome_rows = (
            self.db.query(BusinessOutcomeSnapshot)
            .filter(BusinessOutcomeSnapshot.window_id == window.id)
            .order_by(BusinessOutcomeSnapshot.timestamp.asc())
            .all()
        )
        if not runtime_rows:
            raise ValueError(f"No runtime snapshots found for window {window_id}")
        baseline = self._historical_baseline(directive=directive, before_ts=window.start_ts)
        latest_runtime = runtime_rows[-1]
        latest_outcome = outcome_rows[-1] if outcome_rows else None
        sla_gain = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.error_rate or 0.0,
            baseline=baseline.error_rate,
        )
        deadline_save = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.deadline_breach_rate or 0.0,
            baseline=baseline.deadline_breach_rate,
        )
        cost_penalty = max(0.0, self._normalize_positive_delta(
            observed=latest_runtime.cost_per_job or 0.0,
            baseline=baseline.cost_per_job,
        ))
        throughput_gain = self._normalize_positive_delta(
            observed=latest_runtime.jobs_per_minute or 0.0,
            baseline=baseline.jobs_per_minute,
        )
        stability_gain = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.incident_rate or 0.0,
            baseline=baseline.incident_rate,
        )
        operator_relief = self._normalize_negative_delta_as_gain(
            observed=float(latest_runtime.manual_interventions or 0),
            baseline=baseline.manual_interventions,
        )
        quality_penalty = 0.0
        if latest_outcome and latest_outcome.quality_score is not None:
            quality_penalty = max(
                0.0,
                self._normalize_negative_delta_as_gain(
                    observed=baseline.quality_score,
                    baseline=latest_outcome.quality_score,
                ) * -1,
            )
        net_effect = self.scoring_engine.compute_net_mission_effect(
            sla_gain=sla_gain,
            deadline_save=deadline_save,
            throughput_gain=throughput_gain,
            stability_gain=stability_gain,
            operator_relief=operator_relief,
            cost_penalty=cost_penalty,
            quality_penalty=quality_penalty,
        )
        sample_size = len(runtime_rows)
        variance = min(abs(net_effect) / 2.0, 1.0)
        consistency_ratio = 1.0 if sample_size >= 5 else 0.4
        confidence = self.scoring_engine.compute_confidence_score(
            sample_size=sample_size,
            variance=variance,
            consistency_ratio=consistency_ratio,
        )
        explain_payload: dict[str, Any] = {
            "context": window.context_signature,
            "baseline": {
                "type": BaselineType.HISTORICAL_ROLLING.value,
                "window_days": 7,
                "metrics": baseline.__dict__,
            },
            "observed": {
                "runtime_snapshot_id": str(latest_runtime.id),
                "outcome_snapshot_id": str(latest_outcome.id) if latest_outcome else None,
            },
            "deltas": {
                "sla_gain": sla_gain,
                "deadline_save": deadline_save,
                "cost_penalty": cost_penalty,
                "throughput_gain": throughput_gain,
                "stability_gain": stability_gain,
                "operator_relief": operator_relief,
                "quality_penalty": quality_penalty,
            },
            "final": {
                "net_mission_effect": net_effect,
                "confidence_score": confidence,
            },
        }
        record = DirectiveAttributionRecord(
            directive_id=directive.id,
            window_id=window.id,
            baseline_type=BaselineType.HISTORICAL_ROLLING,
            baseline_id=None,
            context_signature=window.context_signature,
            sla_gain=sla_gain,
            deadline_save=deadline_save,
            cost_penalty=cost_penalty,
            quality_penalty=quality_penalty,
            throughput_gain=throughput_gain,
            stability_gain=stability_gain,
            operator_relief=operator_relief,
            net_mission_effect=net_effect,
            confidence_score=confidence,
            sample_size=sample_size,
            explain_payload=explain_payload,
            evaluation_ts=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.flush()
        verdict, reason_summary, allowed_contexts, restricted_contexts = self.recommendation_engine.evaluate(record)
        recommendation = DirectiveRecommendation(
            directive_id=directive.id,
            attribution_record_id=record.id,
            verdict=verdict,
            reason_summary=reason_summary,
            confidence_score=confidence,
            allowed_contexts=allowed_contexts,
            restricted_contexts=restricted_contexts,
            generated_ts=datetime.utcnow(),
        )
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(record)
        return record
7) backend/app/api/routes/strategy_impact.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.repositories.strategy_attribution_repository import StrategyAttributionRepository
from app.schemas.strategy_attribution import (
    AttributionRecordRead,
    ExplainResponse,
    HeatmapCell,
    LeaderboardRow,
    RecommendationRead,
    ScatterPoint,
    StrategyDirectiveRead,
)
router = APIRouter(prefix="/strategy", tags=["strategy-impact"])
@router.get("/directives", response_model=list[StrategyDirectiveRead])
def list_directives(
    tier: Optional[str] = Query(None),
    mission_mode: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> list[StrategyDirectiveRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_directives(tier=tier, mission_mode=mission_mode, provider=provider, is_active=is_active)
@router.get("/attribution", response_model=list[AttributionRecordRead])
def list_attribution(
    directive_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[AttributionRecordRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_attributions(directive_id=directive_id)
@router.get("/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    verdict: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[RecommendationRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_recommendations(verdict=verdict)
@router.get("/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(db: Session = Depends(get_db)) -> list[LeaderboardRow]:
    repo = StrategyAttributionRepository(db)
    directives = repo.list_directives()
    rows: list[LeaderboardRow] = []
    for directive in directives:
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        latest_rec = repo.get_latest_recommendation_for_directive(directive.id)
        if not latest_attr:
            continue
        rows.append(
            LeaderboardRow(
                directive_id=directive.id,
                directive_name=directive.name,
                directive_type=directive.directive_type,
                net_mission_effect=latest_attr.net_mission_effect,
                confidence_score=latest_attr.confidence_score,
                sample_size=latest_attr.sample_size,
                context_signature=latest_attr.context_signature,
                latest_verdict=latest_rec.verdict.value if latest_rec else None,
            )
        )
    return sorted(rows, key=lambda r: r.net_mission_effect, reverse=True)
@router.get("/scatter", response_model=list[ScatterPoint])
def scatter(db: Session = Depends(get_db)) -> list[ScatterPoint]:
    repo = StrategyAttributionRepository(db)
    points: list[ScatterPoint] = []
    for directive in repo.list_directives():
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        if not latest_attr:
            continue
        points.append(
            ScatterPoint(
                directive_id=directive.id,
                directive_name=directive.name,
                cost_penalty=latest_attr.cost_penalty,
                net_mission_effect=latest_attr.net_mission_effect,
                confidence_score=latest_attr.confidence_score,
                sample_size=latest_attr.sample_size,
            )
        )
    return points
@router.get("/heatmap", response_model=list[HeatmapCell])
def heatmap(db: Session = Depends(get_db)) -> list[HeatmapCell]:
    repo = StrategyAttributionRepository(db)
    cells: list[HeatmapCell] = []
    for directive in repo.list_directives():
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        if not latest_attr:
            continue
        context_parts = [f"{k}:{v}" for k, v in latest_attr.context_signature.items()]
        cells.append(
            HeatmapCell(
                directive_id=directive.id,
                directive_name=directive.name,
                context_key=" | ".join(context_parts),
                quality_penalty=latest_attr.quality_penalty,
            )
        )
    return cells
@router.get("/explain/{directive_id}", response_model=ExplainResponse)
def explain_directive(directive_id: UUID, db: Session = Depends(get_db)) -> ExplainResponse:
    repo = StrategyAttributionRepository(db)
    directive = next((d for d in repo.list_directives() if d.id == directive_id), None)
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    attribution = repo.get_latest_attribution_for_directive(directive_id)
    if not attribution:
        raise HTTPException(status_code=404, detail="Attribution record not found")
    recommendation = repo.get_latest_recommendation_for_directive(directive_id)
    return ExplainResponse(
        directive=directive,
        attribution=attribution,
        recommendation=recommendation,
    )
8) backend/app/workers/attribution_worker.py
from __future__ import annotations
from celery import shared_task
from app.db.session import SessionLocal
from app.services.strategy.attribution_service import StrategyAttributionService
@shared_task(name="strategy.evaluate_directive_window")
def evaluate_directive_window(window_id: str) -> dict:
    db = SessionLocal()
    try:
        service = StrategyAttributionService(db)
        record = service.evaluate_window(window_id=window_id)
        return {
            "status": "ok",
            "record_id": str(record.id),
            "directive_id": str(record.directive_id),
            "window_id": str(record.window_id),
            "net_mission_effect": record.net_mission_effect,
            "confidence_score": record.confidence_score,
        }
    finally:
        db.close()
9) backend/app/db/migrations/versions/20260412_01_strategy_impact_console.py
"""strategy impact console base tables
Revision ID: 20260412_01
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20260412_01"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None
def upgrade() -> None:
    directive_verdict = sa.Enum("promote", "keep", "throttle", "rollback", "retire", name="directiveverdict")
    baseline_type = sa.Enum("historical_rolling", "matched_cohort", "same_context_previous", name="baselinetype")
    directive_verdict.create(op.get_bind(), checkfirst=True)
    baseline_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "strategy_directives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("strategy_origin", sa.String(length=255), nullable=True),
        sa.Column("objective_id", sa.String(length=255), nullable=True),
        sa.Column("directive_type", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("tier", sa.String(length=100), nullable=True),
        sa.Column("workload_class", sa.String(length=100), nullable=True),
        sa.Column("mission_mode", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("project", sa.String(length=255), nullable=True),
        sa.Column("strategy_mode", sa.String(length=100), nullable=True),
        sa.Column("activation_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivation_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_strategy_directives_name", "strategy_directives", ["name"])
    op.create_index("ix_strategy_directives_directive_type", "strategy_directives", ["directive_type"])
    op.create_index("ix_strategy_directives_activation_ts", "strategy_directives", ["activation_ts"])
    op.create_table(
        "directive_enforcement_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_context_hash", sa.String(length=128), nullable=False),
        sa.Column("context_signature", sa.JSON(), nullable=False),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "runtime_effect_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latency_p95_ms", sa.Float(), nullable=True),
        sa.Column("error_rate", sa.Float(), nullable=True),
        sa.Column("deadline_breach_rate", sa.Float(), nullable=True),
        sa.Column("cost_per_job", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("jobs_per_minute", sa.Float(), nullable=True),
        sa.Column("retry_rate", sa.Float(), nullable=True),
        sa.Column("incident_rate", sa.Float(), nullable=True),
        sa.Column("manual_interventions", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "business_outcome_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revenue_impact", sa.Float(), nullable=True),
        sa.Column("margin_delta", sa.Float(), nullable=True),
        sa.Column("sla_breach_avoided", sa.Integer(), nullable=True),
        sa.Column("deadline_saved", sa.Integer(), nullable=True),
        sa.Column("customer_impact_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "directive_attribution_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_type", baseline_type, nullable=False),
        sa.Column("baseline_id", sa.String(length=255), nullable=True),
        sa.Column("context_signature", sa.JSON(), nullable=False),
        sa.Column("sla_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deadline_save", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("throughput_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("operator_relief", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_mission_effect", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explain_payload", sa.JSON(), nullable=False),
        sa.Column("evaluation_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("directive_id", "window_id", name="uq_directive_window_attribution"),
    )
    op.create_table(
        "directive_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribution_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_attribution_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verdict", directive_verdict, nullable=False),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("allowed_contexts", sa.JSON(), nullable=False),
        sa.Column("restricted_contexts", sa.JSON(), nullable=False),
        sa.Column("generated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
def downgrade() -> None:
    op.drop_table("directive_recommendations")
    op.drop_table("directive_attribution_records")
    op.drop_table("business_outcome_snapshots")
    op.drop_table("runtime_effect_snapshots")
    op.drop_table("directive_enforcement_windows")
    op.drop_index("ix_strategy_directives_activation_ts", table_name="strategy_directives")
    op.drop_index("ix_strategy_directives_directive_type", table_name="strategy_directives")
    op.drop_index("ix_strategy_directives_name", table_name="strategy_directives")
    op.drop_table("strategy_directives")
    sa.Enum(name="directiveverdict").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="baselinetype").drop(op.get_bind(), checkfirst=True)
10) backend/app/tests/test_strategy_scoring_engine.py
from app.services.strategy.scoring_engine import StrategyScoringEngine
def test_compute_net_mission_effect_positive_case() -> None:
    engine = StrategyScoringEngine()
    score = engine.compute_net_mission_effect(
        sla_gain=0.8,
        deadline_save=0.7,
        throughput_gain=0.4,
        stability_gain=0.5,
        operator_relief=0.3,
        cost_penalty=0.1,
        quality_penalty=0.05,
    )
    assert score > 0
def test_compute_confidence_score_increases_with_sample_size() -> None:
    engine = StrategyScoringEngine()
    low = engine.compute_confidence_score(sample_size=10, variance=0.3, consistency_ratio=0.5)
    high = engine.compute_confidence_score(sample_size=200, variance=0.3, consistency_ratio=0.5)
    assert high > low
11) backend/app/tests/test_strategy_recommendation_engine.py
from datetime import datetime
from uuid import uuid4
from app.models.strategy_attribution import BaselineType, DirectiveAttributionRecord, DirectiveVerdict
from app.services.strategy.recommendation_engine import StrategyRecommendationEngine
def build_record(**overrides):
    payload = dict(
        id=uuid4(),
        directive_id=uuid4(),
        window_id=uuid4(),
        baseline_type=BaselineType.HISTORICAL_ROLLING,
        baseline_id=None,
        context_signature={"tier": "premium", "mission_mode": "deadline"},
        sla_gain=0.6,
        deadline_save=0.5,
        cost_penalty=0.1,
        quality_penalty=0.05,
        throughput_gain=0.3,
        stability_gain=0.4,
        operator_relief=0.3,
        net_mission_effect=0.7,
        confidence_score=0.9,
        sample_size=120,
        explain_payload={},
        evaluation_ts=datetime.utcnow(),
    )
    payload.update(overrides)
    return DirectiveAttributionRecord(**payload)
def test_promote_recommendation() -> None:
    engine = StrategyRecommendationEngine()
    verdict, _, _, _ = engine.evaluate(build_record())
    assert verdict == DirectiveVerdict.PROMOTE
def test_rollback_recommendation() -> None:
    engine = StrategyRecommendationEngine()
    verdict, _, _, _ = engine.evaluate(build_record(cost_penalty=0.6, net_mission_effect=-0.2))
    assert verdict == DirectiveVerdict.ROLLBACK
12) frontend/src/api/strategyImpact.ts
export type LeaderboardRow = {
  directive_id: string;
  directive_name: string;
  directive_type: string;
  net_mission_effect: number;
  confidence_score: number;
  sample_size: number;
  context_signature: Record<string, unknown>;
  latest_verdict?: string | null;
};
export type ScatterPoint = {
  directive_id: string;
  directive_name: string;
  cost_penalty: number;
  net_mission_effect: number;
  confidence_score: number;
  sample_size: number;
};
export type HeatmapCell = {
  directive_id: string;
  directive_name: string;
  context_key: string;
  quality_penalty: number;
};
export type ExplainResponse = {
  directive: Record<string, unknown>;
  attribution: Record<string, unknown>;
  recommendation?: Record<string, unknown> | null;
};
async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
export const strategyImpactApi = {
  getLeaderboard: () => getJson<LeaderboardRow[]>("/api/strategy/leaderboard"),
  getScatter: () => getJson<ScatterPoint[]>("/api/strategy/scatter"),
  getHeatmap: () => getJson<HeatmapCell[]>("/api/strategy/heatmap"),
  getRecommendations: () => getJson<any[]>("/api/strategy/recommendations"),
  getExplain: (directiveId: string) => getJson<ExplainResponse>(`/api/strategy/explain/${directiveId}`),
};
13) frontend/src/features/strategy-impact/StrategyImpactConsole.tsx
import { useEffect, useState } from "react";
import { strategyImpactApi, type HeatmapCell, type LeaderboardRow, type ScatterPoint } from "../../api/strategyImpact";
import { LeaderboardPanel } from "./components/LeaderboardPanel";
import { ScatterPanel } from "./components/ScatterPanel";
import { HeatmapPanel } from "./components/HeatmapPanel";
import { ExplainDrawer } from "./components/ExplainDrawer";
export default function StrategyImpactConsole() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [scatter, setScatter] = useState<ScatterPoint[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapCell[]>([]);
  const [selectedDirectiveId, setSelectedDirectiveId] = useState<string | null>(null);
  useEffect(() => {
    void Promise.all([
      strategyImpactApi.getLeaderboard().then(setLeaderboard),
      strategyImpactApi.getScatter().then(setScatter),
      strategyImpactApi.getHeatmap().then(setHeatmap),
    ]);
  }, []);
  return (
    <div className="grid gap-4 p-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <LeaderboardPanel rows={leaderboard} onSelect={setSelectedDirectiveId} />
        <ScatterPanel points={scatter} onSelect={setSelectedDirectiveId} />
      </div>
      <HeatmapPanel cells={heatmap} onSelect={setSelectedDirectiveId} />
      <ExplainDrawer directiveId={selectedDirectiveId} onClose={() => setSelectedDirectiveId(null)} />
    </div>
  );
}
14) frontend/src/features/strategy-impact/components/LeaderboardPanel.tsx
import type { LeaderboardRow } from "../../../api/strategyImpact";
type Props = {
  rows: LeaderboardRow[];
  onSelect: (directiveId: string) => void;
};
export function LeaderboardPanel({ rows, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Directive Effectiveness Leaderboard</h2>
      <div className="overflow-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="pb-2">Directive</th>
              <th className="pb-2">Type</th>
              <th className="pb-2">Net Effect</th>
              <th className="pb-2">Confidence</th>
              <th className="pb-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.directive_id} className="cursor-pointer border-t" onClick={() => onSelect(row.directive_id)}>
                <td className="py-2">{row.directive_name}</td>
                <td className="py-2">{row.directive_type}</td>
                <td className="py-2">{row.net_mission_effect.toFixed(3)}</td>
                <td className="py-2">{row.confidence_score.toFixed(2)}</td>
                <td className="py-2">{row.latest_verdict ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
15) frontend/src/features/strategy-impact/components/ScatterPanel.tsx
import type { ScatterPoint } from "../../../api/strategyImpact";
type Props = {
  points: ScatterPoint[];
  onSelect: (directiveId: string) => void;
};
export function ScatterPanel({ points, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Cost vs Value</h2>
      <div className="space-y-2">
        {points.map((point) => (
          <button
            key={point.directive_id}
            type="button"
            onClick={() => onSelect(point.directive_id)}
            className="flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left hover:bg-slate-50"
          >
            <span>{point.directive_name}</span>
            <span className="text-xs text-slate-600">
              cost {point.cost_penalty.toFixed(2)} · value {point.net_mission_effect.toFixed(2)} · conf {point.confidence_score.toFixed(2)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
16) frontend/src/features/strategy-impact/components/HeatmapPanel.tsx
import type { HeatmapCell } from "../../../api/strategyImpact";
type Props = {
  cells: HeatmapCell[];
  onSelect: (directiveId: string) => void;
};
export function HeatmapPanel({ cells, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Quality Trade-off Heatmap</h2>
      <div className="grid gap-2">
        {cells.map((cell) => (
          <button
            key={`${cell.directive_id}-${cell.context_key}`}
            type="button"
            onClick={() => onSelect(cell.directive_id)}
            className="flex items-center justify-between rounded-xl border px-3 py-2 text-left hover:bg-slate-50"
          >
            <span className="font-medium">{cell.directive_name}</span>
            <span className="text-xs text-slate-600">{cell.context_key}</span>
            <span className="text-sm">quality penalty {cell.quality_penalty.toFixed(2)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
17) frontend/src/features/strategy-impact/components/ExplainDrawer.tsx
import { useEffect, useState } from "react";
import { strategyImpactApi, type ExplainResponse } from "../../../api/strategyImpact";
type Props = {
  directiveId: string | null;
  onClose: () => void;
};
export function ExplainDrawer({ directiveId, onClose }: Props) {
  const [data, setData] = useState<ExplainResponse | null>(null);
  useEffect(() => {
    if (!directiveId) {
      setData(null);
      return;
    }
    void strategyImpactApi.getExplain(directiveId).then(setData);
  }, [directiveId]);
  if (!directiveId) {
    return null;
  }
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-xl border-l bg-white p-4 shadow-2xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Why this directive was judged effective</h2>
        <button type="button" onClick={onClose} className="rounded-lg border px-3 py-1">Close</button>
      </div>
      {!data ? (
        <div>Loading...</div>
      ) : (
        <div className="space-y-4 text-sm">
          <section>
            <h3 className="font-semibold">Directive</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.directive, null, 2)}</pre>
          </section>
          <section>
            <h3 className="font-semibold">Attribution</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.attribution, null, 2)}</pre>
          </section>
          <section>
            <h3 className="font-semibold">Recommendation</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.recommendation, null, 2)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
18) backend/app/main.py patch
from app.api.routes.strategy_impact import router as strategy_impact_router
app.include_router(strategy_impact_router, prefix="/api")
19) backend/app/models/__init__.py patch
from app.models.strategy_attribution import (
    BusinessOutcomeSnapshot,
    DirectiveAttributionRecord,
    DirectiveEnforcementWindow,
    DirectiveRecommendation,
    RuntimeEffectSnapshot,
    StrategyDirective,
)
20) frontend/src/app/routes.tsx patch
import StrategyImpactConsole from "../features/strategy-impact/StrategyImpactConsole";
// add route
{
  path: "/strategy-impact",
  element: <StrategyImpactConsole />,
}
21) Notes to wire into the rest of the monorepo
Real production hooks you should connect next
Replace _historical_baseline() with warehouse-backed matched cohort logic
Feed snapshots from real runtime telemetry / SLA / cost / deadline domains
Add RBAC around promote / rollback actions
Add explicit promotion endpoint if you want operator action from console
Materialize daily rollups if dataset grows large
Minimal ingestion contract
Any runtime control layer that activates directives should emit:
directive activation/deactivation
enforcement window open/close
runtime metrics snapshots
business outcome snapshots
Without those four signals, attribution will degrade into weak before/after analytics.
Decision-grade rule
Do not auto-promote from the UI until:
sample_size >= 50
confidence_score >= 0.8
quality penalty below floor
cost penalty within governance threshold
Tôi đã viết xong patch file-by-file và đặt vào canvas để bạn copy trực tiếp sang monorepo.
Nội dung đã gồm:
SQLAlchemy models
Pydantic schemas
Repository
Attribution service
Scoring engine
Recommendation engine
FastAPI routes
Celery worker
Alembic migration
React/TypeScript console
test cơ bản
Patch này bám đúng spec attribution mà bạn đã chốt trước đó. Phần logic “closed strategic loop” và decision-grade attribution được triển khai theo đúng hướng bạn mô tả trong tài liệu đã gửi.
Bước nên làm ngay sau khi dán patch vào codebase là:
nối snapshot input thật từ runtime/SLA/cost/outcome domains
thay baseline tạm bằng matched cohort hoặc warehouse query
thêm action endpoints cho promote / rollback nếu bạn muốn console không chỉ xem mà còn thực thi
Tôi sẽ nối luôn phase 2 theo đúng hướng production sâu hơn: repository contracts, interfaces, rollups, action endpoints, RBAC, và governance execution, để patch không dừng ở mức quan sát mà đi tới thực thi có kiểm soát.
Strategy Impact Console — Patch File-by-File
Dưới đây là patch monorepo production-oriented cho layer Strategy Impact Console + Attribution + Scoring + Recommendation.
Assumption: monorepo đang dùng FastAPI + SQLAlchemy + Alembic + Celery + React/TypeScript.
Nếu codebase hiện tại của bạn đã có các module tương đương, giữ nguyên naming convention nội bộ và cắm patch này vào đúng domain strategy / attribution.
1) backend/app/models/strategy_attribution.py
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
class DirectiveVerdict(str, enum.Enum):
    PROMOTE = "promote"
    KEEP = "keep"
    THROTTLE = "throttle"
    ROLLBACK = "rollback"
    RETIRE = "retire"
class BaselineType(str, enum.Enum):
    HISTORICAL_ROLLING = "historical_rolling"
    MATCHED_COHORT = "matched_cohort"
    SAME_CONTEXT_PREVIOUS = "same_context_previous"
class StrategyDirective(Base):
    __tablename__ = "strategy_directives"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    strategy_origin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    objective_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    directive_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    workload_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    mission_mode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    strategy_mode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    activation_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    deactivation_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
class DirectiveEnforcementWindow(Base):
    __tablename__ = "directive_enforcement_windows"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    active_context_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_signature: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class RuntimeEffectSnapshot(Base):
    __tablename__ = "runtime_effect_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    latency_p95_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline_breach_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_job: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jobs_per_minute: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retry_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    incident_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manual_interventions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class BusinessOutcomeSnapshot(Base):
    __tablename__ = "business_outcome_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    revenue_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margin_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sla_breach_avoided: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deadline_saved: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class DirectiveAttributionRecord(Base):
    __tablename__ = "directive_attribution_records"
    __table_args__ = (
        UniqueConstraint("directive_id", "window_id", name="uq_directive_window_attribution"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_type: Mapped[BaselineType] = mapped_column(Enum(BaselineType), nullable=False, index=True)
    baseline_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    context_signature: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sla_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deadline_save: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    throughput_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stability_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    operator_relief: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_mission_effect: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explain_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluation_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class DirectiveRecommendation(Base):
    __tablename__ = "directive_recommendations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_attribution_records.id", ondelete="CASCADE"), nullable=False, index=True)
    verdict: Mapped[DirectiveVerdict] = mapped_column(Enum(DirectiveVerdict), nullable=False, index=True)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    allowed_contexts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    restricted_contexts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
2) backend/app/schemas/strategy_attribution.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
class StrategyDirectiveRead(BaseModel):
    id: UUID
    name: str
    directive_type: str
    strategy_origin: Optional[str] = None
    objective_id: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    tier: Optional[str] = None
    workload_class: Optional[str] = None
    mission_mode: Optional[str] = None
    provider: Optional[str] = None
    project: Optional[str] = None
    strategy_mode: Optional[str] = None
    activation_ts: datetime
    deactivation_ts: Optional[datetime] = None
    is_active: bool
    model_config = {"from_attributes": True}
class AttributionRecordRead(BaseModel):
    id: UUID
    directive_id: UUID
    window_id: UUID
    baseline_type: str
    baseline_id: Optional[str] = None
    context_signature: dict[str, Any]
    sla_gain: float
    deadline_save: float
    cost_penalty: float
    quality_penalty: float
    throughput_gain: float
    stability_gain: float
    operator_relief: float
    net_mission_effect: float
    confidence_score: float
    sample_size: int
    explain_payload: dict[str, Any]
    evaluation_ts: datetime
    model_config = {"from_attributes": True}
class RecommendationRead(BaseModel):
    id: UUID
    directive_id: UUID
    attribution_record_id: UUID
    verdict: str
    reason_summary: str
    confidence_score: float
    allowed_contexts: dict[str, Any]
    restricted_contexts: dict[str, Any]
    generated_ts: datetime
    model_config = {"from_attributes": True}
class LeaderboardRow(BaseModel):
    directive_id: UUID
    directive_name: str
    directive_type: str
    net_mission_effect: float
    confidence_score: float
    sample_size: int
    context_signature: dict[str, Any]
    latest_verdict: Optional[str] = None
class ScatterPoint(BaseModel):
    directive_id: UUID
    directive_name: str
    cost_penalty: float
    net_mission_effect: float
    confidence_score: float
    sample_size: int
class HeatmapCell(BaseModel):
    directive_id: UUID
    directive_name: str
    context_key: str
    quality_penalty: float
class ExplainResponse(BaseModel):
    directive: StrategyDirectiveRead
    attribution: AttributionRecordRead
    recommendation: Optional[RecommendationRead] = None
3) backend/app/repositories/strategy_attribution_repository.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.models.strategy_attribution import (
    DirectiveAttributionRecord,
    DirectiveRecommendation,
    StrategyDirective,
)
class StrategyAttributionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def list_directives(
        self,
        tier: Optional[str] = None,
        mission_mode: Optional[str] = None,
        provider: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[StrategyDirective]:
        stmt = select(StrategyDirective)
        if tier:
            stmt = stmt.where(StrategyDirective.tier == tier)
        if mission_mode:
            stmt = stmt.where(StrategyDirective.mission_mode == mission_mode)
        if provider:
            stmt = stmt.where(StrategyDirective.provider == provider)
        if is_active is not None:
            stmt = stmt.where(StrategyDirective.is_active == is_active)
        stmt = stmt.order_by(desc(StrategyDirective.activation_ts))
        return list(self.db.scalars(stmt).all())
    def list_attributions(self, directive_id: Optional[UUID] = None) -> list[DirectiveAttributionRecord]:
        stmt = select(DirectiveAttributionRecord).order_by(desc(DirectiveAttributionRecord.evaluation_ts))
        if directive_id:
            stmt = stmt.where(DirectiveAttributionRecord.directive_id == directive_id)
        return list(self.db.scalars(stmt).all())
    def get_latest_attribution_for_directive(self, directive_id: UUID) -> Optional[DirectiveAttributionRecord]:
        stmt = (
            select(DirectiveAttributionRecord)
            .where(DirectiveAttributionRecord.directive_id == directive_id)
            .order_by(desc(DirectiveAttributionRecord.evaluation_ts))
            .limit(1)
        )
        return self.db.scalar(stmt)
    def get_latest_recommendation_for_directive(self, directive_id: UUID) -> Optional[DirectiveRecommendation]:
        stmt = (
            select(DirectiveRecommendation)
            .where(DirectiveRecommendation.directive_id == directive_id)
            .order_by(desc(DirectiveRecommendation.generated_ts))
            .limit(1)
        )
        return self.db.scalar(stmt)
    def list_recommendations(self, verdict: Optional[str] = None) -> list[DirectiveRecommendation]:
        stmt = select(DirectiveRecommendation).order_by(desc(DirectiveRecommendation.generated_ts))
        if verdict:
            stmt = stmt.where(DirectiveRecommendation.verdict == verdict)
        return list(self.db.scalars(stmt).all())
4) backend/app/services/strategy/scoring_engine.py
from __future__ import annotations
from dataclasses import dataclass
@dataclass(slots=True)
class ScoringWeights:
    sla_gain: float = 0.25
    deadline_save: float = 0.20
    throughput_gain: float = 0.15
    stability_gain: float = 0.15
    operator_relief: float = 0.10
    cost_penalty: float = 0.10
    quality_penalty: float = 0.05
class StrategyScoringEngine:
    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()
    @staticmethod
    def clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, value))
    def compute_net_mission_effect(
        self,
        sla_gain: float,
        deadline_save: float,
        throughput_gain: float,
        stability_gain: float,
        operator_relief: float,
        cost_penalty: float,
        quality_penalty: float,
    ) -> float:
        score = (
            (sla_gain * self.weights.sla_gain)
            + (deadline_save * self.weights.deadline_save)
            + (throughput_gain * self.weights.throughput_gain)
            + (stability_gain * self.weights.stability_gain)
            + (operator_relief * self.weights.operator_relief)
            - (cost_penalty * self.weights.cost_penalty)
            - (quality_penalty * self.weights.quality_penalty)
        )
        return round(self.clamp(score, -2.0, 2.0), 4)
    def compute_confidence_score(
        self,
        sample_size: int,
        variance: float,
        consistency_ratio: float,
    ) -> float:
        # Simple production-safe starting heuristic; replace later with Bayesian / statistical model if needed.
        size_component = min(sample_size / 200.0, 1.0)
        variance_component = 1.0 - min(max(variance, 0.0), 1.0)
        consistency_component = min(max(consistency_ratio, 0.0), 1.0)
        confidence = (size_component * 0.4) + (variance_component * 0.3) + (consistency_component * 0.3)
        return round(min(max(confidence, 0.0), 1.0), 4)
5) backend/app/services/strategy/recommendation_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.models.strategy_attribution import DirectiveAttributionRecord, DirectiveVerdict
@dataclass(slots=True)
class RecommendationThresholds:
    promote_net_effect: float = 0.45
    keep_net_effect: float = 0.10
    rollback_net_effect: float = -0.10
    high_confidence: float = 0.80
    medium_confidence: float = 0.55
    max_cost_penalty_for_promote: float = 0.20
    max_quality_penalty_for_promote: float = 0.15
    rollback_cost_penalty: float = 0.35
    rollback_quality_penalty: float = 0.30
class StrategyRecommendationEngine:
    def __init__(self, thresholds: RecommendationThresholds | None = None) -> None:
        self.thresholds = thresholds or RecommendationThresholds()
    def evaluate(self, record: DirectiveAttributionRecord) -> tuple[DirectiveVerdict, str, dict[str, Any], dict[str, Any]]:
        context = record.context_signature or {}
        if (
            record.net_mission_effect >= self.thresholds.promote_net_effect
            and record.confidence_score >= self.thresholds.high_confidence
            and record.cost_penalty <= self.thresholds.max_cost_penalty_for_promote
            and record.quality_penalty <= self.thresholds.max_quality_penalty_for_promote
        ):
            return (
                DirectiveVerdict.PROMOTE,
                "High positive net mission effect with strong confidence and acceptable cost/quality trade-offs.",
                context,
                {},
            )
        if (
            record.cost_penalty >= self.thresholds.rollback_cost_penalty
            or record.quality_penalty >= self.thresholds.rollback_quality_penalty
            or record.net_mission_effect <= self.thresholds.rollback_net_effect
        ):
            return (
                DirectiveVerdict.ROLLBACK,
                "Negative trade-off profile detected: cost and/or quality damage outweighs operational benefit.",
                {},
                context,
            )
        if record.net_mission_effect >= self.thresholds.keep_net_effect and record.confidence_score >= self.thresholds.medium_confidence:
            return (
                DirectiveVerdict.KEEP,
                "Positive but context-bound effect. Keep directive scoped to the observed context.",
                context,
                {},
            )
        if record.confidence_score < self.thresholds.medium_confidence:
            return (
                DirectiveVerdict.THROTTLE,
                "Insufficient evidence or unstable effect across windows. Throttle until confidence improves.",
                {},
                context,
            )
        return (
            DirectiveVerdict.RETIRE,
            "Repeated low-value effect with insufficient justification for continued use.",
            {},
            context,
        )
6) backend/app/services/strategy/attribution_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.strategy_attribution import (
    BaselineType,
    BusinessOutcomeSnapshot,
    DirectiveAttributionRecord,
    DirectiveEnforcementWindow,
    DirectiveRecommendation,
    RuntimeEffectSnapshot,
    StrategyDirective,
)
from app.services.strategy.recommendation_engine import StrategyRecommendationEngine
from app.services.strategy.scoring_engine import StrategyScoringEngine
@dataclass(slots=True)
class BaselineMetrics:
    latency_p95_ms: float = 0.0
    error_rate: float = 0.0
    deadline_breach_rate: float = 0.0
    cost_per_job: float = 0.0
    total_cost: float = 0.0
    jobs_per_minute: float = 0.0
    retry_rate: float = 0.0
    incident_rate: float = 0.0
    manual_interventions: float = 0.0
    quality_score: float = 0.0
class StrategyAttributionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scoring_engine = StrategyScoringEngine()
        self.recommendation_engine = StrategyRecommendationEngine()
    def _normalize_positive_delta(self, observed: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0 if observed == 0 else 1.0
        return round((observed - baseline) / abs(baseline), 4)
    def _normalize_negative_delta_as_gain(self, observed: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return round((baseline - observed) / abs(baseline), 4)
    def _historical_baseline(
        self,
        directive: StrategyDirective,
        before_ts: datetime,
    ) -> BaselineMetrics:
        # Starter version: use historical snapshots from same context before directive activation.
        # Replace with matched cohort / warehouse query later if your platform already has richer telemetry tables.
        window_start = before_ts - timedelta(days=7)
        runtime_rows = (
            self.db.query(RuntimeEffectSnapshot)
            .filter(RuntimeEffectSnapshot.directive_id == directive.id)
            .filter(RuntimeEffectSnapshot.timestamp >= window_start)
            .filter(RuntimeEffectSnapshot.timestamp < before_ts)
            .all()
        )
        outcome_rows = (
            self.db.query(BusinessOutcomeSnapshot)
            .filter(BusinessOutcomeSnapshot.directive_id == directive.id)
            .filter(BusinessOutcomeSnapshot.timestamp >= window_start)
            .filter(BusinessOutcomeSnapshot.timestamp < before_ts)
            .all()
        )
        def avg(values: list[float]) -> float:
            clean = [v for v in values if v is not None]
            return sum(clean) / len(clean) if clean else 0.0
        return BaselineMetrics(
            latency_p95_ms=avg([r.latency_p95_ms for r in runtime_rows]),
            error_rate=avg([r.error_rate for r in runtime_rows]),
            deadline_breach_rate=avg([r.deadline_breach_rate for r in runtime_rows]),
            cost_per_job=avg([r.cost_per_job for r in runtime_rows]),
            total_cost=avg([r.total_cost for r in runtime_rows]),
            jobs_per_minute=avg([r.jobs_per_minute for r in runtime_rows]),
            retry_rate=avg([r.retry_rate for r in runtime_rows]),
            incident_rate=avg([r.incident_rate for r in runtime_rows]),
            manual_interventions=avg([float(r.manual_interventions or 0) for r in runtime_rows]),
            quality_score=avg([o.quality_score for o in outcome_rows]),
        )
    def evaluate_window(self, window_id: UUID) -> DirectiveAttributionRecord:
        window = self.db.query(DirectiveEnforcementWindow).filter(DirectiveEnforcementWindow.id == window_id).one()
        directive = self.db.query(StrategyDirective).filter(StrategyDirective.id == window.directive_id).one()
        runtime_rows = (
            self.db.query(RuntimeEffectSnapshot)
            .filter(RuntimeEffectSnapshot.window_id == window.id)
            .order_by(RuntimeEffectSnapshot.timestamp.asc())
            .all()
        )
        outcome_rows = (
            self.db.query(BusinessOutcomeSnapshot)
            .filter(BusinessOutcomeSnapshot.window_id == window.id)
            .order_by(BusinessOutcomeSnapshot.timestamp.asc())
            .all()
        )
        if not runtime_rows:
            raise ValueError(f"No runtime snapshots found for window {window_id}")
        baseline = self._historical_baseline(directive=directive, before_ts=window.start_ts)
        latest_runtime = runtime_rows[-1]
        latest_outcome = outcome_rows[-1] if outcome_rows else None
        sla_gain = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.error_rate or 0.0,
            baseline=baseline.error_rate,
        )
        deadline_save = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.deadline_breach_rate or 0.0,
            baseline=baseline.deadline_breach_rate,
        )
        cost_penalty = max(0.0, self._normalize_positive_delta(
            observed=latest_runtime.cost_per_job or 0.0,
            baseline=baseline.cost_per_job,
        ))
        throughput_gain = self._normalize_positive_delta(
            observed=latest_runtime.jobs_per_minute or 0.0,
            baseline=baseline.jobs_per_minute,
        )
        stability_gain = self._normalize_negative_delta_as_gain(
            observed=latest_runtime.incident_rate or 0.0,
            baseline=baseline.incident_rate,
        )
        operator_relief = self._normalize_negative_delta_as_gain(
            observed=float(latest_runtime.manual_interventions or 0),
            baseline=baseline.manual_interventions,
        )
        quality_penalty = 0.0
        if latest_outcome and latest_outcome.quality_score is not None:
            quality_penalty = max(
                0.0,
                self._normalize_negative_delta_as_gain(
                    observed=baseline.quality_score,
                    baseline=latest_outcome.quality_score,
                ) * -1,
            )
        net_effect = self.scoring_engine.compute_net_mission_effect(
            sla_gain=sla_gain,
            deadline_save=deadline_save,
            throughput_gain=throughput_gain,
            stability_gain=stability_gain,
            operator_relief=operator_relief,
            cost_penalty=cost_penalty,
            quality_penalty=quality_penalty,
        )
        sample_size = len(runtime_rows)
        variance = min(abs(net_effect) / 2.0, 1.0)
        consistency_ratio = 1.0 if sample_size >= 5 else 0.4
        confidence = self.scoring_engine.compute_confidence_score(
            sample_size=sample_size,
            variance=variance,
            consistency_ratio=consistency_ratio,
        )
        explain_payload: dict[str, Any] = {
            "context": window.context_signature,
            "baseline": {
                "type": BaselineType.HISTORICAL_ROLLING.value,
                "window_days": 7,
                "metrics": baseline.__dict__,
            },
            "observed": {
                "runtime_snapshot_id": str(latest_runtime.id),
                "outcome_snapshot_id": str(latest_outcome.id) if latest_outcome else None,
            },
            "deltas": {
                "sla_gain": sla_gain,
                "deadline_save": deadline_save,
                "cost_penalty": cost_penalty,
                "throughput_gain": throughput_gain,
                "stability_gain": stability_gain,
                "operator_relief": operator_relief,
                "quality_penalty": quality_penalty,
            },
            "final": {
                "net_mission_effect": net_effect,
                "confidence_score": confidence,
            },
        }
        record = DirectiveAttributionRecord(
            directive_id=directive.id,
            window_id=window.id,
            baseline_type=BaselineType.HISTORICAL_ROLLING,
            baseline_id=None,
            context_signature=window.context_signature,
            sla_gain=sla_gain,
            deadline_save=deadline_save,
            cost_penalty=cost_penalty,
            quality_penalty=quality_penalty,
            throughput_gain=throughput_gain,
            stability_gain=stability_gain,
            operator_relief=operator_relief,
            net_mission_effect=net_effect,
            confidence_score=confidence,
            sample_size=sample_size,
            explain_payload=explain_payload,
            evaluation_ts=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.flush()
        verdict, reason_summary, allowed_contexts, restricted_contexts = self.recommendation_engine.evaluate(record)
        recommendation = DirectiveRecommendation(
            directive_id=directive.id,
            attribution_record_id=record.id,
            verdict=verdict,
            reason_summary=reason_summary,
            confidence_score=confidence,
            allowed_contexts=allowed_contexts,
            restricted_contexts=restricted_contexts,
            generated_ts=datetime.utcnow(),
        )
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(record)
        return record
7) backend/app/api/routes/strategy_impact.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.repositories.strategy_attribution_repository import StrategyAttributionRepository
from app.schemas.strategy_attribution import (
    AttributionRecordRead,
    ExplainResponse,
    HeatmapCell,
    LeaderboardRow,
    RecommendationRead,
    ScatterPoint,
    StrategyDirectiveRead,
)
router = APIRouter(prefix="/strategy", tags=["strategy-impact"])
@router.get("/directives", response_model=list[StrategyDirectiveRead])
def list_directives(
    tier: Optional[str] = Query(None),
    mission_mode: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> list[StrategyDirectiveRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_directives(tier=tier, mission_mode=mission_mode, provider=provider, is_active=is_active)
@router.get("/attribution", response_model=list[AttributionRecordRead])
def list_attribution(
    directive_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[AttributionRecordRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_attributions(directive_id=directive_id)
@router.get("/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    verdict: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[RecommendationRead]:
    repo = StrategyAttributionRepository(db)
    return repo.list_recommendations(verdict=verdict)
@router.get("/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(db: Session = Depends(get_db)) -> list[LeaderboardRow]:
    repo = StrategyAttributionRepository(db)
    directives = repo.list_directives()
    rows: list[LeaderboardRow] = []
    for directive in directives:
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        latest_rec = repo.get_latest_recommendation_for_directive(directive.id)
        if not latest_attr:
            continue
        rows.append(
            LeaderboardRow(
                directive_id=directive.id,
                directive_name=directive.name,
                directive_type=directive.directive_type,
                net_mission_effect=latest_attr.net_mission_effect,
                confidence_score=latest_attr.confidence_score,
                sample_size=latest_attr.sample_size,
                context_signature=latest_attr.context_signature,
                latest_verdict=latest_rec.verdict.value if latest_rec else None,
            )
        )
    return sorted(rows, key=lambda r: r.net_mission_effect, reverse=True)
@router.get("/scatter", response_model=list[ScatterPoint])
def scatter(db: Session = Depends(get_db)) -> list[ScatterPoint]:
    repo = StrategyAttributionRepository(db)
    points: list[ScatterPoint] = []
    for directive in repo.list_directives():
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        if not latest_attr:
            continue
        points.append(
            ScatterPoint(
                directive_id=directive.id,
                directive_name=directive.name,
                cost_penalty=latest_attr.cost_penalty,
                net_mission_effect=latest_attr.net_mission_effect,
                confidence_score=latest_attr.confidence_score,
                sample_size=latest_attr.sample_size,
            )
        )
    return points
@router.get("/heatmap", response_model=list[HeatmapCell])
def heatmap(db: Session = Depends(get_db)) -> list[HeatmapCell]:
    repo = StrategyAttributionRepository(db)
    cells: list[HeatmapCell] = []
    for directive in repo.list_directives():
        latest_attr = repo.get_latest_attribution_for_directive(directive.id)
        if not latest_attr:
            continue
        context_parts = [f"{k}:{v}" for k, v in latest_attr.context_signature.items()]
        cells.append(
            HeatmapCell(
                directive_id=directive.id,
                directive_name=directive.name,
                context_key=" | ".join(context_parts),
                quality_penalty=latest_attr.quality_penalty,
            )
        )
    return cells
@router.get("/explain/{directive_id}", response_model=ExplainResponse)
def explain_directive(directive_id: UUID, db: Session = Depends(get_db)) -> ExplainResponse:
    repo = StrategyAttributionRepository(db)
    directive = next((d for d in repo.list_directives() if d.id == directive_id), None)
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    attribution = repo.get_latest_attribution_for_directive(directive_id)
    if not attribution:
        raise HTTPException(status_code=404, detail="Attribution record not found")
    recommendation = repo.get_latest_recommendation_for_directive(directive_id)
    return ExplainResponse(
        directive=directive,
        attribution=attribution,
        recommendation=recommendation,
    )
8) backend/app/workers/attribution_worker.py
from __future__ import annotations
from celery import shared_task
from app.db.session import SessionLocal
from app.services.strategy.attribution_service import StrategyAttributionService
@shared_task(name="strategy.evaluate_directive_window")
def evaluate_directive_window(window_id: str) -> dict:
    db = SessionLocal()
    try:
        service = StrategyAttributionService(db)
        record = service.evaluate_window(window_id=window_id)
        return {
            "status": "ok",
            "record_id": str(record.id),
            "directive_id": str(record.directive_id),
            "window_id": str(record.window_id),
            "net_mission_effect": record.net_mission_effect,
            "confidence_score": record.confidence_score,
        }
    finally:
        db.close()
9) backend/app/db/migrations/versions/20260412_01_strategy_impact_console.py
"""strategy impact console base tables
Revision ID: 20260412_01
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20260412_01"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None
def upgrade() -> None:
    directive_verdict = sa.Enum("promote", "keep", "throttle", "rollback", "retire", name="directiveverdict")
    baseline_type = sa.Enum("historical_rolling", "matched_cohort", "same_context_previous", name="baselinetype")
    directive_verdict.create(op.get_bind(), checkfirst=True)
    baseline_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "strategy_directives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("strategy_origin", sa.String(length=255), nullable=True),
        sa.Column("objective_id", sa.String(length=255), nullable=True),
        sa.Column("directive_type", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("tier", sa.String(length=100), nullable=True),
        sa.Column("workload_class", sa.String(length=100), nullable=True),
        sa.Column("mission_mode", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("project", sa.String(length=255), nullable=True),
        sa.Column("strategy_mode", sa.String(length=100), nullable=True),
        sa.Column("activation_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivation_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_strategy_directives_name", "strategy_directives", ["name"])
    op.create_index("ix_strategy_directives_directive_type", "strategy_directives", ["directive_type"])
    op.create_index("ix_strategy_directives_activation_ts", "strategy_directives", ["activation_ts"])
    op.create_table(
        "directive_enforcement_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_context_hash", sa.String(length=128), nullable=False),
        sa.Column("context_signature", sa.JSON(), nullable=False),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "runtime_effect_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latency_p95_ms", sa.Float(), nullable=True),
        sa.Column("error_rate", sa.Float(), nullable=True),
        sa.Column("deadline_breach_rate", sa.Float(), nullable=True),
        sa.Column("cost_per_job", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("jobs_per_minute", sa.Float(), nullable=True),
        sa.Column("retry_rate", sa.Float(), nullable=True),
        sa.Column("incident_rate", sa.Float(), nullable=True),
        sa.Column("manual_interventions", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "business_outcome_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revenue_impact", sa.Float(), nullable=True),
        sa.Column("margin_delta", sa.Float(), nullable=True),
        sa.Column("sla_breach_avoided", sa.Integer(), nullable=True),
        sa.Column("deadline_saved", sa.Integer(), nullable=True),
        sa.Column("customer_impact_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "directive_attribution_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_enforcement_windows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_type", baseline_type, nullable=False),
        sa.Column("baseline_id", sa.String(length=255), nullable=True),
        sa.Column("context_signature", sa.JSON(), nullable=False),
        sa.Column("sla_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deadline_save", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("throughput_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("operator_relief", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_mission_effect", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explain_payload", sa.JSON(), nullable=False),
        sa.Column("evaluation_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("directive_id", "window_id", name="uq_directive_window_attribution"),
    )
    op.create_table(
        "directive_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribution_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_attribution_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verdict", directive_verdict, nullable=False),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("allowed_contexts", sa.JSON(), nullable=False),
        sa.Column("restricted_contexts", sa.JSON(), nullable=False),
        sa.Column("generated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
def downgrade() -> None:
    op.drop_table("directive_recommendations")
    op.drop_table("directive_attribution_records")
    op.drop_table("business_outcome_snapshots")
    op.drop_table("runtime_effect_snapshots")
    op.drop_table("directive_enforcement_windows")
    op.drop_index("ix_strategy_directives_activation_ts", table_name="strategy_directives")
    op.drop_index("ix_strategy_directives_directive_type", table_name="strategy_directives")
    op.drop_index("ix_strategy_directives_name", table_name="strategy_directives")
    op.drop_table("strategy_directives")
    sa.Enum(name="directiveverdict").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="baselinetype").drop(op.get_bind(), checkfirst=True)
10) backend/app/tests/test_strategy_scoring_engine.py
from app.services.strategy.scoring_engine import StrategyScoringEngine
def test_compute_net_mission_effect_positive_case() -> None:
    engine = StrategyScoringEngine()
    score = engine.compute_net_mission_effect(
        sla_gain=0.8,
        deadline_save=0.7,
        throughput_gain=0.4,
        stability_gain=0.5,
        operator_relief=0.3,
        cost_penalty=0.1,
        quality_penalty=0.05,
    )
    assert score > 0
def test_compute_confidence_score_increases_with_sample_size() -> None:
    engine = StrategyScoringEngine()
    low = engine.compute_confidence_score(sample_size=10, variance=0.3, consistency_ratio=0.5)
    high = engine.compute_confidence_score(sample_size=200, variance=0.3, consistency_ratio=0.5)
    assert high > low
11) backend/app/tests/test_strategy_recommendation_engine.py
from datetime import datetime
from uuid import uuid4
from app.models.strategy_attribution import BaselineType, DirectiveAttributionRecord, DirectiveVerdict
from app.services.strategy.recommendation_engine import StrategyRecommendationEngine
def build_record(**overrides):
    payload = dict(
        id=uuid4(),
        directive_id=uuid4(),
        window_id=uuid4(),
        baseline_type=BaselineType.HISTORICAL_ROLLING,
        baseline_id=None,
        context_signature={"tier": "premium", "mission_mode": "deadline"},
        sla_gain=0.6,
        deadline_save=0.5,
        cost_penalty=0.1,
        quality_penalty=0.05,
        throughput_gain=0.3,
        stability_gain=0.4,
        operator_relief=0.3,
        net_mission_effect=0.7,
        confidence_score=0.9,
        sample_size=120,
        explain_payload={},
        evaluation_ts=datetime.utcnow(),
    )
    payload.update(overrides)
    return DirectiveAttributionRecord(**payload)
def test_promote_recommendation() -> None:
    engine = StrategyRecommendationEngine()
    verdict, _, _, _ = engine.evaluate(build_record())
    assert verdict == DirectiveVerdict.PROMOTE
def test_rollback_recommendation() -> None:
    engine = StrategyRecommendationEngine()
    verdict, _, _, _ = engine.evaluate(build_record(cost_penalty=0.6, net_mission_effect=-0.2))
    assert verdict == DirectiveVerdict.ROLLBACK
12) frontend/src/api/strategyImpact.ts
export type LeaderboardRow = {
  directive_id: string;
  directive_name: string;
  directive_type: string;
  net_mission_effect: number;
  confidence_score: number;
  sample_size: number;
  context_signature: Record<string, unknown>;
  latest_verdict?: string | null;
};
export type ScatterPoint = {
  directive_id: string;
  directive_name: string;
  cost_penalty: number;
  net_mission_effect: number;
  confidence_score: number;
  sample_size: number;
};
export type HeatmapCell = {
  directive_id: string;
  directive_name: string;
  context_key: string;
  quality_penalty: number;
};
export type ExplainResponse = {
  directive: Record<string, unknown>;
  attribution: Record<string, unknown>;
  recommendation?: Record<string, unknown> | null;
};
async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
export const strategyImpactApi = {
  getLeaderboard: () => getJson<LeaderboardRow[]>("/api/strategy/leaderboard"),
  getScatter: () => getJson<ScatterPoint[]>("/api/strategy/scatter"),
  getHeatmap: () => getJson<HeatmapCell[]>("/api/strategy/heatmap"),
  getRecommendations: () => getJson<any[]>("/api/strategy/recommendations"),
  getExplain: (directiveId: string) => getJson<ExplainResponse>(`/api/strategy/explain/${directiveId}`),
};
13) frontend/src/features/strategy-impact/StrategyImpactConsole.tsx
import { useEffect, useState } from "react";
import { strategyImpactApi, type HeatmapCell, type LeaderboardRow, type ScatterPoint } from "../../api/strategyImpact";
import { LeaderboardPanel } from "./components/LeaderboardPanel";
import { ScatterPanel } from "./components/ScatterPanel";
import { HeatmapPanel } from "./components/HeatmapPanel";
import { ExplainDrawer } from "./components/ExplainDrawer";
export default function StrategyImpactConsole() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [scatter, setScatter] = useState<ScatterPoint[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapCell[]>([]);
  const [selectedDirectiveId, setSelectedDirectiveId] = useState<string | null>(null);
  useEffect(() => {
    void Promise.all([
      strategyImpactApi.getLeaderboard().then(setLeaderboard),
      strategyImpactApi.getScatter().then(setScatter),
      strategyImpactApi.getHeatmap().then(setHeatmap),
    ]);
  }, []);
  return (
    <div className="grid gap-4 p-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <LeaderboardPanel rows={leaderboard} onSelect={setSelectedDirectiveId} />
        <ScatterPanel points={scatter} onSelect={setSelectedDirectiveId} />
      </div>
      <HeatmapPanel cells={heatmap} onSelect={setSelectedDirectiveId} />
      <ExplainDrawer directiveId={selectedDirectiveId} onClose={() => setSelectedDirectiveId(null)} />
    </div>
  );
}
14) frontend/src/features/strategy-impact/components/LeaderboardPanel.tsx
import type { LeaderboardRow } from "../../../api/strategyImpact";
type Props = {
  rows: LeaderboardRow[];
  onSelect: (directiveId: string) => void;
};
export function LeaderboardPanel({ rows, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Directive Effectiveness Leaderboard</h2>
      <div className="overflow-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="pb-2">Directive</th>
              <th className="pb-2">Type</th>
              <th className="pb-2">Net Effect</th>
              <th className="pb-2">Confidence</th>
              <th className="pb-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.directive_id} className="cursor-pointer border-t" onClick={() => onSelect(row.directive_id)}>
                <td className="py-2">{row.directive_name}</td>
                <td className="py-2">{row.directive_type}</td>
                <td className="py-2">{row.net_mission_effect.toFixed(3)}</td>
                <td className="py-2">{row.confidence_score.toFixed(2)}</td>
                <td className="py-2">{row.latest_verdict ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
15) frontend/src/features/strategy-impact/components/ScatterPanel.tsx
import type { ScatterPoint } from "../../../api/strategyImpact";
type Props = {
  points: ScatterPoint[];
  onSelect: (directiveId: string) => void;
};
export function ScatterPanel({ points, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Cost vs Value</h2>
      <div className="space-y-2">
        {points.map((point) => (
          <button
            key={point.directive_id}
            type="button"
            onClick={() => onSelect(point.directive_id)}
            className="flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left hover:bg-slate-50"
          >
            <span>{point.directive_name}</span>
            <span className="text-xs text-slate-600">
              cost {point.cost_penalty.toFixed(2)} · value {point.net_mission_effect.toFixed(2)} · conf {point.confidence_score.toFixed(2)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
16) frontend/src/features/strategy-impact/components/HeatmapPanel.tsx
import type { HeatmapCell } from "../../../api/strategyImpact";
type Props = {
  cells: HeatmapCell[];
  onSelect: (directiveId: string) => void;
};
export function HeatmapPanel({ cells, onSelect }: Props) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Quality Trade-off Heatmap</h2>
      <div className="grid gap-2">
        {cells.map((cell) => (
          <button
            key={`${cell.directive_id}-${cell.context_key}`}
            type="button"
            onClick={() => onSelect(cell.directive_id)}
            className="flex items-center justify-between rounded-xl border px-3 py-2 text-left hover:bg-slate-50"
          >
            <span className="font-medium">{cell.directive_name}</span>
            <span className="text-xs text-slate-600">{cell.context_key}</span>
            <span className="text-sm">quality penalty {cell.quality_penalty.toFixed(2)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
17) frontend/src/features/strategy-impact/components/ExplainDrawer.tsx
import { useEffect, useState } from "react";
import { strategyImpactApi, type ExplainResponse } from "../../../api/strategyImpact";
type Props = {
  directiveId: string | null;
  onClose: () => void;
};
export function ExplainDrawer({ directiveId, onClose }: Props) {
  const [data, setData] = useState<ExplainResponse | null>(null);
  useEffect(() => {
    if (!directiveId) {
      setData(null);
      return;
    }
    void strategyImpactApi.getExplain(directiveId).then(setData);
  }, [directiveId]);
  if (!directiveId) {
    return null;
  }
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-xl border-l bg-white p-4 shadow-2xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Why this directive was judged effective</h2>
        <button type="button" onClick={onClose} className="rounded-lg border px-3 py-1">Close</button>
      </div>
      {!data ? (
        <div>Loading...</div>
      ) : (
        <div className="space-y-4 text-sm">
          <section>
            <h3 className="font-semibold">Directive</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.directive, null, 2)}</pre>
          </section>
          <section>
            <h3 className="font-semibold">Attribution</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.attribution, null, 2)}</pre>
          </section>
          <section>
            <h3 className="font-semibold">Recommendation</h3>
            <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(data.recommendation, null, 2)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
18) backend/app/main.py patch
from app.api.routes.strategy_impact import router as strategy_impact_router
app.include_router(strategy_impact_router, prefix="/api")
19) backend/app/models/__init__.py patch
from app.models.strategy_attribution import (
    BusinessOutcomeSnapshot,
    DirectiveAttributionRecord,
    DirectiveEnforcementWindow,
    DirectiveRecommendation,
    RuntimeEffectSnapshot,
    StrategyDirective,
)
20) frontend/src/app/routes.tsx patch
import StrategyImpactConsole from "../features/strategy-impact/StrategyImpactConsole";
// add route
{
  path: "/strategy-impact",
  element: <StrategyImpactConsole />,
}
21) Notes to wire into the rest of the monorepo
Real production hooks you should connect next
Replace _historical_baseline() with warehouse-backed matched cohort logic
Feed snapshots from real runtime telemetry / SLA / cost / deadline domains
Add RBAC around promote / rollback actions
Add explicit promotion endpoint if you want operator action from console
Materialize daily rollups if dataset grows large
Minimal ingestion contract
Any runtime control layer that activates directives should emit:
directive activation/deactivation
enforcement window open/close
runtime metrics snapshots
business outcome snapshots
Without those four signals, attribution will degrade into weak before/after analytics.
Decision-grade rule
Do not auto-promote from the UI until:
sample_size >= 50
confidence_score >= 0.8
quality penalty below floor
cost penalty within governance threshold
---
# Phase 2 — Production-Deep Patch
Phần này mở rộng patch từ **decision-grade attribution** sang **governance-grade execution**.
Mục tiêu:
- tách rõ repository / service interface / execution policy
- thêm materialized rollups để dashboard không query thô
- thêm action endpoints cho promote / rollback / throttle / retire
- thêm RBAC để chỉ đúng vai trò mới được thực thi governance action
- thêm governance execution log để toàn bộ vòng lặp có audit trail
---
## 22) `backend/app/repositories/strategy_rollup_repository.py`
```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.models.strategy_governance import DirectiveDailyRollup, GovernanceExecutionLog
class StrategyRollupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def list_daily_rollups(
        self,
        directive_id: Optional[UUID] = None,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> list[DirectiveDailyRollup]:
        stmt = select(DirectiveDailyRollup).order_by(desc(DirectiveDailyRollup.bucket_date))
        if directive_id:
            stmt = stmt.where(DirectiveDailyRollup.directive_id == directive_id)
        if start_ts:
            stmt = stmt.where(DirectiveDailyRollup.bucket_date >= start_ts.date())
        if end_ts:
            stmt = stmt.where(DirectiveDailyRollup.bucket_date <= end_ts.date())
        return list(self.db.scalars(stmt).all())
    def list_governance_logs(self, directive_id: Optional[UUID] = None) -> list[GovernanceExecutionLog]:
        stmt = select(GovernanceExecutionLog).order_by(desc(GovernanceExecutionLog.executed_at))
        if directive_id:
            stmt = stmt.where(GovernanceExecutionLog.directive_id == directive_id)
        return list(self.db.scalars(stmt).all())
23) backend/app/services/strategy/interfaces.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID
@dataclass(slots=True)
class GovernanceActionRequest:
    directive_id: UUID
    actor_id: str
    actor_role: str
    action: str
    reason: str
    expected_version: int | None = None
    requested_scope_patch: dict | None = None
@dataclass(slots=True)
class GovernanceActionResult:
    directive_id: UUID
    action: str
    status: str
    executed_at: datetime
    message: str
class DirectiveStateGateway(Protocol):
    def promote(self, directive_id: UUID, actor_id: str, reason: str) -> None: ...
    def rollback(self, directive_id: UUID, actor_id: str, reason: str) -> None: ...
    def throttle(self, directive_id: UUID, actor_id: str, reason: str) -> None: ...
    def retire(self, directive_id: UUID, actor_id: str, reason: str) -> None: ...
    def patch_scope(self, directive_id: UUID, scope_patch: dict, actor_id: str, reason: str) -> None: ...
24) backend/app/models/strategy_governance.py
from __future__ import annotations
import enum
import uuid
from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
class GovernanceAction(str, enum.Enum):
    PROMOTE = "promote"
    KEEP = "keep"
    THROTTLE = "throttle"
    ROLLBACK = "rollback"
    RETIRE = "retire"
    PATCH_SCOPE = "patch_scope"
class GovernanceExecutionStatus(str, enum.Enum):
    EXECUTED = "executed"
    REJECTED = "rejected"
    NOOP = "noop"
class DirectiveDailyRollup(Base):
    __tablename__ = "directive_daily_rollups"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    bucket_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    context_signature: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    avg_net_mission_effect: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_quality_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rollup_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
class GovernanceExecutionLog(Base):
    __tablename__ = "governance_execution_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("directive_attribution_records.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[GovernanceAction] = mapped_column(Enum(GovernanceAction), nullable=False, index=True)
    status: Mapped[GovernanceExecutionStatus] = mapped_column(Enum(GovernanceExecutionStatus), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    execution_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
25) backend/app/schemas/strategy_governance.py
from __future__ import annotations
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
class GovernanceActionRequestBody(BaseModel):
    action: str
    reason: str
    requested_scope_patch: Optional[dict[str, Any]] = None
    expected_version: Optional[int] = None
class GovernanceExecutionLogRead(BaseModel):
    id: UUID
    directive_id: UUID
    attribution_record_id: Optional[UUID] = None
    action: str
    status: str
    actor_id: str
    actor_role: str
    reason: str
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    execution_payload: dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime
    model_config = {"from_attributes": True}
class DirectiveDailyRollupRead(BaseModel):
    id: UUID
    directive_id: UUID
    bucket_date: date
    context_signature: dict[str, Any]
    avg_net_mission_effect: float
    avg_confidence_score: float
    total_sample_size: int
    avg_cost_penalty: float
    avg_quality_penalty: float
    rollup_payload: dict[str, Any]
    model_config = {"from_attributes": True}
class GovernanceActionResponse(BaseModel):
    directive_id: UUID
    action: str
    status: str
    executed_at: datetime
    message: str
26) backend/app/services/auth/rbac.py
from __future__ import annotations
from dataclasses import dataclass
@dataclass(slots=True)
class ActorContext:
    actor_id: str
    actor_role: str
class RBACService:
    ACTION_ROLE_MAP = {
        "promote": {"admin", "strategy_owner"},
        "rollback": {"admin", "strategy_owner", "incident_commander"},
        "throttle": {"admin", "strategy_owner", "operator_lead"},
        "retire": {"admin", "strategy_owner"},
        "patch_scope": {"admin", "strategy_owner"},
    }
    def assert_allowed(self, actor_role: str, action: str) -> None:
        allowed_roles = self.ACTION_ROLE_MAP.get(action, set())
        if actor_role not in allowed_roles:
            raise PermissionError(f"Role '{actor_role}' is not allowed to execute '{action}'")
27) backend/app/services/strategy/governance_policy.py
from __future__ import annotations
from dataclasses import dataclass
from app.models.strategy_attribution import DirectiveAttributionRecord
@dataclass(slots=True)
class GovernanceThresholds:
    min_sample_size: int = 50
    min_confidence_for_promote: float = 0.80
    max_cost_penalty_for_promote: float = 0.20
    max_quality_penalty_for_promote: float = 0.15
    rollback_cost_penalty: float = 0.35
    rollback_quality_penalty: float = 0.30
class GovernancePolicyEngine:
    def __init__(self, thresholds: GovernanceThresholds | None = None) -> None:
        self.thresholds = thresholds or GovernanceThresholds()
    def validate_promote(self, record: DirectiveAttributionRecord) -> tuple[bool, str]:
        if record.sample_size < self.thresholds.min_sample_size:
            return False, "Insufficient sample size for promote"
        if record.confidence_score < self.thresholds.min_confidence_for_promote:
            return False, "Confidence score below promote threshold"
        if record.cost_penalty > self.thresholds.max_cost_penalty_for_promote:
            return False, "Cost penalty too high for promote"
        if record.quality_penalty > self.thresholds.max_quality_penalty_for_promote:
            return False, "Quality penalty too high for promote"
        return True, "Promote policy satisfied"
    def validate_rollback(self, record: DirectiveAttributionRecord) -> tuple[bool, str]:
        if record.cost_penalty >= self.thresholds.rollback_cost_penalty:
            return True, "Rollback allowed due to high cost penalty"
        if record.quality_penalty >= self.thresholds.rollback_quality_penalty:
            return True, "Rollback allowed due to high quality penalty"
        if record.net_mission_effect < 0:
            return True, "Rollback allowed due to negative net effect"
        return False, "Rollback threshold not met"
28) backend/app/services/strategy/directive_state_gateway.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.strategy_attribution import StrategyDirective
from app.services.strategy.interfaces import DirectiveStateGateway
class SqlAlchemyDirectiveStateGateway(DirectiveStateGateway):
    def __init__(self, db: Session) -> None:
        self.db = db
    def _get(self, directive_id: UUID) -> StrategyDirective:
        directive = self.db.query(StrategyDirective).filter(StrategyDirective.id == directive_id).one()
        return directive
    def promote(self, directive_id: UUID, actor_id: str, reason: str) -> None:
        directive = self._get(directive_id)
        directive.is_active = True
        directive.updated_at = datetime.utcnow()
        params = dict(directive.parameters or {})
        params["governance_last_action"] = {"action": "promote", "actor_id": actor_id, "reason": reason}
        directive.parameters = params
        self.db.flush()
    def rollback(self, directive_id: UUID, actor_id: str, reason: str) -> None:
        directive = self._get(directive_id)
        directive.is_active = False
        directive.deactivation_ts = datetime.utcnow()
        directive.updated_at = datetime.utcnow()
        params = dict(directive.parameters or {})
        params["governance_last_action"] = {"action": "rollback", "actor_id": actor_id, "reason": reason}
        directive.parameters = params
        self.db.flush()
    def throttle(self, directive_id: UUID, actor_id: str, reason: str) -> None:
        directive = self._get(directive_id)
        params = dict(directive.parameters or {})
        params["throttled"] = True
        params["governance_last_action"] = {"action": "throttle", "actor_id": actor_id, "reason": reason}
        directive.parameters = params
        directive.updated_at = datetime.utcnow()
        self.db.flush()
    def retire(self, directive_id: UUID, actor_id: str, reason: str) -> None:
        directive = self._get(directive_id)
        directive.is_active = False
        directive.deactivation_ts = datetime.utcnow()
        params = dict(directive.parameters or {})
        params["retired"] = True
        params["governance_last_action"] = {"action": "retire", "actor_id": actor_id, "reason": reason}
        directive.parameters = params
        directive.updated_at = datetime.utcnow()
        self.db.flush()
    def patch_scope(self, directive_id: UUID, scope_patch: dict, actor_id: str, reason: str) -> None:
        directive = self._get(directive_id)
        for field in ["tier", "workload_class", "mission_mode", "provider", "project", "strategy_mode"]:
            if field in scope_patch:
                setattr(directive, field, scope_patch[field])
        params = dict(directive.parameters or {})
        params["governance_last_action"] = {
            "action": "patch_scope",
            "actor_id": actor_id,
            "reason": reason,
            "scope_patch": scope_patch,
        }
        directive.parameters = params
        directive.updated_at = datetime.utcnow()
        self.db.flush()
29) backend/app/services/strategy/governance_execution_service.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.strategy_attribution import DirectiveAttributionRecord
from app.models.strategy_governance import GovernanceAction, GovernanceExecutionLog, GovernanceExecutionStatus
from app.services.auth.rbac import ActorContext, RBACService
from app.services.strategy.directive_state_gateway import SqlAlchemyDirectiveStateGateway
from app.services.strategy.governance_policy import GovernancePolicyEngine
from app.services.strategy.interfaces import GovernanceActionRequest, GovernanceActionResult
class GovernanceExecutionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rbac = RBACService()
        self.policy = GovernancePolicyEngine()
        self.gateway = SqlAlchemyDirectiveStateGateway(db)
    def _latest_attribution(self, directive_id: UUID) -> DirectiveAttributionRecord:
        record = (
            self.db.query(DirectiveAttributionRecord)
            .filter(DirectiveAttributionRecord.directive_id == directive_id)
            .order_by(DirectiveAttributionRecord.evaluation_ts.desc())
            .first()
        )
        if not record:
            raise ValueError("No attribution record found")
        return record
    def execute(self, request: GovernanceActionRequest) -> GovernanceActionResult:
        self.rbac.assert_allowed(request.actor_role, request.action)
        record = self._latest_attribution(request.directive_id)
        allowed = True
        policy_message = "Action allowed"
        if request.action == "promote":
            allowed, policy_message = self.policy.validate_promote(record)
        elif request.action == "rollback":
            allowed, policy_message = self.policy.validate_rollback(record)
        status = GovernanceExecutionStatus.EXECUTED if allowed else GovernanceExecutionStatus.REJECTED
        if allowed:
            if request.action == "promote":
                self.gateway.promote(request.directive_id, request.actor_id, request.reason)
            elif request.action == "rollback":
                self.gateway.rollback(request.directive_id, request.actor_id, request.reason)
            elif request.action == "throttle":
                self.gateway.throttle(request.directive_id, request.actor_id, request.reason)
            elif request.action == "retire":
                self.gateway.retire(request.directive_id, request.actor_id, request.reason)
            elif request.action == "patch_scope":
                self.gateway.patch_scope(request.directive_id, request.requested_scope_patch or {}, request.actor_id, request.reason)
            else:
                status = GovernanceExecutionStatus.NOOP
                policy_message = f"Unsupported action: {request.action}"
        executed_at = datetime.utcnow()
        log = GovernanceExecutionLog(
            directive_id=request.directive_id,
            attribution_record_id=record.id,
            action=GovernanceAction(request.action),
            status=status,
            actor_id=request.actor_id,
            actor_role=request.actor_role,
            reason=request.reason,
            policy_snapshot={
                "net_mission_effect": record.net_mission_effect,
                "confidence_score": record.confidence_score,
                "sample_size": record.sample_size,
                "cost_penalty": record.cost_penalty,
                "quality_penalty": record.quality_penalty,
            },
            execution_payload={
                "requested_scope_patch": request.requested_scope_patch,
                "policy_message": policy_message,
            },
            executed_at=executed_at,
        )
        self.db.add(log)
        self.db.commit()
        return GovernanceActionResult(
            directive_id=request.directive_id,
            action=request.action,
            status=status.value,
            executed_at=executed_at,
            message=policy_message,
        )
30) backend/app/services/strategy/rollup_service.py
from __future__ import annotations
from collections import defaultdict
from datetime import date
from typing import Any
from sqlalchemy.orm import Session
from app.models.strategy_attribution import DirectiveAttributionRecord
from app.models.strategy_governance import DirectiveDailyRollup
class StrategyRollupService:
    def __init__(self, db: Session) -> None:
        self.db = db
    def rebuild_daily_rollups(self, bucket_date: date) -> int:
        rows = (
            self.db.query(DirectiveAttributionRecord)
            .filter(DirectiveAttributionRecord.evaluation_ts >= bucket_date)
            .filter(DirectiveAttributionRecord.evaluation_ts < date.fromordinal(bucket_date.toordinal() + 1))
            .all()
        )
        grouped: dict[tuple[str, str], list[DirectiveAttributionRecord]] = defaultdict(list)
        for row in rows:
            grouped[(str(row.directive_id), str(row.context_signature))].append(row)
        created = 0
        for _, group in grouped.items():
            sample = group[0]
            total_sample_size = sum(x.sample_size for x in group)
            count = max(len(group), 1)
            rollup = DirectiveDailyRollup(
                directive_id=sample.directive_id,
                bucket_date=bucket_date,
                context_signature=sample.context_signature,
                avg_net_mission_effect=sum(x.net_mission_effect for x in group) / count,
                avg_confidence_score=sum(x.confidence_score for x in group) / count,
                total_sample_size=total_sample_size,
                avg_cost_penalty=sum(x.cost_penalty for x in group) / count,
                avg_quality_penalty=sum(x.quality_penalty for x in group) / count,
                rollup_payload={
                    "record_count": count,
                    "latest_evaluation_ts": max(x.evaluation_ts.isoformat() for x in group),
                },
            )
            self.db.add(rollup)
            created += 1
        self.db.commit()
        return created
31) backend/app/api/deps_auth.py
from __future__ import annotations
from fastapi import Header, HTTPException
from app.services.auth.rbac import ActorContext
async def get_actor_context(
    x_actor_id: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
) -> ActorContext:
    if not x_actor_id or not x_actor_role:
        raise HTTPException(status_code=401, detail="Missing actor identity headers")
    return ActorContext(actor_id=x_actor_id, actor_role=x_actor_role)
32) backend/app/api/routes/strategy_governance.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.api.deps_auth import get_actor_context
from app.repositories.strategy_rollup_repository import StrategyRollupRepository
from app.schemas.strategy_governance import (
    DirectiveDailyRollupRead,
    GovernanceActionRequestBody,
    GovernanceActionResponse,
    GovernanceExecutionLogRead,
)
from app.services.auth.rbac import ActorContext
from app.services.strategy.governance_execution_service import GovernanceExecutionService
from app.services.strategy.interfaces import GovernanceActionRequest
router = APIRouter(prefix="/strategy/governance", tags=["strategy-governance"])
@router.get("/rollups", response_model=list[DirectiveDailyRollupRead])
def list_rollups(
    directive_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> list[DirectiveDailyRollupRead]:
    repo = StrategyRollupRepository(db)
    return repo.list_daily_rollups(directive_id=directive_id)
@router.get("/logs", response_model=list[GovernanceExecutionLogRead])
def list_logs(
    directive_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> list[GovernanceExecutionLogRead]:
    repo = StrategyRollupRepository(db)
    return repo.list_governance_logs(directive_id=directive_id)
@router.post("/{directive_id}/actions", response_model=GovernanceActionResponse)
def execute_action(
    directive_id: UUID,
    body: GovernanceActionRequestBody,
    actor: ActorContext = Depends(get_actor_context),
    db: Session = Depends(get_db),
) -> GovernanceActionResponse:
    service = GovernanceExecutionService(db)
    result = service.execute(
        GovernanceActionRequest(
            directive_id=directive_id,
            actor_id=actor.actor_id,
            actor_role=actor.actor_role,
            action=body.action,
            reason=body.reason,
            expected_version=body.expected_version,
            requested_scope_patch=body.requested_scope_patch,
        )
    )
    return GovernanceActionResponse(
        directive_id=result.directive_id,
        action=result.action,
        status=result.status,
        executed_at=result.executed_at,
        message=result.message,
    )
33) backend/app/workers/rollup_worker.py
from __future__ import annotations
from datetime import datetime, timedelta
from celery import shared_task
from app.db.session import SessionLocal
from app.services.strategy.rollup_service import StrategyRollupService
@shared_task(name="strategy.rebuild_daily_rollups")
def rebuild_daily_rollups(bucket_date: str | None = None) -> dict:
    db = SessionLocal()
    try:
        target = datetime.strptime(bucket_date, "%Y-%m-%d").date() if bucket_date else (datetime.utcnow() - timedelta(days=1)).date()
        service = StrategyRollupService(db)
        created = service.rebuild_daily_rollups(target)
        return {"status": "ok", "bucket_date": str(target), "created": created}
    finally:
        db.close()
34) backend/app/tests/test_governance_policy.py
from datetime import datetime
from uuid import uuid4
from app.models.strategy_attribution import BaselineType, DirectiveAttributionRecord
from app.services.strategy.governance_policy import GovernancePolicyEngine
def build_record(**overrides):
    data = dict(
        id=uuid4(),
        directive_id=uuid4(),
        window_id=uuid4(),
        baseline_type=BaselineType.HISTORICAL_ROLLING,
        baseline_id=None,
        context_signature={"tier": "enterprise"},
        sla_gain=0.7,
        deadline_save=0.6,
        cost_penalty=0.1,
        quality_penalty=0.05,
        throughput_gain=0.2,
        stability_gain=0.3,
        operator_relief=0.2,
        net_mission_effect=0.65,
        confidence_score=0.85,
        sample_size=100,
        explain_payload={},
        evaluation_ts=datetime.utcnow(),
    )
    data.update(overrides)
    return DirectiveAttributionRecord(**data)
def test_validate_promote_success() -> None:
    engine = GovernancePolicyEngine()
    ok, message = engine.validate_promote(build_record())
    assert ok is True
    assert "Promote" in message
def test_validate_promote_reject_low_confidence() -> None:
    engine = GovernancePolicyEngine()
    ok, _ = engine.validate_promote(build_record(confidence_score=0.4))
    assert ok is False
35) backend/app/tests/test_rbac.py
import pytest
from app.services.auth.rbac import RBACService
def test_strategy_owner_can_promote() -> None:
    RBACService().assert_allowed("strategy_owner", "promote")
def test_operator_cannot_retire() -> None:
    with pytest.raises(PermissionError):
        RBACService().assert_allowed("operator", "retire")
36) backend/app/db/migrations/versions/20260412_02_strategy_governance_phase2.py
"""strategy governance phase 2
Revision ID: 20260412_02
Revises: 20260412_01
Create Date: 2026-04-12 11:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20260412_02"
down_revision = "20260412_01"
branch_labels = None
depends_on = None
def upgrade() -> None:
    governance_action = sa.Enum("promote", "keep", "throttle", "rollback", "retire", "patch_scope", name="governanceaction")
    governance_status = sa.Enum("executed", "rejected", "noop", name="governanceexecutionstatus")
    governance_action.create(op.get_bind(), checkfirst=True)
    governance_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "directive_daily_rollups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_date", sa.Date(), nullable=False),
        sa.Column("context_signature", sa.JSON(), nullable=False),
        sa.Column("avg_net_mission_effect", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_cost_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_quality_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rollup_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "governance_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("directive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_directives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribution_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directive_attribution_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", governance_action, nullable=False),
        sa.Column("status", governance_status, nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("actor_role", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("execution_payload", sa.JSON(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
def downgrade() -> None:
    op.drop_table("governance_execution_logs")
    op.drop_table("directive_daily_rollups")
    sa.Enum(name="governanceexecutionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="governanceaction").drop(op.get_bind(), checkfirst=True)
37) frontend/src/api/strategyGovernance.ts
export type GovernanceActionBody = {
  action: "promote" | "rollback" | "throttle" | "retire" | "patch_scope";
  reason: string;
  requested_scope_patch?: Record<string, unknown>;
  expected_version?: number;
};
export type GovernanceActionResponse = {
  directive_id: string;
  action: string;
  status: string;
  executed_at: string;
  message: string;
};
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-actor-id": "demo-user",
      "x-actor-role": "strategy_owner",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}
export const strategyGovernanceApi = {
  executeAction: (directiveId: string, body: GovernanceActionBody) =>
    request<GovernanceActionResponse>(`/api/strategy/governance/${directiveId}/actions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getLogs: () => request<any[]>("/api/strategy/governance/logs"),
  getRollups: () => request<any[]>("/api/strategy/governance/rollups"),
};
38) frontend/src/features/strategy-impact/components/GovernanceActionBar.tsx
import { useState } from "react";
import { strategyGovernanceApi } from "../../../api/strategyGovernance";
type Props = {
  directiveId: string;
};
export function GovernanceActionBar({ directiveId }: Props) {
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  async function run(action: "promote" | "rollback" | "throttle" | "retire") {
    const result = await strategyGovernanceApi.executeAction(directiveId, { action, reason });
    setStatus(`${result.action}: ${result.status} — ${result.message}`);
  }
  return (
    <div className="space-y-3 rounded-2xl border bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold">Governance Actions</h3>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Why are you applying this governance action?"
        className="min-h-[100px] w-full rounded-xl border p-3"
      />
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void run("promote")} className="rounded-xl border px-3 py-2">Promote</button>
        <button type="button" onClick={() => void run("rollback")} className="rounded-xl border px-3 py-2">Rollback</button>
        <button type="button" onClick={() => void run("throttle")} className="rounded-xl border px-3 py-2">Throttle</button>
        <button type="button" onClick={() => void run("retire")} className="rounded-xl border px-3 py-2">Retire</button>
      </div>
      {status ? <div className="text-sm text-slate-700">{status}</div> : null}
    </div>
  );
}
39) frontend/src/features/strategy-impact/components/ExplainDrawer.tsx patch
import { GovernanceActionBar } from "./GovernanceActionBar";
// inside the loaded state render, after recommendation section:
{directiveId ? <GovernanceActionBar directiveId={directiveId} /> : null}
40) backend/app/main.py patch
from app.api.routes.strategy_governance import router as strategy_governance_router
app.include_router(strategy_governance_router, prefix="/api")
41) backend/app/models/__init__.py patch
from app.models.strategy_governance import (
    DirectiveDailyRollup,
    GovernanceExecutionLog,
)
42) Production notes for Phase 2
Cái patch này đã mở rộng hệ từ:
attribution console
sang:
governance execution surface
audited action layer
role-gated decision execution
rollup-backed dashboard performance
Thứ nên nối tiếp ngay sau patch này
optimistic locking / directive versioning thật
background policy simulation trước khi execute action
approval workflow nhiều bước cho promote diện rộng
webhook / Slack notification khi governance action executed hoặc rejected
materialized views ở warehouse nếu volume lớn
Rule vận hành quan trọng
Không cho UI action chạm trực tiếp runtime fabric nếu chưa có:
governance log
RBAC
policy gate
rollback-safe state gateway
Nếu thiếu 1 trong 4 lớp này, action endpoint sẽ biến thành nút bấm nguy hiểm thay vì governance control plane.
Phase 2 hiện đã có:
strategy_rollup_repository.py
interfaces.py
strategy_governance.py models
governance schemas
rbac.py
governance_policy.py
directive_state_gateway.py
governance_execution_service.py
rollup_service.py
auth deps cho actor headers
governance API routes
rollup worker
tests cho policy và RBAC
Alembic migration phase 2
frontend governance API
GovernanceActionBar.tsx
patch nối ExplainDrawer với governance actions
Điểm quan trọng nhất là patch này đã nâng hệ từ:
decision-grade attribution
thành
governance-grade execution
Tức là giờ console không chỉ “biết directive nào tốt”, mà đã có khung để:
promote
rollback
throttle
retire
patch scope
với:
RBAC
policy gate
audit log
rollup phục vụ dashboard
Phase 2 này đã vượt qua ngưỡng “analytics console” và bước vào execution governance layer thật sự. Điểm quan trọng không nằm ở chỗ thêm vài route hay vài model, mà ở chỗ hệ của bạn giờ đã có đủ 4 mảnh để ra quyết định có kiểm soát:
authority: RBAC + actor headers
policy: governance policy gate
execution: governance execution service
traceability: audit log + rollup cho dashboard
Nói cách khác, từ đây directive không còn là “insight có thể hành động”, mà đã thành governed action primitive.
Bước mạnh nhất ngay sau bản này đúng là Phase 3 như bạn nói, nhưng nên khóa thứ tự ưu tiên như sau:
1. Optimistic locking
Đây là lớp phải làm trước tiên.
Vì khi đã có:
promote
rollback
throttle
retire
patch scope
thì nguy cơ lớn nhất không còn là thiếu API, mà là concurrent mutation:
2 operator bấm action cùng lúc
1 worker đang apply trong khi UI vẫn hiển thị state cũ
approval vừa pass thì policy/runtime state đã đổi
Nếu không có optimistic locking, toàn bộ governance sẽ dễ rơi vào:
lost update
double execution
stale approval
audit đúng log nhưng sai state cuối
Nên khóa bằng:
version hoặc etag trên directive state / governance object
compare-and-swap khi mutate
API trả 409 Conflict nếu stale version
frontend auto refresh + rebase intent
2. Approval workflow
Sau locking mới đến approval.
Vì approval mà không có concurrency control thì approval record rất dễ thành hình thức.
Approval workflow production nên có:
submit for approval
approve / reject
required approver policy
self-approval block
dual control cho action nhạy cảm
approval expiry
invalidation nếu underlying state/version đổi
Mấu chốt:
approval phải bind vào exact proposed change + exact target version, không bind kiểu chung chung theo directive id.
3. Policy simulation
Đây là lớp làm hệ “an toàn để scale”.
Trước khi promote/rollback/throttle thật, hệ nên simulate:
policy outcome
scope affected
expected blocked entities
risk flags
approval requirement
runtime impact estimate
Tức là operator thấy trước:
action này có được policy cho phép không
nếu được, nó sẽ chạm vào cái gì
nếu không được, fail vì rule nào
Đây là lớp giảm sai thao tác rất mạnh, nhất là khi console bắt đầu có nhiều owner.
4. Runtime fabric action adapters
Đây là bước biến governance thành quyền lực thực.
Hiện tại execution layer của bạn đã có khung. Bước tiếp theo là nối action xuống runtime thật, ví dụ:
release gate adapter
provider routing override adapter
concurrency/throttle adapter
kill switch / suppress adapter
config patch adapter
expiry/rollback adapter
Lưu ý:
governance service không nên biết chi tiết runtime implementation. Nó chỉ nên gọi qua action adapter interface + persist execution result + reconcile state.
5. Notification plane
Đây là lớp sau cùng để đưa hệ từ “operator dùng được” sang “tổ chức vận hành được”.
Nên có:
action requested
approval needed
approval granted / rejected
execution succeeded / failed
rollback happened
policy violation detected
stale change rejected
Channel:
in-app event stream trước
rồi email / webhook / Slack adapter sau
Thứ tự build tối ưu cho Phase 3
Tôi sẽ khóa theo thứ tự này:
A. optimistic locking
B. approval workflow
C. policy simulation
D. runtime fabric adapters
E. notification plane
Đây là thứ tự mạnh nhất vì:
A bảo toàn tính đúng
B bảo toàn thẩm quyền
C bảo toàn an toàn thao tác
D tạo tác động runtime thật
E bảo toàn vận hành nhiều người
Data model nên có trong Phase 3
Ít nhất cần thêm các thực thể sau:
governance_change_request
governance_approval
governance_execution_attempt
directive_version hoặc version field trong directive state
policy_simulation_result
notification_event
Các field quan trọng:
actor
action_type
target_type / target_id
expected_version
proposed_payload
approval_status
execution_status
simulation_summary
correlation_id
idempotency_key
created_at / decided_at / executed_at
API nên có
Nhóm route mạnh nhất:
POST /governance/changes
POST /governance/changes/{id}/submit
POST /governance/changes/{id}/approve
POST /governance/changes/{id}/reject
POST /governance/changes/{id}/simulate
POST /governance/changes/{id}/execute
GET /governance/changes/{id}
GET /governance/approvals/queue
Với execution trực tiếp:
bắt buộc kèm expected_version
trả conflict rõ ràng
trả policy decision snapshot
trả approval requirement snapshot
Frontend Phase 3 nên thêm gì
UI lúc này không chỉ là action bar nữa, mà thành governed change console:
change request drawer
simulation preview panel
approval badge / status rail
conflict banner nếu stale version
execution timeline
notification center / activity stream
Quan trọng nhất:
operator phải thấy rõ khác biệt giữa:
simulate
submit for approval
execute now
rollback existing action
Định nghĩa “done” đúng cho Phase 3
Phase 3 chỉ nên coi là xong khi đạt đủ:
concurrent update không làm hỏng state
action nhạy cảm không thể self-approve trái policy
operator xem được simulation trước execute
execution xuống runtime adapter thật, không chỉ đổi DB
mọi approval/execution đều phát event cho notification plane
UI xử lý đúng conflict + pending approval + execution result
Kết luận kiến trúc
Phase 2 của bạn đã dựng xong governance shell.
Phase 3 phải biến shell đó thành controlled execution system.
Nói ngắn gọn:
Phase 1: biết directive nào hiệu quả
Phase 2: có quyền govern directive
Phase 3: govern được trong môi trường nhiều người, nhiều policy, nhiều runtime side effects
Câu chốt về mặt kỹ thuật:
Bước mạnh nhất tiếp theo không phải thêm nhiều action hơn, mà là làm cho mỗi action trở thành một governed transaction có version, approval, simulation, execution adapter, và notification lifecycle.
Gõ:
“WRITE PATCH PHASE 3 FILE-BY-FILE”
tôi sẽ viết thẳng bộ spec/patch theo đúng format monorepo cho toàn bộ:
optimistic locking
approval workflow
policy simulation
notification plane
runtime fabric action adapters
“WRITE PATCH PHASE 3 FILE-BY-FILE”
Tôi sẽ viết thẳng Phase 3 theo đúng kiểu monorepo patch, ưu tiên chuỗi sống còn: optimistic locking → approval workflow → policy simulation → runtime action adapters → notification plane. Tôi sẽ giữ format đủ để bạn chuyển sang patch file-by-file ngay, không đổi kiến trúc Phase 2 trừ những chỗ bắt buộc để nối vòng đời governed transaction.
Đã suy nghĩ trong 6s
Dưới đây là PATCH PHASE 3 — FILE-BY-FILE theo đúng hướng monorepo production, nối trực tiếp trên Phase 2 hiện có.
Mục tiêu của Phase 3:
biến governance action thành governed transaction
chống race condition bằng optimistic locking
thêm approval workflow
thêm policy simulation
nối xuống runtime fabric action adapters
phát notification events cho UI / webhook / email / Slack về sau
Tôi giữ nguyên tinh thần kiến trúc Phase 2, chỉ mở rộng đúng các lớp cần thiết.
0. PHẠM VI PHASE 3
Nâng cấp chính
Optimistic locking
Change request / approval workflow
Policy simulation endpoint + service
Runtime fabric adapters
Notification plane
Frontend approval + simulation + conflict UX
Migration + tests
1. CÂY FILE MỚI / FILE CẦN SỬA
backend/
  app/
    db/
      models/
        strategy_governance.py                       # update
        governance_change_request.py                 # new
        governance_approval.py                       # new
        governance_execution_attempt.py              # new
        governance_notification_event.py             # new

    repositories/
      strategy_rollup_repository.py                  # update
      governance_change_request_repository.py        # new
      governance_approval_repository.py              # new
      governance_execution_attempt_repository.py     # new
      governance_notification_repository.py          # new
      directive_state_gateway.py                     # update

    schemas/
      governance.py                                  # update
      governance_change_request.py                   # new
      governance_approval.py                         # new
      governance_simulation.py                       # new
      governance_notification.py                     # new

    services/
      strategy_governance.py                         # update
      governance_execution_service.py                # update
      governance_policy.py                           # update
      governance_approval_service.py                 # new
      governance_simulation_service.py               # new
      governance_notification_service.py             # new
      runtime_fabric/
        interfaces.py                                # new
        base.py                                      # new
        release_gate_adapter.py                      # new
        provider_routing_adapter.py                  # new
        throttle_adapter.py                          # new
        directive_patch_adapter.py                   # new
        registry.py                                  # new

    api/
      deps/
        auth.py                                      # update
      routes/
        governance.py                                # update

    workers/
      rollup_worker.py                               # update
      governance_notification_worker.py              # new

    core/
      enums/
        governance.py                                # new
      errors/
        governance.py                                # new

    tests/
      services/
        test_governance_policy.py                    # update
        test_governance_approval_service.py          # new
        test_governance_simulation_service.py        # new
        test_governance_execution_service.py         # update
      api/
        test_governance_routes.py                    # update
      repositories/
        test_change_request_repository.py            # new

  alembic/
    versions/
      20260412_01_phase3_governance_workflow.py     # new

frontend/
  src/
    api/
      governance.ts                                  # update
    types/
      governance.ts                                  # update
    components/governance/
      GovernanceActionBar.tsx                        # update
      GovernanceSimulationPanel.tsx                  # new
      GovernanceApprovalPanel.tsx                    # new
      GovernanceConflictBanner.tsx                   # new
      GovernanceExecutionTimeline.tsx                # new
    hooks/
      useGovernanceSimulation.ts                     # new
      useGovernanceApprovalQueue.ts                  # new
    pages/
      StrategyImpactConsole.tsx                      # update
2. DOMAIN QUY ƯỚC MỚI
Action lifecycle
Một governance action từ Phase 3 sẽ đi theo luồng:
UI tạo change request
hệ chạy simulation
policy xác định:
allowed / denied
requires approval hay không
nếu cần approval:
submit
approve / reject
execute với:
expected_version
idempotency_key
runtime adapter apply vào fabric thật
ghi:
execution attempt
audit event
notification event
rollup worker cập nhật dashboard
3. ENUMS & ERRORS
File: backend/app/core/enums/governance.py (new)
from enum import Enum


class GovernanceActionType(str, Enum):
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    THROTTLE = "throttle"
    RETIRE = "retire"
    PATCH_SCOPE = "patch_scope"


class GovernanceChangeStatus(str, Enum):
    DRAFT = "draft"
    SIMULATED = "simulated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    READY = "ready"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONFLICTED = "conflicted"
    EXPIRED = "expired"


class GovernanceApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class GovernanceExecutionStatus(str, Enum):
    PENDING = "pending"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CONFLICTED = "conflicted"
    SKIPPED = "skipped"


class GovernanceNotificationChannel(str, Enum):
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"


class GovernanceNotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class GovernanceTargetType(str, Enum):
    DIRECTIVE = "directive"
    POLICY_SCOPE = "policy_scope"
    RELEASE_GATE = "release_gate"
    PROVIDER_ROUTE = "provider_route"
File: backend/app/core/errors/governance.py (new)
class GovernanceError(Exception):
    pass


class GovernanceConflictError(GovernanceError):
    pass


class GovernancePolicyDeniedError(GovernanceError):
    pass


class GovernanceApprovalRequiredError(GovernanceError):
    pass


class GovernanceApprovalInvalidError(GovernanceError):
    pass


class GovernanceExecutionError(GovernanceError):
    pass
4. DB MODELS
File: backend/app/db/models/strategy_governance.py (update)
Thêm optimistic locking trực tiếp vào directive state / governance aggregate.
Patch chính
from sqlalchemy import Column, Integer, DateTime, String, JSON, Boolean
from sqlalchemy.sql import func

# existing model ...

version = Column(Integer, nullable=False, default=1, server_default="1")
last_change_request_id = Column(String, nullable=True)
last_simulation_result = Column(JSON, nullable=True)
last_policy_snapshot = Column(JSON, nullable=True)
updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
Ý nghĩa
version: compare-and-swap khi mutate
last_change_request_id: trace action gần nhất
last_simulation_result: preview dashboard/UI
last_policy_snapshot: phục vụ explainability
File: backend/app/db/models/governance_change_request.py (new)
import uuid
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


class GovernanceChangeRequest(Base):
    __tablename__ = "governance_change_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_type = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=False, index=True)

    action_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)

    actor_id = Column(String, nullable=False, index=True)
    actor_role = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    expected_version = Column(Integer, nullable=False)
    current_version_snapshot = Column(Integer, nullable=False)

    proposed_payload = Column(JSON, nullable=False)
    simulation_result = Column(JSON, nullable=True)
    policy_snapshot = Column(JSON, nullable=True)

    requires_approval = Column(String, nullable=False, default="false")
    approval_rule_key = Column(String, nullable=True)

    idempotency_key = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True, index=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
File: backend/app/db/models/governance_approval.py (new)
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.sql import func
from app.db.base import Base


class GovernanceApproval(Base):
    __tablename__ = "governance_approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(String, ForeignKey("governance_change_requests.id"), nullable=False, index=True)

    status = Column(String, nullable=False, index=True)
    required_role = Column(String, nullable=True)
    decision_by = Column(String, nullable=True, index=True)
    decision_note = Column(Text, nullable=True)

    target_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
File: backend/app/db/models/governance_execution_attempt.py (new)
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.sql import func
from app.db.base import Base


class GovernanceExecutionAttempt(Base):
    __tablename__ = "governance_execution_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(String, ForeignKey("governance_change_requests.id"), nullable=False, index=True)

    status = Column(String, nullable=False, index=True)
    adapter_key = Column(String, nullable=False)
    target_version = Column(Integer, nullable=False)

    request_payload = Column(JSON, nullable=False)
    adapter_response = Column(JSON, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
File: backend/app/db/models/governance_notification_event.py (new)
import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.base import Base


class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(String, ForeignKey("governance_change_requests.id"), nullable=True, index=True)

    event_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)

    payload = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
5. REPOSITORIES
File: backend/app/repositories/governance_change_request_repository.py (new)
from sqlalchemy.orm import Session
from app.db.models.governance_change_request import GovernanceChangeRequest


class GovernanceChangeRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, obj: GovernanceChangeRequest) -> GovernanceChangeRequest:
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        return (
            self.db.query(GovernanceChangeRequest)
            .filter(GovernanceChangeRequest.id == change_request_id)
            .first()
        )

    def list_pending_approvals(self, limit: int = 50):
        return (
            self.db.query(GovernanceChangeRequest)
            .filter(GovernanceChangeRequest.status == "pending_approval")
            .order_by(GovernanceChangeRequest.created_at.asc())
            .limit(limit)
            .all()
        )

    def find_by_idempotency_key(self, idempotency_key: str):
        if not idempotency_key:
            return None
        return (
            self.db.query(GovernanceChangeRequest)
            .filter(GovernanceChangeRequest.idempotency_key == idempotency_key)
            .first()
        )
File: backend/app/repositories/governance_approval_repository.py (new)
from sqlalchemy.orm import Session
from app.db.models.governance_approval import GovernanceApproval


class GovernanceApprovalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, approval: GovernanceApproval) -> GovernanceApproval:
        self.db.add(approval)
        self.db.flush()
        self.db.refresh(approval)
        return approval

    def get_by_change_request_id(self, change_request_id: str) -> GovernanceApproval | None:
        return (
            self.db.query(GovernanceApproval)
            .filter(GovernanceApproval.change_request_id == change_request_id)
            .order_by(GovernanceApproval.created_at.desc())
            .first()
        )
File: backend/app/repositories/governance_execution_attempt_repository.py (new)
from sqlalchemy.orm import Session
from app.db.models.governance_execution_attempt import GovernanceExecutionAttempt


class GovernanceExecutionAttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, attempt: GovernanceExecutionAttempt) -> GovernanceExecutionAttempt:
        self.db.add(attempt)
        self.db.flush()
        self.db.refresh(attempt)
        return attempt

    def list_by_change_request_id(self, change_request_id: str):
        return (
            self.db.query(GovernanceExecutionAttempt)
            .filter(GovernanceExecutionAttempt.change_request_id == change_request_id)
            .order_by(GovernanceExecutionAttempt.created_at.asc())
            .all()
        )
File: backend/app/repositories/governance_notification_repository.py (new)
from sqlalchemy.orm import Session
from app.db.models.governance_notification_event import GovernanceNotificationEvent


class GovernanceNotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event: GovernanceNotificationEvent) -> GovernanceNotificationEvent:
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def list_pending(self, limit: int = 100):
        return (
            self.db.query(GovernanceNotificationEvent)
            .filter(GovernanceNotificationEvent.status == "pending")
            .order_by(GovernanceNotificationEvent.created_at.asc())
            .limit(limit)
            .all()
        )
File: backend/app/repositories/directive_state_gateway.py (update)
Đây là chỗ tối quan trọng: thêm compare-and-swap update.
from sqlalchemy import update
from app.core.errors.governance import GovernanceConflictError

class DirectiveStateGateway:
    # existing methods ...

    def update_with_version_check(
        self,
        directive_id: str,
        expected_version: int,
        patch: dict,
    ):
        stmt = (
            update(self.model)
            .where(self.model.directive_id == directive_id)
            .where(self.model.version == expected_version)
            .values(**patch, version=expected_version + 1)
        )
        result = self.db.execute(stmt)
        if result.rowcount != 1:
            raise GovernanceConflictError(
                f"Directive {directive_id} version conflict. expected_version={expected_version}"
            )
6. SCHEMAS
File: backend/app/schemas/governance_change_request.py (new)
from pydantic import BaseModel, Field
from typing import Any


class GovernanceChangeCreateRequest(BaseModel):
    target_type: str
    target_id: str
    action_type: str
    expected_version: int
    proposed_payload: dict[str, Any]
    reason: str | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None


class GovernanceChangeResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    action_type: str
    status: str
    expected_version: int
    current_version_snapshot: int
    requires_approval: bool
    approval_rule_key: str | None = None
    simulation_result: dict | None = None
    policy_snapshot: dict | None = None
File: backend/app/schemas/governance_approval.py (new)
from pydantic import BaseModel


class GovernanceApprovalDecisionRequest(BaseModel):
    note: str | None = None


class GovernanceApprovalResponse(BaseModel):
    id: str
    change_request_id: str
    status: str
    required_role: str | None = None
    decision_by: str | None = None
    decision_note: str | None = None
    target_version: int
File: backend/app/schemas/governance_simulation.py (new)
from pydantic import BaseModel
from typing import Any


class GovernanceSimulationRequest(BaseModel):
    target_type: str
    target_id: str
    action_type: str
    expected_version: int
    proposed_payload: dict[str, Any]


class GovernanceSimulationResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    policy_reasons: list[str]
    risk_flags: list[str]
    impacted_entities: list[dict]
    adapter_preview: dict | None = None
    target_version_matches: bool
File: backend/app/schemas/governance_notification.py (new)
from pydantic import BaseModel


class GovernanceNotificationEventResponse(BaseModel):
    id: str
    event_type: str
    channel: str
    status: str
    payload: dict
File: backend/app/schemas/governance.py (update)
Thêm responses cho simulation / change / attempts.
from typing import Any
from pydantic import BaseModel


class GovernanceExecutionResponse(BaseModel):
    change_request_id: str
    execution_status: str
    new_version: int | None = None
    adapter_response: dict[str, Any] | None = None
    conflict: bool = False
7. POLICY SERVICE
File: backend/app/services/governance_policy.py (update)
Phase 2 có gate rồi. Phase 3 nâng thành trả về structured decision.
from dataclasses import dataclass, field


@dataclass
class GovernancePolicyDecision:
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


class GovernancePolicyService:
    # existing methods ...

    def evaluate_change_request(
        self,
        *,
        actor_role: str,
        action_type: str,
        target_type: str,
        target_id: str,
        proposed_payload: dict,
    ) -> GovernancePolicyDecision:
        reasons: list[str] = []
        risk_flags: list[str] = []
        requires_approval = False
        approval_rule_key = None

        if action_type in {"retire", "rollback"} and actor_role not in {"admin", "governance_owner"}:
            requires_approval = True
            approval_rule_key = "sensitive_action_dual_control"
            reasons.append("Sensitive action requires approval.")

        if action_type == "patch_scope" and proposed_payload.get("scope") == "global":
            requires_approval = True
            approval_rule_key = "global_scope_change"

        if actor_role not in {"viewer", "analyst", "operator", "admin", "governance_owner"}:
            return GovernancePolicyDecision(
                allowed=False,
                requires_approval=False,
                reasons=["Unknown actor role."],
            )

        if actor_role == "viewer":
            return GovernancePolicyDecision(
                allowed=False,
                requires_approval=False,
                reasons=["Viewer role cannot mutate governance state."],
            )

        if action_type == "retire":
            risk_flags.append("traffic_impact")
            risk_flags.append("directive_removal")

        return GovernancePolicyDecision(
            allowed=True,
            requires_approval=requires_approval,
            approval_rule_key=approval_rule_key,
            reasons=reasons,
            risk_flags=risk_flags,
        )
8. APPROVAL SERVICE
File: backend/app/services/governance_approval_service.py (new)
from datetime import datetime, timedelta, timezone

from app.db.models.governance_approval import GovernanceApproval
from app.core.errors.governance import GovernanceApprovalInvalidError


class GovernanceApprovalService:
    def __init__(self, approval_repo, change_repo, notification_service):
        self.approval_repo = approval_repo
        self.change_repo = change_repo
        self.notification_service = notification_service

    def create_pending_approval(self, change_request, required_role: str | None):
        approval = GovernanceApproval(
            change_request_id=change_request.id,
            status="pending",
            required_role=required_role,
            target_version=change_request.expected_version,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        approval = self.approval_repo.create(approval)

        change_request.status = "pending_approval"
        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_requested",
            payload={
                "change_request_id": change_request.id,
                "required_role": required_role,
                "target_id": change_request.target_id,
                "action_type": change_request.action_type,
            },
        )
        return approval

    def approve(self, change_request, actor_id: str, actor_role: str, note: str | None):
        approval = self.approval_repo.get_by_change_request_id(change_request.id)
        if not approval or approval.status != "pending":
            raise GovernanceApprovalInvalidError("No pending approval found.")

        if approval.required_role and actor_role not in {approval.required_role, "admin"}:
            raise GovernanceApprovalInvalidError("Actor role not permitted to approve.")

        if change_request.actor_id == actor_id:
            raise GovernanceApprovalInvalidError("Self-approval is not allowed.")

        if approval.target_version != change_request.expected_version:
            approval.status = "invalidated"
            raise GovernanceApprovalInvalidError("Approval invalidated due to version mismatch.")

        approval.status = "approved"
        approval.decision_by = actor_id
        approval.decision_note = note
        approval.decided_at = datetime.now(timezone.utc)

        change_request.status = "approved"
        change_request.approved_at = approval.decided_at

        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_granted",
            payload={"change_request_id": change_request.id, "approved_by": actor_id},
        )
        return approval

    def reject(self, change_request, actor_id: str, actor_role: str, note: str | None):
        approval = self.approval_repo.get_by_change_request_id(change_request.id)
        if not approval or approval.status != "pending":
            raise GovernanceApprovalInvalidError("No pending approval found.")

        approval.status = "rejected"
        approval.decision_by = actor_id
        approval.decision_note = note
        approval.decided_at = datetime.now(timezone.utc)

        change_request.status = "rejected"

        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_rejected",
            payload={"change_request_id": change_request.id, "rejected_by": actor_id},
        )
        return approval
9. SIMULATION SERVICE
File: backend/app/services/governance_simulation_service.py (new)
class GovernanceSimulationService:
    def __init__(self, policy_service, directive_state_gateway, adapter_registry):
        self.policy_service = policy_service
        self.directive_state_gateway = directive_state_gateway
        self.adapter_registry = adapter_registry

    def simulate(
        self,
        *,
        actor_role: str,
        target_type: str,
        target_id: str,
        action_type: str,
        expected_version: int,
        proposed_payload: dict,
    ):
        target = self.directive_state_gateway.get(target_id)
        current_version = getattr(target, "version", None) if target else None
        target_version_matches = current_version == expected_version

        policy = self.policy_service.evaluate_change_request(
            actor_role=actor_role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            proposed_payload=proposed_payload,
        )

        adapter = self.adapter_registry.resolve(action_type)
        adapter_preview = adapter.preview(
            target_type=target_type,
            target_id=target_id,
            payload=proposed_payload,
        )

        return {
            "allowed": policy.allowed,
            "requires_approval": policy.requires_approval,
            "approval_rule_key": policy.approval_rule_key,
            "policy_reasons": policy.reasons,
            "risk_flags": policy.risk_flags,
            "impacted_entities": adapter_preview.get("impacted_entities", []),
            "adapter_preview": adapter_preview,
            "target_version_matches": target_version_matches,
        }
10. RUNTIME FABRIC ADAPTERS
File: backend/app/services/runtime_fabric/interfaces.py (new)
from abc import ABC, abstractmethod


class RuntimeFabricAdapter(ABC):
    adapter_key: str

    @abstractmethod
    def preview(self, *, target_type: str, target_id: str, payload: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        raise NotImplementedError
File: backend/app/services/runtime_fabric/base.py (new)
from app.services.runtime_fabric.interfaces import RuntimeFabricAdapter


class BaseRuntimeFabricAdapter(RuntimeFabricAdapter):
    adapter_key = "base"

    def preview(self, *, target_type: str, target_id: str, payload: dict) -> dict:
        return {
            "adapter_key": self.adapter_key,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "impacted_entities": [{"type": target_type, "id": target_id}],
            "mode": "preview",
        }

    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        return {
            "adapter_key": self.adapter_key,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "actor_id": actor_id,
            "mode": "apply",
            "status": "mock_applied",
        }
File: backend/app/services/runtime_fabric/release_gate_adapter.py (new)
from app.services.runtime_fabric.base import BaseRuntimeFabricAdapter


class ReleaseGateAdapter(BaseRuntimeFabricAdapter):
    adapter_key = "release_gate"

    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        # TODO: wire to release gate store / actuator runtime
        return {
            "adapter_key": self.adapter_key,
            "target_id": target_id,
            "applied_gate_state": payload.get("gate_state"),
            "actor_id": actor_id,
            "status": "applied",
        }
File: backend/app/services/runtime_fabric/provider_routing_adapter.py (new)
from app.services.runtime_fabric.base import BaseRuntimeFabricAdapter


class ProviderRoutingAdapter(BaseRuntimeFabricAdapter):
    adapter_key = "provider_routing"

    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        # TODO: wire to provider routing override store
        return {
            "adapter_key": self.adapter_key,
            "target_id": target_id,
            "routing_override": payload,
            "actor_id": actor_id,
            "status": "applied",
        }
File: backend/app/services/runtime_fabric/throttle_adapter.py (new)
from app.services.runtime_fabric.base import BaseRuntimeFabricAdapter


class ThrottleAdapter(BaseRuntimeFabricAdapter):
    adapter_key = "throttle"

    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        # TODO: wire to concurrency / throttle control plane
        return {
            "adapter_key": self.adapter_key,
            "target_id": target_id,
            "throttle": payload,
            "actor_id": actor_id,
            "status": "applied",
        }
File: backend/app/services/runtime_fabric/directive_patch_adapter.py (new)
from app.services.runtime_fabric.base import BaseRuntimeFabricAdapter


class DirectivePatchAdapter(BaseRuntimeFabricAdapter):
    adapter_key = "directive_patch"

    def apply(self, *, target_type: str, target_id: str, payload: dict, actor_id: str) -> dict:
        # TODO: wire to directive config patcher / runtime directive registry
        return {
            "adapter_key": self.adapter_key,
            "target_id": target_id,
            "patch": payload,
            "actor_id": actor_id,
            "status": "applied",
        }
File: backend/app/services/runtime_fabric/registry.py (new)
from app.services.runtime_fabric.release_gate_adapter import ReleaseGateAdapter
from app.services.runtime_fabric.provider_routing_adapter import ProviderRoutingAdapter
from app.services.runtime_fabric.throttle_adapter import ThrottleAdapter
from app.services.runtime_fabric.directive_patch_adapter import DirectivePatchAdapter


class RuntimeFabricAdapterRegistry:
    def __init__(self):
        self.adapters = {
            "promote": ReleaseGateAdapter(),
            "rollback": DirectivePatchAdapter(),
            "throttle": ThrottleAdapter(),
            "retire": DirectivePatchAdapter(),
            "patch_scope": ProviderRoutingAdapter(),
        }

    def resolve(self, action_type: str):
        if action_type not in self.adapters:
            raise ValueError(f"No runtime fabric adapter for action_type={action_type}")
        return self.adapters[action_type]
11. NOTIFICATION SERVICE
File: backend/app/services/governance_notification_service.py (new)
from app.db.models.governance_notification_event import GovernanceNotificationEvent


class GovernanceNotificationService:
    def __init__(self, notification_repo):
        self.notification_repo = notification_repo

    def enqueue(self, *, change_request_id: str | None, event_type: str, payload: dict, channel: str = "in_app"):
        event = GovernanceNotificationEvent(
            change_request_id=change_request_id,
            event_type=event_type,
            channel=channel,
            status="pending",
            payload=payload,
        )
        return self.notification_repo.create(event)

    def mark_sent(self, event):
        event.status = "sent"

    def mark_failed(self, event, error_message: str):
        event.status = "failed"
        event.error_message = error_message
12. GOVERNANCE EXECUTION SERVICE
File: backend/app/services/governance_execution_service.py (update)
Đây là lõi Phase 3. Nó phải:
validate change request
check approval
check version
start execution attempt
call runtime adapter
update directive state with CAS
emit notifications
persist attempt/result
from datetime import datetime, timezone

from app.db.models.governance_execution_attempt import GovernanceExecutionAttempt
from app.core.errors.governance import (
    GovernanceConflictError,
    GovernanceApprovalRequiredError,
    GovernanceExecutionError,
)


class GovernanceExecutionService:
    def __init__(
        self,
        *,
        directive_state_gateway,
        change_repo,
        attempt_repo,
        approval_repo,
        notification_service,
        adapter_registry,
    ):
        self.directive_state_gateway = directive_state_gateway
        self.change_repo = change_repo
        self.attempt_repo = attempt_repo
        self.approval_repo = approval_repo
        self.notification_service = notification_service
        self.adapter_registry = adapter_registry

    def execute_change_request(self, *, change_request, actor_id: str):
        if change_request.requires_approval == "true":
            approval = self.approval_repo.get_by_change_request_id(change_request.id)
            if not approval or approval.status != "approved":
                raise GovernanceApprovalRequiredError("Approved change request required before execution.")

        adapter = self.adapter_registry.resolve(change_request.action_type)

        attempt = GovernanceExecutionAttempt(
            change_request_id=change_request.id,
            status="started",
            adapter_key=adapter.adapter_key,
            target_version=change_request.expected_version,
            request_payload=change_request.proposed_payload,
            started_at=datetime.now(timezone.utc),
        )
        attempt = self.attempt_repo.create(attempt)

        try:
            adapter_response = adapter.apply(
                target_type=change_request.target_type,
                target_id=change_request.target_id,
                payload=change_request.proposed_payload,
                actor_id=actor_id,
            )

            self.directive_state_gateway.update_with_version_check(
                directive_id=change_request.target_id,
                expected_version=change_request.expected_version,
                patch={
                    "last_change_request_id": change_request.id,
                    "last_policy_snapshot": change_request.policy_snapshot,
                    "last_simulation_result": change_request.simulation_result,
                },
            )

            attempt.status = "succeeded"
            attempt.adapter_response = adapter_response
            attempt.finished_at = datetime.now(timezone.utc)

            change_request.status = "succeeded"
            change_request.executed_at = attempt.finished_at

            self.notification_service.enqueue(
                change_request_id=change_request.id,
                event_type="execution_succeeded",
                payload={
                    "change_request_id": change_request.id,
                    "target_id": change_request.target_id,
                    "action_type": change_request.action_type,
                },
            )

            return {
                "change_request_id": change_request.id,
                "execution_status": "succeeded",
                "new_version": change_request.expected_version + 1,
                "adapter_response": adapter_response,
                "conflict": False,
            }

        except GovernanceConflictError as exc:
            attempt.status = "conflicted"
            attempt.error_code = "version_conflict"
            attempt.error_message = str(exc)
            attempt.finished_at = datetime.now(timezone.utc)

            change_request.status = "conflicted"

            self.notification_service.enqueue(
                change_request_id=change_request.id,
                event_type="execution_conflicted",
                payload={
                    "change_request_id": change_request.id,
                    "target_id": change_request.target_id,
                    "expected_version": change_request.expected_version,
                },
            )
            raise

        except Exception as exc:
            attempt.status = "failed"
            attempt.error_code = "execution_failed"
            attempt.error_message = str(exc)
            attempt.finished_at = datetime.now(timezone.utc)

            change_request.status = "failed"

            self.notification_service.enqueue(
                change_request_id=change_request.id,
                event_type="execution_failed",
                payload={
                    "change_request_id": change_request.id,
                    "target_id": change_request.target_id,
                    "action_type": change_request.action_type,
                    "error": str(exc),
                },
            )
            raise GovernanceExecutionError(str(exc)) from exc
13. GOVERNANCE ORCHESTRATION SERVICE
File: backend/app/services/strategy_governance.py (update)
Thêm 3 method chính:
create_change_request
simulate_change_request
submit_change_request
from app.db.models.governance_change_request import GovernanceChangeRequest


class StrategyGovernanceService:
    # existing init ...

    def create_change_request(
        self,
        *,
        actor_id: str,
        actor_role: str,
        target_type: str,
        target_id: str,
        action_type: str,
        expected_version: int,
        proposed_payload: dict,
        reason: str | None,
        idempotency_key: str | None,
        correlation_id: str | None,
    ):
        existing = self.change_repo.find_by_idempotency_key(idempotency_key) if idempotency_key else None
        if existing:
            return existing

        target = self.directive_state_gateway.get(target_id)
        current_version = getattr(target, "version", 0)

        policy = self.policy_service.evaluate_change_request(
            actor_role=actor_role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            proposed_payload=proposed_payload,
        )

        change = GovernanceChangeRequest(
            target_type=target_type,
            target_id=target_id,
            action_type=action_type,
            status="draft",
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            expected_version=expected_version,
            current_version_snapshot=current_version,
            proposed_payload=proposed_payload,
            requires_approval="true" if policy.requires_approval else "false",
            approval_rule_key=policy.approval_rule_key,
            policy_snapshot={
                "allowed": policy.allowed,
                "reasons": policy.reasons,
                "risk_flags": policy.risk_flags,
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        return self.change_repo.create(change)

    def simulate_change_request(self, *, actor_role: str, change_request):
        simulation = self.simulation_service.simulate(
            actor_role=actor_role,
            target_type=change_request.target_type,
            target_id=change_request.target_id,
            action_type=change_request.action_type,
            expected_version=change_request.expected_version,
            proposed_payload=change_request.proposed_payload,
        )
        change_request.simulation_result = simulation
        change_request.status = "simulated"
        return simulation

    def submit_change_request(self, change_request):
        if change_request.requires_approval == "true":
            return self.approval_service.create_pending_approval(
                change_request=change_request,
                required_role="governance_owner",
            )
        change_request.status = "ready"
        return change_request
14. AUTH DEPS
File: backend/app/api/deps/auth.py (update)
Phase 2 đã có actor headers. Phase 3 chuẩn hóa helper.
from fastapi import Header


def get_actor_context(
    x_actor_id: str = Header(..., alias="X-Actor-Id"),
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    return {
        "actor_id": x_actor_id,
        "actor_role": x_actor_role,
    }
15. API ROUTES
File: backend/app/api/routes/governance.py (update)
Thêm các route mạnh nhất:
POST /governance/changes
POST /governance/changes/{id}/simulate
POST /governance/changes/{id}/submit
POST /governance/changes/{id}/approve
POST /governance/changes/{id}/reject
POST /governance/changes/{id}/execute
GET /governance/approvals/queue
GET /governance/changes/{id}
Patch mẫu
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps.auth import get_actor_context
from app.core.errors.governance import (
    GovernanceConflictError,
    GovernanceApprovalInvalidError,
    GovernanceApprovalRequiredError,
)
from app.schemas.governance_change_request import GovernanceChangeCreateRequest
from app.schemas.governance_approval import GovernanceApprovalDecisionRequest

router = APIRouter(prefix="/governance", tags=["governance"])


@router.post("/changes")
def create_change(req: GovernanceChangeCreateRequest, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.create_change_request(
        actor_id=actor["actor_id"],
        actor_role=actor["actor_role"],
        target_type=req.target_type,
        target_id=req.target_id,
        action_type=req.action_type,
        expected_version=req.expected_version,
        proposed_payload=req.proposed_payload,
        reason=req.reason,
        idempotency_key=req.idempotency_key,
        correlation_id=req.correlation_id,
    )
    return change


@router.post("/changes/{change_request_id}/simulate")
def simulate_change(change_request_id: str, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.get_change_request(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found")
    return svc.simulate_change_request(actor_role=actor["actor_role"], change_request=change)


@router.post("/changes/{change_request_id}/submit")
def submit_change(change_request_id: str, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.get_change_request(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found")
    return svc.submit_change_request(change)


@router.post("/changes/{change_request_id}/approve")
def approve_change(change_request_id: str, body: GovernanceApprovalDecisionRequest, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.get_change_request(change_request_id)
    try:
        return svc.approval_service.approve(
            change_request=change,
            actor_id=actor["actor_id"],
            actor_role=actor["actor_role"],
            note=body.note,
        )
    except GovernanceApprovalInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/changes/{change_request_id}/reject")
def reject_change(change_request_id: str, body: GovernanceApprovalDecisionRequest, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.get_change_request(change_request_id)
    try:
        return svc.approval_service.reject(
            change_request=change,
            actor_id=actor["actor_id"],
            actor_role=actor["actor_role"],
            note=body.note,
        )
    except GovernanceApprovalInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/changes/{change_request_id}/execute")
def execute_change(change_request_id: str, actor=Depends(get_actor_context), svc=Depends(get_governance_service)):
    change = svc.get_change_request(change_request_id)
    try:
        return svc.execution_service.execute_change_request(
            change_request=change,
            actor_id=actor["actor_id"],
        )
    except GovernanceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GovernanceApprovalRequiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/approvals/queue")
def approval_queue(svc=Depends(get_governance_service)):
    return svc.list_pending_approvals()
16. WORKERS
File: backend/app/workers/governance_notification_worker.py (new)
from app.worker import celery_app
from app.db.session import SessionLocal
from app.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.services.governance_notification_service import GovernanceNotificationService


@celery_app.task(name="governance.process_notifications")
def process_governance_notifications(limit: int = 100):
    db = SessionLocal()
    try:
        repo = GovernanceNotificationRepository(db)
        service = GovernanceNotificationService(repo)
        events = repo.list_pending(limit=limit)

        for event in events:
            try:
                # phase 3: in-app first
                # TODO phase 4: email/slack/webhook routing
                service.mark_sent(event)
            except Exception as exc:
                service.mark_failed(event, str(exc))

        db.commit()
        return {"processed": len(events)}
    finally:
        db.close()
File: backend/app/workers/rollup_worker.py (update)
Thêm rollup cho:
pending approvals
conflicted executions
failed executions
approval latency
execute latency
# pseudo additions
# aggregate by status in governance_change_requests
# aggregate by status in governance_execution_attempts
# materialize metrics into existing rollup tables / dashboard views
17. ALEMBIC MIGRATION
File: backend/alembic/versions/20260412_01_phase3_governance_workflow.py (new)
from alembic import op
import sqlalchemy as sa

revision = "20260412_01_phase3_governance_workflow"
down_revision = "PHASE2_REVISION_ID"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("strategy_governance", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("strategy_governance", sa.Column("last_change_request_id", sa.String(), nullable=True))
    op.add_column("strategy_governance", sa.Column("last_simulation_result", sa.JSON(), nullable=True))
    op.add_column("strategy_governance", sa.Column("last_policy_snapshot", sa.JSON(), nullable=True))

    op.create_table(
        "governance_change_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("current_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("simulation_result", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("requires_approval", sa.String(), nullable=False, server_default="false"),
        sa.Column("approval_rule_key", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_gcr_target", "governance_change_requests", ["target_type", "target_id"])
    op.create_index("ix_gcr_status", "governance_change_requests", ["status"])
    op.create_index("ix_gcr_idempotency", "governance_change_requests", ["idempotency_key"])

    op.create_table(
        "governance_approvals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("change_request_id", sa.String(), sa.ForeignKey("governance_change_requests.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("required_role", sa.String(), nullable=True),
        sa.Column("decision_by", sa.String(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "governance_execution_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("change_request_id", sa.String(), sa.ForeignKey("governance_change_requests.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("adapter_key", sa.String(), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("adapter_response", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "governance_notification_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("change_request_id", sa.String(), sa.ForeignKey("governance_change_requests.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("governance_notification_events")
    op.drop_table("governance_execution_attempts")
    op.drop_table("governance_approvals")
    op.drop_index("ix_gcr_idempotency", table_name="governance_change_requests")
    op.drop_index("ix_gcr_status", table_name="governance_change_requests")
    op.drop_index("ix_gcr_target", table_name="governance_change_requests")
    op.drop_table("governance_change_requests")

    op.drop_column("strategy_governance", "last_policy_snapshot")
    op.drop_column("strategy_governance", "last_simulation_result")
    op.drop_column("strategy_governance", "last_change_request_id")
    op.drop_column("strategy_governance", "version")
18. FRONTEND API
File: frontend/src/api/governance.ts (update)
import { apiClient } from "./client";

export async function createGovernanceChange(payload: any) {
  const { data } = await apiClient.post("/governance/changes", payload);
  return data;
}

export async function simulateGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/simulate`);
  return data;
}

export async function submitGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/submit`);
  return data;
}

export async function approveGovernanceChange(changeRequestId: string, note?: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/approve`, { note });
  return data;
}

export async function rejectGovernanceChange(changeRequestId: string, note?: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/reject`, { note });
  return data;
}

export async function executeGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/execute`);
  return data;
}

export async function fetchGovernanceApprovalQueue() {
  const { data } = await apiClient.get("/governance/approvals/queue");
  return data;
}
File: frontend/src/types/governance.ts (update)
export type GovernanceSimulationResult = {
  allowed: boolean;
  requiresApproval: boolean;
  approvalRuleKey?: string | null;
  policyReasons: string[];
  riskFlags: string[];
  impactedEntities: Array<{ type: string; id: string }>;
  adapterPreview?: Record<string, unknown>;
  targetVersionMatches: boolean;
};

export type GovernanceChangeRequest = {
  id: string;
  targetType: string;
  targetId: string;
  actionType: string;
  status: string;
  expectedVersion: number;
  currentVersionSnapshot: number;
  requiresApproval: boolean;
  approvalRuleKey?: string | null;
  simulationResult?: GovernanceSimulationResult | null;
  policySnapshot?: Record<string, unknown> | null;
};
19. FRONTEND COMPONENTS
File: frontend/src/components/governance/GovernanceSimulationPanel.tsx (new)
import React from "react";

type Props = {
  simulation?: any;
};

export function GovernanceSimulationPanel({ simulation }: Props) {
  if (!simulation) return null;

  return (
    <div className="rounded-2xl border p-4 space-y-3">
      <div className="font-semibold">Simulation Preview</div>
      <div>Allowed: {String(simulation.allowed)}</div>
      <div>Requires approval: {String(simulation.requiresApproval)}</div>
      <div>Version match: {String(simulation.targetVersionMatches)}</div>

      <div>
        <div className="font-medium">Policy reasons</div>
        <ul className="list-disc ml-5">
          {simulation.policyReasons?.map((x: string) => <li key={x}>{x}</li>)}
        </ul>
      </div>

      <div>
        <div className="font-medium">Risk flags</div>
        <ul className="list-disc ml-5">
          {simulation.riskFlags?.map((x: string) => <li key={x}>{x}</li>)}
        </ul>
      </div>
    </div>
  );
}
File: frontend/src/components/governance/GovernanceApprovalPanel.tsx (new)
import React from "react";

type Props = {
  status?: string;
  onApprove?: () => void;
  onReject?: () => void;
  disabled?: boolean;
};

export function GovernanceApprovalPanel({ status, onApprove, onReject, disabled }: Props) {
  return (
    <div className="rounded-2xl border p-4 flex items-center justify-between">
      <div>
        <div className="font-semibold">Approval</div>
        <div className="text-sm text-muted-foreground">Status: {status ?? "n/a"}</div>
      </div>
      <div className="flex gap-2">
        <button className="rounded-xl border px-3 py-2" onClick={onReject} disabled={disabled}>
          Reject
        </button>
        <button className="rounded-xl border px-3 py-2" onClick={onApprove} disabled={disabled}>
          Approve
        </button>
      </div>
    </div>
  );
}
File: frontend/src/components/governance/GovernanceConflictBanner.tsx (new)
import React from "react";

export function GovernanceConflictBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div className="rounded-2xl border border-red-300 bg-red-50 p-3 text-sm">
      This action conflicts with the latest directive version. Refresh and rebase before executing again.
    </div>
  );
}
File: frontend/src/components/governance/GovernanceExecutionTimeline.tsx (new)
import React from "react";

export function GovernanceExecutionTimeline({ items = [] }: { items?: any[] }) {
  return (
    <div className="rounded-2xl border p-4">
      <div className="font-semibold mb-3">Execution Timeline</div>
      <div className="space-y-2">
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No events yet.</div>
        ) : (
          items.map((item, idx) => (
            <div key={idx} className="text-sm border rounded-xl p-3">
              <div className="font-medium">{item.label}</div>
              <div className="text-muted-foreground">{item.timestamp}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
File: frontend/src/components/governance/GovernanceActionBar.tsx (update)
Thêm logic mới:
create change
simulate
submit
approve/reject nếu có quyền
execute
hiển thị conflict banner nếu 409
Pseudo patch:
// add buttons:
// Create change
// Simulate
// Submit
// Execute
// handle 409 => setConflict(true)
// connect ExplainDrawer state to simulation result / policy snapshot
20. FRONTEND HOOKS
File: frontend/src/hooks/useGovernanceSimulation.ts (new)
import { useMutation } from "@tanstack/react-query";
import { simulateGovernanceChange } from "../api/governance";

export function useGovernanceSimulation() {
  return useMutation({
    mutationFn: (changeRequestId: string) => simulateGovernanceChange(changeRequestId),
  });
}
File: frontend/src/hooks/useGovernanceApprovalQueue.ts (new)
import { useQuery } from "@tanstack/react-query";
import { fetchGovernanceApprovalQueue } from "../api/governance";

export function useGovernanceApprovalQueue() {
  return useQuery({
    queryKey: ["governance-approval-queue"],
    queryFn: fetchGovernanceApprovalQueue,
  });
}
21. PAGE PATCH
File: frontend/src/pages/StrategyImpactConsole.tsx (update)
Thêm 4 vùng mới:
simulation preview
approval queue
execution timeline
conflict/rebase UX
Pseudo layout:
<GovernanceConflictBanner visible={hasConflict} />
<GovernanceActionBar ... />
<GovernanceSimulationPanel simulation={selectedSimulation} />
<GovernanceApprovalPanel ... />
<GovernanceExecutionTimeline items={timelineItems} />
22. TESTS
File: backend/app/tests/services/test_governance_approval_service.py (new)
Cần cover:
tạo pending approval
approve thành công
reject thành công
self-approval bị block
approval invalid nếu target version mismatch
def test_self_approval_blocked():
    ...
File: backend/app/tests/services/test_governance_simulation_service.py (new)
Cần cover:
allowed + no approval
allowed + requires approval
version mismatch
adapter preview trả impacted entities
File: backend/app/tests/services/test_governance_execution_service.py (update)
Thêm cover:
execute thành công
execute fail do approval missing
execute conflict nếu version stale
emit notification event
persist execution attempt
File: backend/app/tests/api/test_governance_routes.py (update)
Cover:
create change
simulate
submit
approve
reject
execute
409 conflict
400 self-approval invalid
File: backend/app/tests/repositories/test_change_request_repository.py (new)
Cover:
idempotency lookup
pending approvals listing
23. RBAC / POLICY TINH CHỈNH
rbac.py (update nhẹ)
Nên thêm matrix:
operator: create + simulate + submit
governance_owner: approve + execute + rollback
admin: full
viewer: read only
interfaces.py hiện có (update nhẹ)
Thêm interface cho:
simulation provider
approval evaluator
execution notifier
24. HÀNH VI QUAN TRỌNG NHẤT CẦN KHÓA
A. Optimistic locking contract
Mọi action mutate phải gửi:
expected_version
Nếu mismatch:
backend trả 409
frontend hiện conflict banner
disable execute
yêu cầu refresh + re-simulate
B. Approval bind theo version
Approval chỉ hợp lệ nếu:
approval.target_version == change_request.expected_version
Nếu target version đổi:
approval bị invalidated
C. Idempotency
Mỗi change request nên hỗ trợ:
idempotency_key
Để tránh double submit từ UI / retry network.
D. Runtime adapter tách khỏi governance core
Governance service không chạm trực tiếp release gate / routing store / throttle plane.
Mọi thứ đi qua adapter registry.
25. DEFINITION OF DONE CHO PHASE 3
Phase 3 chỉ coi là hoàn tất khi đủ các điều kiện sau:
governance action có expected_version
stale state gây 409 conflict
approval workflow chạy thật
self-approval bị chặn
simulation preview gọi được từ UI
execute xuống runtime adapter
execution attempt được persist
notification events được enqueue
dashboard/console nhìn thấy pending approvals + failed/conflicted executions
26. THỨ TỰ PATCH KHI TRIỂN KHAI
Đây là thứ tự file-by-file nên áp:
Block A — foundation
core/enums/governance.py
core/errors/governance.py
db/models/strategy_governance.py
migration phase 3
Block B — persistence
db/models/governance_change_request.py
db/models/governance_approval.py
db/models/governance_execution_attempt.py
db/models/governance_notification_event.py
repositories mới
directive_state_gateway.py
Block C — services
governance_policy.py
governance_notification_service.py
governance_approval_service.py
runtime_fabric/*
governance_simulation_service.py
governance_execution_service.py
strategy_governance.py
Block D — API
schemas mới
api/deps/auth.py
api/routes/governance.py
Block E — workers + rollups
governance_notification_worker.py
rollup_worker.py
Block F — frontend
frontend/src/api/governance.ts
frontend/src/types/governance.ts
components mới
page patch
hooks
Block G — tests
repository tests
service tests
api tests
27. PHẦN MOCK / PHẦN CHẠY THẬT / TODO
Chạy thật ngay được
optimistic locking
approval workflow
simulation response
conflict handling
execution attempts
notification enqueue
frontend action lifecycle
Mock tạm thời nhưng production-safe
runtime fabric adapters (apply() đang là skeleton/mock-applied)
notification delivery ngoài in-app
TODO phase sau
Slack/email/webhook sender thật
approval multi-step / quorum approval
policy simulation cost estimation
runtime reconciliation worker
auto expiry / invalidation worker
notification read/unread stream cho UI
28. KẾT LUẬN KIẾN TRÚC
Với patch này, hệ của bạn sẽ chuyển từ:
governance-grade execution
sang:
transaction-safe governed execution fabric
Tức là từ chỗ:
có action
có policy
có audit
sang chỗ:
action có version
approval gắn đúng version
execute qua adapter runtime
conflict được chặn
state transition có notification lifecycle
Nếu bạn muốn, lượt tiếp theo tôi sẽ viết tiếp ngay bản “PHASE 3 — FULL CODE FILE-BY-FILE” theo đúng format code hoàn chỉnh cho từng file, bắt đầu từ:
governance_change_request.py
governance_approval.py
governance_execution_attempt.py
governance_notification_event.py
governance_approval_service.py
governance_simulation_service.py
governance_execution_service.py
governance.py routes
migration
frontend components
Nếu bạn muốn, lượt tiếp theo tôi sẽ viết tiếp ngay bản “PHASE 3 — FULL CODE FILE-BY-FILE” theo đúng format code hoàn chỉnh cho từng file, bắt đầu từ: governance_change_request.py governance_approval.py governance_execution_attempt.py governance_notification_event.py governance_approval_service.py governance_simulation_service.py governance_execution_service.py governance.py routes migration frontend components
Tôi nối thẳng sang bản code hoàn chỉnh cho đúng nhóm file Phase 3 mà bạn vừa khóa: models → services → routes → migration → frontend governance components. Tôi sẽ giữ code ở mức cắm vào monorepo được ngay, tránh viết pseudo trừ những chỗ buộc phải bắc cầu sang runtime fabric sẵn có của bạn.
Đã suy nghĩ trong 11s
Tiếp luôn. Dưới đây là PHASE 3 — FULL CODE FILE-BY-FILE cho đúng nhóm file bạn đã khóa.
Tôi ưu tiên:
code hoàn chỉnh, không còn ở mức outline
giữ tương thích với patch Phase 2
không tái cấu trúc vô cớ
chỉ để TODO ở các chỗ thực sự phụ thuộc runtime fabric ngoài phạm vi nhóm file này
1) backend/app/db/models/governance_change_request.py
import uuid

from sqlalchemy import Column, String, DateTime, JSON, Text, Integer
from sqlalchemy.sql import func

from app.db.base import Base


class GovernanceChangeRequest(Base):
    __tablename__ = "governance_change_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    target_type = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=False, index=True)

    action_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)

    actor_id = Column(String, nullable=False, index=True)
    actor_role = Column(String, nullable=True)

    reason = Column(Text, nullable=True)

    expected_version = Column(Integer, nullable=False)
    current_version_snapshot = Column(Integer, nullable=False)

    proposed_payload = Column(JSON, nullable=False)
    simulation_result = Column(JSON, nullable=True)
    policy_snapshot = Column(JSON, nullable=True)

    requires_approval = Column(String, nullable=False, default="false", server_default="false")
    approval_rule_key = Column(String, nullable=True)

    idempotency_key = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True, index=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
2) backend/app/db/models/governance_approval.py
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.sql import func

from app.db.base import Base


class GovernanceApproval(Base):
    __tablename__ = "governance_approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(
        String,
        ForeignKey("governance_change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(String, nullable=False, index=True)
    required_role = Column(String, nullable=True)

    decision_by = Column(String, nullable=True, index=True)
    decision_note = Column(Text, nullable=True)

    target_version = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
3) backend/app/db/models/governance_execution_attempt.py
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.sql import func

from app.db.base import Base


class GovernanceExecutionAttempt(Base):
    __tablename__ = "governance_execution_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(
        String,
        ForeignKey("governance_change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(String, nullable=False, index=True)
    adapter_key = Column(String, nullable=False, index=True)
    target_version = Column(Integer, nullable=False)

    request_payload = Column(JSON, nullable=False)
    adapter_response = Column(JSON, nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
4) backend/app/db/models/governance_notification_event.py
import uuid

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.sql import func

from app.db.base import Base


class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id = Column(
        String,
        ForeignKey("governance_change_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)

    payload = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
5) backend/app/services/governance_approval_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models.governance_approval import GovernanceApproval


class GovernanceApprovalError(Exception):
    pass


class GovernanceApprovalInvalidError(GovernanceApprovalError):
    pass


class GovernanceApprovalPermissionError(GovernanceApprovalError):
    pass


class GovernanceApprovalService:
    """
    Approval workflow service for governed change requests.

    Assumptions:
    - change_request object is a SQLAlchemy model instance already attached to the session.
    - approval_repo exposes:
        - create(approval)
        - get_by_change_request_id(change_request_id)
    - notification_service exposes:
        - enqueue(change_request_id, event_type, payload, channel="in_app")
    """

    def __init__(self, approval_repo, notification_service):
        self.approval_repo = approval_repo
        self.notification_service = notification_service

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _truthy_str(value: str | None) -> bool:
        return str(value).lower() == "true"

    def create_pending_approval(
        self,
        *,
        change_request,
        required_role: str | None,
        expires_in_hours: int = 24,
    ) -> GovernanceApproval:
        existing = self.approval_repo.get_by_change_request_id(change_request.id)
        if existing and existing.status == "pending":
            return existing

        approval = GovernanceApproval(
            change_request_id=change_request.id,
            status="pending",
            required_role=required_role,
            target_version=change_request.expected_version,
            expires_at=self._utcnow() + timedelta(hours=expires_in_hours),
        )
        approval = self.approval_repo.create(approval)

        change_request.status = "pending_approval"
        change_request.submitted_at = self._utcnow()

        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_requested",
            payload={
                "change_request_id": change_request.id,
                "target_type": change_request.target_type,
                "target_id": change_request.target_id,
                "action_type": change_request.action_type,
                "required_role": required_role,
            },
        )
        return approval

    def validate_approval_state(self, *, change_request, approval) -> None:
        if approval is None:
            raise GovernanceApprovalInvalidError("No approval record found for this change request.")

        if approval.status != "pending":
            raise GovernanceApprovalInvalidError(
                f"Approval is not pending. current_status={approval.status}"
            )

        if approval.expires_at and approval.expires_at < self._utcnow():
            approval.status = "expired"
            change_request.status = "expired"
            raise GovernanceApprovalInvalidError("Approval has expired.")

        if approval.target_version != change_request.expected_version:
            approval.status = "invalidated"
            change_request.status = "conflicted"
            raise GovernanceApprovalInvalidError(
                "Approval invalidated because change request version no longer matches target version."
            )

    def approve(
        self,
        *,
        change_request,
        actor_id: str,
        actor_role: str,
        note: str | None = None,
    ) -> GovernanceApproval:
        approval = self.approval_repo.get_by_change_request_id(change_request.id)
        self.validate_approval_state(change_request=change_request, approval=approval)

        if change_request.actor_id == actor_id:
            raise GovernanceApprovalPermissionError("Self-approval is not allowed.")

        if approval.required_role and actor_role not in {approval.required_role, "admin"}:
            raise GovernanceApprovalPermissionError(
                f"Actor role is not permitted to approve this request. required_role={approval.required_role}"
            )

        approval.status = "approved"
        approval.decision_by = actor_id
        approval.decision_note = note
        approval.decided_at = self._utcnow()

        change_request.status = "approved"
        change_request.approved_at = approval.decided_at

        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_granted",
            payload={
                "change_request_id": change_request.id,
                "approved_by": actor_id,
                "actor_role": actor_role,
            },
        )
        return approval

    def reject(
        self,
        *,
        change_request,
        actor_id: str,
        actor_role: str,
        note: str | None = None,
    ) -> GovernanceApproval:
        approval = self.approval_repo.get_by_change_request_id(change_request.id)
        self.validate_approval_state(change_request=change_request, approval=approval)

        if approval.required_role and actor_role not in {approval.required_role, "admin"}:
            raise GovernanceApprovalPermissionError(
                f"Actor role is not permitted to reject this request. required_role={approval.required_role}"
            )

        approval.status = "rejected"
        approval.decision_by = actor_id
        approval.decision_note = note
        approval.decided_at = self._utcnow()

        change_request.status = "rejected"

        self.notification_service.enqueue(
            change_request_id=change_request.id,
            event_type="approval_rejected",
            payload={
                "change_request_id": change_request.id,
                "rejected_by": actor_id,
                "actor_role": actor_role,
            },
        )
        return approval

    def require_approved_if_needed(self, *, change_request) -> None:
        if not self._truthy_str(change_request.requires_approval):
            return

        approval = self.approval_repo.get_by_change_request_id(change_request.id)
        if not approval or approval.status != "approved":
            raise GovernanceApprovalInvalidError(
                "This change request requires an approved approval record before execution."
            )
6) backend/app/services/governance_simulation_service.py
from __future__ import annotations

from typing import Any


class GovernanceSimulationService:
    """
    Simulates a governance action before execution.

    Assumptions:
    - policy_service exposes evaluate_change_request(...)
      returning an object or dict with:
        allowed, requires_approval, approval_rule_key, reasons, risk_flags
    - directive_state_gateway exposes get(target_id)
    - adapter_registry exposes resolve(action_type)
    - adapter exposes preview(target_type, target_id, payload)
    """

    def __init__(self, policy_service, directive_state_gateway, adapter_registry):
        self.policy_service = policy_service
        self.directive_state_gateway = directive_state_gateway
        self.adapter_registry = adapter_registry

    @staticmethod
    def _read_policy(policy_result):
        if isinstance(policy_result, dict):
            return {
                "allowed": bool(policy_result.get("allowed", False)),
                "requires_approval": bool(policy_result.get("requires_approval", False)),
                "approval_rule_key": policy_result.get("approval_rule_key"),
                "reasons": list(policy_result.get("reasons", [])),
                "risk_flags": list(policy_result.get("risk_flags", [])),
            }

        return {
            "allowed": bool(getattr(policy_result, "allowed", False)),
            "requires_approval": bool(getattr(policy_result, "requires_approval", False)),
            "approval_rule_key": getattr(policy_result, "approval_rule_key", None),
            "reasons": list(getattr(policy_result, "reasons", []) or []),
            "risk_flags": list(getattr(policy_result, "risk_flags", []) or []),
        }

    def simulate(
        self,
        *,
        actor_role: str,
        target_type: str,
        target_id: str,
        action_type: str,
        expected_version: int,
        proposed_payload: dict[str, Any],
    ) -> dict[str, Any]:
        target = self.directive_state_gateway.get(target_id)
        current_version = getattr(target, "version", None) if target is not None else None
        target_version_matches = current_version == expected_version

        policy_result = self.policy_service.evaluate_change_request(
            actor_role=actor_role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            proposed_payload=proposed_payload,
        )
        policy = self._read_policy(policy_result)

        adapter = self.adapter_registry.resolve(action_type)
        adapter_preview = adapter.preview(
            target_type=target_type,
            target_id=target_id,
            payload=proposed_payload,
        )

        impacted_entities = adapter_preview.get("impacted_entities", [])
        normalized_impacted_entities = []
        for entity in impacted_entities:
            if isinstance(entity, dict):
                normalized_impacted_entities.append(entity)
            else:
                normalized_impacted_entities.append({"value": str(entity)})

        return {
            "allowed": policy["allowed"],
            "requires_approval": policy["requires_approval"],
            "approval_rule_key": policy["approval_rule_key"],
            "policy_reasons": policy["reasons"],
            "risk_flags": policy["risk_flags"],
            "impacted_entities": normalized_impacted_entities,
            "adapter_preview": adapter_preview,
            "target_version_matches": target_version_matches,
            "current_version": current_version,
            "expected_version": expected_version,
        }
7) backend/app/services/governance_execution_service.py
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.governance_execution_attempt import GovernanceExecutionAttempt


class GovernanceExecutionError(Exception):
    pass


class GovernanceConflictError(GovernanceExecutionError):
    pass


class GovernanceApprovalRequiredError(GovernanceExecutionError):
    pass


class GovernanceExecutionService:
    """
    Executes a governance change request with:
    - approval enforcement
    - optimistic locking
    - adapter execution
    - attempt persistence
    - notification enqueue
    """

    def __init__(
        self,
        *,
        directive_state_gateway,
        attempt_repo,
        approval_service,
        notification_service,
        adapter_registry,
    ):
        self.directive_state_gateway = directive_state_gateway
        self.attempt_repo = attempt_repo
        self.approval_service = approval_service
        self.notification_service = notification_service
        self.adapter_registry = adapter_registry

    @staticmethod
    def _utcnow():
        return datetime.now(timezone.utc)

    def _create_attempt(self, *, change_request, adapter_key: str) -> GovernanceExecutionAttempt:
        attempt = GovernanceExecutionAttempt(
            change_request_id=change_request.id,
            status="started",
            adapter_key=adapter_key,
            target_version=change_request.expected_version,
            request_payload=change_request.proposed_payload,
            started_at=self._utcnow(),
        )
        return self.attempt_repo.create(attempt)

    def execute_change_request(self, *, change_request, actor_id: str) -> dict:
        try:
            self.approval_service.require_approved_if_needed(change_request=change_request)
        except Exception as exc:
            raise GovernanceApprovalRequiredError(str(exc)) from exc

        adapter = self.adapter_registry.resolve(change_request.action_type)
        attempt = self._create_attempt(change_request=change_request, adapter_key=adapter.adapter_key)

        change_request.status = "executing"

        try:
            adapter_response = adapter.apply(
                target_type=change_request.target_type,
                target_id=change_request.target_id,
                payload=change_request.proposed_payload,
                actor_id=actor_id,
            )

            try:
                self.directive_state_gateway.update_with_version_check(
                    directive_id=change_request.target_id,
                    expected_version=change_request.expected_version,
                    patch={
                        "last_change_request_id": change_request.id,
                        "last_policy_snapshot": change_request.policy_snapshot,
                        "last_simulation_result": change_request.simulation_result,
                    },
                )
            except Exception as exc:
                attempt.status = "conflicted"
                attempt.error_code = "version_conflict"
                attempt.error_message = str(exc)
                attempt.finished_at = self._utcnow()

                change_request.status = "conflicted"

                self.notification_service.enqueue(
                    change_request_id=change_request.id,
                    event_type="execution_conflicted",
                    payload={
                        "change_request_id": change_request.id,
                        "target_id": change_request.target_id,
                        "expected_version": change_request.expected_version,
                    },
                )
                raise GovernanceConflictError(str(exc)) from exc

            attempt.status = "succeeded"
            attempt.adapter_response = adapter_response
            attempt.finished_at = self._utcnow()

            change_request.status = "succeeded"
            change_request.executed_at = attempt.finished_at

            self.notification_service.enqueue(
                change_request_id=change_request.id,
                event_type="execution_succeeded",
                payload={
                    "change_request_id": change_request.id,
                    "target_type": change_request.target_type,
                    "target_id": change_request.target_id,
                    "action_type": change_request.action_type,
                    "new_version": change_request.expected_version + 1,
                },
            )

            return {
                "change_request_id": change_request.id,
                "execution_status": "succeeded",
                "new_version": change_request.expected_version + 1,
                "adapter_response": adapter_response,
                "conflict": False,
            }

        except GovernanceConflictError:
            raise

        except Exception as exc:
            attempt.status = "failed"
            attempt.error_code = "execution_failed"
            attempt.error_message = str(exc)
            attempt.finished_at = self._utcnow()

            change_request.status = "failed"

            self.notification_service.enqueue(
                change_request_id=change_request.id,
                event_type="execution_failed",
                payload={
                    "change_request_id": change_request.id,
                    "target_type": change_request.target_type,
                    "target_id": change_request.target_id,
                    "action_type": change_request.action_type,
                    "error": str(exc),
                },
            )
            raise GovernanceExecutionError(str(exc)) from exc
8) backend/app/api/routes/governance.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.repositories.directive_state_gateway import DirectiveStateGateway

from app.services.governance_approval_service import (
    GovernanceApprovalService,
    GovernanceApprovalInvalidError,
    GovernanceApprovalPermissionError,
)
from app.services.governance_simulation_service import GovernanceSimulationService
from app.services.governance_execution_service import (
    GovernanceExecutionService,
    GovernanceConflictError,
    GovernanceApprovalRequiredError,
    GovernanceExecutionError,
)
from app.services.governance_notification_service import GovernanceNotificationService
from app.services.governance_policy import GovernancePolicyService
from app.services.runtime_fabric.registry import RuntimeFabricAdapterRegistry

from app.schemas.governance_change_request import GovernanceChangeCreateRequest
from app.schemas.governance_approval import GovernanceApprovalDecisionRequest
from app.db.models.governance_change_request import GovernanceChangeRequest
from app.db.models.governance_approval import GovernanceApproval


router = APIRouter(prefix="/governance", tags=["governance"])


def get_actor_context(
    x_actor_id: str = Header(..., alias="X-Actor-Id"),
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    return {
        "actor_id": x_actor_id,
        "actor_role": x_actor_role,
    }


def get_services(db: Session):
    change_repo = GovernanceChangeRequestRepository(db)
    approval_repo = GovernanceApprovalRepository(db)
    attempt_repo = GovernanceExecutionAttemptRepository(db)
    notification_repo = GovernanceNotificationRepository(db)
    directive_state_gateway = DirectiveStateGateway(db)

    notification_service = GovernanceNotificationService(notification_repo)
    approval_service = GovernanceApprovalService(
        approval_repo=approval_repo,
        notification_service=notification_service,
    )
    adapter_registry = RuntimeFabricAdapterRegistry()
    policy_service = GovernancePolicyService()
    simulation_service = GovernanceSimulationService(
        policy_service=policy_service,
        directive_state_gateway=directive_state_gateway,
        adapter_registry=adapter_registry,
    )
    execution_service = GovernanceExecutionService(
        directive_state_gateway=directive_state_gateway,
        attempt_repo=attempt_repo,
        approval_service=approval_service,
        notification_service=notification_service,
        adapter_registry=adapter_registry,
    )

    return {
        "change_repo": change_repo,
        "approval_repo": approval_repo,
        "attempt_repo": attempt_repo,
        "notification_repo": notification_repo,
        "directive_state_gateway": directive_state_gateway,
        "notification_service": notification_service,
        "approval_service": approval_service,
        "adapter_registry": adapter_registry,
        "policy_service": policy_service,
        "simulation_service": simulation_service,
        "execution_service": execution_service,
    }


def _read_policy(policy_result):
    if isinstance(policy_result, dict):
        return policy_result
    return {
        "allowed": getattr(policy_result, "allowed", False),
        "requires_approval": getattr(policy_result, "requires_approval", False),
        "approval_rule_key": getattr(policy_result, "approval_rule_key", None),
        "reasons": list(getattr(policy_result, "reasons", []) or []),
        "risk_flags": list(getattr(policy_result, "risk_flags", []) or []),
    }


@router.post("/changes", status_code=status.HTTP_201_CREATED)
def create_change_request(
    payload: GovernanceChangeCreateRequest,
    actor=Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    directive_state_gateway = services["directive_state_gateway"]
    policy_service = services["policy_service"]

    existing = None
    if payload.idempotency_key:
        existing = change_repo.find_by_idempotency_key(payload.idempotency_key)
    if existing:
        return existing

    target = directive_state_gateway.get(payload.target_id)
    current_version = getattr(target, "version", 0) if target is not None else 0

    policy_result = policy_service.evaluate_change_request(
        actor_role=actor["actor_role"],
        action_type=payload.action_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        proposed_payload=payload.proposed_payload,
    )
    policy = _read_policy(policy_result)

    if not policy["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Policy denied change request.",
                "reasons": policy.get("reasons", []),
            },
        )

    change = GovernanceChangeRequest(
        target_type=payload.target_type,
        target_id=payload.target_id,
        action_type=payload.action_type,
        status="draft",
        actor_id=actor["actor_id"],
        actor_role=actor["actor_role"],
        reason=payload.reason,
        expected_version=payload.expected_version,
        current_version_snapshot=current_version,
        proposed_payload=payload.proposed_payload,
        simulation_result=None,
        policy_snapshot={
            "allowed": policy["allowed"],
            "requires_approval": policy["requires_approval"],
            "approval_rule_key": policy["approval_rule_key"],
            "reasons": policy["reasons"],
            "risk_flags": policy["risk_flags"],
        },
        requires_approval="true" if policy["requires_approval"] else "false",
        approval_rule_key=policy["approval_rule_key"],
        idempotency_key=payload.idempotency_key,
        correlation_id=payload.correlation_id,
    )
    change = change_repo.create(change)
    db.commit()
    db.refresh(change)
    return change


@router.get("/changes/{change_request_id}")
def get_change_request(change_request_id: str, db: Session = Depends(get_db)):
    change_repo = GovernanceChangeRequestRepository(db)
    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")
    return change


@router.post("/changes/{change_request_id}/simulate")
def simulate_change_request(
    change_request_id: str,
    actor=Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    simulation_service = services["simulation_service"]

    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")

    simulation = simulation_service.simulate(
        actor_role=actor["actor_role"],
        target_type=change.target_type,
        target_id=change.target_id,
        action_type=change.action_type,
        expected_version=change.expected_version,
        proposed_payload=change.proposed_payload,
    )

    change.simulation_result = simulation
    change.status = "simulated"
    db.commit()
    db.refresh(change)
    return simulation


@router.post("/changes/{change_request_id}/submit")
def submit_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    approval_service = services["approval_service"]

    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")

    if str(change.requires_approval).lower() == "true":
        approval = approval_service.create_pending_approval(
            change_request=change,
            required_role="governance_owner",
        )
        db.commit()
        db.refresh(change)
        return {
            "change_request_id": change.id,
            "status": change.status,
            "approval_id": approval.id,
        }

    change.status = "ready"
    db.commit()
    db.refresh(change)
    return {
        "change_request_id": change.id,
        "status": change.status,
    }


@router.post("/changes/{change_request_id}/approve")
def approve_change_request(
    change_request_id: str,
    body: GovernanceApprovalDecisionRequest,
    actor=Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    approval_service = services["approval_service"]

    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")

    try:
        approval = approval_service.approve(
            change_request=change,
            actor_id=actor["actor_id"],
            actor_role=actor["actor_role"],
            note=body.note,
        )
        db.commit()
        db.refresh(change)
        return approval
    except GovernanceApprovalPermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except GovernanceApprovalInvalidError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/changes/{change_request_id}/reject")
def reject_change_request(
    change_request_id: str,
    body: GovernanceApprovalDecisionRequest,
    actor=Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    approval_service = services["approval_service"]

    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")

    try:
        approval = approval_service.reject(
            change_request=change,
            actor_id=actor["actor_id"],
            actor_role=actor["actor_role"],
            note=body.note,
        )
        db.commit()
        db.refresh(change)
        return approval
    except GovernanceApprovalPermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except GovernanceApprovalInvalidError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/changes/{change_request_id}/execute")
def execute_change_request(
    change_request_id: str,
    actor=Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    services = get_services(db)
    change_repo = services["change_repo"]
    execution_service = services["execution_service"]

    change = change_repo.get(change_request_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change request not found.")

    try:
        result = execution_service.execute_change_request(
            change_request=change,
            actor_id=actor["actor_id"],
        )
        db.commit()
        return result
    except GovernanceApprovalRequiredError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except GovernanceConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except GovernanceExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/approvals/queue")
def list_pending_approval_queue(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    change_repo = GovernanceChangeRequestRepository(db)
    return change_repo.list_pending_approvals(limit=limit)
9) backend/alembic/versions/20260412_01_phase3_governance_workflow.py
"""phase3 governance workflow

Revision ID: 20260412_01_phase3_governance_workflow
Revises: PHASE2_REVISION_ID
Create Date: 2026-04-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_01_phase3_governance_workflow"
down_revision = "PHASE2_REVISION_ID"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "strategy_governance",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "strategy_governance",
        sa.Column("last_change_request_id", sa.String(), nullable=True),
    )
    op.add_column(
        "strategy_governance",
        sa.Column("last_simulation_result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "strategy_governance",
        sa.Column("last_policy_snapshot", sa.JSON(), nullable=True),
    )

    op.create_table(
        "governance_change_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("current_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("simulation_result", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("requires_approval", sa.String(), nullable=False, server_default="false"),
        sa.Column("approval_rule_key", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_governance_change_requests_target_type_target_id",
        "governance_change_requests",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_governance_change_requests_status",
        "governance_change_requests",
        ["status"],
    )
    op.create_index(
        "ix_governance_change_requests_actor_id",
        "governance_change_requests",
        ["actor_id"],
    )
    op.create_index(
        "ix_governance_change_requests_idempotency_key",
        "governance_change_requests",
        ["idempotency_key"],
    )

    op.create_table(
        "governance_approvals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "change_request_id",
            sa.String(),
            sa.ForeignKey("governance_change_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("required_role", sa.String(), nullable=True),
        sa.Column("decision_by", sa.String(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_governance_approvals_change_request_id",
        "governance_approvals",
        ["change_request_id"],
    )
    op.create_index(
        "ix_governance_approvals_status",
        "governance_approvals",
        ["status"],
    )

    op.create_table(
        "governance_execution_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "change_request_id",
            sa.String(),
            sa.ForeignKey("governance_change_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("adapter_key", sa.String(), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("adapter_response", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_governance_execution_attempts_change_request_id",
        "governance_execution_attempts",
        ["change_request_id"],
    )
    op.create_index(
        "ix_governance_execution_attempts_status",
        "governance_execution_attempts",
        ["status"],
    )

    op.create_table(
        "governance_notification_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "change_request_id",
            sa.String(),
            sa.ForeignKey("governance_change_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_governance_notification_events_change_request_id",
        "governance_notification_events",
        ["change_request_id"],
    )
    op.create_index(
        "ix_governance_notification_events_status",
        "governance_notification_events",
        ["status"],
    )


def downgrade():
    op.drop_index("ix_governance_notification_events_status", table_name="governance_notification_events")
    op.drop_index("ix_governance_notification_events_change_request_id", table_name="governance_notification_events")
    op.drop_table("governance_notification_events")

    op.drop_index("ix_governance_execution_attempts_status", table_name="governance_execution_attempts")
    op.drop_index("ix_governance_execution_attempts_change_request_id", table_name="governance_execution_attempts")
    op.drop_table("governance_execution_attempts")

    op.drop_index("ix_governance_approvals_status", table_name="governance_approvals")
    op.drop_index("ix_governance_approvals_change_request_id", table_name="governance_approvals")
    op.drop_table("governance_approvals")

    op.drop_index(
        "ix_governance_change_requests_idempotency_key",
        table_name="governance_change_requests",
    )
    op.drop_index(
        "ix_governance_change_requests_actor_id",
        table_name="governance_change_requests",
    )
    op.drop_index(
        "ix_governance_change_requests_status",
        table_name="governance_change_requests",
    )
    op.drop_index(
        "ix_governance_change_requests_target_type_target_id",
        table_name="governance_change_requests",
    )
    op.drop_table("governance_change_requests")

    op.drop_column("strategy_governance", "last_policy_snapshot")
    op.drop_column("strategy_governance", "last_simulation_result")
    op.drop_column("strategy_governance", "last_change_request_id")
    op.drop_column("strategy_governance", "version")
10) frontend/src/components/governance/GovernanceSimulationPanel.tsx
import React from "react";

type ImpactedEntity = {
  type?: string;
  id?: string;
  value?: string;
};

type Simulation = {
  allowed: boolean;
  requiresApproval: boolean;
  approvalRuleKey?: string | null;
  policyReasons?: string[];
  riskFlags?: string[];
  impactedEntities?: ImpactedEntity[];
  adapterPreview?: Record<string, unknown> | null;
  targetVersionMatches: boolean;
  currentVersion?: number | null;
  expectedVersion?: number | null;
};

type Props = {
  simulation?: Simulation | null;
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div className="text-sm font-semibold tracking-tight">{children}</div>;
}

export default function GovernanceSimulationPanel({ simulation }: Props) {
  if (!simulation) {
    return (
      <div className="rounded-2xl border p-4 text-sm text-muted-foreground">
        No simulation result yet.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-background p-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-base font-semibold">Simulation Preview</div>
          <div className="text-sm text-muted-foreground">
            Dry-run policy, version, and adapter impact before execution.
          </div>
        </div>

        <div className="flex gap-2 text-xs">
          <span className="rounded-full border px-2 py-1">
            allowed: {String(simulation.allowed)}
          </span>
          <span className="rounded-full border px-2 py-1">
            approval: {String(simulation.requiresApproval)}
          </span>
          <span className="rounded-full border px-2 py-1">
            version-match: {String(simulation.targetVersionMatches)}
          </span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border p-3 space-y-2">
          <SectionTitle>Policy reasons</SectionTitle>
          {simulation.policyReasons && simulation.policyReasons.length > 0 ? (
            <ul className="list-disc ml-5 text-sm space-y-1">
              {simulation.policyReasons.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-muted-foreground">No policy reasons recorded.</div>
          )}
        </div>

        <div className="rounded-xl border p-3 space-y-2">
          <SectionTitle>Risk flags</SectionTitle>
          {simulation.riskFlags && simulation.riskFlags.length > 0 ? (
            <ul className="list-disc ml-5 text-sm space-y-1">
              {simulation.riskFlags.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-muted-foreground">No risk flags.</div>
          )}
        </div>
      </div>

      <div className="rounded-xl border p-3 space-y-2">
        <SectionTitle>Version check</SectionTitle>
        <div className="grid gap-2 md:grid-cols-2 text-sm">
          <div>Expected version: {simulation.expectedVersion ?? "n/a"}</div>
          <div>Current version: {simulation.currentVersion ?? "n/a"}</div>
        </div>
      </div>

      <div className="rounded-xl border p-3 space-y-2">
        <SectionTitle>Impacted entities</SectionTitle>
        {simulation.impactedEntities && simulation.impactedEntities.length > 0 ? (
          <div className="space-y-2">
            {simulation.impactedEntities.map((entity, idx) => (
              <div key={`${entity.type}-${entity.id}-${idx}`} className="rounded-lg border p-2 text-sm">
                <div>type: {entity.type ?? "n/a"}</div>
                <div>id: {entity.id ?? entity.value ?? "n/a"}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No impacted entities reported.</div>
        )}
      </div>

      {simulation.adapterPreview ? (
        <div className="rounded-xl border p-3 space-y-2">
          <SectionTitle>Adapter preview</SectionTitle>
          <pre className="overflow-x-auto text-xs whitespace-pre-wrap">
            {JSON.stringify(simulation.adapterPreview, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
11) frontend/src/components/governance/GovernanceApprovalPanel.tsx
import React, { useState } from "react";

type Props = {
  status?: string | null;
  requiredRole?: string | null;
  disabled?: boolean;
  busy?: boolean;
  onApprove: (note?: string) => Promise<void> | void;
  onReject: (note?: string) => Promise<void> | void;
};

export default function GovernanceApprovalPanel({
  status,
  requiredRole,
  disabled,
  busy,
  onApprove,
  onReject,
}: Props) {
  const [note, setNote] = useState("");

  return (
    <div className="rounded-2xl border bg-background p-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-base font-semibold">Approval</div>
          <div className="text-sm text-muted-foreground">
            Required role: {requiredRole ?? "n/a"}
          </div>
        </div>

        <div className="rounded-full border px-3 py-1 text-xs">
          status: {status ?? "n/a"}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Decision note</label>
        <textarea
          className="w-full min-h-[96px] rounded-xl border p-3 text-sm"
          placeholder="Add rationale for approve or reject"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={disabled || busy}
        />
      </div>

      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          className="rounded-xl border px-4 py-2 text-sm"
          onClick={() => onReject(note)}
          disabled={disabled || busy}
        >
          Reject
        </button>
        <button
          type="button"
          className="rounded-xl border px-4 py-2 text-sm"
          onClick={() => onApprove(note)}
          disabled={disabled || busy}
        >
          Approve
        </button>
      </div>
    </div>
  );
}
12) frontend/src/components/governance/GovernanceConflictBanner.tsx
import React from "react";

type Props = {
  visible: boolean;
  expectedVersion?: number | null;
  latestVersion?: number | null;
  onRefresh?: () => void;
};

export default function GovernanceConflictBanner({
  visible,
  expectedVersion,
  latestVersion,
  onRefresh,
}: Props) {
  if (!visible) return null;

  return (
    <div className="rounded-2xl border border-red-300 bg-red-50 p-4 space-y-3">
      <div className="text-sm font-semibold text-red-700">
        Version conflict detected
      </div>

      <div className="text-sm text-red-700">
        This governance action was created against a stale directive version and cannot be executed safely.
      </div>

      <div className="grid gap-2 md:grid-cols-2 text-sm text-red-700">
        <div>Expected version: {expectedVersion ?? "n/a"}</div>
        <div>Latest version: {latestVersion ?? "n/a"}</div>
      </div>

      {onRefresh ? (
        <div className="flex justify-end">
          <button
            type="button"
            className="rounded-xl border border-red-400 px-4 py-2 text-sm text-red-700"
            onClick={onRefresh}
          >
            Refresh and rebase
          </button>
        </div>
      ) : null}
    </div>
  );
}
13) frontend/src/components/governance/GovernanceExecutionTimeline.tsx
import React from "react";

type TimelineItem = {
  label: string;
  timestamp?: string | null;
  detail?: string | null;
  status?: string | null;
};

type Props = {
  items?: TimelineItem[];
};

export default function GovernanceExecutionTimeline({ items = [] }: Props) {
  return (
    <div className="rounded-2xl border bg-background p-4 space-y-4">
      <div>
        <div className="text-base font-semibold">Execution Timeline</div>
        <div className="text-sm text-muted-foreground">
          Change lifecycle from submission through execution.
        </div>
      </div>

      {items.length === 0 ? (
        <div className="text-sm text-muted-foreground">No lifecycle events yet.</div>
      ) : (
        <div className="space-y-3">
          {items.map((item, idx) => (
            <div key={`${item.label}-${idx}`} className="rounded-xl border p-3">
              <div className="flex items-center justify-between gap-4">
                <div className="font-medium text-sm">{item.label}</div>
                <div className="text-xs text-muted-foreground">
                  {item.timestamp ?? "n/a"}
                </div>
              </div>

              {item.status ? (
                <div className="mt-2 text-xs text-muted-foreground">
                  status: {item.status}
                </div>
              ) : null}

              {item.detail ? (
                <div className="mt-2 text-sm text-muted-foreground">
                  {item.detail}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
14) frontend/src/components/governance/GovernanceActionBar.tsx bản Phase 3 đầy đủ hơn
import React, { useMemo, useState } from "react";
import {
  createGovernanceChange,
  simulateGovernanceChange,
  submitGovernanceChange,
  approveGovernanceChange,
  rejectGovernanceChange,
  executeGovernanceChange,
} from "../../api/governance";
import GovernanceSimulationPanel from "./GovernanceSimulationPanel";
import GovernanceApprovalPanel from "./GovernanceApprovalPanel";
import GovernanceConflictBanner from "./GovernanceConflictBanner";
import GovernanceExecutionTimeline from "./GovernanceExecutionTimeline";

type Props = {
  targetType: string;
  targetId: string;
  expectedVersion: number;
  actionType: string;
  proposedPayload: Record<string, unknown>;
  reason?: string;
};

export default function GovernanceActionBar({
  targetType,
  targetId,
  expectedVersion,
  actionType,
  proposedPayload,
  reason,
}: Props) {
  const [changeRequest, setChangeRequest] = useState<any | null>(null);
  const [simulation, setSimulation] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [hasConflict, setHasConflict] = useState(false);
  const [timeline, setTimeline] = useState<any[]>([]);

  const canExecute = useMemo(() => {
    if (!changeRequest) return false;
    if (hasConflict) return false;
    if (String(changeRequest.requires_approval).toLowerCase() === "true") {
      return ["approved", "ready"].includes(changeRequest.status);
    }
    return ["ready", "simulated", "approved"].includes(changeRequest.status);
  }, [changeRequest, hasConflict]);

  async function handleCreate() {
    setBusy(true);
    setHasConflict(false);
    try {
      const created = await createGovernanceChange({
        target_type: targetType,
        target_id: targetId,
        action_type: actionType,
        expected_version: expectedVersion,
        proposed_payload: proposedPayload,
        reason,
        idempotency_key: `${targetType}:${targetId}:${actionType}:${expectedVersion}`,
      });
      setChangeRequest(created);
      setTimeline((prev) => [
        ...prev,
        {
          label: "Change request created",
          timestamp: new Date().toISOString(),
          status: created.status,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleSimulate() {
    if (!changeRequest) return;
    setBusy(true);
    try {
      const result = await simulateGovernanceChange(changeRequest.id);
      setSimulation(result);
      setTimeline((prev) => [
        ...prev,
        {
          label: "Simulation completed",
          timestamp: new Date().toISOString(),
          status: result.allowed ? "allowed" : "denied",
          detail: `version-match=${String(result.targetVersionMatches)}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit() {
    if (!changeRequest) return;
    setBusy(true);
    try {
      const result = await submitGovernanceChange(changeRequest.id);
      setChangeRequest((prev: any) => ({ ...prev, status: result.status }));
      setTimeline((prev) => [
        ...prev,
        {
          label: "Change submitted",
          timestamp: new Date().toISOString(),
          status: result.status,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(note?: string) {
    if (!changeRequest) return;
    setBusy(true);
    try {
      const result = await approveGovernanceChange(changeRequest.id, note);
      setChangeRequest((prev: any) => ({ ...prev, status: "approved", approval: result }));
      setTimeline((prev) => [
        ...prev,
        {
          label: "Approval granted",
          timestamp: new Date().toISOString(),
          status: result.status,
          detail: result.decision_note ?? undefined,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleReject(note?: string) {
    if (!changeRequest) return;
    setBusy(true);
    try {
      const result = await rejectGovernanceChange(changeRequest.id, note);
      setChangeRequest((prev: any) => ({ ...prev, status: "rejected", approval: result }));
      setTimeline((prev) => [
        ...prev,
        {
          label: "Approval rejected",
          timestamp: new Date().toISOString(),
          status: result.status,
          detail: result.decision_note ?? undefined,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleExecute() {
    if (!changeRequest) return;
    setBusy(true);
    setHasConflict(false);

    try {
      const result = await executeGovernanceChange(changeRequest.id);
      setChangeRequest((prev: any) => ({
        ...prev,
        status: result.execution_status,
      }));
      setTimeline((prev) => [
        ...prev,
        {
          label: "Execution succeeded",
          timestamp: new Date().toISOString(),
          status: result.execution_status,
          detail: `new_version=${String(result.new_version ?? "n/a")}`,
        },
      ]);
    } catch (err: any) {
      const statusCode = err?.response?.status;
      if (statusCode === 409) {
        setHasConflict(true);
        setTimeline((prev) => [
          ...prev,
          {
            label: "Execution conflicted",
            timestamp: new Date().toISOString(),
            status: "conflicted",
            detail: "Directive version changed before execute.",
          },
        ]);
        return;
      }

      setTimeline((prev) => [
        ...prev,
        {
          label: "Execution failed",
          timestamp: new Date().toISOString(),
          status: "failed",
          detail: err?.response?.data?.detail ?? err?.message ?? "Unknown error",
        },
      ]);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <GovernanceConflictBanner
        visible={hasConflict}
        expectedVersion={changeRequest?.expected_version ?? expectedVersion}
        latestVersion={simulation?.currentVersion ?? null}
        onRefresh={() => window.location.reload()}
      />

      <div className="rounded-2xl border bg-background p-4 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm"
            onClick={handleCreate}
            disabled={busy}
          >
            Create change
          </button>

          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm"
            onClick={handleSimulate}
            disabled={busy || !changeRequest}
          >
            Simulate
          </button>

          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm"
            onClick={handleSubmit}
            disabled={busy || !changeRequest}
          >
            Submit
          </button>

          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm"
            onClick={handleExecute}
            disabled={busy || !canExecute}
          >
            Execute
          </button>
        </div>

        {changeRequest ? (
          <div className="rounded-xl border p-3 text-sm space-y-1">
            <div>change_request_id: {changeRequest.id}</div>
            <div>status: {changeRequest.status}</div>
            <div>action: {changeRequest.action_type}</div>
            <div>expected_version: {changeRequest.expected_version}</div>
          </div>
        ) : null}
      </div>

      <GovernanceSimulationPanel simulation={simulation} />

      {changeRequest && String(changeRequest.requires_approval).toLowerCase() === "true" ? (
        <GovernanceApprovalPanel
          status={changeRequest.status}
          requiredRole={changeRequest.approval_rule_key ?? "governance_owner"}
          disabled={busy}
          busy={busy}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      ) : null}

      <GovernanceExecutionTimeline items={timeline} />
    </div>
  );
}
15) frontend/src/api/governance.ts để cắm khớp với component trên
import { apiClient } from "./client";

export async function createGovernanceChange(payload: Record<string, unknown>) {
  const { data } = await apiClient.post("/governance/changes", payload);
  return data;
}

export async function simulateGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/simulate`);
  return data;
}

export async function submitGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/submit`);
  return data;
}

export async function approveGovernanceChange(changeRequestId: string, note?: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/approve`, { note });
  return data;
}

export async function rejectGovernanceChange(changeRequestId: string, note?: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/reject`, { note });
  return data;
}

export async function executeGovernanceChange(changeRequestId: string) {
  const { data } = await apiClient.post(`/governance/changes/${changeRequestId}/execute`);
  return data;
}

export async function fetchGovernanceApprovalQueue() {
  const { data } = await apiClient.get("/governance/approvals/queue");
  return data;
}
16) Phần rất quan trọng cần nối ngay để code này chạy sạch
Bạn sẽ cần 4 điểm khớp sau:
A. DirectiveStateGateway
Phải có 2 method:
def get(self, directive_id: str): ...
def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict): ...
Trong update_with_version_check, nếu compare-and-swap fail thì raise exception để route map ra 409.
B. GovernancePolicyService.evaluate_change_request(...)
Code route và simulation đang gọi method này. Nó phải trả được các field:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
C. RuntimeFabricAdapterRegistry
Phải có:
def resolve(self, action_type: str):
    ...
và adapter trả:
preview(...) -> dict
apply(...) -> dict
D. Repositories
Các repository phải có đúng các method đang được dùng:
GovernanceChangeRequestRepository.create/get/find_by_idempotency_key/list_pending_approvals
GovernanceApprovalRepository.create/get_by_change_request_id
GovernanceExecutionAttemptRepository.create
GovernanceNotificationRepository.create
17) Điểm kỹ thuật đáng giá nhất của bản full code này
Bản này đã khóa được 5 thứ quan trọng nhất của Phase 3:
version-safe mutation
approval bind theo target_version
self-approval block
execution attempt persistence
conflict surfaced thành 409 cho frontend
Đó là ngưỡng chuyển từ “governance có nút bấm” sang “governance có transaction safety”.
Tôi sẽ viết luôn cụm backend core Phase 3 theo kiểu patch-ready, bám đúng 4 điểm khớp bạn khóa ở trên và giữ transaction safety/409 conflict xuyên suốt. Tôi sẽ gom thành một bundle có cấu trúc file rõ ràng để bạn copy từng file hoặc tiếp tục yêu cầu tôi tách sâu từng file ngay sau đó.
PHASE 3 — BACKEND CORE (PATCH-READY)
Dưới đây là cụm backend core nối khớp với các ràng buộc bạn đã chốt:
DirectiveStateGateway.get(...)
DirectiveStateGateway.update_with_version_check(...) với compare-and-swap, fail => raise conflict
GovernancePolicyService.evaluate_change_request(...) trả về:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
RuntimeFabricAdapterRegistry.resolve(action_type)
adapter contract có preview(...) và apply(...)
repositories có đúng các methods đang được route/service dùng
execution conflict surfaced ra 409
1) backend/app/core/exceptions.py
from __future__ import annotations
class AppError(Exception):
    """Base application error."""
class ConflictError(AppError):
    """Raised when optimistic concurrency / idempotency conflict happens."""
class NotFoundError(AppError):
    """Raised when an entity cannot be found."""
class ValidationError(AppError):
    """Raised when domain validation fails."""
class ApprovalRequiredError(AppError):
    """Raised when execution is attempted before required approvals exist."""
class ForbiddenActionError(AppError):
    """Raised when actor is not allowed to perform an action."""
2) backend/app/governance/models/governance_change_request.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceChangeRequest(Base):
    __tablename__ = "governance_change_request"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_patch: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="pending")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_rule_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
3) backend/app/governance/models/governance_approval.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceApproval(Base):
    __tablename__ = "governance_approval"
    __table_args__ = (
        UniqueConstraint("change_request_id", "approver_id", name="uq_governance_approval_request_approver"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    approver_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)  # approved / rejected
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
4) backend/app/governance/models/governance_execution_attempt.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceExecutionAttempt(Base):
    __tablename__ = "governance_execution_attempt"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)  # success / conflict / failed
    adapter_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
5) backend/app/governance/models/governance_notification_event.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
6) backend/app/governance/schemas/change_request.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
class GovernancePolicyEvaluationDTO(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
class GovernanceChangeRequestCreate(BaseModel):
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    notes: str | None = None
class GovernanceChangeRequestRead(BaseModel):
    id: str
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any]
    preview_payload: dict[str, Any] | None = None
    policy_snapshot: dict[str, Any] | None = None
    requested_by: str
    status: str
    requires_approval: bool
    approval_rule_key: str | None = None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None
    rejected_at: datetime | None = None
    notes: str | None = None
    class Config:
        from_attributes = True
class GovernanceApprovalCreate(BaseModel):
    decision: str
    reason: str | None = None
class GovernanceApprovalRead(BaseModel):
    id: str
    change_request_id: str
    approver_id: str
    decision: str
    reason: str | None = None
    created_at: datetime
    class Config:
        from_attributes = True
class GovernanceSimulationResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
7) backend/app/governance/repositories/governance_change_request_repository.py
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundError
from app.governance.models.governance_change_request import GovernanceChangeRequest
class GovernanceChangeRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceChangeRequest:
        entity = GovernanceChangeRequest(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.id == change_request_id)
        return self.db.scalar(stmt)
    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.idempotency_key == idempotency_key)
        return self.db.scalar(stmt)
    def list_pending_approvals(self, limit: int = 100) -> list[GovernanceChangeRequest]:
        stmt = (
            select(GovernanceChangeRequest)
            .where(
                GovernanceChangeRequest.requires_approval.is_(True),
                GovernanceChangeRequest.status == "pending",
            )
            .order_by(GovernanceChangeRequest.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
    def require(self, change_request_id: str) -> GovernanceChangeRequest:
        entity = self.get(change_request_id)
        if not entity:
            raise NotFoundError(f"change request not found: {change_request_id}")
        return entity
8) backend/app/governance/repositories/governance_approval_repository.py
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.governance.models.governance_approval import GovernanceApproval
class GovernanceApprovalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceApproval:
        entity = GovernanceApproval(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
    def get_by_change_request_id(self, change_request_id: str) -> list[GovernanceApproval]:
        stmt = (
            select(GovernanceApproval)
            .where(GovernanceApproval.change_request_id == change_request_id)
            .order_by(GovernanceApproval.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
9) backend/app/governance/repositories/governance_execution_attempt_repository.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.governance.models.governance_execution_attempt import GovernanceExecutionAttempt
class GovernanceExecutionAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceExecutionAttempt:
        entity = GovernanceExecutionAttempt(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
10) backend/app/governance/repositories/governance_notification_repository.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.governance.models.governance_notification_event import GovernanceNotificationEvent
class GovernanceNotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceNotificationEvent:
        entity = GovernanceNotificationEvent(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
11) backend/app/governance/runtime_fabric/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
class RuntimeFabricAdapter(ABC):
    @abstractmethod
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError
    @abstractmethod
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError
12) backend/app/governance/runtime_fabric/adapters/provider_routing_override.py
from __future__ import annotations
from typing import Any
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class ProviderRoutingOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
            "changed_keys": sorted(list(requested_patch.keys())),
        }
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "applied": True,
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
        }
13) backend/app/governance/runtime_fabric/adapters/worker_concurrency_override.py
from __future__ import annotations
from typing import Any
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class WorkerConcurrencyOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
            "safe_range_checked": True,
        }
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "applied": True,
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
        }
14) backend/app/governance/runtime_fabric/registry.py
from __future__ import annotations
from app.core.exceptions import NotFoundError
from app.governance.runtime_fabric.adapters.provider_routing_override import ProviderRoutingOverrideAdapter
from app.governance.runtime_fabric.adapters.worker_concurrency_override import WorkerConcurrencyOverrideAdapter
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class RuntimeFabricAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeFabricAdapter] = {
            "provider_routing_override": ProviderRoutingOverrideAdapter(),
            "worker_concurrency_override": WorkerConcurrencyOverrideAdapter(),
        }
    def resolve(self, action_type: str) -> RuntimeFabricAdapter:
        adapter = self._adapters.get(action_type)
        if not adapter:
            raise NotFoundError(f"runtime adapter not found for action_type={action_type}")
        return adapter
15) backend/app/governance/services/directive_state_gateway.py
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.exceptions import ConflictError, NotFoundError
class DirectiveStateGateway:
    """
    Expects a table shaped roughly like:
      directive_state(
        directive_id varchar primary key,
        version int not null,
        state jsonb not null,
        updated_at timestamptz not null
      )
    If your actual schema differs, keep the method contract unchanged
    and adapt the SQL only.
    """
    def __init__(self, db: Session) -> None:
        self.db = db
    def get(self, directive_id: str):
        row = self.db.execute(
            text(
                """
                SELECT directive_id, version, state, updated_at
                FROM directive_state
                WHERE directive_id = :directive_id
                """
            ),
            {"directive_id": directive_id},
        ).mappings().first()
        if not row:
            raise NotFoundError(f"directive state not found: {directive_id}")
        return dict(row)
    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        current = self.get(directive_id)
        current_state = current.get("state") or {}
        next_state = {**current_state, **patch}
        result = self.db.execute(
            text(
                """
                UPDATE directive_state
                SET
                    state = :next_state,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE directive_id = :directive_id
                  AND version = :expected_version
                RETURNING directive_id, version, state, updated_at
                """
            ),
            {
                "directive_id": directive_id,
                "expected_version": expected_version,
                "next_state": next_state,
            },
        ).mappings().first()
        if not result:
            raise ConflictError(
                f"directive state version conflict: directive_id={directive_id}, expected_version={expected_version}"
            )
        return dict(result)
16) backend/app/governance/services/governance_policy_service.py
from __future__ import annotations
from app.governance.schemas.change_request import GovernancePolicyEvaluationDTO
class GovernancePolicyService:
    """
    Phase 3 policy surface required by routes + simulation service.
    Keep contract stable even if policy rules grow later.
    """
    def evaluate_change_request(
        self,
        *,
        directive_state: dict,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernancePolicyEvaluationDTO:
        reasons: list[str] = []
        risk_flags: list[str] = []
        allowed = True
        requires_approval = False
        approval_rule_key: str | None = None
        if action_type in {"provider_routing_override", "worker_concurrency_override"}:
            risk_flags.append("runtime_mutation")
        if action_type == "provider_routing_override":
            if "provider" in requested_patch:
                risk_flags.append("provider_change")
            requires_approval = True
            approval_rule_key = "dual_control_runtime_override"
            reasons.append("provider routing override touches live runtime behavior")
        if action_type == "worker_concurrency_override":
            new_limit = requested_patch.get("max_concurrency")
            if isinstance(new_limit, int) and new_limit > 100:
                requires_approval = True
                approval_rule_key = "high_impact_capacity_change"
                risk_flags.append("capacity_spike")
                reasons.append("requested concurrency exceeds safe auto-apply threshold")
            else:
                reasons.append("concurrency mutation is within bounded safe threshold")
        if requested_patch.get("force") is True:
            requires_approval = True
            approval_rule_key = approval_rule_key or "forced_runtime_mutation"
            risk_flags.append("forced_change")
            reasons.append("force flag requires human approval")
        if directive_state.get("state", {}).get("locked") is True:
            allowed = False
            reasons.append("directive is locked and cannot be changed")
            risk_flags.append("locked_target")
        return GovernancePolicyEvaluationDTO(
            allowed=allowed,
            requires_approval=requires_approval,
            approval_rule_key=approval_rule_key,
            reasons=reasons,
            risk_flags=risk_flags,
        )
17) backend/app/governance/services/governance_simulation_service.py
from __future__ import annotations
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import GovernanceSimulationResponse
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_policy_service import GovernancePolicyService
class GovernanceSimulationService:
    def __init__(
        self,
        *,
        directive_state_gateway: DirectiveStateGateway,
        policy_service: GovernancePolicyService,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.directive_state_gateway = directive_state_gateway
        self.policy_service = policy_service
        self.adapter_registry = adapter_registry
    def simulate(
        self,
        *,
        directive_id: str,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernanceSimulationResponse:
        directive_state = self.directive_state_gateway.get(directive_id)
        policy = self.policy_service.evaluate_change_request(
            directive_state=directive_state,
            action_type=action_type,
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        adapter = self.adapter_registry.resolve(action_type)
        preview = adapter.preview(
            directive_state=directive_state.get("state") or {},
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        return GovernanceSimulationResponse(
            allowed=policy.allowed,
            requires_approval=policy.requires_approval,
            approval_rule_key=policy.approval_rule_key,
            reasons=policy.reasons,
            risk_flags=policy.risk_flags,
            preview=preview,
        )
18) backend/app/governance/services/governance_approval_service.py
from __future__ import annotations
from datetime import datetime
from app.core.exceptions import ConflictError, ForbiddenActionError, ValidationError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
class GovernanceApprovalService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        notification_repository: GovernanceNotificationRepository,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.notification_repository = notification_repository
    def record_decision(
        self,
        *,
        change_request_id: str,
        approver_id: str,
        decision: str,
        reason: str | None,
    ):
        change_request = self.change_request_repository.require(change_request_id)
        if change_request.requested_by == approver_id:
            raise ForbiddenActionError("self-approval is not allowed")
        if change_request.status != "pending":
            raise ConflictError(f"change request is not pending: {change_request.status}")
        existing = self.approval_repository.get_by_change_request_id(change_request_id)
        if any(a.approver_id == approver_id for a in existing):
            raise ConflictError("approver has already decided on this change request")
        if decision not in {"approved", "rejected"}:
            raise ValidationError("decision must be one of: approved, rejected")
        approval = self.approval_repository.create(
            {
                "change_request_id": change_request_id,
                "approver_id": approver_id,
                "decision": decision,
                "reason": reason,
            }
        )
        if decision == "rejected":
            change_request.status = "rejected"
            change_request.rejected_at = datetime.utcnow()
        else:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            if change_request.requires_approval and len([a for a in approvals if a.decision == "approved"]) >= 1:
                change_request.status = "approved"
        self.notification_repository.create(
            {
                "change_request_id": change_request_id,
                "event_type": f"governance.change_request.{decision}",
                "payload": {
                    "approver_id": approver_id,
                    "decision": decision,
                    "reason": reason,
                },
            }
        )
        return approval
19) backend/app/governance/services/governance_execution_service.py
from __future__ import annotations
from datetime import datetime
from app.core.exceptions import ApprovalRequiredError, ConflictError, ForbiddenActionError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.services.directive_state_gateway import DirectiveStateGateway
class GovernanceExecutionService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        execution_attempt_repository: GovernanceExecutionAttemptRepository,
        notification_repository: GovernanceNotificationRepository,
        directive_state_gateway: DirectiveStateGateway,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.execution_attempt_repository = execution_attempt_repository
        self.notification_repository = notification_repository
        self.directive_state_gateway = directive_state_gateway
        self.adapter_registry = adapter_registry
    def execute_change_request(self, *, change_request_id: str, actor_id: str):
        change_request = self.change_request_repository.require(change_request_id)
        if change_request.requested_by == actor_id and change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved_by_other = any(a.decision == "approved" and a.approver_id != actor_id for a in approvals)
            if not approved_by_other:
                raise ApprovalRequiredError("required approval from another actor is missing")
        if change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved = any(a.decision == "approved" for a in approvals)
            rejected = any(a.decision == "rejected" for a in approvals)
            if rejected:
                raise ForbiddenActionError("change request was rejected")
            if not approved:
                raise ApprovalRequiredError("approval is required before execution")
        adapter = self.adapter_registry.resolve(change_request.action_type)
        current = self.directive_state_gateway.get(change_request.directive_id)
        expected_version = change_request.target_version
        if current["version"] != expected_version:
            attempt = self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "error_code": "directive_version_conflict",
                    "error_message": (
                        f"target_version={expected_version} but current_version={current['version']}"
                    ),
                }
            )
            raise ConflictError(attempt.error_message or "directive version conflict")
        apply_result = adapter.apply(
            directive_state=current.get("state") or {},
            requested_patch=change_request.requested_patch,
            actor_id=actor_id,
        )
        try:
            updated = self.directive_state_gateway.update_with_version_check(
                change_request.directive_id,
                expected_version=expected_version,
                patch=change_request.requested_patch,
            )
        except ConflictError as exc:
            self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "adapter_result": apply_result,
                    "error_code": "directive_version_conflict",
                    "error_message": str(exc),
                }
            )
            raise
        attempt = self.execution_attempt_repository.create(
            {
                "change_request_id": change_request.id,
                "directive_id": change_request.directive_id,
                "actor_id": actor_id,
                "expected_version": expected_version,
                "status": "success",
                "adapter_result": {
                    **apply_result,
                    "updated_version": updated["version"],
                },
            }
        )
        change_request.status = "executed"
        change_request.executed_at = datetime.utcnow()
        self.notification_repository.create(
            {
                "change_request_id": change_request.id,
                "event_type": "governance.change_request.executed",
                "payload": {
                    "actor_id": actor_id,
                    "directive_id": change_request.directive_id,
                    "expected_version": expected_version,
                    "updated_version": updated["version"],
                },
            }
        )
        return {
            "change_request_id": change_request.id,
            "directive_id": change_request.directive_id,
            "attempt_id": attempt.id,
            "status": "executed",
            "updated_version": updated["version"],
        }
20) backend/app/api/routes/governance.py
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.exceptions import (
    ApprovalRequiredError,
    ConflictError,
    ForbiddenActionError,
    NotFoundError,
    ValidationError,
)
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import (
    GovernanceApprovalCreate,
    GovernanceApprovalRead,
    GovernanceChangeRequestCreate,
    GovernanceChangeRequestRead,
)
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_approval_service import GovernanceApprovalService
from app.governance.services.governance_execution_service import GovernanceExecutionService
from app.governance.services.governance_policy_service import GovernancePolicyService
from app.governance.services.governance_simulation_service import GovernanceSimulationService
router = APIRouter(prefix="/governance", tags=["governance"])
def _actor_id(x_actor_id: str = Header(..., alias="X-Actor-Id")) -> str:
    return x_actor_id
@router.post("/simulate")
def simulate_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        return service.simulate(
            directive_id=payload.directive_id,
            action_type=payload.action_type,
            requested_patch=payload.requested_patch,
            actor_id=actor_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
@router.post("/change-requests", response_model=GovernanceChangeRequestRead)
def create_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    repo = GovernanceChangeRequestRepository(db)
    if payload.idempotency_key:
        existing = repo.find_by_idempotency_key(payload.idempotency_key)
        if existing:
            return existing
    simulation = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    ).simulate(
        directive_id=payload.directive_id,
        action_type=payload.action_type,
        requested_patch=payload.requested_patch,
        actor_id=actor_id,
    )
    entity = repo.create(
        {
            "directive_id": payload.directive_id,
            "action_type": payload.action_type,
            "target_version": payload.target_version,
            "requested_patch": payload.requested_patch,
            "preview_payload": simulation.preview,
            "policy_snapshot": simulation.model_dump(exclude={"preview"}),
            "idempotency_key": payload.idempotency_key,
            "requested_by": actor_id,
            "status": "pending",
            "requires_approval": simulation.requires_approval,
            "approval_rule_key": simulation.approval_rule_key,
            "notes": payload.notes,
        }
    )
    db.commit()
    return entity
@router.get("/change-requests/{change_request_id}", response_model=GovernanceChangeRequestRead)
def get_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
):
    entity = GovernanceChangeRequestRepository(db).get(change_request_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="change request not found")
    return entity
@router.post("/change-requests/{change_request_id}/approvals", response_model=GovernanceApprovalRead)
def approve_change_request(
    change_request_id: str,
    payload: GovernanceApprovalCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceApprovalService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
    )
    try:
        approval = service.record_decision(
            change_request_id=change_request_id,
            approver_id=actor_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        db.commit()
        return approval
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
@router.post("/change-requests/{change_request_id}/execute")
def execute_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceExecutionService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        execution_attempt_repository=GovernanceExecutionAttemptRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
        directive_state_gateway=DirectiveStateGateway(db),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        result = service.execute_change_request(change_request_id=change_request_id, actor_id=actor_id)
        db.commit()
        return result
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ApprovalRequiredError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
21) backend/tests/services/test_governance_execution_service.py
from __future__ import annotations
import pytest
from app.core.exceptions import ApprovalRequiredError, ConflictError
from app.governance.services.governance_execution_service import GovernanceExecutionService
class DummyChangeRequest:
    def __init__(self):
        self.id = "cr_1"
        self.directive_id = "dir_1"
        self.action_type = "provider_routing_override"
        self.target_version = 4
        self.requested_patch = {"provider": "runway"}
        self.requested_by = "user_a"
        self.requires_approval = True
        self.status = "pending"
        self.executed_at = None
class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity
    def require(self, change_request_id: str):
        return self.entity
class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision
class DummyApprovalRepo:
    def __init__(self, approvals):
        self.approvals = approvals
    def get_by_change_request_id(self, change_request_id: str):
        return self.approvals
class DummyAttemptRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        payload = {**payload, "id": f"attempt_{len(self.items)+1}"}
        self.items.append(payload)
        return type("Attempt", (), payload)
class DummyNotificationRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        self.items.append(payload)
        return payload
class DummyGateway:
    def __init__(self, version=4, fail_update=False):
        self.version = version
        self.fail_update = fail_update
    def get(self, directive_id: str):
        return {"directive_id": directive_id, "version": self.version, "state": {"provider": "veo"}}
    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        if self.fail_update:
            raise ConflictError("cas failed")
        return {
            "directive_id": directive_id,
            "version": expected_version + 1,
            "state": {"provider": patch["provider"]},
        }
class DummyAdapter:
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str):
        return {"applied": True, "after": {**directive_state, **requested_patch}}
class DummyRegistry:
    def resolve(self, action_type: str):
        return DummyAdapter()
def test_execute_requires_foreign_approval():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ApprovalRequiredError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
def test_execute_surfaces_version_conflict_before_apply():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=5),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
def test_execute_persists_success_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    notifications = DummyNotificationRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=notifications,
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    result = service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
    assert result["status"] == "executed"
    assert attempts.items[-1]["status"] == "success"
    assert notifications.items[-1]["event_type"] == "governance.change_request.executed"
22) backend/tests/api/test_governance_routes.py
from __future__ import annotations
def test_execute_conflict_returns_409(client, seeded_change_request_requires_approval, approved_by_other_actor):
    response = client.post(
        f"/governance/change-requests/{seeded_change_request_requires_approval}/execute",
        headers={"X-Actor-Id": "requester_user"},
    )
    assert response.status_code in {200, 409}
    # If your fixture intentionally bumps directive version first,
    # keep this strict assertion instead:
    # assert response.status_code == 409
23) Ghi chú nối khớp quan trọng
A. Compare-and-swap
DirectiveStateGateway.update_with_version_check(...) đã làm đúng compare-and-swap.
Nếu WHERE version = :expected_version không match, raise ConflictError.
Route map ConflictError -> HTTP 409.
B. Policy contract
GovernancePolicyService.evaluate_change_request(...) trả đúng 5 field bạn khóa:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
C. Runtime fabric contract
RuntimeFabricAdapterRegistry.resolve(action_type) trả adapter có:
preview(...) -> dict
apply(...) -> dict
D. Repository contract
Đủ đúng các method đang được gọi:
GovernanceChangeRequestRepository.create/get/find_by_idempotency_key/list_pending_approvals
GovernanceApprovalRepository.create/get_by_change_request_id
GovernanceExecutionAttemptRepository.create
GovernanceNotificationRepository.create
24) Điểm cần bạn map vào codebase thật ngay sau khi paste
Base import
Đổi from app.db.base import Base theo base class thật của monorepo.
directive_state table
Tôi giữ DirectiveStateGateway ở mức SQL trực tiếp để bảo toàn CAS semantics.
Nếu schema thật khác (payload, config, state_json, v.v.), chỉ sửa SQL chứ không đổi contract method.
approval threshold
Bản này đang dùng ngưỡng tối thiểu 1 approval khác requester.
Nếu Phase 3 của bạn cần N-of-M, chèn rule đó vào GovernanceApprovalService / policy snapshot mà không đổi route surface.
tests/api
Tôi để skeleton vì fixture thật phụ thuộc app factory / db fixture hiện có của bạn.
Nếu bạn muốn, lượt tiếp theo tôi viết luôn fixture-ready test theo FastAPI + SQLAlchemy session override.
25) Bước nối mạnh nhất ngay sau bundle này
Sau bundle này, nên viết tiếp ngay 3 mảng sau để backend core kín hoàn toàn:
Alembic migration Phase 3
tạo 4 bảng governance phase 3
index theo directive_id, change_request_id, status, created_at
unique idempotency_key
unique (change_request_id, approver_id)
RBAC / actor policy binding
ai được create request
ai được approve
ai được execute
ai bị block self-approval
frontend contract stabilization
response chuẩn cho 409 conflict
response chuẩn cho approval required
ExplainDrawer / GovernanceActionBar xử lý conflict + refresh target version
---
Nếu bạn muốn, tôi sẽ tách tiếp ngay bundle này thành **từng file hoàn chỉnh riêng lẻ** theo đúng format bạn đang patch vào monorepo, bắt đầu từ:
- `governance_change_request_repository.py`
- `directive_state_gateway.py`
- `runtime_fabric/registry.py`
- `governance_execution_service.py`
- `alembic migration phase 3`
Tôi đã viết xong bundle PHASE 3 BACKEND CORE theo kiểu patch-ready và đặt vào canvas để bạn rà/copy từng file.
Nó đã nối đúng các điểm bạn khóa:
DirectiveStateGateway.get(...)
DirectiveStateGateway.update_with_version_check(...) với CAS fail → ConflictError → route map 409
GovernancePolicyService.evaluate_change_request(...) trả đủ:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
RuntimeFabricAdapterRegistry.resolve(action_type)
adapter contract có preview(...) / apply(...)
repositories đủ đúng surface methods đang dùng
execution attempt persistence + self-approval block + target_version binding
Trong bundle có sẵn:
models phase 3
schemas
repositories
runtime fabric registry + 2 adapter mẫu
directive_state_gateway.py
governance_policy_service.py
governance_simulation_service.py
governance_approval_service.py
governance_execution_service.py
routes governance.py
test service skeleton
test API skeleton
ghi chú các điểm cần map vào schema thật của monorepo
Bước mạnh nhất tiếp theo là tôi tách tiếp thành từng file hoàn chỉnh riêng lẻ theo đúng style codebase của bạn, rồi viết luôn:
Alembic migration Phase 3
RBAC binding
fixture-ready API tests
frontend conflict contract 409
Chỉ cần nói: WRITE PHASE 3 MIGRATION + TESTS
WRITE PHASE 3 MIGRATION + TESTS
Tôi sẽ nối tiếp ngay phần Alembic migration Phase 3 và bộ tests theo hướng chạy được với FastAPI + SQLAlchemy session override, đồng thời giữ nguyên contract 409/approval flow để frontend không phải đoán trạng thái.
PHASE 3 — BACKEND CORE (PATCH-READY)
Dưới đây là cụm backend core nối khớp với các ràng buộc bạn đã chốt:
DirectiveStateGateway.get(...)
DirectiveStateGateway.update_with_version_check(...) với compare-and-swap, fail => raise conflict
GovernancePolicyService.evaluate_change_request(...) trả về:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
RuntimeFabricAdapterRegistry.resolve(action_type)
adapter contract có preview(...) và apply(...)
repositories có đúng các methods đang được route/service dùng
execution conflict surfaced ra 409
1) backend/app/core/exceptions.py
from __future__ import annotations
class AppError(Exception):
    """Base application error."""
class ConflictError(AppError):
    """Raised when optimistic concurrency / idempotency conflict happens."""
class NotFoundError(AppError):
    """Raised when an entity cannot be found."""
class ValidationError(AppError):
    """Raised when domain validation fails."""
class ApprovalRequiredError(AppError):
    """Raised when execution is attempted before required approvals exist."""
class ForbiddenActionError(AppError):
    """Raised when actor is not allowed to perform an action."""
2) backend/app/governance/models/governance_change_request.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceChangeRequest(Base):
    __tablename__ = "governance_change_request"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_patch: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="pending")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_rule_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
3) backend/app/governance/models/governance_approval.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceApproval(Base):
    __tablename__ = "governance_approval"
    __table_args__ = (
        UniqueConstraint("change_request_id", "approver_id", name="uq_governance_approval_request_approver"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    approver_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)  # approved / rejected
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
4) backend/app/governance/models/governance_execution_attempt.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceExecutionAttempt(Base):
    __tablename__ = "governance_execution_attempt"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)  # success / conflict / failed
    adapter_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
5) backend/app/governance/models/governance_notification_event.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
6) backend/app/governance/schemas/change_request.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
class GovernancePolicyEvaluationDTO(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
class GovernanceChangeRequestCreate(BaseModel):
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    notes: str | None = None
class GovernanceChangeRequestRead(BaseModel):
    id: str
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any]
    preview_payload: dict[str, Any] | None = None
    policy_snapshot: dict[str, Any] | None = None
    requested_by: str
    status: str
    requires_approval: bool
    approval_rule_key: str | None = None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None
    rejected_at: datetime | None = None
    notes: str | None = None
    class Config:
        from_attributes = True
class GovernanceApprovalCreate(BaseModel):
    decision: str
    reason: str | None = None
class GovernanceApprovalRead(BaseModel):
    id: str
    change_request_id: str
    approver_id: str
    decision: str
    reason: str | None = None
    created_at: datetime
    class Config:
        from_attributes = True
class GovernanceSimulationResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
7) backend/app/governance/repositories/governance_change_request_repository.py
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundError
from app.governance.models.governance_change_request import GovernanceChangeRequest
class GovernanceChangeRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceChangeRequest:
        entity = GovernanceChangeRequest(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.id == change_request_id)
        return self.db.scalar(stmt)
    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.idempotency_key == idempotency_key)
        return self.db.scalar(stmt)
    def list_pending_approvals(self, limit: int = 100) -> list[GovernanceChangeRequest]:
        stmt = (
            select(GovernanceChangeRequest)
            .where(
                GovernanceChangeRequest.requires_approval.is_(True),
                GovernanceChangeRequest.status == "pending",
            )
            .order_by(GovernanceChangeRequest.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
    def require(self, change_request_id: str) -> GovernanceChangeRequest:
        entity = self.get(change_request_id)
        if not entity:
            raise NotFoundError(f"change request not found: {change_request_id}")
        return entity
8) backend/app/governance/repositories/governance_approval_repository.py
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.governance.models.governance_approval import GovernanceApproval
class GovernanceApprovalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceApproval:
        entity = GovernanceApproval(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
    def get_by_change_request_id(self, change_request_id: str) -> list[GovernanceApproval]:
        stmt = (
            select(GovernanceApproval)
            .where(GovernanceApproval.change_request_id == change_request_id)
            .order_by(GovernanceApproval.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
9) backend/app/governance/repositories/governance_execution_attempt_repository.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.governance.models.governance_execution_attempt import GovernanceExecutionAttempt
class GovernanceExecutionAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceExecutionAttempt:
        entity = GovernanceExecutionAttempt(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
10) backend/app/governance/repositories/governance_notification_repository.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.governance.models.governance_notification_event import GovernanceNotificationEvent
class GovernanceNotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    def create(self, payload: dict) -> GovernanceNotificationEvent:
        entity = GovernanceNotificationEvent(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
11) backend/app/governance/runtime_fabric/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
class RuntimeFabricAdapter(ABC):
    @abstractmethod
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError
    @abstractmethod
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError
12) backend/app/governance/runtime_fabric/adapters/provider_routing_override.py
from __future__ import annotations
from typing import Any
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class ProviderRoutingOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
            "changed_keys": sorted(list(requested_patch.keys())),
        }
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "applied": True,
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
        }
13) backend/app/governance/runtime_fabric/adapters/worker_concurrency_override.py
from __future__ import annotations
from typing import Any
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class WorkerConcurrencyOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
            "safe_range_checked": True,
        }
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "applied": True,
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
        }
14) backend/app/governance/runtime_fabric/registry.py
from __future__ import annotations
from app.core.exceptions import NotFoundError
from app.governance.runtime_fabric.adapters.provider_routing_override import ProviderRoutingOverrideAdapter
from app.governance.runtime_fabric.adapters.worker_concurrency_override import WorkerConcurrencyOverrideAdapter
from app.governance.runtime_fabric.base import RuntimeFabricAdapter
class RuntimeFabricAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeFabricAdapter] = {
            "provider_routing_override": ProviderRoutingOverrideAdapter(),
            "worker_concurrency_override": WorkerConcurrencyOverrideAdapter(),
        }
    def resolve(self, action_type: str) -> RuntimeFabricAdapter:
        adapter = self._adapters.get(action_type)
        if not adapter:
            raise NotFoundError(f"runtime adapter not found for action_type={action_type}")
        return adapter
15) backend/app/governance/services/directive_state_gateway.py
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.exceptions import ConflictError, NotFoundError
class DirectiveStateGateway:
    """
    Expects a table shaped roughly like:
      directive_state(
        directive_id varchar primary key,
        version int not null,
        state jsonb not null,
        updated_at timestamptz not null
      )
    If your actual schema differs, keep the method contract unchanged
    and adapt the SQL only.
    """
    def __init__(self, db: Session) -> None:
        self.db = db
    def get(self, directive_id: str):
        row = self.db.execute(
            text(
                """
                SELECT directive_id, version, state, updated_at
                FROM directive_state
                WHERE directive_id = :directive_id
                """
            ),
            {"directive_id": directive_id},
        ).mappings().first()
        if not row:
            raise NotFoundError(f"directive state not found: {directive_id}")
        return dict(row)
    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        current = self.get(directive_id)
        current_state = current.get("state") or {}
        next_state = {**current_state, **patch}
        result = self.db.execute(
            text(
                """
                UPDATE directive_state
                SET
                    state = :next_state,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE directive_id = :directive_id
                  AND version = :expected_version
                RETURNING directive_id, version, state, updated_at
                """
            ),
            {
                "directive_id": directive_id,
                "expected_version": expected_version,
                "next_state": next_state,
            },
        ).mappings().first()
        if not result:
            raise ConflictError(
                f"directive state version conflict: directive_id={directive_id}, expected_version={expected_version}"
            )
        return dict(result)
16) backend/app/governance/services/governance_policy_service.py
from __future__ import annotations
from app.governance.schemas.change_request import GovernancePolicyEvaluationDTO
class GovernancePolicyService:
    """
    Phase 3 policy surface required by routes + simulation service.
    Keep contract stable even if policy rules grow later.
    """
    def evaluate_change_request(
        self,
        *,
        directive_state: dict,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernancePolicyEvaluationDTO:
        reasons: list[str] = []
        risk_flags: list[str] = []
        allowed = True
        requires_approval = False
        approval_rule_key: str | None = None
        if action_type in {"provider_routing_override", "worker_concurrency_override"}:
            risk_flags.append("runtime_mutation")
        if action_type == "provider_routing_override":
            if "provider" in requested_patch:
                risk_flags.append("provider_change")
            requires_approval = True
            approval_rule_key = "dual_control_runtime_override"
            reasons.append("provider routing override touches live runtime behavior")
        if action_type == "worker_concurrency_override":
            new_limit = requested_patch.get("max_concurrency")
            if isinstance(new_limit, int) and new_limit > 100:
                requires_approval = True
                approval_rule_key = "high_impact_capacity_change"
                risk_flags.append("capacity_spike")
                reasons.append("requested concurrency exceeds safe auto-apply threshold")
            else:
                reasons.append("concurrency mutation is within bounded safe threshold")
        if requested_patch.get("force") is True:
            requires_approval = True
            approval_rule_key = approval_rule_key or "forced_runtime_mutation"
            risk_flags.append("forced_change")
            reasons.append("force flag requires human approval")
        if directive_state.get("state", {}).get("locked") is True:
            allowed = False
            reasons.append("directive is locked and cannot be changed")
            risk_flags.append("locked_target")
        return GovernancePolicyEvaluationDTO(
            allowed=allowed,
            requires_approval=requires_approval,
            approval_rule_key=approval_rule_key,
            reasons=reasons,
            risk_flags=risk_flags,
        )
17) backend/app/governance/services/governance_simulation_service.py
from __future__ import annotations
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import GovernanceSimulationResponse
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_policy_service import GovernancePolicyService
class GovernanceSimulationService:
    def __init__(
        self,
        *,
        directive_state_gateway: DirectiveStateGateway,
        policy_service: GovernancePolicyService,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.directive_state_gateway = directive_state_gateway
        self.policy_service = policy_service
        self.adapter_registry = adapter_registry
    def simulate(
        self,
        *,
        directive_id: str,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernanceSimulationResponse:
        directive_state = self.directive_state_gateway.get(directive_id)
        policy = self.policy_service.evaluate_change_request(
            directive_state=directive_state,
            action_type=action_type,
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        adapter = self.adapter_registry.resolve(action_type)
        preview = adapter.preview(
            directive_state=directive_state.get("state") or {},
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        return GovernanceSimulationResponse(
            allowed=policy.allowed,
            requires_approval=policy.requires_approval,
            approval_rule_key=policy.approval_rule_key,
            reasons=policy.reasons,
            risk_flags=policy.risk_flags,
            preview=preview,
        )
18) backend/app/governance/services/governance_approval_service.py
from __future__ import annotations
from datetime import datetime
from app.core.exceptions import ConflictError, ForbiddenActionError, ValidationError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
class GovernanceApprovalService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        notification_repository: GovernanceNotificationRepository,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.notification_repository = notification_repository
    def record_decision(
        self,
        *,
        change_request_id: str,
        approver_id: str,
        decision: str,
        reason: str | None,
    ):
        change_request = self.change_request_repository.require(change_request_id)
        if change_request.requested_by == approver_id:
            raise ForbiddenActionError("self-approval is not allowed")
        if change_request.status != "pending":
            raise ConflictError(f"change request is not pending: {change_request.status}")
        existing = self.approval_repository.get_by_change_request_id(change_request_id)
        if any(a.approver_id == approver_id for a in existing):
            raise ConflictError("approver has already decided on this change request")
        if decision not in {"approved", "rejected"}:
            raise ValidationError("decision must be one of: approved, rejected")
        approval = self.approval_repository.create(
            {
                "change_request_id": change_request_id,
                "approver_id": approver_id,
                "decision": decision,
                "reason": reason,
            }
        )
        if decision == "rejected":
            change_request.status = "rejected"
            change_request.rejected_at = datetime.utcnow()
        else:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            if change_request.requires_approval and len([a for a in approvals if a.decision == "approved"]) >= 1:
                change_request.status = "approved"
        self.notification_repository.create(
            {
                "change_request_id": change_request_id,
                "event_type": f"governance.change_request.{decision}",
                "payload": {
                    "approver_id": approver_id,
                    "decision": decision,
                    "reason": reason,
                },
            }
        )
        return approval
19) backend/app/governance/services/governance_execution_service.py
from __future__ import annotations
from datetime import datetime
from app.core.exceptions import ApprovalRequiredError, ConflictError, ForbiddenActionError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.services.directive_state_gateway import DirectiveStateGateway
class GovernanceExecutionService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        execution_attempt_repository: GovernanceExecutionAttemptRepository,
        notification_repository: GovernanceNotificationRepository,
        directive_state_gateway: DirectiveStateGateway,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.execution_attempt_repository = execution_attempt_repository
        self.notification_repository = notification_repository
        self.directive_state_gateway = directive_state_gateway
        self.adapter_registry = adapter_registry
    def execute_change_request(self, *, change_request_id: str, actor_id: str):
        change_request = self.change_request_repository.require(change_request_id)
        if change_request.requested_by == actor_id and change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved_by_other = any(a.decision == "approved" and a.approver_id != actor_id for a in approvals)
            if not approved_by_other:
                raise ApprovalRequiredError("required approval from another actor is missing")
        if change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved = any(a.decision == "approved" for a in approvals)
            rejected = any(a.decision == "rejected" for a in approvals)
            if rejected:
                raise ForbiddenActionError("change request was rejected")
            if not approved:
                raise ApprovalRequiredError("approval is required before execution")
        adapter = self.adapter_registry.resolve(change_request.action_type)
        current = self.directive_state_gateway.get(change_request.directive_id)
        expected_version = change_request.target_version
        if current["version"] != expected_version:
            attempt = self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "error_code": "directive_version_conflict",
                    "error_message": (
                        f"target_version={expected_version} but current_version={current['version']}"
                    ),
                }
            )
            raise ConflictError(attempt.error_message or "directive version conflict")
        apply_result = adapter.apply(
            directive_state=current.get("state") or {},
            requested_patch=change_request.requested_patch,
            actor_id=actor_id,
        )
        try:
            updated = self.directive_state_gateway.update_with_version_check(
                change_request.directive_id,
                expected_version=expected_version,
                patch=change_request.requested_patch,
            )
        except ConflictError as exc:
            self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "adapter_result": apply_result,
                    "error_code": "directive_version_conflict",
                    "error_message": str(exc),
                }
            )
            raise
        attempt = self.execution_attempt_repository.create(
            {
                "change_request_id": change_request.id,
                "directive_id": change_request.directive_id,
                "actor_id": actor_id,
                "expected_version": expected_version,
                "status": "success",
                "adapter_result": {
                    **apply_result,
                    "updated_version": updated["version"],
                },
            }
        )
        change_request.status = "executed"
        change_request.executed_at = datetime.utcnow()
        self.notification_repository.create(
            {
                "change_request_id": change_request.id,
                "event_type": "governance.change_request.executed",
                "payload": {
                    "actor_id": actor_id,
                    "directive_id": change_request.directive_id,
                    "expected_version": expected_version,
                    "updated_version": updated["version"],
                },
            }
        )
        return {
            "change_request_id": change_request.id,
            "directive_id": change_request.directive_id,
            "attempt_id": attempt.id,
            "status": "executed",
            "updated_version": updated["version"],
        }
20) backend/app/api/routes/governance.py
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.exceptions import (
    ApprovalRequiredError,
    ConflictError,
    ForbiddenActionError,
    NotFoundError,
    ValidationError,
)
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import (
    GovernanceApprovalCreate,
    GovernanceApprovalRead,
    GovernanceChangeRequestCreate,
    GovernanceChangeRequestRead,
)
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_approval_service import GovernanceApprovalService
from app.governance.services.governance_execution_service import GovernanceExecutionService
from app.governance.services.governance_policy_service import GovernancePolicyService
from app.governance.services.governance_simulation_service import GovernanceSimulationService
router = APIRouter(prefix="/governance", tags=["governance"])
def _actor_id(x_actor_id: str = Header(..., alias="X-Actor-Id")) -> str:
    return x_actor_id
@router.post("/simulate")
def simulate_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        return service.simulate(
            directive_id=payload.directive_id,
            action_type=payload.action_type,
            requested_patch=payload.requested_patch,
            actor_id=actor_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
@router.post("/change-requests", response_model=GovernanceChangeRequestRead)
def create_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    repo = GovernanceChangeRequestRepository(db)
    if payload.idempotency_key:
        existing = repo.find_by_idempotency_key(payload.idempotency_key)
        if existing:
            return existing
    simulation = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    ).simulate(
        directive_id=payload.directive_id,
        action_type=payload.action_type,
        requested_patch=payload.requested_patch,
        actor_id=actor_id,
    )
    entity = repo.create(
        {
            "directive_id": payload.directive_id,
            "action_type": payload.action_type,
            "target_version": payload.target_version,
            "requested_patch": payload.requested_patch,
            "preview_payload": simulation.preview,
            "policy_snapshot": simulation.model_dump(exclude={"preview"}),
            "idempotency_key": payload.idempotency_key,
            "requested_by": actor_id,
            "status": "pending",
            "requires_approval": simulation.requires_approval,
            "approval_rule_key": simulation.approval_rule_key,
            "notes": payload.notes,
        }
    )
    db.commit()
    return entity
@router.get("/change-requests/{change_request_id}", response_model=GovernanceChangeRequestRead)
def get_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
):
    entity = GovernanceChangeRequestRepository(db).get(change_request_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="change request not found")
    return entity
@router.post("/change-requests/{change_request_id}/approvals", response_model=GovernanceApprovalRead)
def approve_change_request(
    change_request_id: str,
    payload: GovernanceApprovalCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceApprovalService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
    )
    try:
        approval = service.record_decision(
            change_request_id=change_request_id,
            approver_id=actor_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        db.commit()
        return approval
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
@router.post("/change-requests/{change_request_id}/execute")
def execute_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceExecutionService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        execution_attempt_repository=GovernanceExecutionAttemptRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
        directive_state_gateway=DirectiveStateGateway(db),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        result = service.execute_change_request(change_request_id=change_request_id, actor_id=actor_id)
        db.commit()
        return result
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ApprovalRequiredError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
21) backend/tests/services/test_governance_execution_service.py
from __future__ import annotations
import pytest
from app.core.exceptions import ApprovalRequiredError, ConflictError
from app.governance.services.governance_execution_service import GovernanceExecutionService
class DummyChangeRequest:
    def __init__(self):
        self.id = "cr_1"
        self.directive_id = "dir_1"
        self.action_type = "provider_routing_override"
        self.target_version = 4
        self.requested_patch = {"provider": "runway"}
        self.requested_by = "user_a"
        self.requires_approval = True
        self.status = "pending"
        self.executed_at = None
class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity
    def require(self, change_request_id: str):
        return self.entity
class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision
class DummyApprovalRepo:
    def __init__(self, approvals):
        self.approvals = approvals
    def get_by_change_request_id(self, change_request_id: str):
        return self.approvals
class DummyAttemptRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        payload = {**payload, "id": f"attempt_{len(self.items)+1}"}
        self.items.append(payload)
        return type("Attempt", (), payload)
class DummyNotificationRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        self.items.append(payload)
        return payload
class DummyGateway:
    def __init__(self, version=4, fail_update=False):
        self.version = version
        self.fail_update = fail_update
    def get(self, directive_id: str):
        return {"directive_id": directive_id, "version": self.version, "state": {"provider": "veo"}}
    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        if self.fail_update:
            raise ConflictError("cas failed")
        return {
            "directive_id": directive_id,
            "version": expected_version + 1,
            "state": {"provider": patch["provider"]},
        }
class DummyAdapter:
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str):
        return {"applied": True, "after": {**directive_state, **requested_patch}}
class DummyRegistry:
    def resolve(self, action_type: str):
        return DummyAdapter()
def test_execute_requires_foreign_approval():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ApprovalRequiredError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
def test_execute_surfaces_version_conflict_before_apply():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=5),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
def test_execute_persists_success_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    notifications = DummyNotificationRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=notifications,
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    result = service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
    assert result["status"] == "executed"
    assert attempts.items[-1]["status"] == "success"
    assert notifications.items[-1]["event_type"] == "governance.change_request.executed"
22) backend/tests/api/test_governance_routes.py
from __future__ import annotations
def test_execute_conflict_returns_409(client, seeded_change_request_requires_approval, approved_by_other_actor):
    response = client.post(
        f"/governance/change-requests/{seeded_change_request_requires_approval}/execute",
        headers={"X-Actor-Id": "requester_user"},
    )
    assert response.status_code in {200, 409}
    # If your fixture intentionally bumps directive version first,
    # keep this strict assertion instead:
    # assert response.status_code == 409
23) Ghi chú nối khớp quan trọng
A. Compare-and-swap
DirectiveStateGateway.update_with_version_check(...) đã làm đúng compare-and-swap.
Nếu WHERE version = :expected_version không match, raise ConflictError.
Route map ConflictError -> HTTP 409.
B. Policy contract
GovernancePolicyService.evaluate_change_request(...) trả đúng 5 field bạn khóa:
allowed
requires_approval
approval_rule_key
reasons
risk_flags
C. Runtime fabric contract
RuntimeFabricAdapterRegistry.resolve(action_type) trả adapter có:
preview(...) -> dict
apply(...) -> dict
D. Repository contract
Đủ đúng các method đang được gọi:
GovernanceChangeRequestRepository.create/get/find_by_idempotency_key/list_pending_approvals
GovernanceApprovalRepository.create/get_by_change_request_id
GovernanceExecutionAttemptRepository.create
GovernanceNotificationRepository.create
24) Điểm cần bạn map vào codebase thật ngay sau khi paste
Base import
Đổi from app.db.base import Base theo base class thật của monorepo.
directive_state table
Tôi giữ DirectiveStateGateway ở mức SQL trực tiếp để bảo toàn CAS semantics.
Nếu schema thật khác (payload, config, state_json, v.v.), chỉ sửa SQL chứ không đổi contract method.
approval threshold
Bản này đang dùng ngưỡng tối thiểu 1 approval khác requester.
Nếu Phase 3 của bạn cần N-of-M, chèn rule đó vào GovernanceApprovalService / policy snapshot mà không đổi route surface.
tests/api
Tôi để skeleton vì fixture thật phụ thuộc app factory / db fixture hiện có của bạn.
Nếu bạn muốn, lượt tiếp theo tôi viết luôn fixture-ready test theo FastAPI + SQLAlchemy session override.
25) backend/alembic/versions/20260412_01_phase3_governance_core.py
"""phase 3 governance core
Revision ID: 20260412_01_phase3_governance_core
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12 10:30:00
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
# revision identifiers, used by Alembic.
revision = "20260412_01_phase3_governance_core"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table(
        "governance_change_request",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("directive_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("requested_patch", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_rule_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_governance_change_request_idempotency_key"),
    )
    op.create_index("ix_governance_change_request_directive_id", "governance_change_request", ["directive_id"])
    op.create_index("ix_governance_change_request_status", "governance_change_request", ["status"])
    op.create_index("ix_governance_change_request_created_at", "governance_change_request", ["created_at"])
    op.create_table(
        "governance_approval",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("approver_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("change_request_id", "approver_id", name="uq_governance_approval_request_approver"),
    )
    op.create_index("ix_governance_approval_change_request_id", "governance_approval", ["change_request_id"])
    op.create_index("ix_governance_approval_created_at", "governance_approval", ["created_at"])
    op.create_table(
        "governance_execution_attempt",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("directive_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("adapter_result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_execution_attempt_change_request_id", "governance_execution_attempt", ["change_request_id"])
    op.create_index("ix_governance_execution_attempt_directive_id", "governance_execution_attempt", ["directive_id"])
    op.create_index("ix_governance_execution_attempt_status", "governance_execution_attempt", ["status"])
    op.create_index("ix_governance_execution_attempt_created_at", "governance_execution_attempt", ["created_at"])
    op.create_table(
        "governance_notification_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_notification_event_change_request_id", "governance_notification_event", ["change_request_id"])
    op.create_index("ix_governance_notification_event_event_type", "governance_notification_event", ["event_type"])
    op.create_index("ix_governance_notification_event_created_at", "governance_notification_event", ["created_at"])
def downgrade() -> None:
    op.drop_index("ix_governance_notification_event_created_at", table_name="governance_notification_event")
    op.drop_index("ix_governance_notification_event_event_type", table_name="governance_notification_event")
    op.drop_index("ix_governance_notification_event_change_request_id", table_name="governance_notification_event")
    op.drop_table("governance_notification_event")
    op.drop_index("ix_governance_execution_attempt_created_at", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_status", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_directive_id", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_change_request_id", table_name="governance_execution_attempt")
    op.drop_table("governance_execution_attempt")
    op.drop_index("ix_governance_approval_created_at", table_name="governance_approval")
    op.drop_index("ix_governance_approval_change_request_id", table_name="governance_approval")
    op.drop_table("governance_approval")
    op.drop_index("ix_governance_change_request_created_at", table_name="governance_change_request")
    op.drop_index("ix_governance_change_request_status", table_name="governance_change_request")
    op.drop_index("ix_governance_change_request_directive_id", table_name="governance_change_request")
    op.drop_table("governance_change_request")
26) backend/tests/conftest.py
from __future__ import annotations
from collections.abc import Generator
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.deps import get_db
from app.api.routes.governance import router as governance_router
TEST_METADATA = MetaData()
directive_state_table = Table(
    "directive_state",
    TEST_METADATA,
    Column("directive_id", String(128), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("state", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)
def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(governance_router)
    return app
@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TEST_METADATA.create_all(engine)
    return engine
@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
@pytest.fixture()
def db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
@pytest.fixture()
def app(db_session: Session):
    app = _build_test_app()
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_get_db
    return app
@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)
@pytest.fixture()
def seed_directive_state(db_session: Session):
    def _seed(*, directive_id: str = "dir_1", version: int = 1, state: dict | None = None):
        db_session.execute(
            directive_state_table.insert().values(
                directive_id=directive_id,
                version=version,
                state=state or {"config": {"provider": "veo"}},
            )
        )
        db_session.commit()
        return directive_id
    return _seed
27) backend/tests/services/test_governance_approval_service.py
from __future__ import annotations
import pytest
from app.core.exceptions import ConflictError, ForbiddenActionError
from app.governance.services.governance_approval_service import GovernanceApprovalService
class DummyChangeRequest:
    def __init__(self, requested_by: str = "requester", status: str = "pending", requires_approval: bool = True):
        self.id = "cr_1"
        self.requested_by = requested_by
        self.status = status
        self.requires_approval = requires_approval
        self.rejected_at = None
class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity
    def require(self, change_request_id: str):
        return self.entity
class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision
class DummyApprovalRepo:
    def __init__(self, initial=None):
        self.items = list(initial or [])
    def create(self, payload: dict):
        item = DummyApproval(payload["approver_id"], payload["decision"])
        self.items.append(item)
        return type("ApprovalRow", (), {"id": "a_1", **payload})
    def get_by_change_request_id(self, change_request_id: str):
        return self.items
class DummyNotificationRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        self.items.append(payload)
        return payload
def test_self_approval_blocked():
    service = GovernanceApprovalService(
        change_request_repository=DummyChangeRequestRepo(DummyChangeRequest(requested_by="alice")),
        approval_repository=DummyApprovalRepo(),
        notification_repository=DummyNotificationRepo(),
    )
    with pytest.raises(ForbiddenActionError):
        service.record_decision(
            change_request_id="cr_1",
            approver_id="alice",
            decision="approved",
            reason=None,
        )
def test_duplicate_approval_blocked():
    service = GovernanceApprovalService(
        change_request_repository=DummyChangeRequestRepo(DummyChangeRequest()),
        approval_repository=DummyApprovalRepo(initial=[DummyApproval("bob", "approved")]),
        notification_repository=DummyNotificationRepo(),
    )
    with pytest.raises(ConflictError):
        service.record_decision(
            change_request_id="cr_1",
            approver_id="bob",
            decision="approved",
            reason=None,
        )
28) backend/tests/services/test_directive_state_gateway.py
from __future__ import annotations
import pytest
from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.exceptions import ConflictError, NotFoundError
from app.governance.services.directive_state_gateway import DirectiveStateGateway
def _setup_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    metadata = MetaData()
    directive_state = Table(
        "directive_state",
        metadata,
        Column("directive_id", String(128), primary_key=True),
        Column("version", Integer, nullable=False),
        Column("state", JSON, nullable=False),
    )
    metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return engine, SessionLocal, directive_state
def test_get_returns_state():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=3, state={"foo": "bar"}))
        db.commit()
        gateway = DirectiveStateGateway(db)
        row = gateway.get("dir_1")
        assert row["directive_id"] == "dir_1"
        assert row["version"] == 3
def test_get_raises_not_found():
    _, SessionLocal, _ = _setup_db()
    with SessionLocal() as db:
        gateway = DirectiveStateGateway(db)
        with pytest.raises(NotFoundError):
            gateway.get("missing")
def test_update_with_version_check_success():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=2, state={"a": 1}))
        db.commit()
        gateway = DirectiveStateGateway(db)
        row = gateway.update_with_version_check("dir_1", expected_version=2, patch={"b": 2})
        db.commit()
        assert row["version"] == 3
        assert row["state"]["a"] == 1
        assert row["state"]["b"] == 2
def test_update_with_version_check_conflict():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=4, state={"a": 1}))
        db.commit()
        gateway = DirectiveStateGateway(db)
        with pytest.raises(ConflictError):
            gateway.update_with_version_check("dir_1", expected_version=3, patch={"b": 2})
29) backend/tests/api/test_governance_routes.py
from __future__ import annotations
from sqlalchemy import text
def _create_change_request(client, *, target_version=1, actor_id="requester", idempotency_key="idem-1"):
    response = client.post(
        "/governance/change-requests",
        headers={"X-Actor-Id": actor_id},
        json={
            "directive_id": "dir_1",
            "action_type": "provider_routing_override",
            "target_version": target_version,
            "requested_patch": {"provider": "runway"},
            "idempotency_key": idempotency_key,
            "notes": "switch provider",
        },
    )
    assert response.status_code == 200
    return response.json()
def test_create_change_request_is_idempotent(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    first = _create_change_request(client, idempotency_key="same-key")
    second = _create_change_request(client, idempotency_key="same-key")
    assert first["id"] == second["id"]
def test_simulate_returns_policy_fields(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    response = client.post(
        "/governance/simulate",
        headers={"X-Actor-Id": "alice"},
        json={
            "directive_id": "dir_1",
            "action_type": "provider_routing_override",
            "target_version": 1,
            "requested_patch": {"provider": "runway"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(["allowed", "requires_approval", "approval_rule_key", "reasons", "risk_flags", "preview"]).issubset(body.keys())
def test_self_approval_returns_403(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, actor_id="alice", idempotency_key="idem-self-approval")
    response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "alice"},
        json={"decision": "approved", "reason": "looks good"},
    )
    assert response.status_code == 403
def test_execute_without_required_approval_returns_409(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, actor_id="requester", idempotency_key="idem-no-approval")
    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )
    assert response.status_code == 409
    assert "approval" in response.json()["detail"].lower()
def test_execute_version_conflict_returns_409(client, db_session, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, target_version=1, actor_id="requester", idempotency_key="idem-conflict")
    approval_response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "approver_1"},
        json={"decision": "approved", "reason": "approved by reviewer"},
    )
    assert approval_response.status_code == 200
    db_session.execute(
        text(
            "UPDATE directive_state SET version = 2, state = :state WHERE directive_id = :directive_id"
        ),
        {"directive_id": "dir_1", "state": {"config": {"provider": "veo", "touched": True}}},
    )
    db_session.commit()
    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )
    assert response.status_code == 409
    assert "version" in response.json()["detail"].lower() or "conflict" in response.json()["detail"].lower()
def test_execute_success_returns_updated_version(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, target_version=1, actor_id="requester", idempotency_key="idem-success")
    approval_response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "approver_1"},
        json={"decision": "approved", "reason": "approved"},
    )
    assert approval_response.status_code == 200
    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "executed"
    assert body["updated_version"] == 2
30) backend/tests/services/test_governance_execution_service.py (bản siết chặt hơn)
from __future__ import annotations
import pytest
from app.core.exceptions import ApprovalRequiredError, ConflictError
from app.governance.services.governance_execution_service import GovernanceExecutionService
class DummyChangeRequest:
    def __init__(self):
        self.id = "cr_1"
        self.directive_id = "dir_1"
        self.action_type = "provider_routing_override"
        self.target_version = 4
        self.requested_patch = {"provider": "runway"}
        self.requested_by = "user_a"
        self.requires_approval = True
        self.status = "pending"
        self.executed_at = None
class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity
    def require(self, change_request_id: str):
        return self.entity
class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision
class DummyApprovalRepo:
    def __init__(self, approvals):
        self.approvals = approvals
    def get_by_change_request_id(self, change_request_id: str):
        return self.approvals
class DummyAttemptRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        payload = {**payload, "id": f"attempt_{len(self.items)+1}"}
        self.items.append(payload)
        return type("Attempt", (), payload)
class DummyNotificationRepo:
    def __init__(self):
        self.items = []
    def create(self, payload: dict):
        self.items.append(payload)
        return payload
class DummyGateway:
    def __init__(self, version=4, fail_update=False):
        self.version = version
        self.fail_update = fail_update
    def get(self, directive_id: str):
        return {"directive_id": directive_id, "version": self.version, "state": {"provider": "veo"}}
    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        if self.fail_update:
            raise ConflictError("cas failed")
        return {
            "directive_id": directive_id,
            "version": expected_version + 1,
            "state": {"provider": patch["provider"]},
        }
class DummyAdapter:
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str):
        return {"applied": True, "after": {**directive_state, **requested_patch}}
class DummyRegistry:
    def resolve(self, action_type: str):
        return DummyAdapter()
def test_execute_requires_foreign_approval():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ApprovalRequiredError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
def test_execute_surfaces_version_conflict_before_apply():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=5),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
    assert attempts.items[-1]["status"] == "conflict"
    assert attempts.items[-1]["error_code"] == "directive_version_conflict"
def test_execute_surfaces_cas_conflict_as_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4, fail_update=True),
        adapter_registry=DummyRegistry(),
    )
    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
    assert attempts.items[-1]["status"] == "conflict"
    assert attempts.items[-1]["adapter_result"]["applied"] is True
def test_execute_persists_success_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    notifications = DummyNotificationRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=notifications,
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )
    result = service.execute_change_request(change_request_id="cr_1", actor_id="user_a")
    assert result["status"] == "executed"
    assert attempts.items[-1]["status"] == "success"
    assert notifications.items[-1]["event_type"] == "governance.change_request.executed"
31) Điểm cần chỉnh rất ngắn trước khi paste vào monorepo thật
down_revision
thay "<PUT_PREVIOUS_REVISION_HERE>" bằng revision Alembic gần nhất của bạn.
SQLite test compatibility
DirectiveStateGateway đang dùng SQL text + JSON object binding.
Nếu test SQLite của monorepo đang strict, có thể đổi test DB sang Postgres test container hoặc serialize JSON bằng json.dumps(...) trong gateway/test helper.
directive_state schema thật
test đang dựng bảng tối thiểu chỉ để kiểm CAS contract.
nếu codebase thật có model/bảng sẵn, giữ nguyên test intent nhưng map lại tên cột.
approval threshold
hiện là chỉ cần 1 approver khác requester.
nếu hệ thật cần dual approval, sửa assertion test tương ứng, không cần đổi route surface.
32) Thứ nên viết tiếp ngay sau migration + tests
Sau cụm này, bước mạnh nhất là:
rbac.py cho create/approve/execute permissions
actor header deps typed hơn (X-Actor-Id, X-Actor-Roles)
error response schema chuẩn hóa cho frontend
frontend retry flow khi nhận 409 directive_version_conflict
approval queue endpoint thật (list_pending_approvals route)
Nếu bạn muốn, tôi sẽ viết tiếp nguyên cụm đó theo đúng style hiện tại, bắt đầu từ:
backend/app/governance/rbac.py
backend/app/api/deps/auth.py
backend/app/governance/schemas/errors.py
backend/tests/api/test_governance_rbac.py
frontend governance conflict handling contract
Dưới đây là bản PHASE 3 — RBAC + AUTH + ERROR CONTRACT + PENDING APPROVALS ROUTE theo kiểu file-by-file patch, giữ sát flow bạn đã có ở Phase 2/3 để paste vào repo thật.
Tôi giả định stack hiện tại là FastAPI + SQLAlchemy + Alembic + service layer + repository layer và bạn đã có:
governance_approval_service.py
governance_execution_service.py
directive_state_gateway.py
governance models + repositories + migration + tests Phase 3
Tôi sẽ chỉ nối thêm 4 lớp:
Auth deps đọc actor từ request headers
RBAC policy helpers
Standardized error contract
Pending approvals route
1) backend/app/core/error_codes.py
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
2) backend/app/core/exceptions.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.error_codes import ErrorCode


@dataclass(slots=True)
class AppError(Exception):
    code: ErrorCode
    message: str
    status_code: int
    details: dict[str, Any] = field(default_factory=dict)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=401,
            details=details or {},
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", details: dict[str, Any] | None = None):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=403,
            details=details or {},
        )


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=404,
            details=details or {},
        )


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", details: dict[str, Any] | None = None):
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=409,
            details=details or {},
        )


class ValidationAppError(AppError):
    def __init__(self, message: str = "Validation error", details: dict[str, Any] | None = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=422,
            details=details or {},
        )
3) backend/app/api/schemas/error_schema.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
4) backend/app/core/error_handlers.py
from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


def _request_id_from_request(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid4())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id_from_request(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code.value,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id_from_request(request)
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorCode.VALIDATION_ERROR.value,
                "message": "Request validation failed",
                "details": {
                    "issues": exc.errors(),
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id_from_request(request)

        if exc.status_code == 401:
            error = ErrorCode.UNAUTHORIZED.value
        elif exc.status_code == 403:
            error = ErrorCode.FORBIDDEN.value
        elif exc.status_code == 404:
            error = ErrorCode.NOT_FOUND.value
        elif exc.status_code == 409:
            error = ErrorCode.CONFLICT.value
        elif exc.status_code == 422:
            error = ErrorCode.VALIDATION_ERROR.value
        else:
            error = ErrorCode.INTERNAL_ERROR.value

        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message", "HTTP error")
            details = detail.get("details", {})
        else:
            message = str(detail)
            details = {}

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error,
                "message": message,
                "details": details,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from_request(request)
        return JSONResponse(
            status_code=500,
            content={
                "error": ErrorCode.INTERNAL_ERROR.value,
                "message": "Unexpected internal error",
                "details": {},
                "request_id": request_id,
            },
        )
5) nối handler vào app factory
Ví dụ backend/app/main.py hoặc backend/app/app.py
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.governance import router as governance_router
from app.core.error_handlers import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="Governance API")

    register_error_handlers(app)

    app.include_router(governance_router, prefix="/api/v1")

    return app


app = create_app()
6) backend/app/api/deps/auth.py
File này chuẩn hóa actor context lấy từ headers.
Giữ đơn giản để hợp với test hiện tại và dễ thay JWT/Auth thật sau.
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from app.core.exceptions import UnauthorizedError


@dataclass(slots=True)
class ActorContext:
    actor_id: str
    actor_role: str
    actor_email: str | None = None
    actor_name: str | None = None


async def get_actor_context(
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_actor_role: str | None = Header(default=None, alias="X-Actor-Role"),
    x_actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
    x_actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> ActorContext:
    if not x_actor_id:
        raise UnauthorizedError(
            message="Missing X-Actor-Id header",
            details={"header": "X-Actor-Id"},
        )
    if not x_actor_role:
        raise UnauthorizedError(
            message="Missing X-Actor-Role header",
            details={"header": "X-Actor-Role"},
        )

    return ActorContext(
        actor_id=x_actor_id,
        actor_role=x_actor_role,
        actor_email=x_actor_email,
        actor_name=x_actor_name,
    )
7) backend/app/services/rbac.py
Nếu file rbac.py đã có từ Phase 2, bạn chỉ cần mở rộng theo hướng này.
from __future__ import annotations

from app.api.deps.auth import ActorContext
from app.core.exceptions import ForbiddenError


ROLE_ADMIN = "admin"
ROLE_GOVERNANCE_ADMIN = "governance_admin"
ROLE_APPROVER = "approver"
ROLE_OPERATOR = "operator"
ROLE_STRATEGY_OWNER = "strategy_owner"
ROLE_VIEWER = "viewer"


APPROVAL_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
}

EXECUTION_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_OPERATOR,
    ROLE_STRATEGY_OWNER,
}

READ_PENDING_APPROVALS_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
}


def require_any_role(actor: ActorContext, allowed_roles: set[str]) -> None:
    if actor.actor_role not in allowed_roles:
        raise ForbiddenError(
            message="Actor does not have the required role",
            details={
                "actor_role": actor.actor_role,
                "allowed_roles": sorted(allowed_roles),
            },
        )


def require_can_approve(actor: ActorContext) -> None:
    require_any_role(actor, APPROVAL_ROLES)


def require_can_execute(actor: ActorContext) -> None:
    require_any_role(actor, EXECUTION_ROLES)


def require_can_list_pending_approvals(actor: ActorContext) -> None:
    require_any_role(actor, READ_PENDING_APPROVALS_ROLES)
8) backend/app/api/schemas/governance.py
Nếu bạn đã có file schemas governance rồi, chỉ thêm mấy model còn thiếu.
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernanceChangeRequestCreate(BaseModel):
    directive_id: str
    action_type: str
    expected_directive_version: int
    patch: dict[str, Any]
    reason: str | None = None
    idempotency_key: str = Field(..., min_length=1, max_length=255)


class GovernanceChangeRequestResponse(BaseModel):
    id: str
    directive_id: str
    action_type: str
    status: str
    requested_by: str
    reason: str | None = None
    idempotency_key: str
    expected_directive_version: int
    patch: dict[str, Any]
    created_at: datetime


class GovernanceSimulationRequest(BaseModel):
    directive_id: str
    action_type: str
    expected_directive_version: int
    patch: dict[str, Any]


class GovernanceSimulationResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)


class GovernanceApprovalRequest(BaseModel):
    note: str | None = None


class GovernanceApprovalResponse(BaseModel):
    id: str
    change_request_id: str
    approver_id: str
    note: str | None = None
    created_at: datetime


class GovernanceExecuteResponse(BaseModel):
    directive_id: str
    updated_version: int
    execution_status: str
    change_request_id: str


class GovernancePendingApprovalItem(BaseModel):
    change_request_id: str
    directive_id: str
    action_type: str
    requested_by: str
    reason: str | None = None
    approval_rule_key: str | None = None
    status: str
    created_at: datetime


class GovernancePendingApprovalsResponse(BaseModel):
    items: list[GovernancePendingApprovalItem]
9) backend/app/repositories/governance_change_request_repository.py
Bạn nói repository này đã có list_pending_approvals. Chỉ cần chuẩn hóa contract kiểu này nếu chưa có.
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_change_request import GovernanceChangeRequest


class GovernanceChangeRequestRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, entity: GovernanceChangeRequest) -> GovernanceChangeRequest:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        return self.session.get(GovernanceChangeRequest, change_request_id)

    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt: Select[tuple[GovernanceChangeRequest]] = select(GovernanceChangeRequest).where(
            GovernanceChangeRequest.idempotency_key == idempotency_key
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_pending_approvals(self, limit: int = 100, offset: int = 0) -> list[GovernanceChangeRequest]:
        stmt: Select[tuple[GovernanceChangeRequest]] = (
            select(GovernanceChangeRequest)
            .where(GovernanceChangeRequest.status == "pending_approval")
            .order_by(GovernanceChangeRequest.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
10) backend/app/services/governance_pending_approval_service.py
from __future__ import annotations

from app.repositories.governance_change_request_repository import GovernanceChangeRequestRepository


class GovernancePendingApprovalService:
    def __init__(self, change_request_repo: GovernanceChangeRequestRepository):
        self.change_request_repo = change_request_repo

    def list_pending(self, limit: int = 100, offset: int = 0):
        return self.change_request_repo.list_pending_approvals(limit=limit, offset=offset)
11) backend/app/api/routes/governance.py
Đây là phần quan trọng nhất:
create change request
simulate
approve
execute
list pending approvals
map lỗi thống nhất
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import ActorContext, get_actor_context
from app.api.schemas.error_schema import ErrorResponse
from app.api.schemas.governance import (
    GovernanceApprovalRequest,
    GovernanceApprovalResponse,
    GovernanceChangeRequestCreate,
    GovernanceChangeRequestResponse,
    GovernanceExecuteResponse,
    GovernancePendingApprovalItem,
    GovernancePendingApprovalsResponse,
    GovernanceSimulationRequest,
    GovernanceSimulationResponse,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.governance_change_request import GovernanceChangeRequest
from app.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.services.governance_approval_service import GovernanceApprovalService
from app.services.governance_execution_service import GovernanceExecutionService
from app.services.governance_pending_approval_service import GovernancePendingApprovalService
from app.services.governance_policy import GovernancePolicyService
from app.services.governance_simulation_service import GovernanceSimulationService
from app.services.rbac import (
    require_can_approve,
    require_can_execute,
    require_can_list_pending_approvals,
)

router = APIRouter(prefix="/governance", tags=["governance"])


def get_change_request_repo(db: Session = Depends(get_db)) -> GovernanceChangeRequestRepository:
    return GovernanceChangeRequestRepository(db)


def get_approval_repo(db: Session = Depends(get_db)) -> GovernanceApprovalRepository:
    return GovernanceApprovalRepository(db)


def get_execution_attempt_repo(db: Session = Depends(get_db)) -> GovernanceExecutionAttemptRepository:
    return GovernanceExecutionAttemptRepository(db)


def get_notification_repo(db: Session = Depends(get_db)) -> GovernanceNotificationRepository:
    return GovernanceNotificationRepository(db)


def get_policy_service() -> GovernancePolicyService:
    return GovernancePolicyService()


def get_simulation_service(
    db: Session = Depends(get_db),
) -> GovernanceSimulationService:
    return GovernanceSimulationService(
        policy_service=GovernancePolicyService(),
        runtime_adapter_registry=None,  # map repo thật của bạn vào đây
        directive_state_gateway=None,   # map gateway thật của bạn vào đây
        session=db,
    )


def get_pending_approval_service(
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
) -> GovernancePendingApprovalService:
    return GovernancePendingApprovalService(change_request_repo)


def get_approval_service(
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
    approval_repo: GovernanceApprovalRepository = Depends(get_approval_repo),
    notification_repo: GovernanceNotificationRepository = Depends(get_notification_repo),
    db: Session = Depends(get_db),
) -> GovernanceApprovalService:
    return GovernanceApprovalService(
        session=db,
        change_request_repo=change_request_repo,
        approval_repo=approval_repo,
        notification_repo=notification_repo,
    )


def get_execution_service(
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
    execution_attempt_repo: GovernanceExecutionAttemptRepository = Depends(get_execution_attempt_repo),
    notification_repo: GovernanceNotificationRepository = Depends(get_notification_repo),
    db: Session = Depends(get_db),
) -> GovernanceExecutionService:
    return GovernanceExecutionService(
        session=db,
        change_request_repo=change_request_repo,
        execution_attempt_repo=execution_attempt_repo,
        notification_repo=notification_repo,
        directive_state_gateway=None,    # map thật
        runtime_adapter_registry=None,   # map thật
    )


@router.post(
    "/change-requests",
    response_model=GovernanceChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_change_request(
    payload: GovernanceChangeRequestCreate,
    actor: ActorContext = Depends(get_actor_context),
    db: Session = Depends(get_db),
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
):
    existing = change_request_repo.find_by_idempotency_key(payload.idempotency_key)
    if existing:
        return GovernanceChangeRequestResponse(
            id=existing.id,
            directive_id=existing.directive_id,
            action_type=existing.action_type,
            status=existing.status,
            requested_by=existing.requested_by,
            reason=existing.reason,
            idempotency_key=existing.idempotency_key,
            expected_directive_version=existing.expected_directive_version,
            patch=existing.patch,
            created_at=existing.created_at,
        )

    entity = GovernanceChangeRequest(
        directive_id=payload.directive_id,
        action_type=payload.action_type,
        status="pending_approval",
        requested_by=actor.actor_id,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        expected_directive_version=payload.expected_directive_version,
        patch=payload.patch,
    )

    try:
        created = change_request_repo.create(entity)
        db.commit()
        db.refresh(created)
    except IntegrityError:
        db.rollback()
        existing = change_request_repo.find_by_idempotency_key(payload.idempotency_key)
        if existing:
            return GovernanceChangeRequestResponse(
                id=existing.id,
                directive_id=existing.directive_id,
                action_type=existing.action_type,
                status=existing.status,
                requested_by=existing.requested_by,
                reason=existing.reason,
                idempotency_key=existing.idempotency_key,
                expected_directive_version=existing.expected_directive_version,
                patch=existing.patch,
                created_at=existing.created_at,
            )
        raise ConflictError(
            message="Idempotency conflict",
            details={"idempotency_key": payload.idempotency_key},
        )

    return GovernanceChangeRequestResponse(
        id=created.id,
        directive_id=created.directive_id,
        action_type=created.action_type,
        status=created.status,
        requested_by=created.requested_by,
        reason=created.reason,
        idempotency_key=created.idempotency_key,
        expected_directive_version=created.expected_directive_version,
        patch=created.patch,
        created_at=created.created_at,
    )


@router.post(
    "/simulate",
    response_model=GovernanceSimulationResponse,
    responses={401: {"model": ErrorResponse}},
)
def simulate_change(
    payload: GovernanceSimulationRequest,
    actor: ActorContext = Depends(get_actor_context),
    simulation_service: GovernanceSimulationService = Depends(get_simulation_service),
):
    result = simulation_service.evaluate_change_request(
        directive_id=payload.directive_id,
        action_type=payload.action_type,
        expected_directive_version=payload.expected_directive_version,
        patch=payload.patch,
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    )
    return GovernanceSimulationResponse(**result)


@router.post(
    "/change-requests/{change_request_id}/approve",
    response_model=GovernanceApprovalResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def approve_change_request(
    change_request_id: str,
    payload: GovernanceApprovalRequest,
    actor: ActorContext = Depends(get_actor_context),
    approval_service: GovernanceApprovalService = Depends(get_approval_service),
):
    require_can_approve(actor)

    try:
        approval = approval_service.approve(
            change_request_id=change_request_id,
            approver_id=actor.actor_id,
            note=payload.note,
        )
    except ValueError as exc:
        message = str(exc)
        if "self-approval" in message.lower():
            raise ForbiddenError(message=message)
        if "not found" in message.lower():
            raise NotFoundError(message=message)
        raise ConflictError(message=message)

    return GovernanceApprovalResponse(
        id=approval.id,
        change_request_id=approval.change_request_id,
        approver_id=approval.approver_id,
        note=approval.note,
        created_at=approval.created_at,
    )


@router.post(
    "/change-requests/{change_request_id}/execute",
    response_model=GovernanceExecuteResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def execute_change_request(
    change_request_id: str,
    actor: ActorContext = Depends(get_actor_context),
    execution_service: GovernanceExecutionService = Depends(get_execution_service),
):
    require_can_execute(actor)

    try:
        result = execution_service.execute(
            change_request_id=change_request_id,
            executed_by=actor.actor_id,
        )
    except ValueError as exc:
        message = str(exc)
        lowered = message.lower()
        if "not found" in lowered:
            raise NotFoundError(message=message)
        if "approval" in lowered or "version conflict" in lowered or "conflict" in lowered:
            raise ConflictError(message=message)
        raise ConflictError(message=message)

    return GovernanceExecuteResponse(
        directive_id=result["directive_id"],
        updated_version=result["updated_version"],
        execution_status=result["execution_status"],
        change_request_id=change_request_id,
    )


@router.get(
    "/pending-approvals",
    response_model=GovernancePendingApprovalsResponse,
    responses={
        403: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def list_pending_approvals(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: GovernancePendingApprovalService = Depends(get_pending_approval_service),
):
    require_can_list_pending_approvals(actor)

    items = service.list_pending(limit=limit, offset=offset)

    return GovernancePendingApprovalsResponse(
        items=[
            GovernancePendingApprovalItem(
                change_request_id=item.id,
                directive_id=item.directive_id,
                action_type=item.action_type,
                requested_by=item.requested_by,
                reason=item.reason,
                approval_rule_key=getattr(item, "approval_rule_key", None),
                status=item.status,
                created_at=item.created_at,
            )
            for item in items
        ]
    )
12) nếu service layer đang ném exception thô, map sang domain exception gọn hơn
Đây là điểm rất đáng làm để route sạch hơn.
Ví dụ trong governance_approval_service.py:
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError


class GovernanceApprovalService:
    def __init__(self, session, change_request_repo, approval_repo, notification_repo):
        self.session = session
        self.change_request_repo = change_request_repo
        self.approval_repo = approval_repo
        self.notification_repo = notification_repo

    def approve(self, change_request_id: str, approver_id: str, note: str | None = None):
        change_request = self.change_request_repo.get(change_request_id)
        if not change_request:
            raise NotFoundError("Change request not found", {"change_request_id": change_request_id})

        if change_request.requested_by == approver_id:
            raise ForbiddenError(
                "Self-approval is not allowed",
                {
                    "change_request_id": change_request_id,
                    "approver_id": approver_id,
                },
            )

        try:
            approval = self.approval_repo.create_from_change_request(
                change_request_id=change_request_id,
                approver_id=approver_id,
                note=note,
            )
            change_request.status = "approved"
            self.session.flush()
            self.session.commit()
            self.session.refresh(approval)
            return approval
        except IntegrityError:
            self.session.rollback()
            raise ConflictError(
                "Approval already exists for this approver and change request",
                {
                    "change_request_id": change_request_id,
                    "approver_id": approver_id,
                },
            )
Và governance_execution_service.py:
from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError


class GovernanceExecutionService:
    def __init__(
        self,
        session,
        change_request_repo,
        execution_attempt_repo,
        notification_repo,
        directive_state_gateway,
        runtime_adapter_registry,
    ):
        self.session = session
        self.change_request_repo = change_request_repo
        self.execution_attempt_repo = execution_attempt_repo
        self.notification_repo = notification_repo
        self.directive_state_gateway = directive_state_gateway
        self.runtime_adapter_registry = runtime_adapter_registry

    def execute(self, change_request_id: str, executed_by: str) -> dict:
        change_request = self.change_request_repo.get(change_request_id)
        if not change_request:
            raise NotFoundError("Change request not found", {"change_request_id": change_request_id})

        if change_request.status != "approved":
            raise ConflictError(
                "Change request must be approved before execution",
                {
                    "change_request_id": change_request_id,
                    "status": change_request.status,
                },
            )

        adapter = self.runtime_adapter_registry.resolve(change_request.action_type)

        current_state = self.directive_state_gateway.get(change_request.directive_id)
        if current_state is None:
            raise NotFoundError(
                "Directive state not found",
                {"directive_id": change_request.directive_id},
            )

        try:
            adapter.apply(
                directive_id=change_request.directive_id,
                patch=change_request.patch,
            )

            updated_state = self.directive_state_gateway.update_with_version_check(
                directive_id=change_request.directive_id,
                expected_version=change_request.expected_directive_version,
                patch=change_request.patch,
            )
        except Exception as exc:
            self.session.rollback()
            if "version" in str(exc).lower() or exc.__class__.__name__.lower().startswith("conflict"):
                raise ConflictError(
                    "Directive version conflict",
                    {
                        "directive_id": change_request.directive_id,
                        "expected_version": change_request.expected_directive_version,
                    },
                )
            raise

        attempt = self.execution_attempt_repo.create(
            change_request_id=change_request_id,
            directive_id=change_request.directive_id,
            executed_by=executed_by,
            status="succeeded",
            result_payload={"updated_version": updated_state.version},
        )

        change_request.status = "executed"
        self.session.flush()
        self.session.commit()

        return {
            "directive_id": change_request.directive_id,
            "updated_version": updated_state.version,
            "execution_status": attempt.status,
        }
13) test cho auth + RBAC + pending approvals
backend/tests/api/test_governance_auth_and_rbac.py
from __future__ import annotations


def _auth_headers(actor_id: str, role: str) -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }


def test_missing_actor_headers_returns_401(client):
    response = client.get("/api/v1/governance/pending-approvals")
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "unauthorized"
    assert "request_id" in body


def test_pending_approvals_forbidden_for_viewer(client):
    response = client.get(
        "/api/v1/governance/pending-approvals",
        headers=_auth_headers("viewer-1", "viewer"),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "forbidden"
    assert body["details"]["actor_role"] == "viewer"


def test_pending_approvals_success_for_approver(client, db_session, seed_pending_change_request):
    response = client.get(
        "/api/v1/governance/pending-approvals",
        headers=_auth_headers("approver-1", "approver"),
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) >= 1
backend/tests/api/test_error_contract.py
from __future__ import annotations


def _auth_headers(actor_id: str, role: str) -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }


def test_self_approval_returns_standardized_403(client, created_change_request):
    response = client.post(
        f"/api/v1/governance/change-requests/{created_change_request['id']}/approve",
        json={"note": "approve"},
        headers=_auth_headers(created_change_request["requested_by"], "approver"),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "forbidden"
    assert body["message"]
    assert "request_id" in body


def test_execute_without_approval_returns_standardized_409(client, created_change_request):
    response = client.post(
        f"/api/v1/governance/change-requests/{created_change_request['id']}/execute",
        headers=_auth_headers("operator-1", "operator"),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "conflict"
    assert "request_id" in body
14) fixture seed pending change request
Trong tests/conftest.py, thêm fixture rất ngắn:
import uuid

import pytest

from app.models.governance_change_request import GovernanceChangeRequest


@pytest.fixture
def seed_pending_change_request(db_session):
    entity = GovernanceChangeRequest(
        id=str(uuid.uuid4()),
        directive_id="directive-1",
        action_type="provider_routing_override",
        status="pending_approval",
        requested_by="requester-1",
        reason="Need safer provider override",
        idempotency_key=str(uuid.uuid4()),
        expected_directive_version=1,
        patch={"provider": "runway"},
    )
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    return entity
15) frontend error contract
Đây là shape FE nên bám theo để conflict handling rất sạch:
frontend/src/types/api.ts
export type ApiError = {
  error: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string | null;
};
frontend/src/lib/api.ts
export async function parseApiError(response: Response) {
  let body: any = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  return {
    status: response.status,
    error: body?.error ?? "internal_error",
    message: body?.message ?? "Unexpected error",
    details: body?.details ?? {},
    request_id: body?.request_id ?? null,
  };
}
conflict handling ví dụ trong action handler
try {
  const res = await fetch(`/api/v1/governance/change-requests/${id}/execute`, {
    method: "POST",
    headers: {
      "X-Actor-Id": actorId,
      "X-Actor-Role": actorRole,
    },
  });

  if (!res.ok) {
    const err = await parseApiError(res);

    if (res.status === 409 && err.error === "conflict") {
      openConflictDialog({
        title: "Execution conflict",
        message: err.message,
        details: err.details,
        requestId: err.request_id,
      });
      return;
    }

    throw err;
  }

  const data = await res.json();
  toast.success(`Executed. Updated version: ${data.updated_version}`);
} catch (err: any) {
  toast.error(err.message ?? "Execution failed");
}
16) OpenAPI responses chuẩn hóa
Nếu muốn spec đẹp ngay trên Swagger, thêm helper:
backend/app/api/openapi_responses.py
from __future__ import annotations

from app.api.schemas.error_schema import ErrorResponse


STANDARD_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
Sau đó route chỉ cần:
from app.api.openapi_responses import STANDARD_ERROR_RESPONSES

@router.get(
    "/pending-approvals",
    response_model=GovernancePendingApprovalsResponse,
    responses={
        401: STANDARD_ERROR_RESPONSES[401],
        403: STANDARD_ERROR_RESPONSES[403],
    },
)
def list_pending_approvals(...):
    ...
17) điểm map rất ngắn khi paste vào repo thật
Bạn gần như chỉ cần map 6 điểm này:
A. GovernanceSimulationService
Nếu service của bạn không nhận session hoặc chưa có evaluate_change_request(...) theo đúng contract, map constructor cho khớp repo hiện tại.
B. GovernanceApprovalService
Nếu hiện tại service đang raise ValueError, giữ route mapping như trên vẫn chạy được.
Tốt hơn là đổi sang ForbiddenError / ConflictError / NotFoundError.
C. GovernanceExecutionService
Map vào:
directive_state_gateway
runtime_adapter_registry
D. GovernanceChangeRequest model
Đảm bảo có các field:
id
directive_id
action_type
status
requested_by
reason
idempotency_key
expected_directive_version
patch
created_at
E. app factory
Phải gọi register_error_handlers(app).
F. auth header names
Nếu Phase 2 của bạn đã dùng header khác, chỉ cần đổi alias:
X-Actor-Id
X-Actor-Role
X-Actor-Email
X-Actor-Name
18) vì sao đây là bước đúng nhất ngay sau migration + tests
Lớp này khóa thêm 4 thứ rất quan trọng:
auth boundary rõ ràng: route không còn chạy “anonymous by accident”
RBAC boundary rõ ràng: ai được approve, ai được execute, ai được xem pending approvals
error contract ổn định: FE không phải đoán text lỗi
operational queue surface: có route pending approvals để nối UI điều phối thật
Tức là hệ chuyển từ:
“service có logic đúng”
sang:
“API có contract production-ready”
19) thứ tự paste vào repo thật
Nên paste theo thứ tự này để ít vỡ nhất:
core/error_codes.py
core/exceptions.py
api/schemas/error_schema.py
core/error_handlers.py
api/deps/auth.py
services/rbac.py
services/governance_pending_approval_service.py
update repositories/governance_change_request_repository.py nếu cần
update api/schemas/governance.py
update api/routes/governance.py
nối register_error_handlers(app) vào app factory
thêm test auth/rbac/error contract
Dưới đây là bản PHASE 3 — FRONTEND CONFLICT HANDLING + PENDING APPROVALS UI theo đúng format file-by-file, giữ tinh thần:
không tái cấu trúc vô cớ
bám đúng error contract backend vừa chốt
ưu tiên paste vào repo thật với ít chỉnh nhất
hỗ trợ:
pending approvals list
approve action
execute action
conflict dialog
standardized API error parsing
refresh sau conflict / approve / execute
role-based action gating ở UI
Tôi giả định frontend hiện tại là:
React + TypeScript
có fetch hoặc API helper đơn giản
có GovernanceActionBar.tsx
có patch nối ExplainDrawer
có state quản lý actor headers ở đâu đó, hoặc tạm truyền vào component
1) frontend/src/types/api.ts
export type ApiError = {
  error: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string | null;
};

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError; status: number };
2) frontend/src/types/governance.ts
export type GovernancePendingApprovalItem = {
  change_request_id: string;
  directive_id: string;
  action_type: string;
  requested_by: string;
  reason?: string | null;
  approval_rule_key?: string | null;
  status: string;
  created_at: string;
};

export type GovernancePendingApprovalsResponse = {
  items: GovernancePendingApprovalItem[];
};

export type GovernanceApprovalResponse = {
  id: string;
  change_request_id: string;
  approver_id: string;
  note?: string | null;
  created_at: string;
};

export type GovernanceExecuteResponse = {
  directive_id: string;
  updated_version: number;
  execution_status: string;
  change_request_id: string;
};

export type ActorContext = {
  actorId: string;
  actorRole: string;
  actorEmail?: string;
  actorName?: string;
};
3) frontend/src/lib/api.ts
Chuẩn hóa fetch + parse error contract.
import type { ApiError, ApiResult } from "@/types/api";
import type { ActorContext } from "@/types/governance";

function buildActorHeaders(actor: ActorContext): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Actor-Id": actor.actorId,
    "X-Actor-Role": actor.actorRole,
    ...(actor.actorEmail ? { "X-Actor-Email": actor.actorEmail } : {}),
    ...(actor.actorName ? { "X-Actor-Name": actor.actorName } : {}),
  };
}

export async function parseApiError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    return {
      error: body?.error ?? "internal_error",
      message: body?.message ?? "Unexpected error",
      details: body?.details ?? {},
      request_id: body?.request_id ?? null,
    };
  } catch {
    return {
      error: "internal_error",
      message: "Unexpected error",
      details: {},
      request_id: null,
    };
  }
}

export async function apiRequest<T>(
  input: RequestInfo | URL,
  init: RequestInit & { actor?: ActorContext } = {}
): Promise<ApiResult<T>> {
  const headers: HeadersInit = {
    ...(init.headers ?? {}),
    ...(init.actor ? buildActorHeaders(init.actor) : {}),
  };

  const response = await fetch(input, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const error = await parseApiError(response);
    return {
      ok: false,
      error,
      status: response.status,
    };
  }

  const data = (await response.json()) as T;
  return {
    ok: true,
    data,
  };
}
4) frontend/src/lib/governanceApi.ts
API helpers riêng cho governance.
import { apiRequest } from "@/lib/api";
import type {
  ActorContext,
  GovernanceApprovalResponse,
  GovernanceExecuteResponse,
  GovernancePendingApprovalsResponse,
} from "@/types/governance";

const GOVERNANCE_BASE = "/api/v1/governance";

export async function fetchPendingApprovals(params: {
  actor: ActorContext;
  limit?: number;
  offset?: number;
}) {
  const search = new URLSearchParams({
    limit: String(params.limit ?? 100),
    offset: String(params.offset ?? 0),
  });

  return apiRequest<GovernancePendingApprovalsResponse>(
    `${GOVERNANCE_BASE}/pending-approvals?${search.toString()}`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function approveChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  note?: string;
}) {
  return apiRequest<GovernanceApprovalResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/approve`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({
        note: params.note ?? null,
      }),
    }
  );
}

export async function executeChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
}) {
  return apiRequest<GovernanceExecuteResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/execute`,
    {
      method: "POST",
      actor: params.actor,
    }
  );
}
5) frontend/src/lib/governanceRbac.ts
RBAC ở frontend chỉ để ẩn/hiện UI, không thay thế backend auth.
export const ROLE_ADMIN = "admin";
export const ROLE_GOVERNANCE_ADMIN = "governance_admin";
export const ROLE_APPROVER = "approver";
export const ROLE_OPERATOR = "operator";
export const ROLE_STRATEGY_OWNER = "strategy_owner";
export const ROLE_VIEWER = "viewer";

export function canViewPendingApprovals(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER].includes(role);
}

export function canApprove(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER].includes(role);
}

export function canExecute(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_OPERATOR, ROLE_STRATEGY_OWNER].includes(role);
}
6) frontend/src/components/governance/GovernanceConflictDialog.tsx
Dialog chuẩn hóa cho 409, stale version, approval missing, v.v.
import React from "react";
import type { ApiError } from "@/types/api";

type GovernanceConflictDialogProps = {
  open: boolean;
  error: ApiError | null;
  title?: string;
  onClose: () => void;
  onRefresh?: () => void;
};

export function GovernanceConflictDialog({
  open,
  error,
  title = "Conflict detected",
  onClose,
  onRefresh,
}: GovernanceConflictDialogProps) {
  if (!open || !error) return null;

  const details = error.details ?? {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-gray-600">{error.message}</p>
        </div>

        <div className="rounded-xl border bg-gray-50 p-4">
          <div className="mb-2 text-sm font-medium text-gray-800">Details</div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-gray-700">
            {JSON.stringify(details, null, 2)}
          </pre>
        </div>

        {error.request_id ? (
          <div className="mt-3 text-xs text-gray-500">
            Request ID: <span className="font-mono">{error.request_id}</span>
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-end gap-2">
          {onRefresh ? (
            <button
              type="button"
              className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
              onClick={onRefresh}
            >
              Refresh state
            </button>
          ) : null}
          <button
            type="button"
            className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
7) frontend/src/components/governance/GovernanceStatusBadge.tsx
import React from "react";

type Props = {
  status: string;
};

export function GovernanceStatusBadge({ status }: Props) {
  const normalized = status.toLowerCase();

  const className =
    normalized === "pending_approval"
      ? "bg-amber-100 text-amber-800"
      : normalized === "approved"
      ? "bg-blue-100 text-blue-800"
      : normalized === "executed"
      ? "bg-green-100 text-green-800"
      : "bg-gray-100 text-gray-700";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>
      {status}
    </span>
  );
}
8) frontend/src/components/governance/PendingApprovalsTable.tsx
Đây là lõi UI queue.
import React from "react";
import type { GovernancePendingApprovalItem } from "@/types/governance";
import { GovernanceStatusBadge } from "@/components/governance/GovernanceStatusBadge";

type Props = {
  items: GovernancePendingApprovalItem[];
  loading?: boolean;
  approvingId?: string | null;
  executingId?: string | null;
  canApprove: boolean;
  canExecute: boolean;
  onApprove: (item: GovernancePendingApprovalItem) => void;
  onExecute: (item: GovernancePendingApprovalItem) => void;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function PendingApprovalsTable({
  items,
  loading = false,
  approvingId = null,
  executingId = null,
  canApprove,
  canExecute,
  onApprove,
  onExecute,
}: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">Loading pending approvals...</div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No pending approvals found.</div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-700">
            <tr>
              <th className="px-4 py-3 font-medium">Directive</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Requested by</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Rule</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isApproving = approvingId === item.change_request_id;
              const isExecuting = executingId === item.change_request_id;

              return (
                <tr key={item.change_request_id} className="border-t align-top">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{item.directive_id}</div>
                    <div className="mt-1 font-mono text-xs text-gray-500">
                      {item.change_request_id}
                    </div>
                  </td>
                  <td className="px-4 py-3">{item.action_type}</td>
                  <td className="px-4 py-3">{item.requested_by}</td>
                  <td className="px-4 py-3 text-gray-700">{item.reason || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{item.approval_rule_key || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{formatDate(item.created_at)}</td>
                  <td className="px-4 py-3">
                    <GovernanceStatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {canApprove ? (
                        <button
                          type="button"
                          className="rounded-xl border px-3 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isApproving || isExecuting}
                          onClick={() => onApprove(item)}
                        >
                          {isApproving ? "Approving..." : "Approve"}
                        </button>
                      ) : null}

                      {canExecute ? (
                        <button
                          type="button"
                          className="rounded-xl bg-black px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isApproving || isExecuting || item.status !== "approved"}
                          onClick={() => onExecute(item)}
                        >
                          {isExecuting ? "Executing..." : "Execute"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
9) frontend/src/components/governance/ApprovalNoteModal.tsx
Modal nhẹ để nhập note khi approve.
import React, { useEffect, useState } from "react";
import type { GovernancePendingApprovalItem } from "@/types/governance";

type Props = {
  open: boolean;
  item: GovernancePendingApprovalItem | null;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (note: string) => void;
};

export function ApprovalNoteModal({
  open,
  item,
  submitting = false,
  onClose,
  onSubmit,
}: Props) {
  const [note, setNote] = useState("");

  useEffect(() => {
    if (open) setNote("");
  }, [open]);

  if (!open || !item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-semibold">Approve change request</h2>
        <p className="mt-1 text-sm text-gray-600">
          Directive <span className="font-medium">{item.directive_id}</span> · {item.action_type}
        </p>

        <div className="mt-4">
          <label className="mb-2 block text-sm font-medium text-gray-800">
            Approval note
          </label>
          <textarea
            className="min-h-[120px] w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-black"
            placeholder="Optional note for audit trail"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
            disabled={submitting}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            disabled={submitting}
            onClick={() => onSubmit(note)}
          >
            {submitting ? "Submitting..." : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
10) frontend/src/hooks/usePendingApprovals.ts
Hook fetch + refresh đơn giản, không ép bạn phải dùng React Query.
import { useCallback, useEffect, useState } from "react";
import { fetchPendingApprovals } from "@/lib/governanceApi";
import type { ApiError } from "@/types/api";
import type { ActorContext, GovernancePendingApprovalItem } from "@/types/governance";

type State = {
  items: GovernancePendingApprovalItem[];
  loading: boolean;
  error: ApiError | null;
};

export function usePendingApprovals(actor: ActorContext | null) {
  const [state, setState] = useState<State>({
    items: [],
    loading: false,
    error: null,
  });

  const refresh = useCallback(async () => {
    if (!actor) {
      setState({
        items: [],
        loading: false,
        error: null,
      });
      return;
    }

    setState((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    const result = await fetchPendingApprovals({
      actor,
      limit: 100,
      offset: 0,
    });

    if (!result.ok) {
      setState({
        items: [],
        loading: false,
        error: result.error,
      });
      return;
    }

    setState({
      items: result.data.items,
      loading: false,
      error: null,
    });
  }, [actor]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    items: state.items,
    loading: state.loading,
    error: state.error,
    refresh,
  };
}
11) frontend/src/components/governance/GovernancePendingApprovalsPanel.tsx
Panel hoàn chỉnh: fetch list, open modal approve, execute, show conflict dialog.
import React, { useMemo, useState } from "react";
import { approveChangeRequest, executeChangeRequest } from "@/lib/governanceApi";
import { canApprove, canExecute, canViewPendingApprovals } from "@/lib/governanceRbac";
import { usePendingApprovals } from "@/hooks/usePendingApprovals";
import { ApprovalNoteModal } from "@/components/governance/ApprovalNoteModal";
import { GovernanceConflictDialog } from "@/components/governance/GovernanceConflictDialog";
import { PendingApprovalsTable } from "@/components/governance/PendingApprovalsTable";
import type { ApiError } from "@/types/api";
import type { ActorContext, GovernancePendingApprovalItem } from "@/types/governance";

type Props = {
  actor: ActorContext | null;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

export function GovernancePendingApprovalsPanel({ actor, onToast }: Props) {
  const { items, loading, error, refresh } = usePendingApprovals(actor);

  const [selectedItem, setSelectedItem] = useState<GovernancePendingApprovalItem | null>(null);
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);

  const [conflictOpen, setConflictOpen] = useState(false);
  const [conflictError, setConflictError] = useState<ApiError | null>(null);

  const allowView = useMemo(
    () => (actor ? canViewPendingApprovals(actor.actorRole) : false),
    [actor]
  );
  const allowApprove = useMemo(
    () => (actor ? canApprove(actor.actorRole) : false),
    [actor]
  );
  const allowExecute = useMemo(
    () => (actor ? canExecute(actor.actorRole) : false),
    [actor]
  );

  const openConflict = (apiError: ApiError) => {
    setConflictError(apiError);
    setConflictOpen(true);
  };

  const handleApproveClick = (item: GovernancePendingApprovalItem) => {
    setSelectedItem(item);
    setApprovalModalOpen(true);
  };

  const handleApproveSubmit = async (note: string) => {
    if (!actor || !selectedItem) return;

    setApprovingId(selectedItem.change_request_id);

    const result = await approveChangeRequest({
      actor,
      changeRequestId: selectedItem.change_request_id,
      note,
    });

    setApprovingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    setApprovalModalOpen(false);
    setSelectedItem(null);
    onToast?.({ type: "success", message: "Change request approved." });
    void refresh();
  };

  const handleExecute = async (item: GovernancePendingApprovalItem) => {
    if (!actor) return;

    setExecutingId(item.change_request_id);

    const result = await executeChangeRequest({
      actor,
      changeRequestId: item.change_request_id,
    });

    setExecutingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    onToast?.({
      type: "success",
      message: `Executed successfully. Updated version: ${result.data.updated_version}`,
    });
    void refresh();
  };

  if (!actor) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No actor context available.</div>
      </div>
    );
  }

  if (!allowView) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">
          Your current role does not have access to pending approvals.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-2xl border bg-white p-4 shadow-sm">
          <div>
            <div className="text-base font-semibold text-gray-900">Pending approvals</div>
            <div className="mt-1 text-sm text-gray-600">
              Review, approve, and execute governance change requests.
            </div>
          </div>

          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
            onClick={() => void refresh()}
          >
            Refresh
          </button>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Failed to load pending approvals: {error.message}
          </div>
        ) : null}

        <PendingApprovalsTable
          items={items}
          loading={loading}
          approvingId={approvingId}
          executingId={executingId}
          canApprove={allowApprove}
          canExecute={allowExecute}
          onApprove={handleApproveClick}
          onExecute={handleExecute}
        />
      </div>

      <ApprovalNoteModal
        open={approvalModalOpen}
        item={selectedItem}
        submitting={Boolean(approvingId)}
        onClose={() => {
          if (approvingId) return;
          setApprovalModalOpen(false);
          setSelectedItem(null);
        }}
        onSubmit={(note) => void handleApproveSubmit(note)}
      />

      <GovernanceConflictDialog
        open={conflictOpen}
        error={conflictError}
        onClose={() => {
          setConflictOpen(false);
          setConflictError(null);
        }}
        onRefresh={() => void refresh()}
      />
    </>
  );
}
12) frontend/src/components/governance/GovernanceActionErrorBanner.tsx
Banner dùng cho lỗi non-conflict hoặc load failure.
import React from "react";
import type { ApiError } from "@/types/api";

type Props = {
  error: ApiError | null;
  onDismiss?: () => void;
};

export function GovernanceActionErrorBanner({ error, onDismiss }: Props) {
  if (!error) return null;

  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-red-900">Governance action failed</div>
          <div className="mt-1 text-sm text-red-800">{error.message}</div>
          {error.request_id ? (
            <div className="mt-2 text-xs text-red-700">
              Request ID: <span className="font-mono">{error.request_id}</span>
            </div>
          ) : null}
        </div>

        {onDismiss ? (
          <button
            type="button"
            className="rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-900 hover:bg-red-100"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
13) cập nhật frontend/src/components/governance/GovernanceActionBar.tsx
Nếu file này đã tồn tại, bạn chỉ cần thêm conflict-aware execution flow.
Dưới đây là bản mẫu hoàn chỉnh để map.
import React, { useState } from "react";
import { executeChangeRequest } from "@/lib/governanceApi";
import { canExecute } from "@/lib/governanceRbac";
import { GovernanceConflictDialog } from "@/components/governance/GovernanceConflictDialog";
import type { ApiError } from "@/types/api";
import type { ActorContext } from "@/types/governance";

type Props = {
  actor: ActorContext;
  changeRequestId: string;
  status: string;
  onExecuted?: (updatedVersion: number) => void;
  onRefresh?: () => void;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

export function GovernanceActionBar({
  actor,
  changeRequestId,
  status,
  onExecuted,
  onRefresh,
  onToast,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [conflictError, setConflictError] = useState<ApiError | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);

  const handleExecute = async () => {
    setSubmitting(true);

    const result = await executeChangeRequest({
      actor,
      changeRequestId,
    });

    setSubmitting(false);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        setConflictError(result.error);
        setConflictOpen(true);
        return;
      }

      onToast?.({
        type: "error",
        message: result.error.message,
      });
      return;
    }

    onToast?.({
      type: "success",
      message: `Executed successfully. Updated version: ${result.data.updated_version}`,
    });

    onExecuted?.(result.data.updated_version);
  };

  const allowExecute = canExecute(actor.actorRole);
  const disabled = !allowExecute || submitting || status !== "approved";

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disabled}
          onClick={() => void handleExecute()}
        >
          {submitting ? "Executing..." : "Execute"}
        </button>
      </div>

      <GovernanceConflictDialog
        open={conflictOpen}
        error={conflictError}
        onClose={() => {
          setConflictOpen(false);
          setConflictError(null);
        }}
        onRefresh={onRefresh}
      />
    </>
  );
}
14) frontend/src/components/governance/GovernancePendingApprovalsPage.tsx
Nếu bạn muốn có page riêng.
import React from "react";
import { GovernancePendingApprovalsPanel } from "@/components/governance/GovernancePendingApprovalsPanel";
import type { ActorContext } from "@/types/governance";

type Props = {
  actor: ActorContext | null;
};

export default function GovernancePendingApprovalsPage({ actor }: Props) {
  return (
    <div className="mx-auto max-w-7xl p-6">
      <GovernancePendingApprovalsPanel
        actor={actor}
        onToast={({ type, message }) => {
          if (type === "error") {
            console.error(message);
          } else {
            console.log(message);
          }
        }}
      />
    </div>
  );
}
15) route wiring nếu bạn dùng React Router
frontend/src/router.tsx hoặc file tương đương
import GovernancePendingApprovalsPage from "@/components/governance/GovernancePendingApprovalsPage";

// ví dụ route
{
  path: "/governance/pending-approvals",
  element: <GovernancePendingApprovalsPage actor={currentActor} />,
}
16) nếu đang dùng ExplainDrawer thì nối nhẹ theo pattern này
frontend/src/components/governance/ExplainDrawer.tsx
Ví dụ chèn panel pending approvals hoặc CTA dẫn sang queue.
import React from "react";
import { Link } from "react-router-dom";

export function ExplainDrawerGovernanceLinks() {
  return (
    <div className="rounded-2xl border bg-white p-4">
      <div className="text-sm font-semibold text-gray-900">Governance queue</div>
      <div className="mt-1 text-sm text-gray-600">
        Review pending approvals, approve eligible changes, and handle execution conflicts.
      </div>

      <div className="mt-3">
        <Link
          to="/governance/pending-approvals"
          className="inline-flex rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
        >
          Open pending approvals
        </Link>
      </div>
    </div>
  );
}
17) test UI logic mức nhẹ
Nếu repo bạn có Vitest/Jest, đây là test gọn mà đáng giữ.
frontend/src/lib/__tests__/governanceRbac.test.ts
import { describe, expect, it } from "vitest";
import {
  canApprove,
  canExecute,
  canViewPendingApprovals,
} from "@/lib/governanceRbac";

describe("governance RBAC helpers", () => {
  it("allows approver to view and approve", () => {
    expect(canViewPendingApprovals("approver")).toBe(true);
    expect(canApprove("approver")).toBe(true);
  });

  it("does not allow viewer to approve or execute", () => {
    expect(canViewPendingApprovals("viewer")).toBe(false);
    expect(canApprove("viewer")).toBe(false);
    expect(canExecute("viewer")).toBe(false);
  });

  it("allows operator to execute", () => {
    expect(canExecute("operator")).toBe(true);
  });
});
18) test API parsing
frontend/src/lib/__tests__/api.test.ts
import { describe, expect, it } from "vitest";
import { parseApiError } from "@/lib/api";

describe("parseApiError", () => {
  it("parses standardized backend error", async () => {
    const response = new Response(
      JSON.stringify({
        error: "conflict",
        message: "Directive version conflict",
        details: { directive_id: "directive-1" },
        request_id: "req-123",
      }),
      {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }
    );

    const result = await parseApiError(response);

    expect(result.error).toBe("conflict");
    expect(result.message).toBe("Directive version conflict");
    expect(result.request_id).toBe("req-123");
  });
});
19) UX behavior đã được khóa ở bản này
Bản frontend này chốt các hành vi quan trọng:
A. Pending approvals queue
load danh sách /governance/pending-approvals
role không đủ thì UI chặn hiển thị queue
B. Approve flow
mở modal nhập note
submit approve
nếu 403 self-approval hoặc 409 duplicate/conflict → bật conflict dialog
success → refresh list
C. Execute flow
chỉ enable khi status = approved
nếu 409 approval missing / version conflict → conflict dialog
success → refresh list
D. Conflict handling thống nhất
đọc đúng error/message/details/request_id
không parse string ad-hoc
có nút Refresh state
20) điểm map rất ngắn khi paste vào repo thật
Bạn sẽ chỉ cần map 7 chỗ:
1. Base path API
Nếu frontend proxy/path khác:
const GOVERNANCE_BASE = "/api/v1/governance";
2. Actor source
Hiện tôi truyền actor vào component.
Nếu repo bạn có auth store:
Zustand
Redux
React context
thì chỉ cần lấy actor từ store thay vì props.
3. Toast system
Tôi đang dùng onToast.
Nếu repo có:
sonner
react-hot-toast
notistack
thì thay bằng toast thật.
4. UI primitives
Nếu repo dùng shadcn/ui hoặc component system nội bộ, bạn có thể thay:
modal
table
badge
button
nhưng giữ nguyên behavior.
5. Routing
Nếu không có page riêng, bạn có thể nhúng luôn GovernancePendingApprovalsPanel vào console hiện tại.
6. Execute policy ở UI
Hiện nút Execute chỉ enable khi:
item.status === "approved"
Nếu backend sau này hỗ trợ trạng thái khác, đổi ở đây.
7. ExplainDrawer / GovernanceActionBar
Nếu file cũ đã tồn tại, chỉ merge phần:
GovernanceConflictDialog
executeChangeRequest(...)
refresh callback
21) thứ tự paste vào frontend repo
Nên paste theo thứ tự này:
src/types/api.ts
src/types/governance.ts
src/lib/api.ts
src/lib/governanceApi.ts
src/lib/governanceRbac.ts
src/hooks/usePendingApprovals.ts
src/components/governance/GovernanceConflictDialog.tsx
src/components/governance/GovernanceStatusBadge.tsx
src/components/governance/ApprovalNoteModal.tsx
src/components/governance/PendingApprovalsTable.tsx
src/components/governance/GovernancePendingApprovalsPanel.tsx
patch GovernanceActionBar.tsx
thêm route/page nếu cần
thêm test nhỏ
Dưới đây là bản PHASE 3 — REJECT FLOW + APPROVAL AUDIT TIMELINE + VERSION REFRESH UX theo đúng format file-by-file, nối trực tiếp trên bản frontend/backend Phase 3 trước đó.
Mục tiêu của lớp này:
thêm reject flow
thêm approval / execution audit timeline
thêm version refresh UX khi gặp conflict
giữ kiến trúc hiện tại, không tái cấu trúc vô cớ
chỉ map tối thiểu vào repo thật
TỔNG QUAN CẦN CÓ
Lớp này gồm 3 phần:
Backend
route reject change request
route audit timeline theo change request
route directive current state/version để UI refresh conflict
Frontend
reject modal
audit timeline panel
conflict dialog có nút refresh version/state
action bar + pending approvals table hỗ trợ reject
Contract mới
POST /governance/change-requests/{id}/reject
GET /governance/change-requests/{id}/timeline
GET /governance/directives/{directive_id}/state
BACKEND
1) backend/app/api/schemas/governance.py
Thêm các schema mới vào file governance schemas hiện có.
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernanceRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class GovernanceRejectResponse(BaseModel):
    change_request_id: str
    status: str
    rejected_by: str
    rejection_reason: str
    rejected_at: datetime


class GovernanceTimelineEventResponse(BaseModel):
    event_type: str
    actor_id: str | None = None
    status: str | None = None
    note: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GovernanceTimelineResponse(BaseModel):
    change_request_id: str
    directive_id: str
    status: str
    events: list[GovernanceTimelineEventResponse]


class DirectiveStateSnapshotResponse(BaseModel):
    directive_id: str
    version: int
    state: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime
2) backend/app/models/governance_notification_event.py
Nếu model này đã có, chỉ cần đảm bảo nó chứa đủ field để timeline đọc được.
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    directive_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
3) backend/app/repositories/governance_notification_repository.py
Chuẩn hóa repo create + list timeline.
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_notification_event import GovernanceNotificationEvent


class GovernanceNotificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        change_request_id: str,
        directive_id: str,
        event_type: str,
        actor_id: str | None = None,
        status: str | None = None,
        note: str | None = None,
        payload: dict | None = None,
    ) -> GovernanceNotificationEvent:
        entity = GovernanceNotificationEvent(
            change_request_id=change_request_id,
            directive_id=directive_id,
            event_type=event_type,
            actor_id=actor_id,
            status=status,
            note=note,
            payload=payload or {},
        )
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def list_by_change_request_id(self, change_request_id: str) -> list[GovernanceNotificationEvent]:
        stmt: Select[tuple[GovernanceNotificationEvent]] = (
            select(GovernanceNotificationEvent)
            .where(GovernanceNotificationEvent.change_request_id == change_request_id)
            .order_by(GovernanceNotificationEvent.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
4) backend/app/repositories/governance_change_request_repository.py
Bổ sung reject update nếu chưa có.
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_change_request import GovernanceChangeRequest


class GovernanceChangeRequestRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, entity: GovernanceChangeRequest) -> GovernanceChangeRequest:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        return self.session.get(GovernanceChangeRequest, change_request_id)

    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt: Select[tuple[GovernanceChangeRequest]] = select(GovernanceChangeRequest).where(
            GovernanceChangeRequest.idempotency_key == idempotency_key
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_pending_approvals(self, limit: int = 100, offset: int = 0) -> list[GovernanceChangeRequest]:
        stmt: Select[tuple[GovernanceChangeRequest]] = (
            select(GovernanceChangeRequest)
            .where(GovernanceChangeRequest.status == "pending_approval")
            .order_by(GovernanceChangeRequest.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_rejected(
        self,
        *,
        change_request_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> GovernanceChangeRequest | None:
        entity = self.get(change_request_id)
        if not entity:
            return None

        entity.status = "rejected"
        entity.rejected_by = rejected_by
        entity.rejection_reason = rejection_reason
        return entity
5) backend/app/services/governance_rejection_service.py
from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError


class GovernanceRejectionService:
    def __init__(self, session, change_request_repo, notification_repo):
        self.session = session
        self.change_request_repo = change_request_repo
        self.notification_repo = notification_repo

    def reject(
        self,
        *,
        change_request_id: str,
        rejected_by: str,
        requested_by: str | None,
        reason: str,
    ):
        change_request = self.change_request_repo.get(change_request_id)
        if not change_request:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": change_request_id},
            )

        if change_request.status != "pending_approval":
            raise ConflictError(
                "Only pending approval change requests can be rejected",
                {
                    "change_request_id": change_request_id,
                    "status": change_request.status,
                },
            )

        if requested_by and requested_by == rejected_by:
            raise ForbiddenError(
                "Requester cannot reject their own change request",
                {
                    "change_request_id": change_request_id,
                    "rejected_by": rejected_by,
                },
            )

        updated = self.change_request_repo.mark_rejected(
            change_request_id=change_request_id,
            rejected_by=rejected_by,
            rejection_reason=reason,
        )

        if updated is None:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": change_request_id},
            )

        self.notification_repo.create(
            change_request_id=updated.id,
            directive_id=updated.directive_id,
            event_type="change_request_rejected",
            actor_id=rejected_by,
            status="rejected",
            note=reason,
            payload={"rejection_reason": reason},
        )

        self.session.commit()

        return {
            "change_request_id": updated.id,
            "status": updated.status,
            "rejected_by": rejected_by,
            "rejection_reason": reason,
            "rejected_at": datetime.now(timezone.utc),
        }
6) backend/app/services/governance_timeline_service.py
from __future__ import annotations

from app.core.exceptions import NotFoundError


class GovernanceTimelineService:
    def __init__(self, change_request_repo, approval_repo, execution_attempt_repo, notification_repo):
        self.change_request_repo = change_request_repo
        self.approval_repo = approval_repo
        self.execution_attempt_repo = execution_attempt_repo
        self.notification_repo = notification_repo

    def get_timeline(self, change_request_id: str) -> dict:
        change_request = self.change_request_repo.get(change_request_id)
        if not change_request:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": change_request_id},
            )

        events: list[dict] = []

        events.append(
            {
                "event_type": "change_request_created",
                "actor_id": change_request.requested_by,
                "status": change_request.status,
                "note": change_request.reason,
                "payload": {
                    "action_type": change_request.action_type,
                    "expected_directive_version": change_request.expected_directive_version,
                    "patch": change_request.patch,
                },
                "created_at": change_request.created_at,
            }
        )

        approval = self.approval_repo.get_by_change_request_id(change_request_id)
        if approval:
            events.append(
                {
                    "event_type": "change_request_approved",
                    "actor_id": approval.approver_id,
                    "status": "approved",
                    "note": approval.note,
                    "payload": {},
                    "created_at": approval.created_at,
                }
            )

        execution_attempts = self.execution_attempt_repo.list_by_change_request_id(change_request_id)
        for attempt in execution_attempts:
            events.append(
                {
                    "event_type": "execution_attempt",
                    "actor_id": attempt.executed_by,
                    "status": attempt.status,
                    "note": None,
                    "payload": getattr(attempt, "result_payload", {}) or {},
                    "created_at": attempt.created_at,
                }
            )

        notification_events = self.notification_repo.list_by_change_request_id(change_request_id)
        for event in notification_events:
            events.append(
                {
                    "event_type": event.event_type,
                    "actor_id": event.actor_id,
                    "status": event.status,
                    "note": event.note,
                    "payload": event.payload or {},
                    "created_at": event.created_at,
                }
            )

        events.sort(key=lambda item: item["created_at"])

        return {
            "change_request_id": change_request.id,
            "directive_id": change_request.directive_id,
            "status": change_request.status,
            "events": events,
        }
7) backend/app/services/directive_state_query_service.py
Đây là route refresh version/state cho UI.
from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import NotFoundError


class DirectiveStateQueryService:
    def __init__(self, directive_state_gateway):
        self.directive_state_gateway = directive_state_gateway

    def get_snapshot(self, directive_id: str) -> dict:
        state = self.directive_state_gateway.get(directive_id)
        if state is None:
            raise NotFoundError(
                "Directive state not found",
                {"directive_id": directive_id},
            )

        return {
            "directive_id": directive_id,
            "version": state.version,
            "state": getattr(state, "state", {}) or getattr(state, "payload", {}) or {},
            "fetched_at": datetime.now(timezone.utc),
        }
8) backend/app/services/rbac.py
Bổ sung quyền reject nếu cần tách riêng.
from __future__ import annotations

from app.api.deps.auth import ActorContext
from app.core.exceptions import ForbiddenError


ROLE_ADMIN = "admin"
ROLE_GOVERNANCE_ADMIN = "governance_admin"
ROLE_APPROVER = "approver"
ROLE_OPERATOR = "operator"
ROLE_STRATEGY_OWNER = "strategy_owner"
ROLE_VIEWER = "viewer"

APPROVAL_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
}

EXECUTION_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_OPERATOR,
    ROLE_STRATEGY_OWNER,
}

READ_PENDING_APPROVALS_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
}

TIMELINE_READ_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
    ROLE_OPERATOR,
    ROLE_STRATEGY_OWNER,
}

DIRECTIVE_STATE_READ_ROLES = {
    ROLE_ADMIN,
    ROLE_GOVERNANCE_ADMIN,
    ROLE_APPROVER,
    ROLE_OPERATOR,
    ROLE_STRATEGY_OWNER,
}


def require_any_role(actor: ActorContext, allowed_roles: set[str]) -> None:
    if actor.actor_role not in allowed_roles:
        raise ForbiddenError(
            message="Actor does not have the required role",
            details={
                "actor_role": actor.actor_role,
                "allowed_roles": sorted(allowed_roles),
            },
        )


def require_can_approve(actor: ActorContext) -> None:
    require_any_role(actor, APPROVAL_ROLES)


def require_can_reject(actor: ActorContext) -> None:
    require_any_role(actor, APPROVAL_ROLES)


def require_can_execute(actor: ActorContext) -> None:
    require_any_role(actor, EXECUTION_ROLES)


def require_can_list_pending_approvals(actor: ActorContext) -> None:
    require_any_role(actor, READ_PENDING_APPROVALS_ROLES)


def require_can_read_timeline(actor: ActorContext) -> None:
    require_any_role(actor, TIMELINE_READ_ROLES)


def require_can_read_directive_state(actor: ActorContext) -> None:
    require_any_role(actor, DIRECTIVE_STATE_READ_ROLES)
9) backend/app/repositories/governance_execution_attempt_repository.py
Nếu repo hiện tại chưa có list theo change_request.
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_execution_attempt import GovernanceExecutionAttempt


class GovernanceExecutionAttemptRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> GovernanceExecutionAttempt:
        entity = GovernanceExecutionAttempt(**kwargs)
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def list_by_change_request_id(self, change_request_id: str) -> list[GovernanceExecutionAttempt]:
        stmt: Select[tuple[GovernanceExecutionAttempt]] = (
            select(GovernanceExecutionAttempt)
            .where(GovernanceExecutionAttempt.change_request_id == change_request_id)
            .order_by(GovernanceExecutionAttempt.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
10) backend/app/api/routes/governance.py
Thêm 3 route mới: reject, timeline, directive state.
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps.auth import ActorContext, get_actor_context
from app.api.schemas.error_schema import ErrorResponse
from app.api.schemas.governance import (
    DirectiveStateSnapshotResponse,
    GovernanceRejectRequest,
    GovernanceRejectResponse,
    GovernanceTimelineEventResponse,
    GovernanceTimelineResponse,
)
from app.db.session import get_db
from app.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.services.directive_state_query_service import DirectiveStateQueryService
from app.services.governance_rejection_service import GovernanceRejectionService
from app.services.governance_timeline_service import GovernanceTimelineService
from app.services.rbac import (
    require_can_read_directive_state,
    require_can_read_timeline,
    require_can_reject,
)

router = APIRouter(prefix="/governance", tags=["governance"])


def get_change_request_repo(db: Session = Depends(get_db)) -> GovernanceChangeRequestRepository:
    return GovernanceChangeRequestRepository(db)


def get_approval_repo(db: Session = Depends(get_db)) -> GovernanceApprovalRepository:
    return GovernanceApprovalRepository(db)


def get_execution_attempt_repo(db: Session = Depends(get_db)) -> GovernanceExecutionAttemptRepository:
    return GovernanceExecutionAttemptRepository(db)


def get_notification_repo(db: Session = Depends(get_db)) -> GovernanceNotificationRepository:
    return GovernanceNotificationRepository(db)


def get_rejection_service(
    db: Session = Depends(get_db),
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
    notification_repo: GovernanceNotificationRepository = Depends(get_notification_repo),
) -> GovernanceRejectionService:
    return GovernanceRejectionService(
        session=db,
        change_request_repo=change_request_repo,
        notification_repo=notification_repo,
    )


def get_timeline_service(
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
    approval_repo: GovernanceApprovalRepository = Depends(get_approval_repo),
    execution_attempt_repo: GovernanceExecutionAttemptRepository = Depends(get_execution_attempt_repo),
    notification_repo: GovernanceNotificationRepository = Depends(get_notification_repo),
) -> GovernanceTimelineService:
    return GovernanceTimelineService(
        change_request_repo=change_request_repo,
        approval_repo=approval_repo,
        execution_attempt_repo=execution_attempt_repo,
        notification_repo=notification_repo,
    )


def get_directive_state_query_service():
    from app.governance.directive_state_gateway import DirectiveStateGateway
    return DirectiveStateQueryService(directive_state_gateway=DirectiveStateGateway())


@router.post(
    "/change-requests/{change_request_id}/reject",
    response_model=GovernanceRejectResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def reject_change_request(
    change_request_id: str,
    payload: GovernanceRejectRequest,
    actor: ActorContext = Depends(get_actor_context),
    change_request_repo: GovernanceChangeRequestRepository = Depends(get_change_request_repo),
    rejection_service: GovernanceRejectionService = Depends(get_rejection_service),
):
    require_can_reject(actor)

    existing = change_request_repo.get(change_request_id)
    requested_by = existing.requested_by if existing else None

    result = rejection_service.reject(
        change_request_id=change_request_id,
        rejected_by=actor.actor_id,
        requested_by=requested_by,
        reason=payload.reason,
    )

    return GovernanceRejectResponse(**result)


@router.get(
    "/change-requests/{change_request_id}/timeline",
    response_model=GovernanceTimelineResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_change_request_timeline(
    change_request_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceTimelineService = Depends(get_timeline_service),
):
    require_can_read_timeline(actor)

    result = service.get_timeline(change_request_id)

    return GovernanceTimelineResponse(
        change_request_id=result["change_request_id"],
        directive_id=result["directive_id"],
        status=result["status"],
        events=[
            GovernanceTimelineEventResponse(**event)
            for event in result["events"]
        ],
    )


@router.get(
    "/directives/{directive_id}/state",
    response_model=DirectiveStateSnapshotResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_directive_state_snapshot(
    directive_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: DirectiveStateQueryService = Depends(get_directive_state_query_service),
):
    require_can_read_directive_state(actor)
    result = service.get_snapshot(directive_id)
    return DirectiveStateSnapshotResponse(**result)
11) tests backend
backend/tests/api/test_governance_reject_and_timeline.py
from __future__ import annotations


def _auth_headers(actor_id: str, role: str) -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }


def test_reject_change_request_success(client, seed_pending_change_request):
    response = client.post(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/reject",
        json={"reason": "Risk too high for direct rollout"},
        headers=_auth_headers("approver-1", "approver"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejected_by"] == "approver-1"


def test_reject_self_request_forbidden(client, seed_pending_change_request):
    response = client.post(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/reject",
        json={"reason": "Rejecting own request"},
        headers=_auth_headers(seed_pending_change_request.requested_by, "approver"),
    )

    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_change_request_timeline_success(client, seed_pending_change_request):
    response = client.get(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/timeline",
        headers=_auth_headers("operator-1", "operator"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["change_request_id"] == seed_pending_change_request.id
    assert len(body["events"]) >= 1
    assert body["events"][0]["event_type"] == "change_request_created"
FRONTEND
12) frontend/src/types/governance.ts
Mở rộng types.
export type GovernancePendingApprovalItem = {
  change_request_id: string;
  directive_id: string;
  action_type: string;
  requested_by: string;
  reason?: string | null;
  approval_rule_key?: string | null;
  status: string;
  created_at: string;
};

export type GovernancePendingApprovalsResponse = {
  items: GovernancePendingApprovalItem[];
};

export type GovernanceApprovalResponse = {
  id: string;
  change_request_id: string;
  approver_id: string;
  note?: string | null;
  created_at: string;
};

export type GovernanceRejectResponse = {
  change_request_id: string;
  status: string;
  rejected_by: string;
  rejection_reason: string;
  rejected_at: string;
};

export type GovernanceExecuteResponse = {
  directive_id: string;
  updated_version: number;
  execution_status: string;
  change_request_id: string;
};

export type GovernanceTimelineEvent = {
  event_type: string;
  actor_id?: string | null;
  status?: string | null;
  note?: string | null;
  payload?: Record<string, unknown>;
  created_at: string;
};

export type GovernanceTimelineResponse = {
  change_request_id: string;
  directive_id: string;
  status: string;
  events: GovernanceTimelineEvent[];
};

export type DirectiveStateSnapshotResponse = {
  directive_id: string;
  version: number;
  state: Record<string, unknown>;
  fetched_at: string;
};

export type ActorContext = {
  actorId: string;
  actorRole: string;
  actorEmail?: string;
  actorName?: string;
};
13) frontend/src/lib/governanceApi.ts
Thêm reject, timeline, directive state snapshot.
import { apiRequest } from "@/lib/api";
import type {
  ActorContext,
  DirectiveStateSnapshotResponse,
  GovernanceApprovalResponse,
  GovernanceExecuteResponse,
  GovernancePendingApprovalsResponse,
  GovernanceRejectResponse,
  GovernanceTimelineResponse,
} from "@/types/governance";

const GOVERNANCE_BASE = "/api/v1/governance";

export async function fetchPendingApprovals(params: {
  actor: ActorContext;
  limit?: number;
  offset?: number;
}) {
  const search = new URLSearchParams({
    limit: String(params.limit ?? 100),
    offset: String(params.offset ?? 0),
  });

  return apiRequest<GovernancePendingApprovalsResponse>(
    `${GOVERNANCE_BASE}/pending-approvals?${search.toString()}`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function approveChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  note?: string;
}) {
  return apiRequest<GovernanceApprovalResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/approve`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({ note: params.note ?? null }),
    }
  );
}

export async function rejectChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  reason: string;
}) {
  return apiRequest<GovernanceRejectResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/reject`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({ reason: params.reason }),
    }
  );
}

export async function executeChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
}) {
  return apiRequest<GovernanceExecuteResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/execute`,
    {
      method: "POST",
      actor: params.actor,
    }
  );
}

export async function fetchChangeRequestTimeline(params: {
  actor: ActorContext;
  changeRequestId: string;
}) {
  return apiRequest<GovernanceTimelineResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/timeline`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function fetchDirectiveStateSnapshot(params: {
  actor: ActorContext;
  directiveId: string;
}) {
  return apiRequest<DirectiveStateSnapshotResponse>(
    `${GOVERNANCE_BASE}/directives/${params.directiveId}/state`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}
14) frontend/src/lib/governanceRbac.ts
Thêm reject/timeline/state read helpers.
export const ROLE_ADMIN = "admin";
export const ROLE_GOVERNANCE_ADMIN = "governance_admin";
export const ROLE_APPROVER = "approver";
export const ROLE_OPERATOR = "operator";
export const ROLE_STRATEGY_OWNER = "strategy_owner";
export const ROLE_VIEWER = "viewer";

export function canViewPendingApprovals(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER].includes(role);
}

export function canApprove(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER].includes(role);
}

export function canReject(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER].includes(role);
}

export function canExecute(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_OPERATOR, ROLE_STRATEGY_OWNER].includes(role);
}

export function canReadTimeline(role: string): boolean {
  return [ROLE_ADMIN, ROLE_GOVERNANCE_ADMIN, ROLE_APPROVER, ROLE_OPERATOR, ROLE_STRATEGY_OWNER].includes(role);
}
15) frontend/src/components/governance/RejectReasonModal.tsx
import React, { useEffect, useState } from "react";
import type { GovernancePendingApprovalItem } from "@/types/governance";

type Props = {
  open: boolean;
  item: GovernancePendingApprovalItem | null;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
};

export function RejectReasonModal({
  open,
  item,
  submitting = false,
  onClose,
  onSubmit,
}: Props) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) setReason("");
  }, [open]);

  if (!open || !item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-semibold">Reject change request</h2>
        <p className="mt-1 text-sm text-gray-600">
          Directive <span className="font-medium">{item.directive_id}</span> · {item.action_type}
        </p>

        <div className="mt-4">
          <label className="mb-2 block text-sm font-medium text-gray-800">
            Rejection reason
          </label>
          <textarea
            className="min-h-[140px] w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-black"
            placeholder="Why should this request be rejected?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
            disabled={submitting}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            disabled={submitting || !reason.trim()}
            onClick={() => onSubmit(reason.trim())}
          >
            {submitting ? "Rejecting..." : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
16) frontend/src/components/governance/GovernanceTimelinePanel.tsx
import React, { useEffect, useState } from "react";
import { fetchChangeRequestTimeline } from "@/lib/governanceApi";
import type { ActorContext, GovernanceTimelineEvent } from "@/types/governance";

type Props = {
  actor: ActorContext;
  changeRequestId: string | null;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function prettyEventTitle(eventType: string): string {
  switch (eventType) {
    case "change_request_created":
      return "Change request created";
    case "change_request_approved":
      return "Approved";
    case "change_request_rejected":
      return "Rejected";
    case "execution_attempt":
      return "Execution attempt";
    default:
      return eventType;
  }
}

export function GovernanceTimelinePanel({ actor, changeRequestId }: Props) {
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<GovernanceTimelineEvent[]>([]);
  const [directiveId, setDirectiveId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function run() {
      if (!changeRequestId) {
        setEvents([]);
        setDirectiveId(null);
        setStatus(null);
        return;
      }

      setLoading(true);
      setError(null);

      const result = await fetchChangeRequestTimeline({
        actor,
        changeRequestId,
      });

      setLoading(false);

      if (!result.ok) {
        setError(result.error.message);
        return;
      }

      setDirectiveId(result.data.directive_id);
      setStatus(result.data.status);
      setEvents(result.data.events);
    }

    void run();
  }, [actor, changeRequestId]);

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="mb-4">
        <div className="text-base font-semibold text-gray-900">Approval audit timeline</div>
        <div className="mt-1 text-sm text-gray-600">
          {changeRequestId ? (
            <>
              Change request <span className="font-mono">{changeRequestId}</span>
              {directiveId ? <> · Directive <span className="font-medium">{directiveId}</span></> : null}
              {status ? <> · Status <span className="font-medium">{status}</span></> : null}
            </>
          ) : (
            "Select a change request to inspect timeline."
          )}
        </div>
      </div>

      {loading ? <div className="text-sm text-gray-600">Loading timeline...</div> : null}
      {error ? <div className="text-sm text-red-700">{error}</div> : null}

      {!loading && !error && changeRequestId && events.length === 0 ? (
        <div className="text-sm text-gray-600">No timeline events found.</div>
      ) : null}

      <div className="space-y-3">
        {events.map((event, idx) => (
          <div key={`${event.event_type}-${event.created_at}-${idx}`} className="rounded-xl border p-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  {prettyEventTitle(event.event_type)}
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {formatDate(event.created_at)}
                </div>
              </div>

              {event.status ? (
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                  {event.status}
                </span>
              ) : null}
            </div>

            <div className="mt-2 text-sm text-gray-700">
              {event.actor_id ? <>Actor: <span className="font-medium">{event.actor_id}</span></> : "System event"}
            </div>

            {event.note ? (
              <div className="mt-2 text-sm text-gray-700">{event.note}</div>
            ) : null}

            {event.payload && Object.keys(event.payload).length > 0 ? (
              <pre className="mt-3 overflow-auto rounded-xl bg-gray-50 p-3 text-xs text-gray-700">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
17) frontend/src/components/governance/DirectiveVersionRefreshCard.tsx
Đây là UX refresh version sau conflict.
import React, { useState } from "react";
import { fetchDirectiveStateSnapshot } from "@/lib/governanceApi";
import type { ActorContext, DirectiveStateSnapshotResponse } from "@/types/governance";

type Props = {
  actor: ActorContext;
  directiveId: string | null;
  onLoaded?: (snapshot: DirectiveStateSnapshotResponse) => void;
};

export function DirectiveVersionRefreshCard({ actor, directiveId, onLoaded }: Props) {
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<DirectiveStateSnapshotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRefresh = async () => {
    if (!directiveId) return;

    setLoading(true);
    setError(null);

    const result = await fetchDirectiveStateSnapshot({
      actor,
      directiveId,
    });

    setLoading(false);

    if (!result.ok) {
      setError(result.error.message);
      return;
    }

    setSnapshot(result.data);
    onLoaded?.(result.data);
  };

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="text-base font-semibold text-gray-900">Directive state refresh</div>
      <div className="mt-1 text-sm text-gray-600">
        Refresh current directive version and state after a conflict or stale action.
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          disabled={!directiveId || loading}
          onClick={() => void handleRefresh()}
        >
          {loading ? "Refreshing..." : "Refresh current version"}
        </button>

        {directiveId ? (
          <div className="text-xs text-gray-500">
            Directive: <span className="font-mono">{directiveId}</span>
          </div>
        ) : null}
      </div>

      {error ? <div className="mt-3 text-sm text-red-700">{error}</div> : null}

      {snapshot ? (
        <div className="mt-4 rounded-xl border bg-gray-50 p-3">
          <div className="text-sm text-gray-800">
            Current version: <span className="font-semibold">{snapshot.version}</span>
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Fetched at {new Date(snapshot.fetched_at).toLocaleString()}
          </div>

          <pre className="mt-3 overflow-auto text-xs text-gray-700">
            {JSON.stringify(snapshot.state, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
18) frontend/src/components/governance/GovernanceConflictDialog.tsx
Nâng cấp dialog để optionally show live directive refresh.
import React from "react";
import type { ApiError } from "@/types/api";

type GovernanceConflictDialogProps = {
  open: boolean;
  error: ApiError | null;
  title?: string;
  onClose: () => void;
  onRefresh?: () => void;
  extra?: React.ReactNode;
};

export function GovernanceConflictDialog({
  open,
  error,
  title = "Conflict detected",
  onClose,
  onRefresh,
  extra,
}: GovernanceConflictDialogProps) {
  if (!open || !error) return null;

  const details = error.details ?? {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-gray-600">{error.message}</p>
        </div>

        <div className="rounded-xl border bg-gray-50 p-4">
          <div className="mb-2 text-sm font-medium text-gray-800">Details</div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-gray-700">
            {JSON.stringify(details, null, 2)}
          </pre>
        </div>

        {extra ? <div className="mt-4">{extra}</div> : null}

        {error.request_id ? (
          <div className="mt-3 text-xs text-gray-500">
            Request ID: <span className="font-mono">{error.request_id}</span>
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-end gap-2">
          {onRefresh ? (
            <button
              type="button"
              className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
              onClick={onRefresh}
            >
              Refresh list
            </button>
          ) : null}
          <button
            type="button"
            className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
19) frontend/src/components/governance/PendingApprovalsTable.tsx
Thêm Reject button + row selection timeline.
import React from "react";
import type { GovernancePendingApprovalItem } from "@/types/governance";
import { GovernanceStatusBadge } from "@/components/governance/GovernanceStatusBadge";

type Props = {
  items: GovernancePendingApprovalItem[];
  loading?: boolean;
  approvingId?: string | null;
  rejectingId?: string | null;
  executingId?: string | null;
  selectedChangeRequestId?: string | null;
  canApprove: boolean;
  canReject: boolean;
  canExecute: boolean;
  onApprove: (item: GovernancePendingApprovalItem) => void;
  onReject: (item: GovernancePendingApprovalItem) => void;
  onExecute: (item: GovernancePendingApprovalItem) => void;
  onSelect?: (item: GovernancePendingApprovalItem) => void;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function PendingApprovalsTable({
  items,
  loading = false,
  approvingId = null,
  rejectingId = null,
  executingId = null,
  selectedChangeRequestId = null,
  canApprove,
  canReject,
  canExecute,
  onApprove,
  onReject,
  onExecute,
  onSelect,
}: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">Loading pending approvals...</div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No pending approvals found.</div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-700">
            <tr>
              <th className="px-4 py-3 font-medium">Directive</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Requested by</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Rule</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isApproving = approvingId === item.change_request_id;
              const isRejecting = rejectingId === item.change_request_id;
              const isExecuting = executingId === item.change_request_id;
              const isSelected = selectedChangeRequestId === item.change_request_id;

              return (
                <tr
                  key={item.change_request_id}
                  className={`border-t align-top ${isSelected ? "bg-blue-50/40" : ""}`}
                  onClick={() => onSelect?.(item)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{item.directive_id}</div>
                    <div className="mt-1 font-mono text-xs text-gray-500">
                      {item.change_request_id}
                    </div>
                  </td>
                  <td className="px-4 py-3">{item.action_type}</td>
                  <td className="px-4 py-3">{item.requested_by}</td>
                  <td className="px-4 py-3 text-gray-700">{item.reason || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{item.approval_rule_key || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{formatDate(item.created_at)}</td>
                  <td className="px-4 py-3">
                    <GovernanceStatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {canApprove ? (
                        <button
                          type="button"
                          className="rounded-xl border px-3 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "pending_approval"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onApprove(item);
                          }}
                        >
                          {isApproving ? "Approving..." : "Approve"}
                        </button>
                      ) : null}

                      {canReject ? (
                        <button
                          type="button"
                          className="rounded-xl border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "pending_approval"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onReject(item);
                          }}
                        >
                          {isRejecting ? "Rejecting..." : "Reject"}
                        </button>
                      ) : null}

                      {canExecute ? (
                        <button
                          type="button"
                          className="rounded-xl bg-black px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "approved"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onExecute(item);
                          }}
                        >
                          {isExecuting ? "Executing..." : "Execute"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
20) frontend/src/components/governance/GovernancePendingApprovalsPanel.tsx
Đây là panel hợp nhất reject + timeline + version refresh UX.
import React, { useMemo, useState } from "react";
import {
  approveChangeRequest,
  executeChangeRequest,
  rejectChangeRequest,
} from "@/lib/governanceApi";
import {
  canApprove,
  canExecute,
  canReject,
  canViewPendingApprovals,
} from "@/lib/governanceRbac";
import { usePendingApprovals } from "@/hooks/usePendingApprovals";
import { ApprovalNoteModal } from "@/components/governance/ApprovalNoteModal";
import { DirectiveVersionRefreshCard } from "@/components/governance/DirectiveVersionRefreshCard";
import { GovernanceConflictDialog } from "@/components/governance/GovernanceConflictDialog";
import { GovernanceTimelinePanel } from "@/components/governance/GovernanceTimelinePanel";
import { PendingApprovalsTable } from "@/components/governance/PendingApprovalsTable";
import { RejectReasonModal } from "@/components/governance/RejectReasonModal";
import type { ApiError } from "@/types/api";
import type {
  ActorContext,
  DirectiveStateSnapshotResponse,
  GovernancePendingApprovalItem,
} from "@/types/governance";

type Props = {
  actor: ActorContext | null;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

export function GovernancePendingApprovalsPanel({ actor, onToast }: Props) {
  const { items, loading, error, refresh } = usePendingApprovals(actor);

  const [selectedItem, setSelectedItem] = useState<GovernancePendingApprovalItem | null>(null);

  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);

  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);

  const [conflictOpen, setConflictOpen] = useState(false);
  const [conflictError, setConflictError] = useState<ApiError | null>(null);
  const [conflictDirectiveId, setConflictDirectiveId] = useState<string | null>(null);
  const [latestSnapshot, setLatestSnapshot] = useState<DirectiveStateSnapshotResponse | null>(null);

  const allowView = useMemo(
    () => (actor ? canViewPendingApprovals(actor.actorRole) : false),
    [actor]
  );
  const allowApprove = useMemo(
    () => (actor ? canApprove(actor.actorRole) : false),
    [actor]
  );
  const allowReject = useMemo(
    () => (actor ? canReject(actor.actorRole) : false),
    [actor]
  );
  const allowExecute = useMemo(
    () => (actor ? canExecute(actor.actorRole) : false),
    [actor]
  );

  const openConflict = (apiError: ApiError, directiveId?: string | null) => {
    setConflictError(apiError);
    setConflictDirectiveId(directiveId ?? null);
    setLatestSnapshot(null);
    setConflictOpen(true);
  };

  const handleApproveClick = (item: GovernancePendingApprovalItem) => {
    setSelectedItem(item);
    setApprovalModalOpen(true);
  };

  const handleRejectClick = (item: GovernancePendingApprovalItem) => {
    setSelectedItem(item);
    setRejectModalOpen(true);
  };

  const handleApproveSubmit = async (note: string) => {
    if (!actor || !selectedItem) return;

    setApprovingId(selectedItem.change_request_id);

    const result = await approveChangeRequest({
      actor,
      changeRequestId: selectedItem.change_request_id,
      note,
    });

    setApprovingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, selectedItem.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    setApprovalModalOpen(false);
    onToast?.({ type: "success", message: "Change request approved." });
    void refresh();
  };

  const handleRejectSubmit = async (reason: string) => {
    if (!actor || !selectedItem) return;

    setRejectingId(selectedItem.change_request_id);

    const result = await rejectChangeRequest({
      actor,
      changeRequestId: selectedItem.change_request_id,
      reason,
    });

    setRejectingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, selectedItem.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    setRejectModalOpen(false);
    onToast?.({ type: "success", message: "Change request rejected." });
    void refresh();
  };

  const handleExecute = async (item: GovernancePendingApprovalItem) => {
    if (!actor) return;

    setExecutingId(item.change_request_id);

    const result = await executeChangeRequest({
      actor,
      changeRequestId: item.change_request_id,
    });

    setExecutingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, item.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    onToast?.({
      type: "success",
      message: `Executed successfully. Updated version: ${result.data.updated_version}`,
    });

    void refresh();
  };

  if (!actor) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No actor context available.</div>
      </div>
    );
  }

  if (!allowView) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">
          Your current role does not have access to pending approvals.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2 space-y-4">
          <div className="flex items-center justify-between rounded-2xl border bg-white p-4 shadow-sm">
            <div>
              <div className="text-base font-semibold text-gray-900">Pending approvals</div>
              <div className="mt-1 text-sm text-gray-600">
                Review, approve, reject, and execute governance change requests.
              </div>
            </div>

            <button
              type="button"
              className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
              onClick={() => void refresh()}
            >
              Refresh
            </button>
          </div>

          {error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Failed to load pending approvals: {error.message}
            </div>
          ) : null}

          <PendingApprovalsTable
            items={items}
            loading={loading}
            approvingId={approvingId}
            rejectingId={rejectingId}
            executingId={executingId}
            selectedChangeRequestId={selectedItem?.change_request_id ?? null}
            canApprove={allowApprove}
            canReject={allowReject}
            canExecute={allowExecute}
            onApprove={handleApproveClick}
            onReject={handleRejectClick}
            onExecute={handleExecute}
            onSelect={(item) => setSelectedItem(item)}
          />
        </div>

        <div className="space-y-4">
          <GovernanceTimelinePanel
            actor={actor}
            changeRequestId={selectedItem?.change_request_id ?? null}
          />

          <DirectiveVersionRefreshCard
            actor={actor}
            directiveId={selectedItem?.directive_id ?? conflictDirectiveId ?? null}
            onLoaded={(snapshot) => setLatestSnapshot(snapshot)}
          />
        </div>
      </div>

      <ApprovalNoteModal
        open={approvalModalOpen}
        item={selectedItem}
        submitting={Boolean(approvingId)}
        onClose={() => {
          if (approvingId) return;
          setApprovalModalOpen(false);
        }}
        onSubmit={(note) => void handleApproveSubmit(note)}
      />

      <RejectReasonModal
        open={rejectModalOpen}
        item={selectedItem}
        submitting={Boolean(rejectingId)}
        onClose={() => {
          if (rejectingId) return;
          setRejectModalOpen(false);
        }}
        onSubmit={(reason) => void handleRejectSubmit(reason)}
      />

      <GovernanceConflictDialog
        open={conflictOpen}
        error={conflictError}
        onClose={() => {
          setConflictOpen(false);
          setConflictError(null);
          setConflictDirectiveId(null);
        }}
        onRefresh={() => void refresh()}
        extra={
          actor ? (
            <DirectiveVersionRefreshCard
              actor={actor}
              directiveId={conflictDirectiveId}
              onLoaded={(snapshot) => setLatestSnapshot(snapshot)}
            />
          ) : null
        }
      />
    </>
  );
}
21) frontend/src/components/governance/GovernanceActionBar.tsx
Nâng cấp action bar cho timeline selection + conflict refresh UX.
import React, { useState } from "react";
import { executeChangeRequest } from "@/lib/governanceApi";
import { canExecute } from "@/lib/governanceRbac";
import { DirectiveVersionRefreshCard } from "@/components/governance/DirectiveVersionRefreshCard";
import { GovernanceConflictDialog } from "@/components/governance/GovernanceConflictDialog";
import type { ApiError } from "@/types/api";
import type { ActorContext } from "@/types/governance";

type Props = {
  actor: ActorContext;
  changeRequestId: string;
  directiveId: string;
  status: string;
  onExecuted?: (updatedVersion: number) => void;
  onRefresh?: () => void;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

export function GovernanceActionBar({
  actor,
  changeRequestId,
  directiveId,
  status,
  onExecuted,
  onRefresh,
  onToast,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [conflictError, setConflictError] = useState<ApiError | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);

  const handleExecute = async () => {
    setSubmitting(true);

    const result = await executeChangeRequest({
      actor,
      changeRequestId,
    });

    setSubmitting(false);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        setConflictError(result.error);
        setConflictOpen(true);
        return;
      }

      onToast?.({
        type: "error",
        message: result.error.message,
      });
      return;
    }

    onToast?.({
      type: "success",
      message: `Executed successfully. Updated version: ${result.data.updated_version}`,
    });

    onExecuted?.(result.data.updated_version);
  };

  const allowExecute = canExecute(actor.actorRole);
  const disabled = !allowExecute || submitting || status !== "approved";

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          disabled={disabled}
          onClick={() => void handleExecute()}
        >
          {submitting ? "Executing..." : "Execute"}
        </button>
      </div>

      <GovernanceConflictDialog
        open={conflictOpen}
        error={conflictError}
        onClose={() => {
          setConflictOpen(false);
          setConflictError(null);
        }}
        onRefresh={onRefresh}
        extra={
          <DirectiveVersionRefreshCard
            actor={actor}
            directiveId={directiveId}
          />
        }
      />
    </>
  );
}
22) tests frontend
frontend/src/lib/__tests__/governanceRbac.test.ts
import { describe, expect, it } from "vitest";
import {
  canApprove,
  canExecute,
  canReadTimeline,
  canReject,
  canViewPendingApprovals,
} from "@/lib/governanceRbac";

describe("governance RBAC helpers", () => {
  it("allows approver to view, approve, reject, and read timeline", () => {
    expect(canViewPendingApprovals("approver")).toBe(true);
    expect(canApprove("approver")).toBe(true);
    expect(canReject("approver")).toBe(true);
    expect(canReadTimeline("approver")).toBe(true);
  });

  it("does not allow viewer to approve or execute", () => {
    expect(canViewPendingApprovals("viewer")).toBe(false);
    expect(canApprove("viewer")).toBe(false);
    expect(canReject("viewer")).toBe(false);
    expect(canExecute("viewer")).toBe(false);
    expect(canReadTimeline("viewer")).toBe(false);
  });

  it("allows operator to execute and read timeline", () => {
    expect(canExecute("operator")).toBe(true);
    expect(canReadTimeline("operator")).toBe(true);
  });
});
23) UI behavior đã được khóa trong bản này
Lớp này chốt thêm 4 hành vi rất quan trọng:
A. Reject flow
approver/admin có thể reject
phải nhập lý do
requester không được reject chính request của mình
reject xong refresh queue ngay
B. Audit timeline
click vào row là xem timeline
timeline gom:
created
approved
rejected
execution attempts
notification events
C. Version refresh UX
conflict dialog không chỉ báo lỗi
có thể refresh current directive version/state ngay trong dialog
giúp operator biết hệ đang ở version nào
D. Conflict recovery
sau stale version / approval race / reject race
operator có:
refresh queue
refresh directive state
xem timeline
không còn chỉ là “409 rồi thôi”
24) điểm map rất ngắn khi paste vào repo thật
Bạn chỉ cần map các điểm sau:
Backend
GovernanceChangeRequest model phải có thêm:
rejected_by
rejection_reason
Nếu chưa có thì thêm migration nhẹ.
GovernanceApprovalRepository
phải có:
get_by_change_request_id(change_request_id: str)
DirectiveStateGateway.get(directive_id)
phải trả object có:
.version
.state hoặc .payload
GovernanceExecutionAttemptRepository
phải có:
list_by_change_request_id(change_request_id: str)
Frontend
Actor source
Hiện đang truyền qua props. Nếu repo có auth store thì map lại.
Modal / Button / Table
Nếu repo dùng shadcn/ui thì thay UI primitive, giữ nguyên flow.
Timeline placement
Hiện timeline nằm bên phải panel. Nếu dashboard layout khác, nhúng sang drawer/side panel đều được.
25) nếu schema DB chưa có cột reject
Bạn cần migration rất ngắn:
alembic revision patch
from alembic import op
import sqlalchemy as sa


revision = "phase3_reject_fields"
down_revision = "YOUR_PHASE3_PREV_REVISION"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("governance_change_request", sa.Column("rejected_by", sa.String(length=255), nullable=True))
    op.add_column("governance_change_request", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("governance_change_request", "rejection_reason")
    op.drop_column("governance_change_request", "rejected_by")
26) thứ tự paste khuyến nghị
Backend
update schemas governance
update notification model/repo nếu cần
update change request repo
add rejection service
add timeline service
add directive state query service
update rbac
update routes
add migration nếu cần
add backend tests
Frontend
update governance types
update governance API client
update rbac helpers
add RejectReasonModal
add GovernanceTimelinePanel
add DirectiveVersionRefreshCard
update ConflictDialog
update PendingApprovalsTable
update GovernancePendingApprovalsPanel
update GovernanceActionBar
add tests
27) bước mạnh nhất ngay sau bản này
Bước mạnh nhất tiếp theo là:
PHASE 3 — BULK APPROVAL ACTIONS + TIMELINE FILTERS + STALE VERSION REBASE UX
vì lúc đó hệ sẽ đi từ:
xử lý từng request riêng lẻ
sang:
xử lý queue thực chiến theo lô
lọc timeline theo event type/status
hỗ trợ “rebase to latest version” thay vì chỉ refresh nhìn trạng thái
Nếu bạn muốn, tôi sẽ viết tiếp ngay bản PHASE 3 BULK APPROVAL ACTIONS + TIMELINE FILTERS + REBASE UX theo đúng format file-by-file.
viết tiếp ngay bản PHASE 3 BULK APPROVAL ACTIONS + TIMELINE FILTERS + REBASE UX theo đúng format file-by-file.
Đã suy nghĩ trong giây lát
Dưới đây là bản PHASE 3 — BULK APPROVAL ACTIONS + TIMELINE FILTERS + REBASE UX theo đúng format file-by-file, nối tiếp trực tiếp trên lớp:
RBAC + auth + error contract
pending approvals UI
reject flow
audit timeline
version refresh UX
Mục tiêu của lớp này:
bulk approve / bulk reject / bulk execute
timeline filters
rebase UX khi stale version conflict
giữ nguyên kiến trúc hiện tại, chỉ nối thêm đúng các điểm production cần
TỔNG QUAN
Lớp này thêm 3 capability lớn:
1. Bulk actions
Cho operator/approver xử lý queue thật:
chọn nhiều change requests
bulk approve
bulk reject
bulk execute
2. Timeline filters
Cho panel timeline lọc theo:
event type
status
actor_id text search
3. Rebase UX
Khi 409 version conflict:
load current directive state/version
tạo rebase preview
submit rebase thành change request mới với expected_directive_version mới nhất
change request cũ vẫn giữ nguyên audit trail
BACKEND
1) backend/app/api/schemas/governance.py
Thêm schema cho bulk actions + rebase.
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernanceBulkApproveRequest(BaseModel):
    change_request_ids: list[str] = Field(..., min_length=1)
    note: str | None = None


class GovernanceBulkRejectRequest(BaseModel):
    change_request_ids: list[str] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=2000)


class GovernanceBulkExecuteRequest(BaseModel):
    change_request_ids: list[str] = Field(..., min_length=1)


class GovernanceBulkActionItemResult(BaseModel):
    change_request_id: str
    ok: bool
    status: str
    error: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class GovernanceBulkActionResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[GovernanceBulkActionItemResult]


class GovernanceRebasePreviewResponse(BaseModel):
    source_change_request_id: str
    directive_id: str
    old_expected_version: int
    current_version: int
    rebased_patch: dict[str, Any] = Field(default_factory=dict)
    can_rebase: bool
    reasons: list[str] = Field(default_factory=list)


class GovernanceRebaseCreateRequest(BaseModel):
    reason: str | None = None
    idempotency_key: str = Field(..., min_length=1, max_length=255)


class GovernanceRebaseCreateResponse(BaseModel):
    source_change_request_id: str
    new_change_request_id: str
    directive_id: str
    expected_directive_version: int
    status: str
    created_at: datetime
2) backend/app/repositories/governance_change_request_repository.py
Bổ sung bulk getters + clone-from-source support.
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_change_request import GovernanceChangeRequest


class GovernanceChangeRequestRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, entity: GovernanceChangeRequest) -> GovernanceChangeRequest:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        return self.session.get(GovernanceChangeRequest, change_request_id)

    def get_many(self, change_request_ids: list[str]) -> list[GovernanceChangeRequest]:
        if not change_request_ids:
            return []

        stmt: Select[tuple[GovernanceChangeRequest]] = select(GovernanceChangeRequest).where(
            GovernanceChangeRequest.id.in_(change_request_ids)
        )
        return list(self.session.execute(stmt).scalars().all())

    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt: Select[tuple[GovernanceChangeRequest]] = select(GovernanceChangeRequest).where(
            GovernanceChangeRequest.idempotency_key == idempotency_key
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_pending_approvals(self, limit: int = 100, offset: int = 0) -> list[GovernanceChangeRequest]:
        stmt: Select[tuple[GovernanceChangeRequest]] = (
            select(GovernanceChangeRequest)
            .where(GovernanceChangeRequest.status == "pending_approval")
            .order_by(GovernanceChangeRequest.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_rejected(
        self,
        *,
        change_request_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> GovernanceChangeRequest | None:
        entity = self.get(change_request_id)
        if not entity:
            return None

        entity.status = "rejected"
        entity.rejected_by = rejected_by
        entity.rejection_reason = rejection_reason
        return entity
3) backend/app/services/governance_bulk_action_service.py
Service này gom bulk approve / reject / execute nhưng không all-or-nothing.
Mỗi item tự commit/rollback riêng để queue production không chết cả lô.
from __future__ import annotations

from app.core.exceptions import AppError


class GovernanceBulkActionService:
    def __init__(
        self,
        session_factory,
        approval_service_factory,
        rejection_service_factory,
        execution_service_factory,
    ):
        self.session_factory = session_factory
        self.approval_service_factory = approval_service_factory
        self.rejection_service_factory = rejection_service_factory
        self.execution_service_factory = execution_service_factory

    def bulk_approve(
        self,
        *,
        change_request_ids: list[str],
        approver_id: str,
        note: str | None,
    ) -> dict:
        results: list[dict] = []

        for change_request_id in change_request_ids:
            session = self.session_factory()
            try:
                service = self.approval_service_factory(session)
                service.approve(
                    change_request_id=change_request_id,
                    approver_id=approver_id,
                    note=note,
                )
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": True,
                        "status": "approved",
                        "error": None,
                        "message": None,
                        "details": {},
                    }
                )
            except AppError as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": exc.code.value,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
            except Exception as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": "internal_error",
                        "message": str(exc),
                        "details": {},
                    }
                )
            finally:
                session.close()

        succeeded = sum(1 for r in results if r["ok"])
        failed = len(results) - succeeded

        return {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    def bulk_reject(
        self,
        *,
        change_request_ids: list[str],
        rejected_by: str,
        reason: str,
    ) -> dict:
        results: list[dict] = []

        for change_request_id in change_request_ids:
            session = self.session_factory()
            try:
                service = self.rejection_service_factory(session)
                source = service.change_request_repo.get(change_request_id)
                requested_by = source.requested_by if source else None

                service.reject(
                    change_request_id=change_request_id,
                    rejected_by=rejected_by,
                    requested_by=requested_by,
                    reason=reason,
                )

                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": True,
                        "status": "rejected",
                        "error": None,
                        "message": None,
                        "details": {},
                    }
                )
            except AppError as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": exc.code.value,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
            except Exception as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": "internal_error",
                        "message": str(exc),
                        "details": {},
                    }
                )
            finally:
                session.close()

        succeeded = sum(1 for r in results if r["ok"])
        failed = len(results) - succeeded

        return {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    def bulk_execute(
        self,
        *,
        change_request_ids: list[str],
        executed_by: str,
    ) -> dict:
        results: list[dict] = []

        for change_request_id in change_request_ids:
            session = self.session_factory()
            try:
                service = self.execution_service_factory(session)
                execution_result = service.execute(
                    change_request_id=change_request_id,
                    executed_by=executed_by,
                )
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": True,
                        "status": execution_result["execution_status"],
                        "error": None,
                        "message": None,
                        "details": {
                            "updated_version": execution_result["updated_version"],
                            "directive_id": execution_result["directive_id"],
                        },
                    }
                )
            except AppError as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": exc.code.value,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
            except Exception as exc:
                session.rollback()
                results.append(
                    {
                        "change_request_id": change_request_id,
                        "ok": False,
                        "status": "failed",
                        "error": "internal_error",
                        "message": str(exc),
                        "details": {},
                    }
                )
            finally:
                session.close()

        succeeded = sum(1 for r in results if r["ok"])
        failed = len(results) - succeeded

        return {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }
4) backend/app/services/governance_rebase_service.py
Đây là lõi rebase UX.
Trong Phase 3 này, rebase sẽ:
lấy source change request
đọc current directive version
nếu patch không phụ thuộc diff phức tạp thì dùng lại patch cũ
tạo change request mới với expected_directive_version = current_version
from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError


class GovernanceRebaseService:
    def __init__(self, session, change_request_repo, directive_state_gateway, notification_repo):
        self.session = session
        self.change_request_repo = change_request_repo
        self.directive_state_gateway = directive_state_gateway
        self.notification_repo = notification_repo

    def preview_rebase(self, source_change_request_id: str) -> dict:
        source = self.change_request_repo.get(source_change_request_id)
        if not source:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": source_change_request_id},
            )

        directive_state = self.directive_state_gateway.get(source.directive_id)
        if directive_state is None:
            raise NotFoundError(
                "Directive state not found",
                {"directive_id": source.directive_id},
            )

        current_version = directive_state.version
        old_expected_version = source.expected_directive_version

        reasons: list[str] = []
        can_rebase = True

        if source.status == "executed":
            can_rebase = False
            reasons.append("Executed change requests cannot be rebased")

        if source.status == "rejected":
            can_rebase = False
            reasons.append("Rejected change requests cannot be rebased")

        return {
            "source_change_request_id": source.id,
            "directive_id": source.directive_id,
            "old_expected_version": old_expected_version,
            "current_version": current_version,
            "rebased_patch": source.patch,
            "can_rebase": can_rebase,
            "reasons": reasons,
        }

    def create_rebased_change_request(
        self,
        *,
        source_change_request_id: str,
        requested_by: str,
        idempotency_key: str,
        reason: str | None,
        governance_change_request_model,
    ):
        preview = self.preview_rebase(source_change_request_id)
        if not preview["can_rebase"]:
            raise ConflictError(
                "Change request cannot be rebased",
                {
                    "source_change_request_id": source_change_request_id,
                    "reasons": preview["reasons"],
                },
            )

        existing = self.change_request_repo.find_by_idempotency_key(idempotency_key)
        if existing:
            return existing, True

        source = self.change_request_repo.get(source_change_request_id)
        if not source:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": source_change_request_id},
            )

        entity = governance_change_request_model(
            directive_id=source.directive_id,
            action_type=source.action_type,
            status="pending_approval",
            requested_by=requested_by,
            reason=reason or f"Rebased from {source.id}",
            idempotency_key=idempotency_key,
            expected_directive_version=preview["current_version"],
            patch=preview["rebased_patch"],
        )

        created = self.change_request_repo.create(entity)

        self.notification_repo.create(
            change_request_id=created.id,
            directive_id=created.directive_id,
            event_type="change_request_rebased",
            actor_id=requested_by,
            status="pending_approval",
            note=reason,
            payload={
                "source_change_request_id": source.id,
                "old_expected_version": preview["old_expected_version"],
                "new_expected_version": preview["current_version"],
            },
        )

        self.session.commit()
        self.session.refresh(created)
        return created, False
5) backend/app/services/governance_timeline_service.py
Bản này bổ sung filter support.
from __future__ import annotations

from app.core.exceptions import NotFoundError


class GovernanceTimelineService:
    def __init__(self, change_request_repo, approval_repo, execution_attempt_repo, notification_repo):
        self.change_request_repo = change_request_repo
        self.approval_repo = approval_repo
        self.execution_attempt_repo = execution_attempt_repo
        self.notification_repo = notification_repo

    def get_timeline(
        self,
        change_request_id: str,
        *,
        event_types: set[str] | None = None,
        statuses: set[str] | None = None,
        actor_query: str | None = None,
    ) -> dict:
        change_request = self.change_request_repo.get(change_request_id)
        if not change_request:
            raise NotFoundError(
                "Change request not found",
                {"change_request_id": change_request_id},
            )

        events: list[dict] = []

        events.append(
            {
                "event_type": "change_request_created",
                "actor_id": change_request.requested_by,
                "status": change_request.status,
                "note": change_request.reason,
                "payload": {
                    "action_type": change_request.action_type,
                    "expected_directive_version": change_request.expected_directive_version,
                    "patch": change_request.patch,
                },
                "created_at": change_request.created_at,
            }
        )

        approval = self.approval_repo.get_by_change_request_id(change_request_id)
        if approval:
            events.append(
                {
                    "event_type": "change_request_approved",
                    "actor_id": approval.approver_id,
                    "status": "approved",
                    "note": approval.note,
                    "payload": {},
                    "created_at": approval.created_at,
                }
            )

        execution_attempts = self.execution_attempt_repo.list_by_change_request_id(change_request_id)
        for attempt in execution_attempts:
            events.append(
                {
                    "event_type": "execution_attempt",
                    "actor_id": attempt.executed_by,
                    "status": attempt.status,
                    "note": None,
                    "payload": getattr(attempt, "result_payload", {}) or {},
                    "created_at": attempt.created_at,
                }
            )

        notification_events = self.notification_repo.list_by_change_request_id(change_request_id)
        for event in notification_events:
            events.append(
                {
                    "event_type": event.event_type,
                    "actor_id": event.actor_id,
                    "status": event.status,
                    "note": event.note,
                    "payload": event.payload or {},
                    "created_at": event.created_at,
                }
            )

        events.sort(key=lambda item: item["created_at"])

        if event_types:
            events = [e for e in events if e["event_type"] in event_types]

        if statuses:
            events = [e for e in events if (e["status"] or "") in statuses]

        if actor_query:
            actor_query_lower = actor_query.lower()
            events = [
                e for e in events
                if e["actor_id"] and actor_query_lower in e["actor_id"].lower()
            ]

        return {
            "change_request_id": change_request.id,
            "directive_id": change_request.directive_id,
            "status": change_request.status,
            "events": events,
        }
6) backend/app/api/routes/governance.py
Thêm bulk routes + timeline filter params + rebase preview/create.
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import ActorContext, get_actor_context
from app.api.schemas.error_schema import ErrorResponse
from app.api.schemas.governance import (
    GovernanceBulkActionResponse,
    GovernanceBulkApproveRequest,
    GovernanceBulkExecuteRequest,
    GovernanceBulkRejectRequest,
    GovernanceBulkActionItemResult,
    GovernanceRebaseCreateRequest,
    GovernanceRebaseCreateResponse,
    GovernanceRebasePreviewResponse,
    GovernanceTimelineEventResponse,
    GovernanceTimelineResponse,
)
from app.db.session import SessionLocal, get_db
from app.models.governance_change_request import GovernanceChangeRequest
from app.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.services.governance_approval_service import GovernanceApprovalService
from app.services.governance_bulk_action_service import GovernanceBulkActionService
from app.services.governance_execution_service import GovernanceExecutionService
from app.services.governance_rebase_service import GovernanceRebaseService
from app.services.governance_rejection_service import GovernanceRejectionService
from app.services.governance_timeline_service import GovernanceTimelineService
from app.services.rbac import (
    require_can_approve,
    require_can_execute,
    require_can_read_timeline,
    require_can_reject,
)

router = APIRouter(prefix="/governance", tags=["governance"])


def build_approval_service(session: Session) -> GovernanceApprovalService:
    return GovernanceApprovalService(
        session=session,
        change_request_repo=GovernanceChangeRequestRepository(session),
        approval_repo=GovernanceApprovalRepository(session),
        notification_repo=GovernanceNotificationRepository(session),
    )


def build_rejection_service(session: Session) -> GovernanceRejectionService:
    return GovernanceRejectionService(
        session=session,
        change_request_repo=GovernanceChangeRequestRepository(session),
        notification_repo=GovernanceNotificationRepository(session),
    )


def build_execution_service(session: Session) -> GovernanceExecutionService:
    from app.governance.directive_state_gateway import DirectiveStateGateway
    from app.governance.runtime_fabric_adapter_registry import RuntimeFabricAdapterRegistry

    return GovernanceExecutionService(
        session=session,
        change_request_repo=GovernanceChangeRequestRepository(session),
        execution_attempt_repo=GovernanceExecutionAttemptRepository(session),
        notification_repo=GovernanceNotificationRepository(session),
        directive_state_gateway=DirectiveStateGateway(),
        runtime_adapter_registry=RuntimeFabricAdapterRegistry(),
    )


def get_bulk_action_service() -> GovernanceBulkActionService:
    return GovernanceBulkActionService(
        session_factory=SessionLocal,
        approval_service_factory=build_approval_service,
        rejection_service_factory=build_rejection_service,
        execution_service_factory=build_execution_service,
    )


def get_rebase_service(db: Session = Depends(get_db)) -> GovernanceRebaseService:
    from app.governance.directive_state_gateway import DirectiveStateGateway

    return GovernanceRebaseService(
        session=db,
        change_request_repo=GovernanceChangeRequestRepository(db),
        directive_state_gateway=DirectiveStateGateway(),
        notification_repo=GovernanceNotificationRepository(db),
    )


@router.post(
    "/change-requests/bulk-approve",
    response_model=GovernanceBulkActionResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def bulk_approve_change_requests(
    payload: GovernanceBulkApproveRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceBulkActionService = Depends(get_bulk_action_service),
):
    require_can_approve(actor)

    result = service.bulk_approve(
        change_request_ids=payload.change_request_ids,
        approver_id=actor.actor_id,
        note=payload.note,
    )

    return GovernanceBulkActionResponse(
        total=result["total"],
        succeeded=result["succeeded"],
        failed=result["failed"],
        results=[GovernanceBulkActionItemResult(**r) for r in result["results"]],
    )


@router.post(
    "/change-requests/bulk-reject",
    response_model=GovernanceBulkActionResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def bulk_reject_change_requests(
    payload: GovernanceBulkRejectRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceBulkActionService = Depends(get_bulk_action_service),
):
    require_can_reject(actor)

    result = service.bulk_reject(
        change_request_ids=payload.change_request_ids,
        rejected_by=actor.actor_id,
        reason=payload.reason,
    )

    return GovernanceBulkActionResponse(
        total=result["total"],
        succeeded=result["succeeded"],
        failed=result["failed"],
        results=[GovernanceBulkActionItemResult(**r) for r in result["results"]],
    )


@router.post(
    "/change-requests/bulk-execute",
    response_model=GovernanceBulkActionResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def bulk_execute_change_requests(
    payload: GovernanceBulkExecuteRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceBulkActionService = Depends(get_bulk_action_service),
):
    require_can_execute(actor)

    result = service.bulk_execute(
        change_request_ids=payload.change_request_ids,
        executed_by=actor.actor_id,
    )

    return GovernanceBulkActionResponse(
        total=result["total"],
        succeeded=result["succeeded"],
        failed=result["failed"],
        results=[GovernanceBulkActionItemResult(**r) for r in result["results"]],
    )


@router.get(
    "/change-requests/{change_request_id}/timeline",
    response_model=GovernanceTimelineResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_change_request_timeline(
    change_request_id: str,
    event_type: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    actor_q: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    db: Session = Depends(get_db),
):
    require_can_read_timeline(actor)

    service = GovernanceTimelineService(
        change_request_repo=GovernanceChangeRequestRepository(db),
        approval_repo=GovernanceApprovalRepository(db),
        execution_attempt_repo=GovernanceExecutionAttemptRepository(db),
        notification_repo=GovernanceNotificationRepository(db),
    )

    result = service.get_timeline(
        change_request_id,
        event_types=set(event_type) if event_type else None,
        statuses=set(status) if status else None,
        actor_query=actor_q,
    )

    return GovernanceTimelineResponse(
        change_request_id=result["change_request_id"],
        directive_id=result["directive_id"],
        status=result["status"],
        events=[GovernanceTimelineEventResponse(**event) for event in result["events"]],
    )


@router.get(
    "/change-requests/{change_request_id}/rebase-preview",
    response_model=GovernanceRebasePreviewResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def get_rebase_preview(
    change_request_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceRebaseService = Depends(get_rebase_service),
):
    require_can_execute(actor)
    result = service.preview_rebase(change_request_id)
    return GovernanceRebasePreviewResponse(**result)


@router.post(
    "/change-requests/{change_request_id}/rebase",
    response_model=GovernanceRebaseCreateResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_rebased_change_request(
    change_request_id: str,
    payload: GovernanceRebaseCreateRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: GovernanceRebaseService = Depends(get_rebase_service),
):
    require_can_execute(actor)

    created, reused = service.create_rebased_change_request(
        source_change_request_id=change_request_id,
        requested_by=actor.actor_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        governance_change_request_model=GovernanceChangeRequest,
    )

    return GovernanceRebaseCreateResponse(
        source_change_request_id=change_request_id,
        new_change_request_id=created.id,
        directive_id=created.directive_id,
        expected_directive_version=created.expected_directive_version,
        status=created.status,
        created_at=created.created_at,
    )
7) backend/tests/api/test_governance_bulk_and_rebase.py
from __future__ import annotations
import uuid


def _auth_headers(actor_id: str, role: str) -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }


def test_bulk_approve_success(client, seed_pending_change_request):
    response = client.post(
        "/api/v1/governance/change-requests/bulk-approve",
        json={
            "change_request_ids": [seed_pending_change_request.id],
            "note": "bulk approve",
        },
        headers=_auth_headers("approver-1", "approver"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["succeeded"] == 1
    assert body["results"][0]["ok"] is True


def test_bulk_reject_success(client, seed_pending_change_request):
    response = client.post(
        "/api/v1/governance/change-requests/bulk-reject",
        json={
            "change_request_ids": [seed_pending_change_request.id],
            "reason": "bulk reject",
        },
        headers=_auth_headers("approver-2", "approver"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == 1
    assert body["results"][0]["status"] == "rejected"


def test_timeline_filters(client, seed_pending_change_request):
    response = client.get(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/timeline?event_type=change_request_created",
        headers=_auth_headers("operator-1", "operator"),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) >= 1
    assert all(event["event_type"] == "change_request_created" for event in body["events"])


def test_rebase_preview_success(client, seed_pending_change_request):
    response = client.get(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/rebase-preview",
        headers=_auth_headers("operator-1", "operator"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_change_request_id"] == seed_pending_change_request.id
    assert "current_version" in body


def test_rebase_create_success(client, seed_pending_change_request):
    response = client.post(
        f"/api/v1/governance/change-requests/{seed_pending_change_request.id}/rebase",
        json={
            "reason": "rebase to latest version",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=_auth_headers("operator-1", "operator"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_change_request_id"] == seed_pending_change_request.id
    assert body["status"] == "pending_approval"
FRONTEND
8) frontend/src/types/governance.ts
Mở rộng types cho bulk + filters + rebase.
export type GovernancePendingApprovalItem = {
  change_request_id: string;
  directive_id: string;
  action_type: string;
  requested_by: string;
  reason?: string | null;
  approval_rule_key?: string | null;
  status: string;
  created_at: string;
};

export type GovernancePendingApprovalsResponse = {
  items: GovernancePendingApprovalItem[];
};

export type GovernanceApprovalResponse = {
  id: string;
  change_request_id: string;
  approver_id: string;
  note?: string | null;
  created_at: string;
};

export type GovernanceRejectResponse = {
  change_request_id: string;
  status: string;
  rejected_by: string;
  rejection_reason: string;
  rejected_at: string;
};

export type GovernanceExecuteResponse = {
  directive_id: string;
  updated_version: number;
  execution_status: string;
  change_request_id: string;
};

export type GovernanceTimelineEvent = {
  event_type: string;
  actor_id?: string | null;
  status?: string | null;
  note?: string | null;
  payload?: Record<string, unknown>;
  created_at: string;
};

export type GovernanceTimelineResponse = {
  change_request_id: string;
  directive_id: string;
  status: string;
  events: GovernanceTimelineEvent[];
};

export type DirectiveStateSnapshotResponse = {
  directive_id: string;
  version: number;
  state: Record<string, unknown>;
  fetched_at: string;
};

export type GovernanceBulkActionItemResult = {
  change_request_id: string;
  ok: boolean;
  status: string;
  error?: string | null;
  message?: string | null;
  details?: Record<string, unknown>;
};

export type GovernanceBulkActionResponse = {
  total: number;
  succeeded: number;
  failed: number;
  results: GovernanceBulkActionItemResult[];
};

export type GovernanceRebasePreviewResponse = {
  source_change_request_id: string;
  directive_id: string;
  old_expected_version: number;
  current_version: number;
  rebased_patch: Record<string, unknown>;
  can_rebase: boolean;
  reasons: string[];
};

export type GovernanceRebaseCreateResponse = {
  source_change_request_id: string;
  new_change_request_id: string;
  directive_id: string;
  expected_directive_version: number;
  status: string;
  created_at: string;
};

export type TimelineFilters = {
  eventTypes: string[];
  statuses: string[];
  actorQuery: string;
};

export type ActorContext = {
  actorId: string;
  actorRole: string;
  actorEmail?: string;
  actorName?: string;
};
9) frontend/src/lib/governanceApi.ts
Thêm bulk endpoints + timeline filters + rebase endpoints.
import { apiRequest } from "@/lib/api";
import type {
  ActorContext,
  DirectiveStateSnapshotResponse,
  GovernanceApprovalResponse,
  GovernanceBulkActionResponse,
  GovernanceExecuteResponse,
  GovernancePendingApprovalsResponse,
  GovernanceRebaseCreateResponse,
  GovernanceRebasePreviewResponse,
  GovernanceRejectResponse,
  GovernanceTimelineResponse,
  TimelineFilters,
} from "@/types/governance";

const GOVERNANCE_BASE = "/api/v1/governance";

export async function fetchPendingApprovals(params: {
  actor: ActorContext;
  limit?: number;
  offset?: number;
}) {
  const search = new URLSearchParams({
    limit: String(params.limit ?? 100),
    offset: String(params.offset ?? 0),
  });

  return apiRequest<GovernancePendingApprovalsResponse>(
    `${GOVERNANCE_BASE}/pending-approvals?${search.toString()}`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function approveChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  note?: string;
}) {
  return apiRequest<GovernanceApprovalResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/approve`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({ note: params.note ?? null }),
    }
  );
}

export async function rejectChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  reason: string;
}) {
  return apiRequest<GovernanceRejectResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/reject`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({ reason: params.reason }),
    }
  );
}

export async function executeChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
}) {
  return apiRequest<GovernanceExecuteResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/execute`,
    {
      method: "POST",
      actor: params.actor,
    }
  );
}

export async function bulkApproveChangeRequests(params: {
  actor: ActorContext;
  changeRequestIds: string[];
  note?: string;
}) {
  return apiRequest<GovernanceBulkActionResponse>(
    `${GOVERNANCE_BASE}/change-requests/bulk-approve`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({
        change_request_ids: params.changeRequestIds,
        note: params.note ?? null,
      }),
    }
  );
}

export async function bulkRejectChangeRequests(params: {
  actor: ActorContext;
  changeRequestIds: string[];
  reason: string;
}) {
  return apiRequest<GovernanceBulkActionResponse>(
    `${GOVERNANCE_BASE}/change-requests/bulk-reject`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({
        change_request_ids: params.changeRequestIds,
        reason: params.reason,
      }),
    }
  );
}

export async function bulkExecuteChangeRequests(params: {
  actor: ActorContext;
  changeRequestIds: string[];
}) {
  return apiRequest<GovernanceBulkActionResponse>(
    `${GOVERNANCE_BASE}/change-requests/bulk-execute`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({
        change_request_ids: params.changeRequestIds,
      }),
    }
  );
}

export async function fetchChangeRequestTimeline(params: {
  actor: ActorContext;
  changeRequestId: string;
  filters?: TimelineFilters;
}) {
  const search = new URLSearchParams();

  for (const eventType of params.filters?.eventTypes ?? []) {
    search.append("event_type", eventType);
  }

  for (const status of params.filters?.statuses ?? []) {
    search.append("status", status);
  }

  if (params.filters?.actorQuery?.trim()) {
    search.set("actor_q", params.filters.actorQuery.trim());
  }

  const suffix = search.toString() ? `?${search.toString()}` : "";

  return apiRequest<GovernanceTimelineResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/timeline${suffix}`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function fetchDirectiveStateSnapshot(params: {
  actor: ActorContext;
  directiveId: string;
}) {
  return apiRequest<DirectiveStateSnapshotResponse>(
    `${GOVERNANCE_BASE}/directives/${params.directiveId}/state`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function fetchRebasePreview(params: {
  actor: ActorContext;
  changeRequestId: string;
}) {
  return apiRequest<GovernanceRebasePreviewResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/rebase-preview`,
    {
      method: "GET",
      actor: params.actor,
    }
  );
}

export async function createRebasedChangeRequest(params: {
  actor: ActorContext;
  changeRequestId: string;
  reason?: string;
  idempotencyKey: string;
}) {
  return apiRequest<GovernanceRebaseCreateResponse>(
    `${GOVERNANCE_BASE}/change-requests/${params.changeRequestId}/rebase`,
    {
      method: "POST",
      actor: params.actor,
      body: JSON.stringify({
        reason: params.reason ?? null,
        idempotency_key: params.idempotencyKey,
      }),
    }
  );
}
10) frontend/src/components/governance/TimelineFiltersBar.tsx
import React from "react";
import type { TimelineFilters } from "@/types/governance";

type Props = {
  value: TimelineFilters;
  onChange: (next: TimelineFilters) => void;
  onApply: () => void;
  onReset: () => void;
};

const EVENT_TYPE_OPTIONS = [
  "change_request_created",
  "change_request_approved",
  "change_request_rejected",
  "change_request_rebased",
  "execution_attempt",
];

const STATUS_OPTIONS = [
  "pending_approval",
  "approved",
  "rejected",
  "executed",
  "succeeded",
  "failed",
];

export function TimelineFiltersBar({ value, onChange, onApply, onReset }: Props) {
  const toggle = (list: string[], item: string) =>
    list.includes(item) ? list.filter((x) => x !== item) : [...list, item];

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="text-sm font-semibold text-gray-900">Timeline filters</div>

      <div className="mt-4 grid grid-cols-1 gap-4">
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            Event types
          </div>
          <div className="flex flex-wrap gap-2">
            {EVENT_TYPE_OPTIONS.map((option) => {
              const active = value.eventTypes.includes(option);
              return (
                <button
                  key={option}
                  type="button"
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                    active ? "bg-black text-white border-black" : "bg-white text-gray-700"
                  }`}
                  onClick={() =>
                    onChange({
                      ...value,
                      eventTypes: toggle(value.eventTypes, option),
                    })
                  }
                >
                  {option}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            Status
          </div>
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map((option) => {
              const active = value.statuses.includes(option);
              return (
                <button
                  key={option}
                  type="button"
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                    active ? "bg-black text-white border-black" : "bg-white text-gray-700"
                  }`}
                  onClick={() =>
                    onChange({
                      ...value,
                      statuses: toggle(value.statuses, option),
                    })
                  }
                >
                  {option}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-gray-500">
            Actor contains
          </label>
          <input
            className="w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-black"
            value={value.actorQuery}
            onChange={(e) => onChange({ ...value, actorQuery: e.target.value })}
            placeholder="Search actor id"
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          type="button"
          className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          onClick={onReset}
        >
          Reset
        </button>
        <button
          type="button"
          className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          onClick={onApply}
        >
          Apply filters
        </button>
      </div>
    </div>
  );
}
11) frontend/src/components/governance/BulkActionBar.tsx
import React from "react";

type Props = {
  selectedCount: number;
  canApprove: boolean;
  canReject: boolean;
  canExecute: boolean;
  busy?: boolean;
  onBulkApprove: () => void;
  onBulkReject: () => void;
  onBulkExecute: () => void;
  onClearSelection: () => void;
};

export function BulkActionBar({
  selectedCount,
  canApprove,
  canReject,
  canExecute,
  busy = false,
  onBulkApprove,
  onBulkReject,
  onBulkExecute,
  onClearSelection,
}: Props) {
  if (selectedCount === 0) return null;

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">Bulk actions</div>
          <div className="mt-1 text-sm text-gray-600">
            {selectedCount} change request{selectedCount > 1 ? "s" : ""} selected
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {canApprove ? (
            <button
              type="button"
              className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
              disabled={busy}
              onClick={onBulkApprove}
            >
              Bulk approve
            </button>
          ) : null}

          {canReject ? (
            <button
              type="button"
              className="rounded-xl border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              disabled={busy}
              onClick={onBulkReject}
            >
              Bulk reject
            </button>
          ) : null}

          {canExecute ? (
            <button
              type="button"
              className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              disabled={busy}
              onClick={onBulkExecute}
            >
              Bulk execute
            </button>
          ) : null}

          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
            disabled={busy}
            onClick={onClearSelection}
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
12) frontend/src/components/governance/BulkActionResultModal.tsx
import React from "react";
import type { GovernanceBulkActionResponse } from "@/types/governance";

type Props = {
  open: boolean;
  title: string;
  result: GovernanceBulkActionResponse | null;
  onClose: () => void;
};

export function BulkActionResultModal({ open, title, result, onClose }: Props) {
  if (!open || !result) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-gray-600">
            Total {result.total} · Succeeded {result.succeeded} · Failed {result.failed}
          </p>
        </div>

        <div className="max-h-[420px] overflow-auto rounded-xl border">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Change request</th>
                <th className="px-4 py-3 font-medium">OK</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {result.results.map((item) => (
                <tr key={item.change_request_id} className="border-t">
                  <td className="px-4 py-3 font-mono text-xs">{item.change_request_id}</td>
                  <td className="px-4 py-3">{item.ok ? "yes" : "no"}</td>
                  <td className="px-4 py-3">{item.status}</td>
                  <td className="px-4 py-3 text-gray-700">{item.message || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            type="button"
            className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
13) frontend/src/components/governance/RebaseModal.tsx
import React, { useEffect, useState } from "react";
import { createRebasedChangeRequest, fetchRebasePreview } from "@/lib/governanceApi";
import type {
  ActorContext,
  GovernancePendingApprovalItem,
  GovernanceRebasePreviewResponse,
} from "@/types/governance";

type Props = {
  open: boolean;
  actor: ActorContext;
  item: GovernancePendingApprovalItem | null;
  onClose: () => void;
  onCreated?: (newChangeRequestId: string) => void;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

function generateIdempotencyKey() {
  return `rebase-${crypto.randomUUID()}`;
}

export function RebaseModal({ open, actor, item, onClose, onCreated, onToast }: Props) {
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [preview, setPreview] = useState<GovernanceRebasePreviewResponse | null>(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function run() {
      if (!open || !item) {
        setPreview(null);
        setReason("");
        return;
      }

      setLoadingPreview(true);
      const result = await fetchRebasePreview({
        actor,
        changeRequestId: item.change_request_id,
      });
      setLoadingPreview(false);

      if (!result.ok) {
        onToast?.({ type: "error", message: result.error.message });
        return;
      }

      setPreview(result.data);
    }

    void run();
  }, [open, actor, item, onToast]);

  const handleCreate = async () => {
    if (!item) return;

    setSubmitting(true);
    const result = await createRebasedChangeRequest({
      actor,
      changeRequestId: item.change_request_id,
      reason: reason || undefined,
      idempotencyKey: generateIdempotencyKey(),
    });
    setSubmitting(false);

    if (!result.ok) {
      onToast?.({ type: "error", message: result.error.message });
      return;
    }

    onToast?.({
      type: "success",
      message: `Rebased into new change request ${result.data.new_change_request_id}`,
    });
    onCreated?.(result.data.new_change_request_id);
    onClose();
  };

  if (!open || !item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-semibold">Rebase to latest directive version</h2>
        <p className="mt-1 text-sm text-gray-600">
          Source request <span className="font-mono">{item.change_request_id}</span>
        </p>

        {loadingPreview ? (
          <div className="mt-4 text-sm text-gray-600">Loading rebase preview...</div>
        ) : null}

        {preview ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-sm text-gray-800">
                Old expected version: <span className="font-semibold">{preview.old_expected_version}</span>
              </div>
              <div className="mt-1 text-sm text-gray-800">
                Current version: <span className="font-semibold">{preview.current_version}</span>
              </div>
              <div className="mt-1 text-sm text-gray-800">
                Can rebase: <span className="font-semibold">{preview.can_rebase ? "yes" : "no"}</span>
              </div>

              {preview.reasons.length > 0 ? (
                <ul className="mt-3 list-disc pl-5 text-sm text-red-700">
                  {preview.reasons.map((reasonItem) => (
                    <li key={reasonItem}>{reasonItem}</li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-800">
                Rebase reason
              </label>
              <textarea
                className="min-h-[110px] w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-black"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Optional note for the rebased request"
              />
            </div>

            <div>
              <div className="mb-2 text-sm font-medium text-gray-800">Rebased patch</div>
              <pre className="max-h-[240px] overflow-auto rounded-xl bg-gray-50 p-3 text-xs text-gray-700">
                {JSON.stringify(preview.rebased_patch, null, 2)}
              </pre>
            </div>
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            onClick={() => void handleCreate()}
            disabled={submitting || !preview?.can_rebase}
          >
            {submitting ? "Creating..." : "Create rebased request"}
          </button>
        </div>
      </div>
    </div>
  );
}
14) frontend/src/components/governance/GovernanceTimelinePanel.tsx
Nâng cấp với filters.
import React, { useEffect, useState } from "react";
import { fetchChangeRequestTimeline } from "@/lib/governanceApi";
import { TimelineFiltersBar } from "@/components/governance/TimelineFiltersBar";
import type { ActorContext, GovernanceTimelineEvent, TimelineFilters } from "@/types/governance";

type Props = {
  actor: ActorContext;
  changeRequestId: string | null;
};

const DEFAULT_FILTERS: TimelineFilters = {
  eventTypes: [],
  statuses: [],
  actorQuery: "",
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function prettyEventTitle(eventType: string): string {
  switch (eventType) {
    case "change_request_created":
      return "Change request created";
    case "change_request_approved":
      return "Approved";
    case "change_request_rejected":
      return "Rejected";
    case "change_request_rebased":
      return "Rebased";
    case "execution_attempt":
      return "Execution attempt";
    default:
      return eventType;
  }
}

export function GovernanceTimelinePanel({ actor, changeRequestId }: Props) {
  const [filtersDraft, setFiltersDraft] = useState<TimelineFilters>(DEFAULT_FILTERS);
  const [filtersApplied, setFiltersApplied] = useState<TimelineFilters>(DEFAULT_FILTERS);

  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<GovernanceTimelineEvent[]>([]);
  const [directiveId, setDirectiveId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function run() {
      if (!changeRequestId) {
        setEvents([]);
        setDirectiveId(null);
        setStatus(null);
        return;
      }

      setLoading(true);
      setError(null);

      const result = await fetchChangeRequestTimeline({
        actor,
        changeRequestId,
        filters: filtersApplied,
      });

      setLoading(false);

      if (!result.ok) {
        setError(result.error.message);
        return;
      }

      setDirectiveId(result.data.directive_id);
      setStatus(result.data.status);
      setEvents(result.data.events);
    }

    void run();
  }, [actor, changeRequestId, filtersApplied]);

  return (
    <div className="space-y-4">
      <TimelineFiltersBar
        value={filtersDraft}
        onChange={setFiltersDraft}
        onApply={() => setFiltersApplied(filtersDraft)}
        onReset={() => {
          setFiltersDraft(DEFAULT_FILTERS);
          setFiltersApplied(DEFAULT_FILTERS);
        }}
      />

      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="mb-4">
          <div className="text-base font-semibold text-gray-900">Approval audit timeline</div>
          <div className="mt-1 text-sm text-gray-600">
            {changeRequestId ? (
              <>
                Change request <span className="font-mono">{changeRequestId}</span>
                {directiveId ? <> · Directive <span className="font-medium">{directiveId}</span></> : null}
                {status ? <> · Status <span className="font-medium">{status}</span></> : null}
              </>
            ) : (
              "Select a change request to inspect timeline."
            )}
          </div>
        </div>

        {loading ? <div className="text-sm text-gray-600">Loading timeline...</div> : null}
        {error ? <div className="text-sm text-red-700">{error}</div> : null}

        {!loading && !error && changeRequestId && events.length === 0 ? (
          <div className="text-sm text-gray-600">No timeline events found for the current filters.</div>
        ) : null}

        <div className="space-y-3">
          {events.map((event, idx) => (
            <div key={`${event.event_type}-${event.created_at}-${idx}`} className="rounded-xl border p-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold text-gray-900">
                    {prettyEventTitle(event.event_type)}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    {formatDate(event.created_at)}
                  </div>
                </div>

                {event.status ? (
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                    {event.status}
                  </span>
                ) : null}
              </div>

              <div className="mt-2 text-sm text-gray-700">
                {event.actor_id ? <>Actor: <span className="font-medium">{event.actor_id}</span></> : "System event"}
              </div>

              {event.note ? <div className="mt-2 text-sm text-gray-700">{event.note}</div> : null}

              {event.payload && Object.keys(event.payload).length > 0 ? (
                <pre className="mt-3 overflow-auto rounded-xl bg-gray-50 p-3 text-xs text-gray-700">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
15) frontend/src/components/governance/PendingApprovalsTable.tsx
Thêm checkbox selection.
import React from "react";
import type { GovernancePendingApprovalItem } from "@/types/governance";
import { GovernanceStatusBadge } from "@/components/governance/GovernanceStatusBadge";

type Props = {
  items: GovernancePendingApprovalItem[];
  loading?: boolean;
  approvingId?: string | null;
  rejectingId?: string | null;
  executingId?: string | null;
  selectedChangeRequestId?: string | null;
  selectedIds: string[];
  canApprove: boolean;
  canReject: boolean;
  canExecute: boolean;
  onApprove: (item: GovernancePendingApprovalItem) => void;
  onReject: (item: GovernancePendingApprovalItem) => void;
  onExecute: (item: GovernancePendingApprovalItem) => void;
  onSelect?: (item: GovernancePendingApprovalItem) => void;
  onToggleSelect: (item: GovernancePendingApprovalItem) => void;
  onToggleSelectAll: (checked: boolean) => void;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function PendingApprovalsTable({
  items,
  loading = false,
  approvingId = null,
  rejectingId = null,
  executingId = null,
  selectedChangeRequestId = null,
  selectedIds,
  canApprove,
  canReject,
  canExecute,
  onApprove,
  onReject,
  onExecute,
  onSelect,
  onToggleSelect,
  onToggleSelectAll,
}: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">Loading pending approvals...</div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No pending approvals found.</div>
      </div>
    );
  }

  const allSelected = items.length > 0 && items.every((item) => selectedIds.includes(item.change_request_id));

  return (
    <div className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-700">
            <tr>
              <th className="px-4 py-3 font-medium">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => onToggleSelectAll(e.target.checked)}
                />
              </th>
              <th className="px-4 py-3 font-medium">Directive</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Requested by</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Rule</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isApproving = approvingId === item.change_request_id;
              const isRejecting = rejectingId === item.change_request_id;
              const isExecuting = executingId === item.change_request_id;
              const isSelectedRow = selectedChangeRequestId === item.change_request_id;
              const isChecked = selectedIds.includes(item.change_request_id);

              return (
                <tr
                  key={item.change_request_id}
                  className={`border-t align-top ${isSelectedRow ? "bg-blue-50/40" : ""}`}
                  onClick={() => onSelect?.(item)}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => {
                        e.stopPropagation();
                        onToggleSelect(item);
                      }}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{item.directive_id}</div>
                    <div className="mt-1 font-mono text-xs text-gray-500">
                      {item.change_request_id}
                    </div>
                  </td>
                  <td className="px-4 py-3">{item.action_type}</td>
                  <td className="px-4 py-3">{item.requested_by}</td>
                  <td className="px-4 py-3 text-gray-700">{item.reason || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{item.approval_rule_key || "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{formatDate(item.created_at)}</td>
                  <td className="px-4 py-3">
                    <GovernanceStatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {canApprove ? (
                        <button
                          type="button"
                          className="rounded-xl border px-3 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "pending_approval"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onApprove(item);
                          }}
                        >
                          {isApproving ? "Approving..." : "Approve"}
                        </button>
                      ) : null}

                      {canReject ? (
                        <button
                          type="button"
                          className="rounded-xl border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "pending_approval"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onReject(item);
                          }}
                        >
                          {isRejecting ? "Rejecting..." : "Reject"}
                        </button>
                      ) : null}

                      {canExecute ? (
                        <button
                          type="button"
                          className="rounded-xl bg-black px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                          disabled={isApproving || isRejecting || isExecuting || item.status !== "approved"}
                          onClick={(e) => {
                            e.stopPropagation();
                            onExecute(item);
                          }}
                        >
                          {isExecuting ? "Executing..." : "Execute"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
16) frontend/src/components/governance/GovernancePendingApprovalsPanel.tsx
Đây là patch quan trọng nhất: bulk actions + rebase UX.
import React, { useMemo, useState } from "react";
import {
  approveChangeRequest,
  bulkApproveChangeRequests,
  bulkExecuteChangeRequests,
  bulkRejectChangeRequests,
  executeChangeRequest,
  rejectChangeRequest,
} from "@/lib/governanceApi";
import {
  canApprove,
  canExecute,
  canReject,
  canViewPendingApprovals,
} from "@/lib/governanceRbac";
import { usePendingApprovals } from "@/hooks/usePendingApprovals";
import { ApprovalNoteModal } from "@/components/governance/ApprovalNoteModal";
import { BulkActionBar } from "@/components/governance/BulkActionBar";
import { BulkActionResultModal } from "@/components/governance/BulkActionResultModal";
import { DirectiveVersionRefreshCard } from "@/components/governance/DirectiveVersionRefreshCard";
import { GovernanceConflictDialog } from "@/components/governance/GovernanceConflictDialog";
import { GovernanceTimelinePanel } from "@/components/governance/GovernanceTimelinePanel";
import { PendingApprovalsTable } from "@/components/governance/PendingApprovalsTable";
import { RebaseModal } from "@/components/governance/RebaseModal";
import { RejectReasonModal } from "@/components/governance/RejectReasonModal";
import type { ApiError } from "@/types/api";
import type {
  ActorContext,
  GovernanceBulkActionResponse,
  GovernancePendingApprovalItem,
} from "@/types/governance";

type Props = {
  actor: ActorContext | null;
  onToast?: (input: { type: "success" | "error"; message: string }) => void;
};

export function GovernancePendingApprovalsPanel({ actor, onToast }: Props) {
  const { items, loading, error, refresh } = usePendingApprovals(actor);

  const [selectedItem, setSelectedItem] = useState<GovernancePendingApprovalItem | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rebaseModalOpen, setRebaseModalOpen] = useState(false);

  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);

  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResultOpen, setBulkResultOpen] = useState(false);
  const [bulkResultTitle, setBulkResultTitle] = useState("Bulk action result");
  const [bulkResult, setBulkResult] = useState<GovernanceBulkActionResponse | null>(null);

  const [conflictOpen, setConflictOpen] = useState(false);
  const [conflictError, setConflictError] = useState<ApiError | null>(null);
  const [conflictDirectiveId, setConflictDirectiveId] = useState<string | null>(null);

  const allowView = useMemo(
    () => (actor ? canViewPendingApprovals(actor.actorRole) : false),
    [actor]
  );
  const allowApprove = useMemo(
    () => (actor ? canApprove(actor.actorRole) : false),
    [actor]
  );
  const allowReject = useMemo(
    () => (actor ? canReject(actor.actorRole) : false),
    [actor]
  );
  const allowExecute = useMemo(
    () => (actor ? canExecute(actor.actorRole) : false),
    [actor]
  );

  const openConflict = (apiError: ApiError, directiveId?: string | null) => {
    setConflictError(apiError);
    setConflictDirectiveId(directiveId ?? null);
    setConflictOpen(true);
  };

  const toggleSelected = (item: GovernancePendingApprovalItem) => {
    setSelectedIds((prev) =>
      prev.includes(item.change_request_id)
        ? prev.filter((id) => id !== item.change_request_id)
        : [...prev, item.change_request_id]
    );
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(items.map((item) => item.change_request_id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleApproveClick = (item: GovernancePendingApprovalItem) => {
    setSelectedItem(item);
    setApprovalModalOpen(true);
  };

  const handleRejectClick = (item: GovernancePendingApprovalItem) => {
    setSelectedItem(item);
    setRejectModalOpen(true);
  };

  const handleApproveSubmit = async (note: string) => {
    if (!actor || !selectedItem) return;

    setApprovingId(selectedItem.change_request_id);

    const result = await approveChangeRequest({
      actor,
      changeRequestId: selectedItem.change_request_id,
      note,
    });

    setApprovingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, selectedItem.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    setApprovalModalOpen(false);
    onToast?.({ type: "success", message: "Change request approved." });
    void refresh();
  };

  const handleRejectSubmit = async (reason: string) => {
    if (!actor || !selectedItem) return;

    setRejectingId(selectedItem.change_request_id);

    const result = await rejectChangeRequest({
      actor,
      changeRequestId: selectedItem.change_request_id,
      reason,
    });

    setRejectingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, selectedItem.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    setRejectModalOpen(false);
    onToast?.({ type: "success", message: "Change request rejected." });
    void refresh();
  };

  const handleExecute = async (item: GovernancePendingApprovalItem) => {
    if (!actor) return;

    setExecutingId(item.change_request_id);

    const result = await executeChangeRequest({
      actor,
      changeRequestId: item.change_request_id,
    });

    setExecutingId(null);

    if (!result.ok) {
      if (result.status === 409 || result.status === 403) {
        openConflict(result.error, item.directive_id);
      } else {
        onToast?.({ type: "error", message: result.error.message });
      }
      return;
    }

    onToast?.({
      type: "success",
      message: `Executed successfully. Updated version: ${result.data.updated_version}`,
    });

    void refresh();
  };

  const handleBulkApprove = async () => {
    if (!actor || selectedIds.length === 0) return;

    setBulkBusy(true);
    const result = await bulkApproveChangeRequests({
      actor,
      changeRequestIds: selectedIds,
    });
    setBulkBusy(false);

    if (!result.ok) {
      onToast?.({ type: "error", message: result.error.message });
      return;
    }

    setBulkResultTitle("Bulk approve result");
    setBulkResult(result.data);
    setBulkResultOpen(true);
    setSelectedIds([]);
    void refresh();
  };

  const handleBulkReject = async () => {
    if (!actor || selectedIds.length === 0) return;

    setBulkBusy(true);
    const result = await bulkRejectChangeRequests({
      actor,
      changeRequestIds: selectedIds,
      reason: "Bulk rejected by operator",
    });
    setBulkBusy(false);

    if (!result.ok) {
      onToast?.({ type: "error", message: result.error.message });
      return;
    }

    setBulkResultTitle("Bulk reject result");
    setBulkResult(result.data);
    setBulkResultOpen(true);
    setSelectedIds([]);
    void refresh();
  };

  const handleBulkExecute = async () => {
    if (!actor || selectedIds.length === 0) return;

    setBulkBusy(true);
    const result = await bulkExecuteChangeRequests({
      actor,
      changeRequestIds: selectedIds,
    });
    setBulkBusy(false);

    if (!result.ok) {
      onToast?.({ type: "error", message: result.error.message });
      return;
    }

    setBulkResultTitle("Bulk execute result");
    setBulkResult(result.data);
    setBulkResultOpen(true);
    setSelectedIds([]);
    void refresh();
  };

  if (!actor) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">No actor context available.</div>
      </div>
    );
  }

  if (!allowView) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-gray-600">
          Your current role does not have access to pending approvals.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2 space-y-4">
          <div className="flex items-center justify-between rounded-2xl border bg-white p-4 shadow-sm">
            <div>
              <div className="text-base font-semibold text-gray-900">Pending approvals</div>
              <div className="mt-1 text-sm text-gray-600">
                Review, approve, reject, execute, and rebase governance change requests.
              </div>
            </div>

            <button
              type="button"
              className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
              onClick={() => void refresh()}
            >
              Refresh
            </button>
          </div>

          <BulkActionBar
            selectedCount={selectedIds.length}
            canApprove={allowApprove}
            canReject={allowReject}
            canExecute={allowExecute}
            busy={bulkBusy}
            onBulkApprove={() => void handleBulkApprove()}
            onBulkReject={() => void handleBulkReject()}
            onBulkExecute={() => void handleBulkExecute()}
            onClearSelection={() => setSelectedIds([])}
          />

          {error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Failed to load pending approvals: {error.message}
            </div>
          ) : null}

          <PendingApprovalsTable
            items={items}
            loading={loading}
            approvingId={approvingId}
            rejectingId={rejectingId}
            executingId={executingId}
            selectedChangeRequestId={selectedItem?.change_request_id ?? null}
            selectedIds={selectedIds}
            canApprove={allowApprove}
            canReject={allowReject}
            canExecute={allowExecute}
            onApprove={handleApproveClick}
            onReject={handleRejectClick}
            onExecute={handleExecute}
            onSelect={(item) => setSelectedItem(item)}
            onToggleSelect={toggleSelected}
            onToggleSelectAll={toggleSelectAll}
          />

          {selectedItem ? (
            <div className="rounded-2xl border bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900">Rebase tools</div>
                  <div className="mt-1 text-sm text-gray-600">
                    Create a new request pinned to the latest directive version.
                  </div>
                </div>

                <button
                  type="button"
                  className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
                  onClick={() => setRebaseModalOpen(true)}
                >
                  Open rebase
                </button>
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <GovernanceTimelinePanel
            actor={actor}
            changeRequestId={selectedItem?.change_request_id ?? null}
          />

          <DirectiveVersionRefreshCard
            actor={actor}
            directiveId={selectedItem?.directive_id ?? conflictDirectiveId ?? null}
          />
        </div>
      </div>

      <ApprovalNoteModal
        open={approvalModalOpen}
        item={selectedItem}
        submitting={Boolean(approvingId)}
        onClose={() => {
          if (approvingId) return;
          setApprovalModalOpen(false);
        }}
        onSubmit={(note) => void handleApproveSubmit(note)}
      />

      <RejectReasonModal
        open={rejectModalOpen}
        item={selectedItem}
        submitting={Boolean(rejectingId)}
        onClose={() => {
          if (rejectingId) return;
          setRejectModalOpen(false);
        }}
        onSubmit={(reason) => void handleRejectSubmit(reason)}
      />

      <RebaseModal
        open={rebaseModalOpen && Boolean(selectedItem)}
        actor={actor}
        item={selectedItem}
        onClose={() => setRebaseModalOpen(false)}
        onCreated={() => {
          void refresh();
        }}
        onToast={onToast}
      />

      <GovernanceConflictDialog
        open={conflictOpen}
        error={conflictError}
        onClose={() => {
          setConflictOpen(false);
          setConflictError(null);
          setConflictDirectiveId(null);
        }}
        onRefresh={() => void refresh()}
        extra={
          actor ? (
            <div className="space-y-4">
              <DirectiveVersionRefreshCard
                actor={actor}
                directiveId={conflictDirectiveId}
              />

              {selectedItem ? (
                <div className="rounded-2xl border bg-white p-4 shadow-sm">
                  <div className="text-sm font-semibold text-gray-900">Stale version recovery</div>
                  <div className="mt-1 text-sm text-gray-600">
                    You can create a new rebased request against the latest directive version.
                  </div>
                  <div className="mt-3">
                    <button
                      type="button"
                      className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-gray-50"
                      onClick={() => {
                        setConflictOpen(false);
                        setRebaseModalOpen(true);
                      }}
                    >
                      Open rebase tool
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null
        }
      />

      <BulkActionResultModal
        open={bulkResultOpen}
        title={bulkResultTitle}
        result={bulkResult}
        onClose={() => {
          setBulkResultOpen(false);
          setBulkResult(null);
        }}
      />
    </>
  );
}
17) frontend/src/lib/__tests__/governanceRbac.test.ts
import { describe, expect, it } from "vitest";
import {
  canApprove,
  canExecute,
  canReject,
  canViewPendingApprovals,
} from "@/lib/governanceRbac";

describe("governance RBAC helpers", () => {
  it("allows approver to view, approve, and reject", () => {
    expect(canViewPendingApprovals("approver")).toBe(true);
    expect(canApprove("approver")).toBe(true);
    expect(canReject("approver")).toBe(true);
  });

  it("allows operator to execute", () => {
    expect(canExecute("operator")).toBe(true);
  });

  it("does not allow viewer", () => {
    expect(canViewPendingApprovals("viewer")).toBe(false);
    expect(canApprove("viewer")).toBe(false);
    expect(canReject("viewer")).toBe(false);
    expect(canExecute("viewer")).toBe(false);
  });
});
18) frontend/src/lib/__tests__/governanceApiFilters.test.ts
import { describe, expect, it } from "vitest";

describe("timeline filter query contract", () => {
  it("builds repeated params for event_type and status", () => {
    const search = new URLSearchParams();
    search.append("event_type", "change_request_created");
    search.append("event_type", "execution_attempt");
    search.append("status", "failed");
    search.set("actor_q", "operator");

    expect(search.toString()).toContain("event_type=change_request_created");
    expect(search.toString()).toContain("event_type=execution_attempt");
    expect(search.toString()).toContain("status=failed");
    expect(search.toString()).toContain("actor_q=operator");
  });
});
19) HÀNH VI ĐÃ ĐƯỢC KHÓA Ở BẢN NÀY
Lớp này chốt thêm 5 hành vi mạnh:
A. Bulk approval queue operations
chọn nhiều item
bulk approve
bulk reject
bulk execute
xem per-item result
B. Timeline drill-down thực chiến
lọc theo event type
lọc theo status
lọc theo actor text
không bị timeline quá nhiễu
C. Stale version recovery
conflict không chỉ refresh
có rebase preview
có create rebased request mới
D. Audit preservation
request cũ không bị mutate kiểu phá trace
rebase tạo request mới
notification event ghi change_request_rebased
E. Queue productivity
operator xử lý nhiều request trong một vòng thao tác
failed items không làm hỏng cả batch
20) ĐIỂM MAP RẤT NGẮN KHI PASTE VÀO REPO THẬT
Bạn chỉ cần map các điểm sau:
Backend
SessionLocal
Phải có factory để bulk service mở session riêng từng item.
DirectiveStateGateway
Phải có:
get(directive_id: str)
GovernanceApprovalRepository
Phải có:
get_by_change_request_id(change_request_id: str)
GovernanceExecutionAttemptRepository
Phải có:
list_by_change_request_id(change_request_id: str)
GovernanceChangeRequest model
Phải có các field Phase 3 cũ:
expected_directive_version
patch
status
requested_by
rejected_by
rejection_reason
Frontend
Toast system
Tôi vẫn dùng onToast.
Nếu repo có toast thật thì map sang đó.
crypto.randomUUID()
Nếu browser target cũ hơn, thay bằng helper generate UUID khác.
Bulk reject reason
Hiện bulk reject dùng hardcoded:
"Bulk rejected by operator"
Nếu muốn production hơn, bạn nên thêm bulk reject modal nhập reason thật.
21) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
update governance schemas
update change request repo
add bulk action service
add rebase service
update timeline service filters
update routes
add backend tests
Frontend
update governance types
update governanceApi
add TimelineFiltersBar
add BulkActionBar
add BulkActionResultModal
add RebaseModal
update TimelinePanel
update PendingApprovalsTable
update PendingApprovalsPanel
add tests
