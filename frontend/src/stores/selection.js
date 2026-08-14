import { reactive } from 'vue'

/**
 * 内存级选择状态 store（不持久化）。
 *
 * 设计意图：
 * - 政策勾选 / 合规资讯正文只存在内存中，刷新或重新进入网页即清空。
 * - 仅在当前 SPA 会话内有效，Home ↔ Editor 页之间共享。
 * - selectedDate 仍走 localStorage，因为它是用户主动选的日期过滤条件。
 */
export const selectionStore = reactive({
  centralIds: [],
  localIds: [],
  legalText: ''
})
