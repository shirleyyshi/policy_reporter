"""
Eval 运行器。

批量跑测试集，收集 per-run 指标，聚合 aggregate 指标。
支持 ablation 配置，用于消融实验对比。

用法：
    from agent.eval.runner import EvalRunner
    runner = EvalRunner()
    report = runner.run()  # 跑默认测试集
    report = runner.run(config={"critic_every_n": 999})  # ablation: 去掉 Critic
"""
import logging
import time
from datetime import datetime
from typing import Optional

from agent.core import run_agent
from agent.eval.testset import TestCase, discover_test_cases
from agent.eval.metrics import collect_run_metrics

logger = logging.getLogger(__name__)


# Ablation 预设配置
ABLATION_CONFIGS = {
    "baseline": None,  # 默认配置
    "no_critic": {
        "critic_every_n": 999,
        "stall_detection_enabled": False,
    },
    "no_replanner": {
        "replanner_enabled": False,
    },
    "no_stall": {
        "stall_detection_enabled": False,
    },
}


class EvalRunner:
    """Eval 运行器。"""

    def __init__(self, test_cases: Optional[list[TestCase]] = None):
        self.test_cases = test_cases or discover_test_cases()

    def run_single(self, case: TestCase, config: Optional[dict] = None) -> dict:
        """
        跑单个测试用例。
        返回 {case_id, scenario, config_name, run_id, metrics, duration_sec, error}
        """
        config_name = "custom"
        for name, cfg in ABLATION_CONFIGS.items():
            if cfg == config:
                config_name = name
                break
        if config is None:
            config_name = "baseline"

        start = time.time()
        config_tag = config_name

        logger.info(f"[{config_tag}] 跑 {case.case_id}: date={case.date}, scenario={case.scenario}")

        try:
            run_id, state = run_agent(
                date=case.date,
                legal_text=case.legal_text,
                config=config,
            )
            duration = round(time.time() - start, 1)
            metrics = collect_run_metrics(run_id)

            logger.info(
                f"[{config_tag}] {case.case_id} 完成: "
                f"status={metrics['status']}, steps={metrics['step_count']}, "
                f"duration={duration}s"
            )

            return {
                "case_id": case.case_id,
                "scenario": case.scenario,
                "description": case.description,
                "date": case.date,
                "config_name": config_name,
                "run_id": str(run_id),
                "metrics": metrics,
                "duration_sec": duration,
                "error": None,
            }

        except Exception as e:
            duration = round(time.time() - start, 1)
            logger.exception(f"[{config_tag}] {case.case_id} 失败: {e}")
            return {
                "case_id": case.case_id,
                "scenario": case.scenario,
                "description": case.description,
                "date": case.date,
                "config_name": config_name,
                "run_id": None,
                "metrics": None,
                "duration_sec": duration,
                "error": str(e),
            }

    def run(
        self,
        config: Optional[dict] = None,
        config_name: str = "baseline",
    ) -> dict:
        """
        跑完整测试集。
        返回 eval 报告 dict（含 per-run 结果 + aggregate 指标）。
        """
        config_name = config_name or "baseline"
        results = []
        total_start = time.time()

        for case in self.test_cases:
            result = self.run_single(case, config=config)
            results.append(result)

        total_duration = round(time.time() - total_start, 1)
        aggregate = self._aggregate(results, config_name, total_duration)

        return {
            "config_name": config_name,
            "config": config,
            "timestamp": datetime.now().isoformat(),
            "total_duration_sec": total_duration,
            "test_case_count": len(self.test_cases),
            "results": results,
            "aggregate": aggregate,
        }

    def run_ablation(self, ablation_name: str) -> dict:
        """跑单个 ablation 配置。"""
        config = ABLATION_CONFIGS.get(ablation_name)
        if ablation_name not in ABLATION_CONFIGS:
            raise ValueError(f"未知 ablation: {ablation_name}，可选: {list(ABLATION_CONFIGS.keys())}")
        return self.run(config=config, config_name=ablation_name)

    def run_all_ablations(self) -> list[dict]:
        """跑所有 ablation 配置（含 baseline），返回报告列表。"""
        reports = []
        for name in ABLATION_CONFIGS:
            logger.info(f"===== 开始 ablation: {name} =====")
            report = self.run_ablation(name)
            reports.append(report)
        return reports

    def _aggregate(self, results: list[dict], config_name: str, total_duration: float) -> dict:
        """聚合所有 run 的指标。"""
        valid = [r for r in results if r["metrics"] is not None]
        failed_runs = [r for r in results if r["error"] is not None]

        if not valid:
            return {
                "config_name": config_name,
                "total_cases": len(results),
                "valid_cases": 0,
                "failed_cases": len(failed_runs),
                "success_rate": 0,
                "total_duration_sec": total_duration,
            }

        success_count = sum(1 for r in valid if r["metrics"]["success"])
        avg_steps = sum(r["metrics"]["step_count"] for r in valid) / len(valid)
        avg_critic = sum(r["metrics"]["critic_count"] for r in valid) / len(valid)
        avg_errors = sum(r["metrics"]["error_count"] for r in valid) / len(valid)

        # Critic 修复率（只算有 Critic 触发的 run）
        replan_rates = [
            r["metrics"]["critic_replan_rate"]
            for r in valid
            if r["metrics"]["critic_replan_rate"] is not None
        ]
        avg_replan_rate = sum(replan_rates) / len(replan_rates) if replan_rates else None

        # LLM judge 平均分
        judge_scores = [
            r["metrics"]["llm_judge"]["overall_score"]
            for r in valid
            if r["metrics"]["llm_judge"] and "overall_score" in r["metrics"]["llm_judge"]
        ]
        avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else None

        # 状态分布
        status_dist = {}
        for r in valid:
            s = r["metrics"]["status"]
            status_dist[s] = status_dist.get(s, 0) + 1

        # 工具调用分布（全部 run 合并）
        tool_dist = {}
        for r in valid:
            for tool, count in r["metrics"]["tool_calls"].items():
                tool_dist[tool] = tool_dist.get(tool, 0) + count

        # 平均耗时
        avg_duration = sum(r["duration_sec"] for r in valid) / len(valid)

        return {
            "config_name": config_name,
            "total_cases": len(results),
            "valid_cases": len(valid),
            "failed_cases": len(failed_runs),
            "success_count": success_count,
            "success_rate": round(success_count / len(valid), 4),
            "avg_step_count": round(avg_steps, 1),
            "avg_critic_count": round(avg_critic, 1),
            "avg_critic_replan_rate": round(avg_replan_rate, 4) if avg_replan_rate is not None else None,
            "avg_error_count": round(avg_errors, 1),
            "avg_llm_judge_score": round(avg_judge, 2) if avg_judge is not None else None,
            "avg_duration_sec": round(avg_duration, 1),
            "total_duration_sec": total_duration,
            "status_distribution": status_dist,
            "tool_call_distribution": tool_dist,
        }
