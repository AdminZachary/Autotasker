const test = require("node:test");
const assert = require("node:assert/strict");

const helpers = require("../static/state-helpers.js");

function createStorage(initial = {}) {
  const store = new Map(Object.entries(initial).map(([key, value]) => [key, String(value)]));
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

test("readDraftWorkspace falls back safely on malformed JSON", () => {
  const storage = createStorage({
    "autotasker-draft": "{broken",
    "autotasker-draft-goal": "完成课程项目",
    "autotasker-draft-version": "3",
    "autotasker-draft-versions": "{broken",
  });

  const workspace = helpers.readDraftWorkspace(storage);
  assert.deepEqual(workspace.draft, []);
  assert.equal(workspace.draftGoalText, "完成课程项目");
  assert.equal(workspace.draftVersion, 3);
  assert.deepEqual(workspace.draftVersionHistory, []);
});

test("persistDraftWorkspaceState and clearDraftWorkspaceState round-trip draft state", () => {
  const storage = createStorage();
  const workspace = {
    draft: [{ title: "任务 A" }],
    draftGoalText: "本周完成演示",
    draftFeedback: "先推进关键路径",
    draftConversation: [{ role: "assistant", content: "初版草案已生成" }],
    draftVersion: 2,
    draftVersionHistory: [{ version: 1 }],
  };

  helpers.persistDraftWorkspaceState(storage, workspace);
  const restored = helpers.readDraftWorkspace(storage);
  assert.deepEqual(restored, workspace);

  helpers.clearDraftWorkspaceState(storage);
  const cleared = helpers.readDraftWorkspace(storage);
  assert.deepEqual(cleared.draft, []);
  assert.equal(cleared.draftGoalText, "");
  assert.equal(cleared.draftVersion, 0);
});

test("applyDiscussionResult appends conversation and bumps version history", () => {
  const workspace = {
    draft: [{ title: "调研竞品" }],
    draftFeedback: "先给你一版初稿",
    draftConversation: [{ role: "assistant", content: "先给你一版初稿" }],
    draftVersion: 1,
    draftVersionHistory: [helpers.createVersionEntry(1, "先给你一版初稿", [{ title: "调研竞品" }], "2026-05-19T10:00:00.000Z")],
  };

  const nextWorkspace = helpers.applyDiscussionResult(
    workspace,
    {
      assistant_message: "我把高价值任务前移到上午，并拆细了第一项。",
      updated_plan: [{ title: "竞品清单" }, { title: "竞品对比" }],
      version: 2,
    },
    {
      message: "",
      actions: ["split_tasks", "raise_priority"],
      quickActionLabels: {
        split_tasks: "拆小任务",
        raise_priority: "提高优先级",
      },
    }
  );

  assert.equal(nextWorkspace.draftVersion, 2);
  assert.equal(nextWorkspace.draft.length, 2);
  assert.equal(nextWorkspace.draftConversation.length, 3);
  assert.match(nextWorkspace.draftConversation[1].content, /快捷操作/);
  assert.equal(nextWorkspace.draftVersionHistory.length, 2);
  assert.equal(nextWorkspace.draftVersionHistory[1].task_count, 2);
});
