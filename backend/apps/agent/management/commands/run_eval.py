"""
Django 管理命令：运行 eval。

用法：
    # 跑 baseline（默认配置）
    python manage.py run_eval

    # 跑单个 ablation
    python manage.py run_eval --ablation no_critic

    # 跑全部 ablation 对比实验
    python manage.py run_eval --all-ablations

    # 指定输出目录
    python manage.py run_eval --output-dir eval_reports

    # 只看测试集（不实际跑）
    python manage.py run_eval --dry-run
"""
import logging

from django.core.management.base import BaseCommand

from agent.eval.testset import discover_test_cases
from agent.eval.runner import EvalRunner, ABLATION_CONFIGS
from agent.eval.reporter import save_report, save_ablation_report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "运行 Agent eval 评估框架"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ablation",
            type=str,
            choices=list(ABLATION_CONFIGS.keys()),
            help="跑单个 ablation 配置（baseline/no_critic/no_replanner/no_stall）",
        )
        parser.add_argument(
            "--all-ablations",
            action="store_true",
            help="跑全部 ablation 配置并生成对比报告",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default="eval_reports",
            help="报告输出目录（默认 eval_reports）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只列出测试用例，不实际运行",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="跳过交互确认（用于 CI/非交互环境）",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.MIGRATE_HEADING("  Agent Eval 评估框架"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))

        # 构建测试集（自动从 DB 发现，DB 为空时返回最小测试集）
        test_cases = discover_test_cases()

        self.stdout.write(f"\n测试用例 ({len(test_cases)} 条):")
        for tc in test_cases:
            self.stdout.write(f"  - {tc.case_id}: {tc.scenario} | {tc.description}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--dry-run: 不实际运行"))
            return

        runner = EvalRunner(test_cases=test_cases)
        output_dir = options["output_dir"]

        if options["all_ablations"]:
            # 跑全部 ablation 对比
            self.stdout.write(self.style.WARNING(
                f"\n即将跑 {len(ABLATION_CONFIGS)} 组 ablation × {len(test_cases)} 条用例 "
                f"= {len(ABLATION_CONFIGS) * len(test_cases)} 次 Agent 运行"
            ))
            self.stdout.write("配置列表: " + ", ".join(ABLATION_CONFIGS.keys()))

            # 交互确认（CI/非交互环境用 --yes 跳过）
            if not options["yes"]:
                try:
                    confirm = input("\n确认运行？(y/N): ")
                except EOFError:
                    self.stdout.write(self.style.ERROR(
                        "非交互环境无法确认，请加 --yes 参数跳过确认"
                    ))
                    return
                if confirm.lower() != 'y':
                    self.stdout.write("已取消")
                    return

            reports = runner.run_all_ablations()
            paths = save_ablation_report(reports, output_dir=output_dir)

            self.stdout.write(self.style.SUCCESS(f"\n报告已保存:"))
            self.stdout.write(f"  JSON: {paths['json']}")
            self.stdout.write(f"  Markdown: {paths['markdown']}")

            # 打印对比摘要
            self.stdout.write(self.style.MIGRATE_HEADING("\n===== 对比摘要 ====="))
            self.stdout.write(f"{'配置':<15} {'成功率':<10} {'步数':<8} {'Critic':<8} {'修复率':<10} {'judge':<8} {'耗时':<8}")
            self.stdout.write("-" * 67)
            for report in reports:
                agg = report["aggregate"]
                sr = f"{agg.get('success_rate', 0):.1%}"
                steps = str(agg.get('avg_step_count', '-'))
                critic = str(agg.get('avg_critic_count', '-'))
                replan = f"{agg.get('avg_critic_replan_rate', 0):.1%}" if agg.get('avg_critic_replan_rate') is not None else "-"
                judge = str(agg.get('avg_llm_judge_score', '-'))
                dur = f"{agg.get('avg_duration_sec', '-')}s"
                self.stdout.write(f"{report['config_name']:<15} {sr:<10} {steps:<8} {critic:<8} {replan:<10} {judge:<8} {dur:<8}")

            # all-ablations 分支到此结束，不继续走 baseline 的最终摘要逻辑
            return

        elif options["ablation"]:
            # 跑单个 ablation
            ablation_name = options["ablation"]
            self.stdout.write(self.style.WARNING(
                f"\n即将跑 ablation={ablation_name} × {len(test_cases)} 条用例"
            ))
            report = runner.run_ablation(ablation_name)
            paths = save_report(report, output_dir=output_dir)

            self.stdout.write(self.style.SUCCESS(f"\n报告已保存:"))
            self.stdout.write(f"  JSON: {paths['json']}")
            self.stdout.write(f"  Markdown: {paths['markdown']}")

        else:
            # 跑 baseline
            self.stdout.write(self.style.WARNING(
                f"\n即将跑 baseline × {len(test_cases)} 条用例"
            ))
            report = runner.run(config_name="baseline")
            paths = save_report(report, output_dir=output_dir)

            self.stdout.write(self.style.SUCCESS(f"\n报告已保存:"))
            self.stdout.write(f"  JSON: {paths['json']}")
            self.stdout.write(f"  Markdown: {paths['markdown']}")

        # 打印最终摘要
        agg = report["aggregate"]
        self.stdout.write(self.style.MIGRATE_HEADING("\n===== 最终摘要 ====="))
        self.stdout.write(f"  成功率: {agg.get('success_rate', 0):.1%} ({agg.get('success_count', 0)}/{agg.get('valid_cases', 0)})")
        self.stdout.write(f"  平均步数: {agg.get('avg_step_count', '-')}")
        self.stdout.write(f"  平均 Critic 触发: {agg.get('avg_critic_count', '-')}")
        if agg.get('avg_critic_replan_rate') is not None:
            self.stdout.write(f"  Critic 修复率: {agg['avg_critic_replan_rate']:.1%}")
        self.stdout.write(f"  LLM-judge 平均分: {agg.get('avg_llm_judge_score', '-')} / 5")
        self.stdout.write(f"  总耗时: {agg.get('total_duration_sec', '-')}s")
