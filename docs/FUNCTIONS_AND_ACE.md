# Functions & ACE Documentation

Auto-generated inventory of current backend and frontend functions.

## Snapshot

- Python functions/methods: **168**
- Template JavaScript functions: **462**
- URL endpoints mapped in `myApp/urls.py`: **97**

## ACE (Architecture, Capabilities, Entry Points)

- **Architecture:** Django monolith (`myProject`) with server-rendered templates and JSON API endpoints in `myApp/views.py`.
- **Capabilities:** authentication, onboarding, profiles, agents, prompts, chat, industries, events, tools, banners, admin operations, and impersonation.
- **Entry points:** routes in `myApp/urls.py` and client-side template JavaScript.

### Endpoint Groups

#### Authentication (6)
- `api/auth/login`
- `api/auth/logout`
- `api/auth/me`
- `api/auth/register`
- `api/auth/resend-verification`
- `api/auth/verify-email`

#### Admin APIs (27)
- `api/admin/agents`
- `api/admin/agents/<int:agent_id>`
- `api/admin/agents/generate`
- `api/admin/banners`
- `api/admin/banners/<int:banner_id>`
- `api/admin/events`
- `api/admin/events/<int:event_id>`
- `api/admin/industries`
- `api/admin/industries/<int:industry_id>`
- `api/admin/ops/audit`
- `api/admin/ops/errors`
- `api/admin/ops/summary`
- `api/admin/ops/token-usage`
- `api/admin/prompts`
- `api/admin/prompts/<int:prompt_id>`
- `api/admin/prompts/categories`
- `api/admin/prompts/import`
- `api/admin/pulse`
- `api/admin/stop-impersonation`
- `api/admin/tools`
- `api/admin/tools/<int:tool_id>`
- `api/admin/users`
- `api/admin/users/<int:user_id>`
- `api/admin/users/<int:user_id>/impersonate`
- `api/admin/users/<int:user_id>/suspend`
- `api/admin/users/<int:user_id>/unsuspend`
- `api/admin/users/export`

#### Chat APIs (6)
- `api/chat/messages/<int:message_id>/feedback`
- `api/chat/sessions`
- `api/chat/sessions/<int:session_id>/messages`
- `api/chat/sessions/<int:session_id>/send`
- `api/chat/sessions/create`
- `api/chat/upload-file`

#### Core APIs (12)
- `api/agents`
- `api/banners`
- `api/dashboard`
- `api/events`
- `api/industries`
- `api/onboarding/complete`
- `api/onboarding/state`
- `api/profile`
- `api/prompts`
- `api/prompts/<int:prompt_id>/save`
- `api/prompts/submit`
- `api/tools`

#### Admin UI Routes (27)
- `admin-dashboard/`
- `admin-dashboard/content/`
- `admin-dashboard/content/agents/`
- `admin-dashboard/content/agents/<int:agent_id>/`
- `admin-dashboard/content/agents/new/`
- `admin-dashboard/content/banners/`
- `admin-dashboard/content/banners/<int:banner_id>/`
- `admin-dashboard/content/banners/new/`
- `admin-dashboard/content/events/`
- `admin-dashboard/content/events/<int:event_id>/`
- `admin-dashboard/content/events/new/`
- `admin-dashboard/content/industries/`
- `admin-dashboard/content/industries/<int:industry_id>/`
- `admin-dashboard/content/industries/new/`
- `admin-dashboard/content/prompts/`
- `admin-dashboard/content/prompts/<int:prompt_id>/`
- `admin-dashboard/content/prompts/new/`
- `admin-dashboard/content/tools/`
- `admin-dashboard/content/tools/<int:tool_id>/`
- `admin-dashboard/content/tools/new/`
- `admin-dashboard/operations/`
- `admin-dashboard/operations/audit/`
- `admin-dashboard/operations/errors/`
- `admin-dashboard/operations/tokens/`
- `admin-dashboard/pulse/`
- `admin-dashboard/users/`
- `admin-dashboard/users/<int:user_id>/`

#### Web UI Routes (19)
- `agent-chat/`
- `agents/`
- `billing/`
- `consulting/`
- `dashboard/`
- `events/`
- `index/`
- `industries/`
- `login/`
- `onboarding/`
- `profile/`
- `prompt-import/`
- `prompts/`
- `register/`
- `settings/`
- `shared.css`
- `tools/`
- `verify-email-required/`
- `verify-email/`

## Python Function Inventory

### `myApp/admin_audit.py` (2)
- `record_admin_action(admin, action_type, target_type=None, target_id=None, metadata=None)`
- `log_error(error_type, message, user=None, metadata=None)`

### `myApp/auth_utils.py` (11)
- `_do_restore_impersonation(request)`
- `check_impersonation_timeout(request)`
- `get_request_json(request)`
- `login_user(request, user)`
- `logout_user(request)`
- `get_current_user(request)`
- `_is_admin_user(custom_user)`
- `admin_required(view_func)`
- `wrapper(request, *args, **kwargs)`
- `login_required_api(view_func)`
- `wrapper(request, *args, **kwargs)`

### `myApp/email_service.py` (16)
- `send_welcome_verification_email(user, *, request=None)`
- `send_day_3_email(user)`
- `send_day_14_email(user, *, agents_used, prompts_run)`
- `_send(*, to, subject, html, text, kind, user=None)`
- `_log_email_error(*, user, message, metadata)`
- `_build_verify_url(user, *, request=None)`
- `_greeting(user)`
- `_shell(inner_html)`
- `_button(label, url)`
- `_signoff()`
- `_render_welcome_html(user, verify_url)`
- `_render_welcome_text(user, verify_url)`
- `_render_day3_html(user)`
- `_render_day3_text(user)`
- `_render_day14_html(user, *, agents_used, prompts_run)`
- `_render_day14_text(user, *, agents_used, prompts_run)`

### `myApp/management/commands/backfill_agent_avatars.py` (2)
- `add_arguments(self, parser)`
- `handle(self, *args, dry_run=False, force=False, limit=0, **opts)`

### `myApp/management/commands/send_lifecycle_emails.py` (2)
- `add_arguments(self, parser)`
- `handle(self, *args, dry_run=False, **opts)`

### `myApp/migrations/0006_email_verification_and_onboarding.py` (2)
- `backfill_existing_users(apps, schema_editor)`
- `noop_reverse(apps, schema_editor)`

### `myApp/models.py` (11)
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`
- `__str__(self)`

### `myApp/openai_service.py` (8)
- `_resolve_industry_backdrop(industry)`
- `_resolve_gender_presentation(name)`
- `_est_tokens(text)`
- `trim_history_to_budget(history, system_content, budget=HISTORY_TOKEN_BUDGET)`
- `estimate_messages_tokens(system_content, messages)`
- `get_openai_reply(messages)`
- `_build_avatar_prompt(name, industry, description, tag)`
- `generate_agent_avatar_bytes(name, industry, description="", tag="")`

### `myApp/personalization.py` (3)
- `build_agent_identity_prompt(agent, agent_prompts)`
- `build_user_personalization_prompt(user)`
- `build_full_system_prompt(agent, agent_prompts, user, base_context=DEFAULT_BASE_CONTEXT)`

### `myApp/seed_data.py` (5)
- `seed_agents_and_prompts()`
- `seed_industries()`
- `_parse_event_datetime(date_str, time_str)`
- `seed_events()`
- `seed_tools()`

### `myApp/views.py` (106)
- `ensure_seed_prompts()`
- `ensure_seed_agents()`
- `ensure_seed_industries()`
- `ensure_seed_events()`
- `ensure_seed_tools()`
- `_parse_event_date(raw)`
- `home(request)`
- `dashboard(request)`
- `agents(request)`
- `agent_chat(request)`
- `prompts(request)`
- `industries(request)`
- `events(request)`
- `tools(request)`
- `consulting(request)`
- `billing(request)`
- `profile_page(request)`
- `settings_page(request)`
- `login(request)`
- `register(request)`
- `verify_email_required(request)`
- `verify_email_page(request)`
- `onboarding_page(request)`
- `shared_css(request)`
- `legacy_html_redirect(request, page)`
- `admin_dashboard(request, **kwargs)`
- `prompt_import_dashboard(request)`
- `api_register(request)`
- `api_login(request)`
- `api_logout(request)`
- `api_me(request)`
- `api_verify_email(request)`
- `api_resend_verification(request)`
- `api_onboarding_state(request)`
- `api_onboarding_complete(request)`
- `_validate_and_build_profile_updates(payload)`
- `api_profile(request)`
- `_is_valid_hex_color(value)`
- `_serialize_agent(agent, include_prompts=False)`
- `_to_non_negative_int(value, default=0)`
- `api_agents(request)`
- `api_admin_agents(request)`
- `api_admin_agent_detail(request, agent_id)`
- `api_admin_agent_regenerate_avatar(request, agent_id)`
- `api_admin_agent_generate(request)`
- `api_admin_agent_prompts(request, agent_id)`
- `api_admin_agent_prompt_detail(request, prompt_id)`
- `_normalize_header(header)`
- `_normalize_industry(raw_industry)`
- `_extract_rows_from_upload(uploaded_file)`
- `_extract_text_from_uploaded_file(file_name, file_bytes)`
- `_upload_to_cloudinary(file_name, file_bytes)`
- `_upload_avatar_to_cloudinary(image_bytes, slug)`
- `_generate_and_store_agent_avatar(agent)`
- `api_admin_import_prompts(request)`
- `_serialize_prompt(prompt)`
- `api_admin_prompts(request)`
- `api_admin_prompt_detail(request, prompt_id)`
- `api_admin_prompts_categories(request)`
- `api_dashboard(request)`
- `api_pulse(request)`
- `_parse_active_after(value)`
- `_parse_since(value, now)`
- `_relative_time(dt, now)`
- `_build_user_queryset(params)`
- `_serialize_user_item(user, superuser_emails, superuser_usernames)`
- `iso(dt)`
- `_serialize_user_full(target, superuser_emails, superuser_usernames)`
- `iso(dt)`
- `api_admin_users(request)`
- `api_admin_users_export(request)`
- `api_admin_user_detail(request, user_id)`
- `iso(dt)`
- `api_admin_user_suspend(request, user_id)`
- `api_admin_user_unsuspend(request, user_id)`
- `api_admin_user_impersonate(request, user_id)`
- `api_admin_stop_impersonation(request)`
- `api_admin_ops_summary(request)`
- `api_admin_ops_token_usage(request)`
- `api_admin_ops_audit(request)`
- `api_admin_ops_errors(request)`
- `api_prompts(request)`
- `api_submit_prompt(request)`
- `api_toggle_save_prompt(request, prompt_id)`
- `api_chat_sessions(request)`
- `api_create_chat_session(request)`
- `api_chat_messages(request, session_id)`
- `api_chat_upload_file(request)`
- `api_send_chat_message(request, session_id)`
- `api_message_feedback(request, message_id)`
- `_serialize_industry(industry)`
- `api_industries(request)`
- `api_admin_industries(request)`
- `api_admin_industry_detail(request, industry_id)`
- `_serialize_event(event)`
- `api_events(request)`
- `api_admin_events(request)`
- `api_admin_event_detail(request, event_id)`
- `_serialize_tool(tool)`
- `api_tools(request)`
- `api_admin_tools(request)`
- `api_admin_tool_detail(request, tool_id)`
- `_serialize_banner(banner)`
- `api_banners(request)`
- `api_admin_banners(request)`
- `api_admin_banner_detail(request, banner_id)`

## Frontend Template JS Function Inventory

### `myApp/templates/admin-dashboard.html` (239)
- `fmtNum(n)` - function
- `fmtCost(v)` - function
- `renderPulseTiles(d)` - function
- `renderPulseSkeleton()` - function
- `updatePulseTimestamp()` - function
- `async loadPulse()` - function
- `startPulseRefresh()` - function
- `stopPulseRefresh()` - function
- `getInitSection(pathname)` - function
- `opsSubpanelTeardown(key)` - function
- `opsShowSubpanel(key)` - function
- `showSection(key, params)` - function
- `navigateTo(path, section, params)` - function
- `fmtK(n)` - function
- `opsSummaryUpdateTimestamp()` - function
- `opsSummaryRender(data)` - function
- `pillHtml(status)` - function
- `tile(icon, colorCls, label, value, sub, clickCode)` - function
- `async opsSummaryRefresh()` - function
- `async opsSummaryMount()` - function
- `opsTokensRangeChange(days)` - function
- `opsTokensRender(data, days)` - function
- `async opsTokensLoadAndRender(days)` - function
- `opsTokensMount()` - function
- `logPagination(data, fnName)` - function
- `opsAuditActionColor(action)` - function
- `opsAuditSkeleton()` - function
- `opsAuditToggleRow(id)` - function
- `opsAuditRender(data)` - function
- `opsAuditPushUrl()` - function
- `async opsAuditLoadAndRender()` - function
- `opsAuditFilter()` - function
- `opsAuditGoPage(page)` - function
- `opsAuditClearFilters()` - function
- `async opsAuditMount()` - function
- `opsErrorsTypeColor(type)` - function
- `opsErrorsSkeleton()` - function
- `opsErrorsToggleRow(id)` - function
- `opsErrorsRender(data)` - function
- `opsErrorsPushUrl()` - function
- `async opsErrorsLoadAndRender()` - function
- `opsErrorsFilter()` - function
- `opsErrorsGoPage(page)` - function
- `opsErrorsClearFilters()` - function
- `async opsErrorsMount()` - function
- `usersFilters()` - function
- `usersBuildQuery(filters, page)` - function
- `usersUpdateUrl(filters, page)` - function
- `escHtml(s)` - function
- `userAvatar(item)` - function
- `fmtDateShort(iso)` - function
- `fmtRelative(iso)` - function
- `usersRenderRow(item)` - function
- `usersTableShell(bodyHtml)` - function
- `usersRenderSkeleton()` - function
- `usersRenderEmpty()` - function
- `usersPaginationRender(data)` - function
- `usersRender(data)` - function
- `async loadUsers(page)` - function
- `usersRefetch()` - function
- `usersClearFilters()` - function
- `usersOpenDetail(id)` - function
- `async exportUsers()` - function
- `usersToast(msg)` - function
- `usersReadUrlParams()` - function
- `usersMount()` - function
- `udInitials(u)` - function
- `udFullName(u)` - function
- `udFieldVal(v, isArea)` - function
- `udUpdateLoadedAt()` - function
- `udToast(msg, type)` - function
- `udShowModal(html)` - function
- `udCloseModal()` - function
- `udRenderSkeleton()` - function
- `udRenderError(msg, retryLabel)` - function
- `udRenderIdentityCard(u, admin)` - function
- `udRenderStats(stats)` - function
- `udViewField(label, value, isArea)` - function
- `udRenderProfileView(u)` - function
- `udSel(id, opts, cur)` - function
- `udRenderProfileEdit(u)` - function
- `udRenderSideCards(stats)` - function
- `bars(items, nameKey, countKey)` - function
- `udRenderSessions(sessions)` - function
- `udRenderFull(data, admin)` - function
- `udEnterEditMode()` - function
- `udExitEditMode()` - function
- `udToggleEdit()` - function
- `udCancelEdit()` - function
- `udClearFieldErrors()` - function
- `async udSaveProfile()` - function
- `udSuspend()` - function
- `async udConfirmSuspend()` - function
- `udUnsuspend()` - function
- `async udConfirmUnsuspend()` - function
- `udImpersonate()` - function
- `async udConfirmImpersonate()` - function
- `async userDetailMount(userId)` - function
- `agentsTitleCase(s)` - function
- `agentsCountPrompts(a)` - function
- `agentsRenderRow(a)` - function
- `agentsTableShell(rows)` - function
- `agentsRenderSkeleton()` - function
- `agentsRenderEmpty()` - function
- `agentsRenderNoMatches()` - function
- `agentsRender()` - function
- `async agentsLoad()` - function
- `agentsMount()` - function
- `agentsOpenCreate()` - function
- `agentsOpenEdit(id)` - function
- `agentsConfirmDelete(id)` - function
- `async agentsPerformDelete(id)` - function
- `loadIndustries()` - function
- `async agentEditMount(params)` - function
- `aeRenderFull(agentData)` - function
- `aeRenderHintsList()` - function
- `aeRenderUseCasesList()` - function
- `aeBindHintsList()` - function
- `aeBindUseCasesList()` - function
- `aeUpdateAddHintBtnState()` - function
- `aeUpdateAddUcBtnState()` - function
- `aeUpdatePreview()` - function
- `aeRefreshIconBtn()` - function
- `aeRefreshAvatarFrame()` - function
- `async aeRegenerateAvatar()` - function
- `openIconPicker(initialIcon, onSelect)` - function
- `buildBody(filter)` - function
- `closeIp()` - function
- `bindCells()` - function
- `aeOpenIconPicker()` - function
- `aeBindAll()` - function
- `aeShowFieldErrors(errors)` - function
- `async aeGenerate()` - function
- `async aeSave()` - function
- `aeDeleteAgent()` - function
- `async aePerformDelete()` - function
- `promptsStatusPill(status)` - function
- `promptsRenderSkeleton()` - function
- `promptsRenderRow(p)` - function
- `promptsPaginationHtml(data)` - function
- `async promptsLoad(page)` - function
- `promptsClearFilters()` - function
- `promptsMount()` - function
- `promptsOpenCreate()` - function
- `promptsOpenEdit(id)` - function
- `promptsConfirmDelete(id, title)` - function
- `async promptsDoDelete(id)` - function
- `async peFetchCategories()` - function
- `peBuildForm(promptData)` - function
- `peShowCombobox(cats, query, dropdown)` - function
- `peSelectCategory(cat)` - function
- `peComboboxOutsideHandler(e)` - function
- `peRenderFieldErrors(errors)` - function
- `peValidate()` - function
- `async peSave()` - function
- `peWireEvents()` - function
- `async promptEditMount(params)` - function
- `industriesMount()` - function
- `async industriesLoad()` - function
- `industryRow(ind)` - function
- `industriesOpenCreate()` - function
- `industriesOpenEdit(id)` - function
- `async industriesConfirmDelete(id)` - function
- `async industryEditMount(params)` - function
- `ieRenderSkeleton()` - function
- `ieRenderFull(ind)` - function
- `iePreviewHtml(name, iconClass)` - function
- `ieRefreshIconBtn()` - function
- `ieUpdatePreview()` - function
- `ieBindAll()` - function
- `async ieSave()` - function
- `async ieDeleteIndustry()` - function
- `fmtEventDate(iso)` - function
- `isoToDatetimeLocal(iso)` - function
- `eventsMount()` - function
- `eventsRefetch()` - function
- `eventsGoPage(page)` - function
- `async eventsLoad()` - function
- `eventsRender(data)` - function
- `evRow(ev)` - function
- `eventsOpenCreate()` - function
- `eventsOpenEdit(id)` - function
- `async eventsConfirmDelete(id)` - function
- `async eventEditMount(params)` - function
- `evRenderSkeleton()` - function
- `evRenderFull(data)` - function
- `evBindAll()` - function
- `async evSave()` - function
- `evSetErr(el, errEl, msg)` - function
- `async evDeleteEvent()` - function
- `toolsMount()` - function
- `toolsRefetch()` - function
- `async toolsLoad()` - function
- `tlPopulateCategories(items)` - function
- `toolsRender()` - function
- `tlRow(tool)` - function
- `toolsOpenCreate()` - function
- `toolsOpenEdit(id)` - function
- `async toolsConfirmDelete(id)` - function
- `async toolEditMount(params)` - function
- `teRenderSkeleton()` - function
- `teRenderFull(data)` - function
- `teRefreshIconBtn()` - function
- `teBindAll()` - function
- `async teSave()` - function
- `teSetErr(el, errEl, msg)` - function
- `async teDeleteTool()` - function
- `bannersMount()` - function
- `bannersRefetch()` - function
- `async bannersLoad()` - function
- `bannersRender()` - function
- `bnTypePill(type)` - function
- `bnFmtWindow(start_at, end_at)` - function
- `bnRow(b)` - function
- `bannersOpenCreate()` - function
- `bannersOpenEdit(id)` - function
- `async bannersConfirmDelete(id)` - function
- `async bannerEditMount(params)` - function
- `bnRenderSkeleton()` - function
- `bnDefaultStart()` - function
- `bnDefaultEnd()` - function
- `bnRenderFull(data)` - function
- `bnUpdatePreview()` - function
- `bnBindAll()` - function
- `async bnSave()` - function
- `bnSetErr(el, errEl, msg)` - function
- `async bnDeleteBanner()` - function
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `r()` - arrow-function
- `r()` - arrow-function
- `skelRow()` - arrow-function
- `set(id, key, def)` - arrow-function
- `skelRow()` - arrow-function
- `escHandler(e)` - arrow-function
- `escHtml(s)` - arrow-function

### `myApp/templates/agent-chat.html` (46)
- `async hydrateAgentConfigFromApi()` - function
- `sanitizeImportedPromptText(text)` - function
- `escapeHtml(s)` - function
- `clearOneTimeChatParams()` - function
- `hidePreloader()` - function
- `titleCase(s)` - function
- `getAgentConfig(agentName, industry)` - function
- `normalizeAgentRecord(agent)` - function
- `async loadAvailableAgents()` - function
- `renderAgentPicker()` - function
- `async openAgentPicker()` - function
- `closeAgentPicker()` - function
- `updateAgentUI(agentName, industry)` - function
- `getTime()` - function
- `renderMessageContent(rawContent)` - function
- `closeLists()` - function
- `closeTable()` - function
- `esc(s)` - function
- `inline(s)` - function
- `splitTableCells(line)` - function
- `addMessage(content, role, messageId=null)` - function
- `showTyping()` - function
- `removeTyping()` - function
- `sendMessage()` - function
- `handleKey(e)` - function
- `autoResize(el)` - function
- `useHint(el)` - function
- `fillInput(text)` - function
- `triggerFileUpload()` - function
- `uploadChatFile(file)` - function
- `copyMsg(btn)` - function
- `copySession(btn)` - function
- `flashBtn(btn, iconClass, title, ms)` - function
- `clearChat()` - function
- `resetChatUI()` - function
- `newChat(options = {})` - function
- `sendFeedback(messageId, feedback)` - function
- `loadSessions()` - function
- `selectSession(sessionId)` - function
- `loadMessages()` - function
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/agents.html` (22)
- `esc(s)` - function
- `initIndustryFilters()` - function
- `iconBg(a)` - function
- `parseColorToken(token)` - function
- `luminance(rgb)` - function
- `isLightColor(value)` - function
- `iconColorFor(bg)` - function
- `formatUses(n)` - function
- `bySort(list)` - function
- `updateCount(count)` - function
- `renderAgents()` - function
- `filterInd(ind,btn)` - function
- `clearAllFilters()` - function
- `searchAgents(v)` - function
- `sortAgents(v)` - function
- `renderFeatured()` - function
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/billing.html` (10)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `openUpgrade()` - function
- `closeUpgrade()` - function
- `exploreAgents()` - function
- `goUpStep(n)` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/consulting.html` (10)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `toggleSection(id)` - function
- `updateStatus(sel)` - function
- `showNewEng()` - function
- `showToast(msg,type='')` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/dashboard.html` (21)
- `escHtml(s)` - function
- `initialsFor(name)` - function
- `formatMinutesToHours(min)` - function
- `formatUsageCount(n)` - function
- `showToast(msg)` - function
- `hidePreloader()` - function
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `renderUserIdentity(name)` - function
- `renderRecentChats(recentChats, recommendedAgents)` - function
- `renderStats(stats)` - function
- `renderRecommendedAgents(agents, userIndustrySlug, userIndustryName)` - function
- `renderTodaysPrompt(prompt)` - function
- `renderStrategyCTA(show)` - function
- `renderDashboard(data)` - function
- `renderFallbackOnError()` - function
- `initDashboard()` - function
- `performSignOut()` - function

### `myApp/templates/events.html` (16)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - function
- `showToast(msg,type='')` - function
- `fmtEvDate(iso)` - function
- `initEvIndustryFilters()` - function
- `filterEvInd(slug)` - function
- `evSkeleton()` - function
- `async fetchAndRenderEvents()` - function
- `evEmptyState(msg)` - function
- `renderFilteredEvents()` - function
- `renderEventCard(ev)` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/industries.html` (9)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `esc(s)` - function
- `getIndustrySlug()` - function
- `applyIndustryFromUrl()` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/login.html` (1)
- `doLogin()` - function

### `myApp/templates/onboarding.html` (15)
- `showStep(n)` - function
- `showToast(msg, isError)` - function
- `escapeHtml(s)` - function
- `async loadIndustries()` - function
- `selectIndustry(slug, name, cardEl)` - function
- `refreshStep2Continue()` - function
- `renderUseCases()` - function
- `toggleUseCase(label, chip)` - function
- `refreshStep3Continue()` - function
- `async submitOnboarding()` - function
- `async doSkip()` - function
- `async loadRecommendations()` - function
- `async loadFinalAgents(slug)` - function
- `async loadFinalPrompts(slug)` - function
- `async bootstrap()` - function

### `myApp/templates/profile.html` (13)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `toggleChip(el)` - function
- `updateFormality(val)` - function
- `updateCounter(id)` - function
- `clearErrors()` - function
- `showFieldError(field, msg)` - function
- `saveProfile()` - function
- `showToast(msg, type)` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/prompt-import.html` (3)
- `hidePreloader()` - function
- `isAcceptedFile(file)` - function
- `setSelectedFile(file)` - function

### `myApp/templates/prompts.html` (25)
- `applyIndustryQueryFromUrl()` - function
- `compactNum(n)` - function
- `deriveDisplayName(data)` - function
- `renderUserIdentity(data)` - function
- `updateLibraryTitle(totalPrompts)` - function
- `displayPromptTitle(title)` - function
- `renderPrompts()` - function
- `filterP(ind,el)` - function
- `filterLibrary(view,el)` - function
- `searchP(v)` - function
- `toggleSave(id,btn)` - function
- `copyPrompt(id,btn)` - function
- `showSubmitModal()` - function
- `hideSubmitModal()` - function
- `submitPrompt()` - function
- `showToast(msg,type='')` - function
- `hidePreloader()` - function
- `usePrompt(id)` - function
- `loadPrompts()` - function
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/register.html` (3)
- `checkPw(v)` - function
- `showError(msg)` - function
- `async doSignup()` - function

### `myApp/templates/settings.html` (6)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/tools.html` (16)
- `async applyActiveBanners()` - function
- `renderSystemBanner(b)` - function
- `dismissSystemBanner(id)` - function
- `applyImpersonationBanner(meData)` - function
- `async stopImpersonation()` - function
- `escHtml(s)` - function
- `showToast(msg,type='')` - function
- `tlCatGradient(cat)` - function
- `initTlCategoryFilters(tools)` - function
- `filterTlCat(cat)` - function
- `tlSkeleton()` - function
- `async fetchAndRenderTools()` - function
- `tlEmptyState(msg)` - function
- `renderFilteredTools()` - function
- `renderToolCard(tl)` - function
- `escHtml(s)` - arrow-function

### `myApp/templates/verify-email-required.html` (3)
- `showToast(msg, isError)` - function
- `async loadMe()` - function
- `async doResend()` - function

### `myApp/templates/verify-email.html` (4)
- `showState(name)` - function
- `showToast(msg, isError)` - function
- `async verifyToken(token)` - function
- `async resendFromExpired()` - function

## Notes

- This file is generated; refresh it whenever function signatures change.
- Includes Python `def`/`async def` declarations and JS template function declarations/arrow functions.
