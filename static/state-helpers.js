(function (global, factory) {
  const helpers = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = helpers;
  }
  global.AutoTaskerStateHelpers = helpers;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const DRAFT_STORAGE_KEYS = {
    draft: "autotasker-draft",
    draftGoalText: "autotasker-draft-goal",
    draftFeedback: "autotasker-draft-feedback",
    draftConversation: "autotasker-draft-conversation",
    draftVersion: "autotasker-draft-version",
    draftVersionHistory: "autotasker-draft-versions",
  };

  function safeJsonParse(raw, fallback) {
    try {
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function createVersionEntry(version, assistantMessage, draft, updatedAt) {
    return {
      version,
      assistant_message: assistantMessage,
      task_count: Array.isArray(draft) ? draft.length : 0,
      updated_at: updatedAt || new Date().toISOString(),
    };
  }

  function readDraftWorkspace(storage) {
    return {
      draft: safeJsonParse(storage.getItem(DRAFT_STORAGE_KEYS.draft) || "[]", []),
      draftGoalText: storage.getItem(DRAFT_STORAGE_KEYS.draftGoalText) || "",
      draftFeedback: storage.getItem(DRAFT_STORAGE_KEYS.draftFeedback) || "",
      draftConversation: safeJsonParse(storage.getItem(DRAFT_STORAGE_KEYS.draftConversation) || "[]", []),
      draftVersion: Number(storage.getItem(DRAFT_STORAGE_KEYS.draftVersion) || "0"),
      draftVersionHistory: safeJsonParse(storage.getItem(DRAFT_STORAGE_KEYS.draftVersionHistory) || "[]", []),
    };
  }

  function persistDraftWorkspaceState(storage, workspace) {
    storage.setItem(DRAFT_STORAGE_KEYS.draft, JSON.stringify(workspace.draft || []));
    storage.setItem(DRAFT_STORAGE_KEYS.draftGoalText, workspace.draftGoalText || "");
    storage.setItem(DRAFT_STORAGE_KEYS.draftFeedback, workspace.draftFeedback || "");
    storage.setItem(DRAFT_STORAGE_KEYS.draftConversation, JSON.stringify(workspace.draftConversation || []));
    storage.setItem(DRAFT_STORAGE_KEYS.draftVersion, String(workspace.draftVersion || 0));
    storage.setItem(DRAFT_STORAGE_KEYS.draftVersionHistory, JSON.stringify(workspace.draftVersionHistory || []));
  }

  function clearDraftWorkspaceState(storage) {
    Object.values(DRAFT_STORAGE_KEYS).forEach((key) => storage.removeItem(key));
  }

  function buildFallbackUserText(actions, quickActionLabels) {
    return (actions || []).map((item) => `[快捷操作] ${quickActionLabels[item] || item}`).join("，");
  }

  function applyDiscussionResult(workspace, result, options) {
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
  }

  return {
    DRAFT_STORAGE_KEYS,
    safeJsonParse,
    createVersionEntry,
    readDraftWorkspace,
    persistDraftWorkspaceState,
    clearDraftWorkspaceState,
    buildFallbackUserText,
    applyDiscussionResult,
  };
});
