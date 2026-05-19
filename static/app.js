const defaultAiSettings = {
  provider: "openai",
  model: "",
  base_url: "https://api.openai.com/v1",
  api_key: "",
};

const stateHelpers = window.AutoTaskerStateHelpers || {};
const safeJsonParse =
  stateHelpers.safeJsonParse ||
  function safeJsonParseFallback(raw, fallback) {
    try {
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  };
const createVersionEntry =
  stateHelpers.createVersionEntry ||
  function createVersionEntryFallback(version, assistantMessage, draft) {
    return {
      version,
      assistant_message: assistantMessage,
      task_count: draft.length,
      updated_at: new Date().toISOString(),
    };
  };
const readDraftWorkspace =
  stateHelpers.readDraftWorkspace ||
  function readDraftWorkspaceFallback(storage) {
    return {
      draft: safeJsonParse(storage.getItem("autotasker-draft") || "[]", []),
      draftGoalText: storage.getItem("autotasker-draft-goal") || "",
      draftFeedback: storage.getItem("autotasker-draft-feedback") || "",
      draftConversation: safeJsonParse(storage.getItem("autotasker-draft-conversation") || "[]", []),
      draftVersion: Number(storage.getItem("autotasker-draft-version") || "0"),
      draftVersionHistory: safeJsonParse(storage.getItem("autotasker-draft-versions") || "[]", []),
    };
  };
const persistDraftWorkspaceState =
  stateHelpers.persistDraftWorkspaceState ||
  function persistDraftWorkspaceStateFallback(storage, workspace) {
    storage.setItem("autotasker-draft", JSON.stringify(workspace.draft || []));
    storage.setItem("autotasker-draft-goal", workspace.draftGoalText || "");
    storage.setItem("autotasker-draft-feedback", workspace.draftFeedback || "");
    storage.setItem("autotasker-draft-conversation", JSON.stringify(workspace.draftConversation || []));
    storage.setItem("autotasker-draft-version", String(workspace.draftVersion || 0));
    storage.setItem("autotasker-draft-versions", JSON.stringify(workspace.draftVersionHistory || []));
  };
const clearDraftWorkspaceState =
  stateHelpers.clearDraftWorkspaceState ||
  function clearDraftWorkspaceStateFallback(storage) {
    storage.removeItem("autotasker-draft");
    storage.removeItem("autotasker-draft-goal");
    storage.removeItem("autotasker-draft-feedback");
    storage.removeItem("autotasker-draft-conversation");
    storage.removeItem("autotasker-draft-version");
    storage.removeItem("autotasker-draft-versions");
  };
const buildFallbackUserText =
  stateHelpers.buildFallbackUserText ||
  function buildFallbackUserTextFallback(actions, labels) {
    return (actions || []).map((item) => `[快捷操作] ${labels[item] || item}`).join("，");
  };
const applyDiscussionResult =
  stateHelpers.applyDiscussionResult ||
  function applyDiscussionResultFallback(workspace, result, options) {
    const normalizedMessage = String(options?.message || "").trim();
    const fallbackUserText = buildFallbackUserText(options?.actions || [], options?.quickActionLabels || {});
    const nextConversation = Array.isArray(workspace?.draftConversation) ? [...workspace.draftConversation] : [];

    if (normalizedMessage || fallbackUserText) {
      nextConversation.push({
        role: "user",
        content: normalizedMessage || fallbackUserText,
      });
    }

    nextConversation.push({
      role: "assistant",
      content: result.assistant_message,
    });

    const nextDraft = Array.isArray(result.updated_plan) ? [...result.updated_plan] : [];
    const nextVersion = Number(result.version || Math.max(Number(workspace?.draftVersion || 0) + 1, 1));
    const nextHistory = Array.isArray(workspace?.draftVersionHistory) ? [...workspace.draftVersionHistory] : [];
    nextHistory.push(createVersionEntry(nextVersion, result.assistant_message, nextDraft));

    return {
      draft: nextDraft,
      draftFeedback: result.assistant_message,
      draftConversation: nextConversation,
      draftVersion: nextVersion,
      draftVersionHistory: nextHistory,
    };
  };

const quickActionLabels = {
  split_tasks: "拆小任务",
  compress_schedule: "压缩周期",
  delay_one_day: "推迟一天",
  avoid_quiet_hours: "避开安静时段",
  raise_priority: "提高优先级",
};

const initialDraftWorkspace = readDraftWorkspace(window.localStorage);

const state = {
  token: localStorage.getItem("autotasker-token") || "",
  user: null,
  tasks: [],
  stats: null,
  userProfile: null,
  draft: initialDraftWorkspace.draft,
  draftGoalText: initialDraftWorkspace.draftGoalText,
  draftFeedback: initialDraftWorkspace.draftFeedback,
  draftConversation: initialDraftWorkspace.draftConversation,
  draftVersion: initialDraftWorkspace.draftVersion,
  draftVersionHistory: initialDraftWorkspace.draftVersionHistory,
  recentLogs: [],
  timer: safeJsonParse(localStorage.getItem("autotasker-timer") || "null", null),
  aiSettings: { ...defaultAiSettings, ...safeJsonParse(localStorage.getItem("autotasker-ai-settings") || "{}", {}) },
  providerPresets: {
    openai: "https://api.openai.com/v1",
    azure_openai: "",
    deepseek: "https://api.deepseek.com/v1",
    qwen: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    glm: "https://open.bigmodel.cn/api/paas/v4",
    gemini: "https://generativelanguage.googleapis.com/v1beta",
  },
  reviewOverride: localStorage.getItem("autotasker-review-override") || "",
};

const els = {
  appShell: document.querySelector(".app-shell, .app-layout"),
  loginStatus: document.getElementById("login-status-chip"),
  navItems: Array.from(document.querySelectorAll(".nav-item")),
  views: Array.from(document.querySelectorAll(".view")),
  navFocus: document.getElementById("nav-focus"),
  authPanel: document.getElementById("auth-panel"),
  authForm: document.getElementById("auth-form"),
  authMessage: document.getElementById("auth-message"),
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  profileCard: document.getElementById("profile-card"),
  profileName: document.getElementById("profile-name"),
  profileHint: document.getElementById("profile-hint"),
  preferencesForm: document.getElementById("preferences-form"),
  focusMinutes: document.getElementById("focus-minutes"),
  breakMinutes: document.getElementById("break-minutes"),
  quietHours: document.getElementById("quiet-hours"),
  aiForm: document.getElementById("ai-form"),
  aiProvider: document.getElementById("ai-provider"),
  aiModel: document.getElementById("ai-model"),
  aiBaseUrl: document.getElementById("ai-base-url"),
  aiApiKey: document.getElementById("ai-api-key"),
  goalForm: document.getElementById("goal-form"),
  goalText: document.getElementById("goal-text"),
  goalFeedback: document.getElementById("goal-feedback"),
  discussionVersion: document.getElementById("discussion-version"),
  discussionList: document.getElementById("discussion-list"),
  discussionForm: document.getElementById("discussion-form"),
  discussionInput: document.getElementById("discussion-input"),
  draftList: document.getElementById("draft-list"),
  versionHistory: document.getElementById("version-history"),
  confirmDraft: document.getElementById("confirm-draft"),
  clearDraft: document.getElementById("clear-draft"),
  todoColumn: document.getElementById("todo-column"),
  progressColumn: document.getElementById("progress-column"),
  doneColumn: document.getElementById("done-column"),
  todoCount: document.getElementById("todo-count"),
  progressCount: document.getElementById("progress-count"),
  doneCount: document.getElementById("done-count"),
  pomodoroForm: document.getElementById("pomodoro-form"),
  pomodoroTask: document.getElementById("pomodoro-task"),
  pomodoroMinutes: document.getElementById("pomodoro-minutes"),
  pomodoroPause: document.getElementById("pomodoro-pause"),
  pomodoroDone: document.getElementById("pomodoro-done"),
  pomodoroStop: document.getElementById("pomodoro-stop"),
  timerCardEl: document.getElementById("timer-card-el"),
  timerTaskName: document.getElementById("timer-task-name"),
  timerValue: document.getElementById("timer-value"),
  timerStatus: document.getElementById("timer-status"),
  statsCards: document.getElementById("stats-cards"),
  trendBars: document.getElementById("trend-bars"),
  trendCaption: document.getElementById("trend-caption"),
  reviewText: document.getElementById("review-text"),
  logList: document.getElementById("log-list"),
  generateReview: document.getElementById("generate-review"),
  traitSummary: document.getElementById("trait-summary"),
  traitPeakPeriod: document.getElementById("trait-peak-period"),
  traitFocusWindow: document.getElementById("trait-focus-window"),
  traitTaskStyle: document.getElementById("trait-task-style"),
  traitDiscipline: document.getElementById("trait-discipline"),
  periodBreakdown: document.getElementById("period-breakdown"),
  quickActionButtons: Array.from(document.querySelectorAll("[data-quick-action]")),
};

let countdownTicker = null;
const visualState = {
  revealObserver: null,
  reduceMotion: window.matchMedia("(prefers-reduced-motion: reduce)"),
  finePointer: window.matchMedia("(hover: hover) and (pointer: fine)"),
  scrollTicking: false,
};

const MOTION_CARD_SELECTOR = [".glass", ".task-card", ".draft-card", ".metric", ".log-item", ".trait-card", ".period-card"].join(
  ", "
);

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    ...options,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || "请求失败");
  return data;
}

function flash(message, isError = false) {
  if (!els.authMessage) return;
  els.authMessage.textContent = message;
  els.authMessage.style.color = isError ? "#b5542c" : "#2c7a52";
}

function setGoalFeedback(text, isMuted = false) {
  if (!els.goalFeedback) return;
  els.goalFeedback.textContent = text;
  els.goalFeedback.classList.toggle("empty", isMuted || !text);
}

function persistDraftWorkspace() {
  persistDraftWorkspaceState(localStorage, state);
}

function clearDraftState() {
  state.draft = [];
  state.draftGoalText = "";
  state.draftFeedback = "";
  state.draftConversation = [];
  state.draftVersion = 0;
  state.draftVersionHistory = [];
  clearDraftWorkspaceState(localStorage);
}

function persistTimer() {
  if (state.timer) {
    localStorage.setItem("autotasker-timer", JSON.stringify(state.timer));
  } else {
    localStorage.removeItem("autotasker-timer");
  }
}

function persistAiSettings() {
  localStorage.setItem("autotasker-ai-settings", JSON.stringify(state.aiSettings));
}

function persistReviewOverride() {
  if (state.reviewOverride) {
    localStorage.setItem("autotasker-review-override", state.reviewOverride);
  } else {
    localStorage.removeItem("autotasker-review-override");
  }
}

function formatDateTime(value) {
  if (!value) return "未安排时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} ${date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function formatShortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} ${date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toInputDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function getAiConfig() {
  return {
    provider: els.aiProvider.value,
    model: els.aiModel.value.trim(),
    base_url: els.aiBaseUrl.value.trim(),
    api_key: els.aiApiKey.value.trim(),
  };
}

function hydrateAiForm() {
  els.aiProvider.value = state.aiSettings.provider || "openai";
  els.aiModel.value = state.aiSettings.model || "";
  els.aiBaseUrl.value = state.aiSettings.base_url || state.providerPresets[state.aiSettings.provider] || "";
  els.aiApiKey.value = state.aiSettings.api_key || "";
}

function syncBaseUrlPreset(force = false) {
  const provider = els.aiProvider.value;
  if (provider === "custom_compatible") return;
  const preset = state.providerPresets[provider] || "";
  if (force || !els.aiBaseUrl.value.trim()) {
    els.aiBaseUrl.value = preset;
  }
}

function switchView(viewName) {
  if (!els.navItems.length || !els.views.length) return;
  els.navItems.forEach((button) => button.classList.toggle("active", button.dataset.view === viewName));
  els.views.forEach((view) => view.classList.toggle("active", view.id === `view-${viewName}`));
}

function renderAuth() {
  const loggedIn = Boolean(state.user);
  els.authPanel.classList.toggle("hidden", loggedIn);
  els.profileCard.classList.toggle("hidden", !loggedIn);
  if (els.loginStatus) {
    els.loginStatus.textContent = loggedIn ? state.user.username : "Offline";
    els.loginStatus.style.background = loggedIn ? "#e6ffe6" : "#ffeeee";
    els.loginStatus.style.color = loggedIn ? "#006600" : "var(--accent-red)";
  }
  if (!loggedIn) {
    switchView("settings");
    return;
  }
  els.profileName.textContent = state.user.username;
  els.profileHint.textContent = `当前默认番茄 ${state.user.focus_minutes} 分钟，休息 ${state.user.break_minutes} 分钟`;
  els.focusMinutes.value = state.user.focus_minutes;
  els.breakMinutes.value = state.user.break_minutes;
  els.quietHours.value = state.user.quiet_hours;
  els.pomodoroMinutes.value = state.user.focus_minutes;
  hydrateAiForm();
}

function renderDiscussion() {
  const hasDraft = state.draft.length > 0;
  els.discussionVersion.textContent = `v${state.draftVersion || 0}`;
  els.discussionInput.disabled = !hasDraft;
  els.discussionForm.querySelector("button").disabled = !hasDraft;
  els.quickActionButtons.forEach((button) => {
    button.disabled = !hasDraft;
  });

  if (!state.draftConversation.length) {
    els.discussionList.innerHTML =
      '<p class="empty" style="display:block;font-size: 14px;">生成首版草案后，你可以继续像聊天一样让 AI 重排、拆分、压缩或解释安排。</p>';
    return;
  }

  els.discussionList.innerHTML = state.draftConversation
    .map(
      (item) => `
      <article class="discussion-bubble ${item.role}">
        <small>${item.role === "user" ? "User" : "Assistant"}</small>
        <div>${escapeHtml(item.content).replaceAll("\n", "<br />")}</div>
      </article>
    `
    )
    .join("");
  els.discussionList.scrollTop = els.discussionList.scrollHeight;
}

function renderVersionHistory() {
  if (!state.draftVersionHistory.length) {
    els.versionHistory.innerHTML = '<p class="empty" style="display:block;font-size:14px;">讨论版本历史会显示在这里。</p>';
    return;
  }

  els.versionHistory.innerHTML = [...state.draftVersionHistory]
    .reverse()
    .map(
      (item) => `
      <article class="version-item">
        <small>${formatShortDate(item.updated_at) || "刚刚更新"}</small>
        <strong>v${item.version} · ${item.task_count} 个任务</strong>
        <div>${escapeHtml(item.assistant_message)}</div>
      </article>
    `
    )
    .join("");
}

function renderDraft() {
  const hasDraft = state.draft.length > 0;
  if (!hasDraft) {
    els.draftList.innerHTML = '<p class="empty" style="display:block;font-size: 14px;">生成草案后，可在此微调任务与时间安排。</p>';
    els.confirmDraft.disabled = true;
    els.clearDraft.disabled = true;
    renderVersionHistory();
    return;
  }

  els.confirmDraft.disabled = false;
  els.clearDraft.disabled = false;
  els.draftList.innerHTML = state.draft
    .map(
      (task, index) => `
      <article class="draft-card">
        <div class="draft-grid">
          <label>
            <span>任务标题</span>
            <input class="task-input" data-field="title" data-index="${index}" value="${escapeHtml(task.title)}" />
          </label>
          <label>
            <span>开始时间</span>
            <input class="task-input" data-field="scheduled_for" data-index="${index}" type="datetime-local" value="${toInputDate(task.scheduled_for)}" />
          </label>
          <label>
            <span>截止时间</span>
            <input class="task-input" data-field="due_at" data-index="${index}" type="datetime-local" value="${toInputDate(task.due_at)}" />
          </label>
          <label>
            <span>预计分钟</span>
            <input class="task-input" data-field="estimated_minutes" data-index="${index}" type="number" min="15" max="180" value="${task.estimated_minutes}" />
          </label>
        </div>
        <label>
          <span>任务说明</span>
          <textarea class="task-input" data-field="description" data-index="${index}" rows="2">${escapeHtml(task.description || "")}</textarea>
        </label>
      </article>
    `
    )
    .join("");
  renderVersionHistory();
}

function renderTaskCards(tasks) {
  if (!tasks.length) return '<p class="empty">这里暂时没有任务。</p>';
  return tasks
    .map(
      (task) => `
      <article class="task-card" draggable="true" data-task-id="${task.id}">
        <div class="task-meta">
          <span class="task-badge">${task.status === "todo" ? "待办" : task.status === "in_progress" ? "进行中" : "已完成"}</span>
          <span class="task-badge focus">${task.estimated_minutes} 分钟</span>
          ${task.overdue ? '<span class="task-badge overdue">已逾期</span>' : ""}
          ${task.status === "done" ? '<span class="task-badge done">完成</span>' : ""}
        </div>
        <div>
          <h4>${escapeHtml(task.title)}</h4>
          <p class="empty">${escapeHtml(task.description || "暂无说明")}</p>
        </div>
        <div class="task-meta">
          <span>${formatDateTime(task.scheduled_for)}</span>
          <span>${task.delay_count} 次延期</span>
        </div>
        <div class="task-actions">
          ${task.status !== "in_progress" ? `<button class="btn btn-secondary" data-action="status" data-id="${task.id}" data-status="in_progress">开始</button>` : ""}
          ${task.status !== "done" ? `<button class="btn btn-primary" data-action="status" data-id="${task.id}" data-status="done">完成</button>` : ""}
          ${task.status !== "todo" ? `<button class="btn btn-ghost" data-action="status" data-id="${task.id}" data-status="todo">回待办</button>` : ""}
          ${task.status !== "done" ? `<button class="btn btn-ghost" data-action="postpone" data-id="${task.id}">延期 30 分钟</button>` : ""}
        </div>
      </article>
    `
    )
    .join("");
}

function renderPomodoroTasks() {
  const available = state.tasks.filter((task) => task.status !== "done");
  els.pomodoroTask.innerHTML = available.length
    ? available.map((task) => `<option value="${task.id}">${escapeHtml(task.title)}</option>`).join("")
    : '<option value="">暂无可执行任务</option>';
}

function renderKanban() {
  const groups = { todo: [], in_progress: [], done: [] };
  state.tasks.forEach((task) => groups[task.status].push(task));
  els.todoCount.textContent = groups.todo.length;
  els.progressCount.textContent = groups.in_progress.length;
  els.doneCount.textContent = groups.done.length;
  els.todoColumn.innerHTML = renderTaskCards(groups.todo);
  els.progressColumn.innerHTML = renderTaskCards(groups.in_progress);
  els.doneColumn.innerHTML = renderTaskCards(groups.done);
  renderPomodoroTasks();
  setupDragAndDrop();
}

function renderStats() {
  const stats = state.stats || {
    total_tasks: 0,
    completion_rate: 0,
    overdue_tasks: 0,
    focus_minutes_total: 0,
    trend: [],
    review: "暂无数据",
  };
  els.statsCards.innerHTML = `
    <article class="metric"><span>总任务</span><strong>${stats.total_tasks}</strong></article>
    <article class="metric"><span>完成率</span><strong>${Math.round(stats.completion_rate * 100)}%</strong></article>
    <article class="metric"><span>已逾期</span><strong>${stats.overdue_tasks}</strong></article>
    <article class="metric"><span>专注分钟</span><strong>${stats.focus_minutes_total}</strong></article>
  `;
  const trend = stats.trend || [];
  if (!trend.length) {
    els.trendCaption.textContent = "暂无完成记录";
    els.trendBars.innerHTML = '<p class="empty">完成任务后，这里会出现趋势柱状图。</p>';
  } else {
    const max = Math.max(...trend.map((item) => item.count), 1);
    els.trendCaption.textContent = `最近 ${trend.length} 个日期有完成记录`;
    els.trendBars.innerHTML = trend
      .map(
        (item) => `
        <div class="trend-bar">
          <div class="trend-bar-fill" style="height:${Math.max(14, (item.count / max) * 92)}px"></div>
          <strong>${item.count}</strong>
          <span>${item.day.slice(5)}</span>
        </div>
      `
      )
      .join("");
  }
  els.reviewText.textContent = state.reviewOverride || stats.review;
  els.reviewText.classList.toggle("empty", !els.reviewText.textContent);
}

function renderUserProfile() {
  const profile = state.userProfile || {
    summary: "还没有足够的历史执行数据。",
    peak_period_label: "待观察",
    suggested_focus_window: "待观察",
    preferred_task_style_label: "待观察",
    scheduling_discipline_label: "待观察",
    period_breakdown: [],
  };
  els.traitSummary.textContent = profile.summary;
  els.traitPeakPeriod.textContent = profile.peak_period_label;
  els.traitFocusWindow.textContent = profile.suggested_focus_window;
  els.traitTaskStyle.textContent = profile.preferred_task_style_label;
  els.traitDiscipline.textContent = profile.scheduling_discipline_label;

  if (!profile.period_breakdown?.length || profile.total_completed_sessions === 0) {
    els.periodBreakdown.innerHTML =
      '<p class="empty" style="display:block;font-size:14px;">开始记录番茄钟后，这里会识别你更擅长的时段。</p>';
    return;
  }

  els.periodBreakdown.innerHTML = profile.period_breakdown
    .map(
      (item) => `
      <article class="period-card">
        <small>${escapeHtml(item.label)}</small>
        <strong>${item.focus_minutes} 分钟专注</strong>
        <div>${item.completed_sessions}/${item.total_sessions} 次完成，完成率 ${Math.round(item.completion_rate * 100)}%</div>
      </article>
    `
    )
    .join("");
}

function renderLogs() {
  if (!state.recentLogs.length) {
    els.logList.innerHTML = '<p class="empty">还没有番茄钟记录，开始第一轮后会展示在这里。</p>';
    return;
  }
  els.logList.innerHTML = state.recentLogs
    .map(
      (item) => `
      <article class="log-item">
        <strong>${escapeHtml(item.task_title)}</strong>
        <div class="log-meta">
          <span>${item.planned_minutes} 分钟</span>
          <span>${Math.round(item.actual_seconds / 60)} 分钟实际专注</span>
          <span>${item.status === "done" ? "完成" : item.status === "running" ? "进行中" : "中断"}</span>
        </div>
      </article>
    `
    )
    .join("");
}

function renderTimer() {
  if (!state.timer) {
    els.timerCardEl?.classList.remove("is-running");
    els.navFocus?.classList.remove("has-timer");
    els.timerTaskName.textContent = "未开始";
    els.timerValue.textContent = `${String(Number(els.pomodoroMinutes.value || 25)).padStart(2, "0")}:00`;
    els.timerStatus.textContent = "等待选择一个任务开始。";
    els.pomodoroPause.disabled = true;
    els.pomodoroDone.disabled = true;
    els.pomodoroStop.disabled = true;
    els.pomodoroPause.textContent = "Pause";
    return;
  }
  const task = state.tasks.find((item) => item.id === state.timer.taskId);
  const remaining = Math.max(0, Math.floor((state.timer.endsAt - Date.now()) / 1000));
  els.navFocus?.classList.add("has-timer");
  els.timerTaskName.textContent = task ? task.title : "进行中的任务";
  els.timerValue.textContent = `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;
  els.timerStatus.textContent = state.timer.paused
    ? `已暂停，已累计 ${Math.round(state.timer.elapsedSeconds / 60)} 分钟。`
    : remaining > 0
      ? "专注进行中，结束后可直接记为完成。"
      : "时间到，可以完成本轮或继续追加。";
  els.timerCardEl?.classList.toggle("is-running", !state.timer.paused && remaining > 0);
  els.pomodoroPause.disabled = false;
  els.pomodoroDone.disabled = false;
  els.pomodoroStop.disabled = false;
  els.pomodoroPause.textContent = state.timer.paused ? "Resume" : "Pause";
}

function renderAll() {
  renderAuth();
  renderDiscussion();
  renderDraft();
  renderKanban();
  renderStats();
  renderUserProfile();
  renderLogs();
  renderTimer();
  if (state.draftGoalText) els.goalText.value = state.draftGoalText;
  if (state.draftFeedback) setGoalFeedback(state.draftFeedback);
  refreshImmersiveUi();
}

function createRevealObserver() {
  if (visualState.revealObserver) return visualState.revealObserver;
  visualState.revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
        } else if (!visualState.reduceMotion.matches) {
          entry.target.classList.remove("is-visible");
        }
      });
    },
    {
      rootMargin: "0px 0px -12% 0px",
      threshold: 0.12,
    }
  );
  return visualState.revealObserver;
}

function applyScrollScene() {
  const progress = Math.min(window.scrollY / Math.max(window.innerHeight, 1), 1);
  document.body.style.setProperty("--scroll-progress", progress.toFixed(3));
  if (els.appShell) {
    els.appShell.style.setProperty("--shell-shift", `${progress * -12}px`);
  }
}

function queueScrollScene() {
  if (visualState.scrollTicking) return;
  visualState.scrollTicking = true;
  window.requestAnimationFrame(() => {
    applyScrollScene();
    visualState.scrollTicking = false;
  });
}

function bindCardTilt(element, index) {
  if (element.dataset.motionBound === "true") return;
  element.dataset.motionBound = "true";
  element.style.setProperty("--reveal-delay", `${Math.min(index * 35, 280)}ms`);

  element.addEventListener("pointermove", (event) => {
    if (visualState.reduceMotion.matches || !visualState.finePointer.matches) return;
    const rect = element.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width;
    const py = (event.clientY - rect.top) / rect.height;
    const rotateY = (px - 0.5) * 12;
    const rotateX = (0.5 - py) * 10;
    const glowX = `${Math.round(px * 100)}%`;
    const glowY = `${Math.round(py * 100)}%`;

    element.style.setProperty("--tilt-x", `${rotateX.toFixed(2)}deg`);
    element.style.setProperty("--tilt-y", `${rotateY.toFixed(2)}deg`);
    element.style.setProperty("--glow-x", glowX);
    element.style.setProperty("--glow-y", glowY);
    element.style.setProperty("--pointer-alpha", "1");
  });

  element.addEventListener("pointerleave", () => {
    element.style.setProperty("--tilt-x", "0deg");
    element.style.setProperty("--tilt-y", "0deg");
    element.style.setProperty("--pointer-alpha", "0");
  });
}

function refreshImmersiveUi() {
  const observer = createRevealObserver();
  document.querySelectorAll(MOTION_CARD_SELECTOR).forEach((element, index) => {
    element.classList.add("motion-reveal");
    bindCardTilt(element, index);
    observer.observe(element);
  });
}

function setupImmersiveUi() {
  document.body.classList.add("immersive-ready");
  applyScrollScene();
  refreshImmersiveUi();

  window.addEventListener("scroll", queueScrollScene, { passive: true });
  window.addEventListener("resize", queueScrollScene);

  document.addEventListener("pointermove", (event) => {
    if (visualState.reduceMotion.matches || !visualState.finePointer.matches) return;
    const x = (event.clientX / window.innerWidth) * 100;
    const y = (event.clientY / window.innerHeight) * 100;
    document.body.style.setProperty("--cursor-x", `${x.toFixed(2)}%`);
    document.body.style.setProperty("--cursor-y", `${y.toFixed(2)}%`);
  });

  visualState.reduceMotion.addEventListener("change", () => {
    document.body.classList.toggle("reduced-motion", visualState.reduceMotion.matches);
    refreshImmersiveUi();
  });

  visualState.finePointer.addEventListener("change", () => {
    document.body.classList.toggle("fine-pointer", visualState.finePointer.matches);
  });

  document.body.classList.toggle("reduced-motion", visualState.reduceMotion.matches);
  document.body.classList.toggle("fine-pointer", visualState.finePointer.matches);
}

async function bootstrap() {
  if (!state.token) {
    renderAll();
    return;
  }
  try {
    const data = await api("/api/bootstrap");
    state.user = data.user;
    state.tasks = data.tasks;
    state.stats = data.stats;
    state.userProfile = data.user_profile;
    state.recentLogs = data.recent_logs;
    state.providerPresets = { ...state.providerPresets, ...(data.provider_presets || {}) };
    renderAll();
  } catch (error) {
    state.token = "";
    state.user = null;
    localStorage.removeItem("autotasker-token");
    flash(error.message, true);
    renderAll();
  }
}

async function submitAuth(mode) {
  const username = els.username.value.trim();
  const password = els.password.value.trim();
  const path = mode === "register" ? "/api/auth/register" : "/api/auth/login";
  const data = await api(path, { method: "POST", body: { username, password } });
  state.token = data.token;
  state.user = data.user;
  localStorage.setItem("autotasker-token", state.token);
  flash(mode === "register" ? "注册成功，已自动登录。" : "登录成功。");
  await bootstrap();
  switchView("dashboard");
}

async function generateDraft() {
  if (!state.user) {
    setGoalFeedback("请先登录后再生成任务草案。");
    return;
  }
  const goalText = els.goalText.value.trim();
  if (!goalText) {
    setGoalFeedback("请先输入一个明确目标。");
    return;
  }
  state.aiSettings = getAiConfig();
  persistAiSettings();
  setGoalFeedback("AI 正在生成首版草案...");
  const data = await api("/api/goals/analyze", {
    method: "POST",
    body: { goal_text: goalText, ai_config: state.aiSettings },
  });

  state.draftGoalText = goalText;
  state.draftFeedback = data.agent_feedback;
  state.draft = data.staging_tasks || [];
  state.draftConversation = data.agent_feedback ? [{ role: "assistant", content: data.agent_feedback }] : [];
  state.draftVersion = state.draft.length ? 1 : 0;
  state.draftVersionHistory = state.draft.length ? [createVersionEntry(1, data.agent_feedback, state.draft)] : [];
  persistDraftWorkspace();

  const meta = data.provider && data.model ? `当前模型：${data.provider} / ${data.model}` : "";
  setGoalFeedback([data.agent_feedback, meta].filter(Boolean).join("\n"));
  renderDiscussion();
  renderDraft();
}

async function discussDraft(message = "", actions = []) {
  if (!state.user || !state.draft.length) return;
  const normalizedMessage = message.trim();
  state.aiSettings = getAiConfig();
  persistAiSettings();

  const data = await api("/api/goals/discuss", {
    method: "POST",
    body: {
      goal_text: state.draftGoalText,
      current_plan: state.draft,
      conversation: state.draftConversation,
      user_message: normalizedMessage,
      actions,
      version: Math.max(state.draftVersion, 1),
      ai_config: state.aiSettings,
    },
  });

  const nextWorkspace = applyDiscussionResult(
    {
      draft: state.draft,
      draftFeedback: state.draftFeedback,
      draftConversation: state.draftConversation,
      draftVersion: state.draftVersion,
      draftVersionHistory: state.draftVersionHistory,
    },
    data,
    {
      message: normalizedMessage,
      actions,
      quickActionLabels,
    }
  );
  state.draftConversation = nextWorkspace.draftConversation;
  state.draftFeedback = nextWorkspace.draftFeedback;
  state.draft = nextWorkspace.draft;
  state.draftVersion = nextWorkspace.draftVersion;
  state.draftVersionHistory = nextWorkspace.draftVersionHistory;
  persistDraftWorkspace();
  setGoalFeedback(`当前版本 v${data.version}\n${data.assistant_message}`);
  els.discussionInput.value = "";
  renderDiscussion();
  renderDraft();
}

async function confirmDraft() {
  if (!state.draft.length) return;
  await api("/api/goals/confirm", {
    method: "POST",
    body: {
      goal_text: state.draftGoalText,
      agent_feedback: state.draftFeedback || "用户已确认多轮讨论后的最终草案",
      tasks: state.draft,
    },
  });
  clearDraftState();
  setGoalFeedback("草案已同步到正式看板。");
  await bootstrap();
  switchView("kanban");
}

async function updatePreferences() {
  const data = await api("/api/preferences", {
    method: "PUT",
    body: {
      focus_minutes: Number(els.focusMinutes.value),
      break_minutes: Number(els.breakMinutes.value),
      quiet_hours: els.quietHours.value.trim(),
    },
  });
  state.user = data.user;
  renderAuth();
}

function saveAiSettings() {
  state.aiSettings = getAiConfig();
  persistAiSettings();
  flash("AI 配置已保存在当前浏览器。");
}

async function generateAiReview() {
  state.aiSettings = getAiConfig();
  persistAiSettings();
  const data = await api("/api/review/generate", {
    method: "POST",
    body: { ai_config: state.aiSettings },
  });
  state.reviewOverride = `${data.review}\n\n来自 ${data.provider} / ${data.model}`;
  persistReviewOverride();
  renderStats();
}

async function updateTaskStatus(taskId, status) {
  await api(`/api/tasks/${taskId}/status`, { method: "PATCH", body: { status } });
  await bootstrap();
}

async function postponeTask(taskId) {
  await api("/api/tasks/postpone", { method: "POST", body: { task_id: Number(taskId), minutes: 30 } });
  await bootstrap();
}

async function startPomodoro() {
  const taskId = Number(els.pomodoroTask.value);
  if (!taskId) return;
  const minutes = Number(els.pomodoroMinutes.value) || (state.user?.focus_minutes ?? 25);
  const data = await api("/api/pomodoro/start", {
    method: "POST",
    body: { task_id: taskId, planned_minutes: minutes },
  });
  state.timer = {
    logId: data.log_id,
    taskId,
    plannedMinutes: minutes,
    startedAt: Date.now(),
    endsAt: Date.now() + minutes * 60 * 1000,
    paused: false,
    pausedAt: null,
    elapsedSeconds: 0,
  };
  persistTimer();
  startTicker();
  await bootstrap();
  switchView("focus");
}

async function finishPomodoro(result) {
  if (!state.timer) return;
  const elapsedSeconds = state.timer.paused
    ? state.timer.elapsedSeconds
    : state.timer.elapsedSeconds + Math.max(0, Math.floor((Date.now() - state.timer.startedAt) / 1000));
  await api("/api/pomodoro/finish", {
    method: "POST",
    body: {
      log_id: state.timer.logId,
      task_id: state.timer.taskId,
      actual_seconds: elapsedSeconds,
      result,
    },
  });
  state.timer = null;
  persistTimer();
  stopTicker();
  await bootstrap();
}

function togglePause() {
  if (!state.timer) return;
  if (state.timer.paused) {
    const pauseDuration = Date.now() - state.timer.pausedAt;
    state.timer.startedAt += pauseDuration;
    state.timer.endsAt += pauseDuration;
    state.timer.paused = false;
    state.timer.pausedAt = null;
  } else {
    state.timer.elapsedSeconds += Math.max(0, Math.floor((Date.now() - state.timer.startedAt) / 1000));
    state.timer.paused = true;
    state.timer.pausedAt = Date.now();
  }
  persistTimer();
  renderTimer();
}

function startTicker() {
  stopTicker();
  countdownTicker = window.setInterval(() => {
    if (state.timer && !state.timer.paused && state.timer.endsAt <= Date.now()) {
      state.timer.endsAt = Date.now();
    }
    renderTimer();
    persistTimer();
  }, 1000);
}

function stopTicker() {
  if (countdownTicker) {
    clearInterval(countdownTicker);
    countdownTicker = null;
  }
}

function setupDragAndDrop() {
  document.querySelectorAll(".task-card").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      card.classList.add("dragging");
      event.dataTransfer?.setData("text/plain", card.dataset.taskId);
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
  });
  document.querySelectorAll(".column-body").forEach((column) => {
    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      column.classList.add("drag-over");
    });
    column.addEventListener("dragleave", () => column.classList.remove("drag-over"));
    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("drag-over");
      const taskId = Number(event.dataTransfer.getData("text/plain"));
      const status = column.parentElement.dataset.status;
      if (taskId && status) await updateTaskStatus(taskId, status);
    });
  });
}

document.addEventListener("input", (event) => {
  const target = event.target;
  if (target.classList.contains("task-input")) {
    const index = Number(target.dataset.index);
    const field = target.dataset.field;
    state.draft[index][field] = field === "estimated_minutes" ? Number(target.value) : target.value;
    persistDraftWorkspace();
  }
});

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (target.dataset.action === "status") {
    await updateTaskStatus(target.dataset.id, target.dataset.status);
  }
  if (target.dataset.action === "postpone") {
    await postponeTask(target.dataset.id);
  }
  if (target.dataset.quickAction) {
    try {
      await discussDraft("", [target.dataset.quickAction]);
    } catch (error) {
      setGoalFeedback(`${error.message}\n当前草案已保留。`);
    }
  }
});

els.navItems.forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

els.aiProvider.addEventListener("change", () => syncBaseUrlPreset(true));

els.authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = event.submitter?.dataset.mode || "login";
  try {
    await submitAuth(mode);
  } catch (error) {
    flash(error.message, true);
  }
});

els.preferencesForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await updatePreferences();
    flash("偏好已更新。");
  } catch (error) {
    flash(error.message, true);
  }
});

els.aiForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveAiSettings();
});

els.goalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await generateDraft();
  } catch (error) {
    setGoalFeedback(error.message);
  }
});

els.discussionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await discussDraft(els.discussionInput.value, []);
  } catch (error) {
    setGoalFeedback(`${error.message}\n当前草案已保留。`);
  }
});

els.confirmDraft.addEventListener("click", async () => {
  try {
    await confirmDraft();
  } catch (error) {
    setGoalFeedback(error.message);
  }
});

els.clearDraft.addEventListener("click", () => {
  clearDraftState();
  setGoalFeedback("草案与讨论历史已清空。");
  renderDiscussion();
  renderDraft();
});

els.generateReview.addEventListener("click", async () => {
  try {
    await generateAiReview();
  } catch (error) {
    state.reviewOverride = "";
    persistReviewOverride();
    els.reviewText.textContent = error.message;
  }
});

els.pomodoroForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await startPomodoro();
  } catch (error) {
    els.timerStatus.textContent = error.message;
  }
});

els.pomodoroPause.addEventListener("click", togglePause);
els.pomodoroDone.addEventListener("click", async () => finishPomodoro("done"));
els.pomodoroStop.addEventListener("click", async () => finishPomodoro("interrupted"));

if (state.timer) startTicker();
hydrateAiForm();
renderAll();
setupImmersiveUi();
bootstrap();
