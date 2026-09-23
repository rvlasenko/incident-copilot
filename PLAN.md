# incident-copilot — план и чеклист

Controlled agentic workflow для on-call инженеров: агент ищет по runbooks/postmortems, вызывает read-only tools (метрики, деплои, логи), verifier сверяет evidence, рискованные действия (rollback) — только через approval человека.

Темп: 3–4 ч/день, ~20–25 ч/неделю. Сложность: low / medium / high.

Подход: итерациями — контракт → минимальная версия → тест → усложнять, когда появится причина. Проверки только под реальную модель угроз.

## Ядро: 4 результата, которые проект должен показать

1. **Orchestration layer** на LangGraph: planner → retrieval → executor → verifier → answer, typed state, маршруты, budgets, явные termination outcomes
2. **Typed tool integration layer**: Pydantic-контракты, RBAC по владению сервисами, валидация результатов, минимизация полей, audit log
3. **Evidence verification**: evidence ledger, проверка достаточности, citation validation, один ограниченный retry retrieval, handoff вместо неподтверждённого ответа
4. **Offline trajectory evaluation + observability**: frozen cases, записанные tool fixtures, replay, метрики по routing/tools/evidence/citations/termination, OpenTelemetry

## Домен (синтетика в `data/`)

- Сервисы: `checkout`, `payments`, `inventory`, `auth` + владельцы-команды (для RBAC)
- Документы: ~10 runbooks, ~5 postmortems (Markdown)
- Фикстуры (`data/fixtures/`, «живое состояние» для tools): `services.json`, `dependencies.json` (внешние зависимости), `deploys.json`, `metrics.json`, `logs.jsonl`
- Документы (`data/docs/`, для retrieval): runbooks, postmortems
- Все timestamps в UTC, timezone-aware
- Маршрут Planner (`Route` enum): `retrieval_only`, `investigation`, `clarification`, `handoff`; workflow — по типу запроса (`runbook_question`, `incident_investigation`), не по причине
- Причина инцидента (`deploy_regression`, `dependency_outage`, `config_error`, `unknown`) — гипотеза, которую подтверждает evidence, а не выбор Planner
- Read-only tools: `get_service_health`, `get_recent_deploys`, `search_logs`, `get_dependency_status`
- Approval-only: `propose_rollback` — формирует предложение, ничего не выполняет
- Verifier verdicts: `PASS`, `INSUFFICIENT_EVIDENCE`, `CONFLICT`, `REQUIRES_APPROVAL`
- `TerminationOutcome`: `COMPLETED`, `RETRIEVAL_ONLY`, `CLARIFICATION_NEEDED`, `REFUSED`, `HANDED_OFF`, `WAITING_FOR_APPROVAL`, `BUDGET_EXHAUSTED` — каждый run заканчивается ровно одним с reason code
- Budgets: шаги, время, tool calls, токены — проверяются на каждом переходе
- У каждого workflow tools делятся на обязательные и опциональные; упавший опциональный tool не блокирует `PASS`, но попадает в `VerifierDecision.unverified_checks`, и Answer обязан это упомянуть
- Два разных retry: transient-ошибка tool (таймаут) → retry policy оркестратора до verifier; нехватка evidence → verifier отправляет на повторный retrieval

## Неделя 0 — разминка (3–4 дня)

- [x] 0.1 Репо: `uv`, Python 3.13, `ruff`, `mypy --strict`, `pytest`, структура `src/incident_copilot/` — low
- [x] 0.2 Pydantic v2 модели домена (`Service`, `Dependency`, `Deploy`, `MetricPoint`, `LogEntry`) + загрузка фикстур через `pathlib` + проверка ссылок между файлами — low-medium
  - Отложенные проверки фикстур (добавлять, когда появится причина):
    - циклы в `depends_on` → вместе с tool, который обходит граф зависимостей
    - дубли id деплоев / точек метрик → когда tools начнут агрегировать или считать метрики
    - дубли в `depends_on`, совпадение имени сервиса и внешней зависимости → если это реально случится при правке данных
- [x] 0.3 ~~asyncio~~ → перенесено в неделю 2 (executor с таймаутами)
- [x] 0.4 ~~pytest~~ → по ходу, на тестах своего кода

## Неделя 1 — скелет orchestration (результат 1)

- [x] 1.1 FastAPI — low
  - `uv add "fastapi[standard]"`, `httpx2` для TestClient
  - контракт: `AssistRequest(query: QueryText)`, `AssistResponse(run_id, answer)`; `QueryText` — strip, 1..`MAX_QUERY_LENGTH` (2000), лимит против огромных логов в LLM
  - `create_app()` в `src/incident_copilot/api/app.py`, `GET /health`, `POST /assist` → заглушка
  - тесты: границы длины (ровно лимит → 200, лимит + 1 → 422), пробелы → 422, проверка `loc` ошибки
  - `Makefile`: `make check` перед каждым коммитом
- [ ] 1.2 Контракты: `AgentState`, `Plan`, `RouteDecision`, `ToolCall`, `ToolResult`, `EvidenceItem`, `VerifierDecision`, `TerminationOutcome`, `Budget` — medium
- [ ] 1.3 LangGraph: stub-ноды + conditional routing по `Route`, терминальные состояния — medium
- [ ] 1.4 `LLMProvider` + OpenAI Planner со structured output + backend-валидация плана — medium
- [ ] 🔍 Debug: смотреть state после каждой ноды через `graph.stream(..., stream_mode="updates")`; сломать роутер и найти, куда ушёл run
- [ ] 1.5 Budget guard на каждом переходе + тесты на завершение (нет бесконечных циклов) — medium

## Неделя 2 — typed tool integration layer (результат 2)

- [ ] 2.1 `ToolSpec`: input/output модели, JSON Schema, `read_only`, timeout, retry policy, required scope — medium
- [ ] 2.2 Adapters над фикстурами: сырые данные → минимизированный typed result с `source`, `fetched_at`, `trace_id` — medium
- [ ] 2.3 Executor: валидация аргументов до вызова, RBAC по команде/сервису, валидация результата и свежести после — medium
- [ ] 2.4 Retry policy для transient-ошибок, `ToolResult` со статусами `ok/error/timeout/denied` — medium
- [ ] 2.5 Audit log каждого вызова (JSONL сейчас, PostgreSQL позже) + permission-negative тесты: запрещённые данные не попадают в промпт — medium

- [ ] 🔍 Debug: fault injection в tools (таймаут, мусор в ответе, denied) — как заканчивается run и что видно в audit log

## Неделя 3 — retrieval и evidence verification (результат 3)

- [ ] 3.1 Синтетические runbooks/postmortems — low
- [ ] 3.2 FAISS retrieval с фильтром по сервису (`IDSelector` или post-filter) — medium
- [ ] 3.3 Evidence ledger: каждый факт из документа или tool получает id и ссылку на источник — medium
- [ ] 3.4 Verifier: детерминированные проверки (покрытие обязательного evidence, сервис, окно времени, свежесть) + LLM-проверка достаточности и противоречий — high
- [ ] 3.5 Один ограниченный query rewrite + retry retrieval, затем fallback / clarification / handoff — medium

- [ ] 🔍 Debug: убрать нужный документ, добавить противоречащий — как реагирует verifier, что видно в evidence ledger

## Неделя 4 — ответ, citations, stateful runs

- [ ] 4.1 Answer как structured brief: каждый claim ссылается на evidence ids из ledger — medium
- [ ] 4.2 Citation validation: id существует, фрагмент реально есть в источнике, данные в окне инцидента; неподтверждённые claims → удалить или refuse — medium
- [ ] 4.3 Checkpoints в PostgreSQL, interrupt на approval, resume с перепроверкой свежести evidence — high
- [ ] 4.4 Anthropic за `LLMProvider` — low

- [ ] 🔍 Debug: история checkpoints (`get_state_history`), resume с прошлого шага

## Неделя 5 — trajectory evaluation и observability (результат 4)

- [ ] 5.1 Frozen cases (YAML): вход, ожидаемый route, tools, аргументы, verdict, termination, citations; теги по failure mode — medium
- [ ] 5.2 Запись trajectory каждого run + replay на записанных tool fixtures — medium
- [ ] 5.3 Метрики: routing accuracy, tool selection, argument validity, retrieval sufficiency (до/после retry), citation correctness, unsupported-claim rate, successful termination — medium
- [ ] 5.4 Сравнение версий prompt/model/graph, regression gate в pytest — medium
- [ ] 5.5 OpenTelemetry spans на каждую ноду и tool call, версии в атрибутах — medium

- [ ] 🔍 Debug: найти по трейсу, на каком шаге упал frozen case; сравнить trajectory до и после смены промпта

## 🏁 Контрольная точка: конец недели 5

Работающий агент, eval, трейсинг, README со схемой архитектуры. Проект ценен сам по себе, дальше — по желанию.

## Неделя 6 — отладка агентов (drills)

- [ ] 6.1 Claude вносит баг, не говоря где (промпт, роутер, tool adapter, reducer state, verifier); найти по трейсам и тестам — 4–5 заходов разной сложности
- [ ] 6.2 Шаблон разбора: симптом → где видно в трейсе → корневая причина → почему тесты не поймали → какой тест добавить
- [ ] 6.3 Чеклист «как дебажить агента» в `docs/` на основе разборов

## Необязательно: стек для резюме (любой порядок, каждый блок самостоятельный)

- [ ] OpenSearch hybrid search, LlamaIndex ingestion, S3 (MinIO локально) — medium
- [ ] Redis, Celery-воркеры индексации, Kafka `document.uploaded` — medium-high
- [ ] Prometheus, Grafana, Sentry, GitHub Actions (eval как CI gate), docker-compose всего стека — medium
- [ ] kind, Helm chart, ArgoCD, feature flag для investigation path — high
- [ ] Terraform (VPC, EKS, S3, Lambda), деплой → `terraform destroy` — high
- [ ] Next.js + TypeScript: citations, статус выполнения, недостающее evidence, approval — medium