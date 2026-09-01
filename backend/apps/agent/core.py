"""
Agent 主循环（ReAct）。

三角色（面试 tradeoff：7→3 合并）：
- Actuator：每步 1 次 LLM，输出 {reasoning, tool, params, done}。
  合并原 Planner/Tool Selector/Parameter Generator——用 structured output 一次产出。
- Critic：每 3 步或异常时触发，输出 replan_hint 注入下一步。合并原 Critic+Replanner。
- Terminator：代码（非 LLM），硬性终止：max_steps/重复/连续失败/求助上限。

循环防护：
- max_steps=15
- 同一 tool+params 连续 3 次 → 强制 Critic 介入
- 连续 3 次工具调用抛异常 → failed
- 5 步 state 无变化 → 触发 Critic
- ask_human > 3 次 → failed
"""
import json
import uuid
import time
import logging
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection
from openai import OpenAI

from .tools import AgentState, TOOLS
from .prompts import ACTUATOR_SYSTEM, build_step_prompt, CRITIC_SYSTEM, build_critic_prompt
from .models import AgentTrace, AgentRun
from .rag import retrieve_episodic_memory, store_episodic_memory

logger = logging.getLogger(__name__)

MAX_STEPS = 15
CRITIC_EVERY_N = 3
REPEAT_THRESHOLD = 3
FAIL_THRESHOLD = 3
STALL_STEPS = 5
ASK_HUMAN_LIMIT = 3

# DeepSeek 客户端
_openai_client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
)

# 同步运行时的内存缓存：run_id(str) → state（供 download/trace 端点用）
_RUN_CACHE = {}

# Phase 5: 人在回路线程同步
_WAIT_EVENTS = {}    # run_id_str → threading.Event（Agent 线程阻塞等待）
_HUMAN_ANSWERS = {}  # run_id_str → answer string（API 线程提交答案）

# docx 持久化目录：服务器重启后仍可下载历史 run 的 docx
_DOCX_DIR = Path(settings.BASE_DIR) / 'media' / 'agent_docx'
_DOCX_DIR.mkdir(parents=True, exist_ok=True)

# LLM 调用重试配置（应对 DeepSeek 限流/网络抖动）
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0  # 首次重试等待 1s，之后 2s、4s（指数退避）


def _call_llm_with_retry(fn, *args, **kwargs):
    """包装 LLM 调用，失败时指数退避重试。

    用于 _call_actuator / _call_critic，避免 DeepSeek 限流导致整个 run 失败。
    """
    last_exc = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < LLM_MAX_RETRIES - 1:
                delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"LLM 调用失败（第 {attempt+1}/{LLM_MAX_RETRIES} 次），{delay}s 后重试: {e}")
                time.sleep(delay)
    raise last_exc


def _parse_llm_json(content):
    """解析 LLM 返回的 JSON content，容错 None / 非 JSON / JSON 片段。
    Parse LLM JSON output with fallbacks for None / invalid JSON / JSON fragments.
    """
    if not content:
        raise ValueError("LLM 返回空 content")
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        import re
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"无法从 LLM 响应提取 JSON: {content[:100]}")


def _call_actuator(state, replan_hint=None):
    """调 Actuator LLM，返回解析后的 dict。"""
    user_prompt = build_step_prompt(state, MAX_STEPS, replan_hint)
    response = _call_llm_with_retry(
        _openai_client.chat.completions.create,
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": ACTUATOR_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        stream=False,
    )
    return _parse_llm_json(response.choices[0].message.content)


def _call_critic(state):
    """调 Critic LLM，返回 {needs_replan, replan_hint}。"""
    user_prompt = build_critic_prompt(state)
    response = _call_llm_with_retry(
        _openai_client.chat.completions.create,
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        stream=False,
    )
    try:
        return _parse_llm_json(response.choices[0].message.content)
    except (ValueError, json.JSONDecodeError) as e:
        # 不静默：解析失败必须留痕（此前直接吞掉，问题路径无从排查）
        raw = (response.choices[0].message.content or '')[:200]
        logger.warning(f"Critic 输出解析失败，按无需重规划继续: {e}, 原文前200字: {raw!r}")
        return {"needs_replan": False, "replan_hint": ""}


def _record_trace(run_id, step, action, tool=None, input_data=None,
                  output_data=None, reasoning=None):
    """写一条 trace（DB + 内存）。"""
    entry = {
        "step": step,
        "action": action,
        "tool": tool,
        "input": input_data,
        "output": output_data,
        "reasoning": reasoning,
    }
    AgentTrace.objects.create(
        run_id=run_id,
        step=step,
        action=action,
        tool=tool,
        input=input_data,
        output=output_data,
        reasoning=reasoning,
    )
    return entry


def _run_loop(run_id, state, config=None):
    """
    Agent 主循环（同步和异步共用）。
    输入：run_id、state（已初始化）、config（可选 ablation 参数）。
    循环结束后 state.status 为 done/failed，state 已就绪。
    """
    cfg = config or {}
    max_steps = cfg.get('max_steps', MAX_STEPS)
    critic_every_n = cfg.get('critic_every_n', CRITIC_EVERY_N)
    repeat_threshold = cfg.get('repeat_threshold', REPEAT_THRESHOLD)
    fail_threshold = cfg.get('fail_threshold', FAIL_THRESHOLD)
    stall_steps = cfg.get('stall_steps', STALL_STEPS)
    ask_human_limit = cfg.get('ask_human_limit', ASK_HUMAN_LIMIT)
    replanner_enabled = cfg.get('replanner_enabled', True)
    stall_detection_enabled = cfg.get('stall_detection_enabled', True)

    # 停滞检测：记录近 stall_steps 步的 state 摘要
    state_snapshots = deque(maxlen=stall_steps)

    replan_hint = None

    while state.step < max_steps and state.status == "running":
        current_step = state.step + 1

        # ===== Actuator =====
        try:
            decision = _call_actuator(state, replan_hint=replan_hint)
        except Exception as e:
            logger.exception("Actuator LLM 调用失败")
            _record_trace(run_id, current_step, "actuate",
                          reasoning=f"Actuator 异常: {e}")
            state.fail_count += 1
            if state.fail_count >= fail_threshold:
                state.status = "failed"
                break
            state.step = current_step
            continue

        reasoning = decision.get("reasoning", "")
        tool = decision.get("tool", "")
        params = decision.get("params", {}) or {}
        done = decision.get("done", False)

        # 清空已用的 replan_hint
        replan_hint = None

        # ===== Terminator：done 判断 =====
        if done or tool == "finish":
            _record_trace(run_id, current_step, "terminate",
                          reasoning=reasoning or "Actuator 输出 done/finish",
                          output_data={"status": "done"})
            state.status = "done"
            state.step = current_step
            break

        # ===== Terminator：未知工具 =====
        if tool not in TOOLS:
            _record_trace(run_id, current_step, "actuate", tool=tool,
                          input_data=params, reasoning=reasoning,
                          output_data={"error": f"未知工具: {tool}"})
            state.fail_count += 1
            if state.fail_count >= fail_threshold:
                state.status = "failed"
                break
            state.step = current_step
            continue

        # ===== 重复检测 =====
        # ReAct 完整化：last_actions 存 (tool, params_key, observation_preview) 三元组。
        # 此处 observation 尚未产生，先 append 占位空串，工具执行成功后回填真实 observation。
        # 重复检测只比 (tool, params) 前两元，忽略 observation（同一工具+参数可能返回不同结果）。
        params_key = json.dumps(params, sort_keys=True, ensure_ascii=False)
        state.last_actions.append((tool, params_key, ""))
        recent_keys = [(a[0], a[1]) for a in state.last_actions[-repeat_threshold:]]
        if (len(recent_keys) == repeat_threshold
                and len(set(recent_keys)) == 1):
            _record_trace(run_id, current_step, "actuate", tool=tool,
                          input_data=params, reasoning=reasoning,
                          output_data={"warning": "连续重复调用，触发 Critic"})
            # 强制 Critic 介入
            critic_result = _call_critic(state)
            _record_trace(run_id, current_step, "critique",
                          output_data=critic_result,
                          reasoning="重复检测触发 Critic")
            state.trace.append({
                "step": current_step, "action": "critique",
                "tool": None, "output": critic_result,
            })
            if critic_result.get("needs_replan") and replanner_enabled:
                replan_hint = critic_result.get("replan_hint", "")
            state.step = current_step
            # 清空重复计数，避免无限触发
            state.last_actions = []
            continue

        # ===== 执行工具 =====
        try:
            observation = TOOLS[tool](state, params)
            state.fail_count = 0
        except Exception as e:
            logger.exception(f"工具 {tool} 执行异常")
            # 异常时移除占位（未成功执行，不应计入历史）
            state.last_actions.pop()
            _record_trace(run_id, current_step, "actuate", tool=tool,
                          input_data=params, reasoning=reasoning,
                          output_data={"error": str(e)})
            state.fail_count += 1
            if state.fail_count >= fail_threshold:
                state.status = "failed"
                state.step = current_step
                break
            state.step = current_step
            state.trace.append({
                "step": current_step, "action": "actuate",
                "tool": tool, "input": params,
                "output": {"error": str(e)},
            })
            continue

        # 记录工具执行 trace
        trace_entry = _record_trace(run_id, current_step, "actuate",
                                    tool=tool, input_data=params,
                                    output_data=observation,
                                    reasoning=reasoning)
        state.trace.append(trace_entry)

        # 回填真实 observation 到 last_actions（取前 150 字作为 preview，供 ReAct 反馈）
        obs_preview = json.dumps(observation, ensure_ascii=False)[:150]
        state.last_actions[-1] = (tool, params_key, obs_preview)

        # 持久化 state 到 DB（让前端轮询看到进度 + 多 worker 共享）
        try:
            save_state(run_id, state)
        except Exception as e:
            logger.warning(f"save_state 失败（不影响 run）: {e}")

        # ===== ask_human 上限 =====
        if tool == "ask_human" and state.ask_human_count > ask_human_limit:
            _record_trace(run_id, current_step, "terminate",
                          reasoning="ask_human 次数超上限",
                          output_data={"status": "failed"})
            state.status = "failed"
            state.step = current_step
            break

        state.step = current_step

        # ===== Critic：每 N 步触发 =====
        if state.step % critic_every_n == 0:
            try:
                critic_result = _call_critic(state)
                _record_trace(run_id, current_step, "critique",
                              output_data=critic_result,
                              reasoning=f"第 {state.step} 步例行 Critic")
                state.trace.append({
                    "step": current_step, "action": "critique",
                    "tool": None, "output": critic_result,
                })
                if critic_result.get("needs_replan") and replanner_enabled:
                    replan_hint = critic_result.get("replan_hint", "")
            except Exception as e:
                logger.warning(f"Critic 调用失败（忽略）: {e}")

        # ===== 停滞检测 =====
        if stall_detection_enabled:
            current_snapshot = state.summary_view()
            state_snapshots.append(current_snapshot)
            if (len(state_snapshots) == stall_steps
                    and len(set(state_snapshots)) == 1):
                try:
                    critic_result = _call_critic(state)
                    _record_trace(run_id, current_step, "critique",
                                  output_data=critic_result,
                                  reasoning="停滞检测触发 Critic")
                    state.trace.append({
                        "step": current_step, "action": "critique",
                        "tool": None, "output": critic_result,
                    })
                    if critic_result.get("needs_replan") and replanner_enabled:
                        replan_hint = critic_result.get("replan_hint", "")
                    state_snapshots.clear()
                except Exception as e:
                    logger.warning(f"停滞 Critic 调用失败（忽略）: {e}")

    # ===== max_steps 终止 =====
    if state.status == "running":
        _record_trace(run_id, state.step + 1, "terminate",
                      reasoning=f"触达 max_steps={max_steps}",
                      output_data={"status": "failed"})
        state.status = "failed"

    # Fallback：fail_count 途径退出时未记录 terminate trace，补一条
    if state.status == "failed":
        last_trace = AgentTrace.objects.filter(
            run_id=run_id
        ).order_by('-step').first()
        if not last_trace or last_trace.action != 'terminate':
            _record_trace(run_id, state.step + 1, "terminate",
                          reasoning=f"连续失败达上限 (fail_count={state.fail_count})",
                          output_data={"status": "failed"})

    # 持久化 docx 到文件系统（服务器重启后仍可下载）
    if state.docx_bytes:
        try:
            docx_path = _DOCX_DIR / f"{run_id}.docx"
            docx_path.write_bytes(state.docx_bytes)
        except Exception as e:
            logger.warning(f"docx 持久化失败（不影响 run）: {e}")

    state.task_input["run_id"] = str(run_id)

    # A3: 存 episodic memory（仅成功 run 且有 summary 时，避免 failed run 污染经验库）
    if state.status == "done" and state.summary:
        date = state.task_input.get('date', '')
        # key_decisions：取工具调用序列供下次 run 参考策略。
        # last_actions 元组可能被 JSON 序列化成 list，用 len 检查兼容 tuple/list。
        key_decisions = [
            {"tool": a[0], "params": a[1]}
            for a in state.last_actions
            if len(a) >= 2
        ]
        store_episodic_memory(run_id, date, state.summary, key_decisions)

    # 最终状态持久化（done/failed 时确保 DB 记录最终 status + step）
    try:
        save_state(run_id, state)
    except Exception as e:
        logger.warning(f"最终 save_state 失败（不影响 run）: {e}")


def run_agent(date, legal_text="", config=None):
    """
    同步模式（eval 用）。直接调 _run_loop，不设 callback。
    返回 (run_id, state)。
    """
    run_id = uuid.uuid4()
    state = AgentState(task_input={"date": date, "legal_text": legal_text})
    state.step = 0
    # A3: 检索相似历史 run 经验，注入 context_hints 供 LLM 参考
    state.context_hints = retrieve_episodic_memory(f"财税政策日报 {date}")
    _RUN_CACHE[str(run_id)] = state
    save_state(run_id, state)  # 创建 AgentRun 记录
    _run_loop(run_id, state, config)
    return run_id, state


def run_agent_async(date, legal_text="", config=None, user=None):
    """
    异步模式（API 用）。启动后台线程，立即返回 run_id。
    ask_human 通过回调暂停等待人工介入。
    user: 发起用户（AgentRun.user 归属，用于列表/详情/下载隔离）。
    """
    run_id = uuid.uuid4()
    state = AgentState(task_input={"date": date, "legal_text": legal_text})
    state.step = 0
    state.human_input_callback = _make_human_input_handler(run_id, state)
    # A3: 检索相似历史 run 经验，注入 context_hints 供 LLM 参考
    state.context_hints = retrieve_episodic_memory(f"财税政策日报 {date}")
    _RUN_CACHE[str(run_id)] = state
    save_state(run_id, state, user=user)  # 创建 AgentRun 记录

    def _thread_target():
        try:
            _run_loop(run_id, state, config)
        except Exception as e:
            logger.exception("Agent 后台线程异常")
            state.status = "failed"
        finally:
            connection.close()

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    return run_id


def _make_human_input_handler(run_id, state):
    """创建人在回路回调。ask_human 调用时阻塞等待人工介入。"""
    def handler(question, options):
        run_id_str = str(run_id)
        state.status = "waiting_human"
        state.pending_question = {"question": question, "options": options}
        # 持久化 waiting_human 状态（让前端轮询看到 pending_question）
        try:
            save_state(run_id, state)
        except Exception as e:
            logger.warning(f"waiting_human save_state 失败: {e}")

        event = threading.Event()
        _WAIT_EVENTS[run_id_str] = event

        # 等待用户回答（5 分钟超时，超时用默认答案）
        event.wait(timeout=300)

        # 唤醒或超时
        state.status = "running"
        state.pending_question = None
        _WAIT_EVENTS.pop(run_id_str, None)
        # 持久化恢复 running 状态
        try:
            save_state(run_id, state)
        except Exception as e:
            logger.warning(f"恢复 running save_state 失败: {e}")

        answer = _HUMAN_ANSWERS.pop(run_id_str, None)
        if answer is None:
            answer = options[0] if options else "继续"

        return answer

    return handler


def submit_answer(run_id, answer):
    """提交人工回答，唤醒等待中的 Agent 线程。"""
    run_id_str = str(run_id)
    event = _WAIT_EVENTS.get(run_id_str)
    if not event:
        return False
    _HUMAN_ANSWERS[run_id_str] = answer
    event.set()
    return True


def _serialize_state(state: AgentState) -> dict:
    """序列化 state 为可 JSON 存储的 dict。

    排除：trace（在 AgentTrace 表）、docx_bytes（落盘 media/agent_docx/）、
    human_input_callback（callable 不可序列化）、pending_question（瞬时）、
    task_input（AgentRun.task_input 单独字段）。

    raw_policies/clean_policies 含 publish_time（datetime），
    用 default=str 转 ISO 字符串，避免 Django JSONField 序列化报错。
    """
    data = {
        'raw_policies': state.raw_policies,
        'clean_policies': state.clean_policies,
        'summary': state.summary,
        'related_analysis': state.related_analysis,
        'step': state.step,
        'status': state.status,
        'fail_count': state.fail_count,
        'ask_human_count': state.ask_human_count,
        'last_actions': state.last_actions,
        'context_hints': state.context_hints,
    }
    # datetime → ISO 字符串，确保 JSON 可序列化
    return json.loads(json.dumps(data, default=str))


def _restore_datetime(value):
    """ISO 字符串 → datetime。

    _serialize_state 用 default=str 把 publish_time 转成了字符串，
    恢复时转回 datetime，保持与未持久化的内存 state 类型一致。
    clean_policies 的 publish_time 本来就是 str（clean_policy 工具内转换），不在此处理。
    """
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _deserialize_state(state: AgentState, data: dict, run: AgentRun):
    """从 DB AgentRun 记录恢复 state 字段。"""
    data = data or {}
    state.raw_policies = data.get('raw_policies', [])
    for p in state.raw_policies:
        if isinstance(p, dict) and 'publish_time' in p:
            p['publish_time'] = _restore_datetime(p['publish_time'])
    state.clean_policies = data.get('clean_policies', [])
    state.summary = data.get('summary')
    state.related_analysis = data.get('related_analysis')
    state.step = data.get('step', 0)
    state.status = data.get('status', 'running')
    state.fail_count = data.get('fail_count', 0)
    state.ask_human_count = data.get('ask_human_count', 0)
    state.last_actions = data.get('last_actions', [])
    state.context_hints = data.get('context_hints', [])
    state.task_input = run.task_input
    # trace 从 AgentTrace 表重建（按 step 排序）
    state.trace = [
        {
            'step': t.step, 'action': t.action, 'tool': t.tool,
            'input': t.input, 'output': t.output, 'reasoning': t.reasoning,
        }
        for t in AgentTrace.objects.filter(run_id=run.run_id).order_by('step')
    ]
    # docx_bytes 不加载到内存（get_docx 从文件系统读）
    # human_input_callback 不恢复（重启后 waiting_human 已超时）
    # pending_question 不恢复


def save_state(run_id, state: AgentState, user=None):
    """持久化 state 到 DB。

    每次工具调用后调用，确保 gunicorn 多 worker 下 state 可见、服务重启可恢复。
    用 update_or_create 幂等：首次 create，后续 update。
    user 仅在创建时传入；后续 update 不带 user，不覆盖已有归属。
    """
    run_id_str = str(run_id)
    defaults = {
        'status': state.status,
        'step': state.step,
        'task_input': state.task_input,
        'state_json': _serialize_state(state),
        'summary': state.summary or '',
        'docx_path': f'media/agent_docx/{run_id_str}.docx' if state.docx_bytes else None,
        'error': 'see AgentTrace for details' if state.status == 'failed' else None,
    }
    if user is not None:
        defaults['user'] = user
    AgentRun.objects.update_or_create(
        run_id=run_id_str,
        defaults=defaults
    )


def get_state(run_id):
    """优先从内存缓存取 state，回退从 DB AgentRun 反序列化。

    支持 gunicorn 多 worker（_RUN_CACHE 进程内不共享）和服务重启恢复。
    """
    run_id_str = str(run_id)
    if run_id_str in _RUN_CACHE:
        return _RUN_CACHE[run_id_str]
    try:
        run = AgentRun.objects.get(run_id=run_id_str)
    except AgentRun.DoesNotExist:
        return None
    state = AgentState(task_input=run.task_input)
    _deserialize_state(state, run.state_json, run)
    # AgentRun 表的 status/step 是冗余字段，优先用 state_json 内的（更实时）
    state.status = run.status or state.status
    state.step = run.step if run.step is not None else state.step
    _RUN_CACHE[run_id_str] = state
    return state


def get_docx(run_id):
    """取某次 run 的 docx bytes。优先内存缓存，回退文件系统。"""
    run_id_str = str(run_id)
    state = _RUN_CACHE.get(run_id_str)
    if state and state.docx_bytes:
        return state.docx_bytes
    docx_path = _DOCX_DIR / f"{run_id_str}.docx"
    if docx_path.exists():
        return docx_path.read_bytes()
    return None
