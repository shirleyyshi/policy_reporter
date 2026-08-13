"""
Django 管理命令：为 eval 框架植入测试数据。

用法：
    # 预览将要插入的数据（不实际写入）
    python manage.py seed_eval_data --dry-run

    # 执行植入（先清理旧 seed 数据，再插入新的）
    python manage.py seed_eval_data

    # 只清理 seed 数据，不插入
    python manage.py seed_eval_data --clean

设计要点：
1. 幂等：每次执行先删除 source_url 含 "eval_seed" 的旧数据，再插入
2. 三个场景：sparse（数据稀疏）、duplicate（标题重复）、partial_missing（字段缺失）
3. seed 数据的 source_url 统一标记为 https://eval.seed/<scenario>#eval_seed
   ——既是幂等清理的标记，也方便面试时区分"这是造的测试数据"
"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from report.models import CentralPolicy, LocalPolicy

# ==================== 种子数据定义 ====================

SEED_URL = "https://eval.seed/{scenario}/{source}/{idx}#eval_seed"

# sparse 场景：2025-08-15，1 central + 1 local = 2 条
SPARSE_CENTRAL = [
    {
        "title": "教育部关于2025年高校毕业生就业创业工作的通知",
        "content": (
            "教育部发布通知，要求各地高校做好2025届毕业生就业创业工作，"
            "重点拓宽市场化就业渠道，鼓励到基层就业和自主创业，"
            "加强困难毕业生帮扶。各高校需在6月底前完成就业方案制定。"
        ),
        "type": "教育",
        "publish_time": datetime(2025, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    },
]
SPARSE_LOCAL = [
    {
        "title": "深圳市关于支持中小企业数字化转型的若干措施",
        "content": (
            "深圳市出台措施，对实施数字化转型的中小企业给予最高50万元补贴，"
            "重点支持制造业企业上云用云和工业互联网改造。"
        ),
        "province": "广东省",
        "publish_time": datetime(2025, 8, 15, 14, 0, 0, tzinfo=timezone.utc),
    },
]

# duplicate 场景：2025-08-20，3 central（含 1 对相似标题）+ 2 local（含 1 对相似标题）
DUPLICATE_CENTRAL = [
    {
        "title": "财政部关于2025年增值税留抵退税政策有关问题的通知",
        "content": (
            "财政部明确增值税留抵退税政策执行细节，符合条件的企业可按月申请退还增量留抵税额，"
            "退税资金应优先用于技术研发和设备更新。各级财政部门需在15个工作日内完成审核。"
        ),
        "type": "财政",
        "publish_time": datetime(2025, 8, 20, 9, 0, 0, tzinfo=timezone.utc),
    },
    {
        # 标题仅末字不同（通知→公告），相似度≈0.95，应被 dedup 去重
        "title": "财政部关于2025年增值税留抵退税政策有关问题的公告",
        "content": (
            "财政部公告明确增值税留抵退税政策执行细节，符合条件的企业可按月申请退还增量留抵税额，"
            "退税资金应优先用于技术研发和设备更新。各级财政部门需在15个工作日内完成审核。"
        ),
        "type": "财政",
        "publish_time": datetime(2025, 8, 20, 9, 30, 0, tzinfo=timezone.utc),
    },
    {
        "title": "中国人民银行关于完善宏观审慎管理框架的指导意见",
        "content": (
            "人民银行提出完善宏观审慎管理框架的指导意见，重点加强系统性金融机构监管，"
            "完善跨境资本流动宏观审慎管理，建立逆周期调节机制。"
        ),
        "type": "金融",
        "publish_time": datetime(2025, 8, 20, 11, 0, 0, tzinfo=timezone.utc),
    },
]
DUPLICATE_LOCAL = [
    {
        "title": "江苏省关于推动跨境电商高质量发展的实施方案",
        "content": (
            "江苏省商务厅会同相关部门制定本实施方案，明确跨境电商高质量发展的重点任务和时间表，"
            "包括平台搭建、人才培训、品牌出海等六大工程，2025年底前完成阶段性目标。"
        ),
        "province": "江苏省",
        "publish_time": datetime(2025, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
    },
    {
        # 标题仅末尾不同（方案→意见），相似度≈0.90，应被 dedup 去重
        "title": "江苏省关于推动跨境电商高质量发展的实施意见",
        "content": (
            "江苏省商务厅会同相关部门制定本实施意见，明确跨境电商高质量发展的重点任务和时间表，"
            "包括平台搭建、人才培训、品牌出海等六大工程，2025年底前完成阶段性目标。"
        ),
        "province": "江苏省",
        "publish_time": datetime(2025, 8, 20, 10, 30, 0, tzinfo=timezone.utc),
    },
]

# partial_missing 场景：2025-08-25，3 central（含空内容/空类型）+ 2 local（含空内容/空省份）
PARTIAL_CENTRAL = [
    {
        "title": "交通运输部关于加快推进智慧交通发展的实施意见",
        "content": (
            "交通运输部提出到2025年基本建成智慧交通体系，重点推进高速公路智能化升级、"
            "港口数字化改造、城市交通大数据平台建设，鼓励交通与5G、人工智能等新技术深度融合。"
        ),
        "type": "交通",
        "publish_time": datetime(2025, 8, 25, 9, 0, 0, tzinfo=timezone.utc),
    },
    {
        # type 为空——测试 Agent 对缺失分类字段的处理
        "title": "生态环境部关于深入打好污染防治攻坚战的指导意见",
        "content": (
            "各地区各部门应深入贯彻习近平生态文明思想，以减污降碳协同增效为总抓手，"
            "统筹推进大气、水、土壤污染防治，持续改善生态环境质量，"
            "到2025年实现主要污染物排放总量持续下降。"
        ),
        "type": "",
        "publish_time": datetime(2025, 8, 25, 10, 0, 0, tzinfo=timezone.utc),
    },
    {
        # content 为空——测试 Agent 对空内容政策的处理（summarize 应跳过）
        "title": "国家发展改革委关于2025年新型城镇化建设重点任务的公告",
        "content": "",
        "type": "发改",
        "publish_time": datetime(2025, 8, 25, 11, 0, 0, tzinfo=timezone.utc),
    },
]
PARTIAL_LOCAL = [
    {
        "title": "四川省关于支持大学生创新创业的扶持政策",
        "content": (
            "四川省出台扶持政策，对在校大学生和毕业5年内高校毕业生创业给予最高20万元补贴，"
            "提供免费创业孵化场地和导师辅导服务，重点支持科技型创业项目。"
        ),
        "province": "四川省",
        "publish_time": datetime(2025, 8, 25, 14, 0, 0, tzinfo=timezone.utc),
    },
    {
        # province 为空、content 为空——双重缺失
        "title": "关于推进养老服务高质量发展的若干措施",
        "content": "",
        "province": "",
        "publish_time": datetime(2025, 8, 25, 15, 0, 0, tzinfo=timezone.utc),
    },
]

# 场景汇总
SCENARIOS = [
    ("sparse", "2025-08-15", SPARSE_CENTRAL, SPARSE_LOCAL),
    ("duplicate", "2025-08-20", DUPLICATE_CENTRAL, DUPLICATE_LOCAL),
    ("partial_missing", "2025-08-25", PARTIAL_CENTRAL, PARTIAL_LOCAL),
]


class Command(BaseCommand):
    help = "为 eval 框架植入测试数据（sparse/duplicate/partial_missing 场景）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只打印将要插入的数据，不实际写入",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="只清理 seed 数据，不插入新的",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.MIGRATE_HEADING("  Eval Seed Data 植入"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))

        # 清理旧 seed 数据
        old_c = CentralPolicy.objects.filter(source_url__contains="eval_seed").count()
        old_l = LocalPolicy.objects.filter(source_url__contains="eval_seed").count()
        if old_c or old_l:
            self.stdout.write(f"发现旧 seed 数据: 中央={old_c} 地方={old_l}")
            if not options["dry_run"]:
                deleted_c, _ = CentralPolicy.objects.filter(
                    source_url__contains="eval_seed"
                ).delete()
                deleted_l, _ = LocalPolicy.objects.filter(
                    source_url__contains="eval_seed"
                ).delete()
                self.stdout.write(self.style.WARNING(
                    f"已清理: 中央={deleted_c} 地方={deleted_l}"
                ))
            else:
                self.stdout.write("--dry-run: 跳过清理")

        if options["clean"]:
            self.stdout.write(self.style.SUCCESS("\n--clean: 仅清理完成"))
            return

        # 预览 / 插入新数据
        self.stdout.write(f"\n即将植入 {len(SCENARIOS)} 个场景的数据:")
        total_c = 0
        total_l = 0
        for scenario, date, centrals, locals_ in SCENARIOS:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n  [{scenario}] 日期={date} 中央={len(centrals)} 地方={len(locals_)}"
            ))
            for i, c in enumerate(centrals, 1):
                content_preview = c["content"][:60] + "..." if c["content"] else "(空)"
                self.stdout.write(f"    中央 [{c['type'] or '空'}] {c['title']}")
                self.stdout.write(f"      content: {content_preview}")
            for i, l in enumerate(locals_, 1):
                content_preview = l["content"][:60] + "..." if l["content"] else "(空)"
                self.stdout.write(f"    地方 [{l['province'] or '空'}] {l['title']}")
                self.stdout.write(f"      content: {content_preview}")
            total_c += len(centrals)
            total_l += len(locals_)

        self.stdout.write(f"\n总计: 中央={total_c} 地方={total_l}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--dry-run: 不实际写入"))
            return

        # 实际插入（每条政策唯一 URL，避免 dedup 按 URL 误删）
        for scenario, date, centrals, locals_ in SCENARIOS:
            for i, c in enumerate(centrals, 1):
                url = SEED_URL.format(scenario=scenario, source="central", idx=i)
                CentralPolicy.objects.create(source_url=url, **c)
            for i, l in enumerate(locals_, 1):
                url = SEED_URL.format(scenario=scenario, source="local", idx=i)
                LocalPolicy.objects.create(source_url=url, **l)

        self.stdout.write(self.style.SUCCESS(
            f"\n植入完成: 中央={total_c} 地方={total_l}"
        ))
