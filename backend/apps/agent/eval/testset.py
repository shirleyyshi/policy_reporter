"""
Eval 测试集定义。

设计要点：
1. 测试用例覆盖 6 种数据场景：empty / sparse / dense / with_legal / duplicate / partial_missing
2. 不依赖手写标准摘要——v1 只跑不需要 ground truth 的指标
3. discover_test_cases() 自动从 DB 查询有数据的日期，避免硬编码过期日期
4. duplicate / partial_missing 场景由 seed_eval_data 命令植入，discover 时自动识别
"""
import difflib
from dataclasses import dataclass
from typing import Optional

from report.models import CentralPolicy, LocalPolicy


@dataclass
class TestCase:
    """单条 eval 测试用例。"""
    case_id: str          # 唯一标识，如 "dense_2025_07_31"
    date: str             # 日期，如 "2025-07-31"
    legal_text: str       # 合规资讯正文（可为空）
    scenario: str         # "empty" / "sparse" / "dense" / "with_legal" / "duplicate" / "partial_missing"
    description: str      # 人类可读描述


def _count_policies(date: str) -> tuple[int, int]:
    """返回 (central_count, local_count) for a given date."""
    central = CentralPolicy.objects.filter(publish_time__date=date).count()
    local = LocalPolicy.objects.filter(publish_time__date=date).count()
    return central, local


def _has_duplicate_titles(date: str) -> bool:
    """检查某日期是否有标题高度相似的政策对（相似度 > 0.85）。"""
    titles = list(
        CentralPolicy.objects.filter(publish_time__date=date).values_list("title", flat=True)
    ) + list(
        LocalPolicy.objects.filter(publish_time__date=date).values_list("title", flat=True)
    )
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if difflib.SequenceMatcher(None, titles[i], titles[j]).ratio() > 0.85:
                return True
    return False


def _has_partial_missing(date: str) -> bool:
    """检查某日期是否有空内容或空分类字段的政策。"""
    central = CentralPolicy.objects.filter(publish_time__date=date)
    if central.filter(content="").exists() or central.filter(type="").exists():
        return True
    local = LocalPolicy.objects.filter(publish_time__date=date)
    if local.filter(content="").exists() or local.filter(province="").exists() or local.filter(type="").exists():
        return True
    return False


def discover_test_cases() -> list[TestCase]:
    """
    从 DB 自动发现测试用例。

    策略：
    - 查所有有政策的日期，按总数排序
    - 取最多政策的日期 → dense 场景
    - 取 1-3 条政策的日期 → sparse 场景
    - 取一个不可能有政策的日期 → empty 场景
    - 对 dense 场景额外附加 legal_text → with_legal 场景
    """
    from django.db.models import Count
    from django.db.models.functions import TruncDate

    # 查所有有中央或地方政策的日期
    central_dates = (
        CentralPolicy.objects
        .annotate(d=TruncDate('publish_time'))
        .values('d')
        .annotate(c=Count('id'))
        .order_by('-c')
    )
    local_dates = (
        LocalPolicy.objects
        .annotate(d=TruncDate('publish_time'))
        .values('d')
        .annotate(c=Count('id'))
        .order_by('-c')
    )

    # 合并日期 → 总数
    date_totals: dict[str, int] = {}
    for item in central_dates:
        if item['d']:
            date_totals.setdefault(item['d'].isoformat(), 0)
            date_totals[item['d'].isoformat()] += item['c']
    for item in local_dates:
        if item['d']:
            date_totals.setdefault(item['d'].isoformat(), 0)
            date_totals[item['d'].isoformat()] += item['c']

    if not date_totals:
        # DB 完全空，返回最小测试集
        return [
            TestCase("empty_0001", "2025-01-01", "", "empty", "DB 无政策数据"),
        ]

    sorted_dates = sorted(date_totals.items(), key=lambda x: -x[1])

    cases: list[TestCase] = []

    # Dense 场景：取政策最多的日期
    dense_date, dense_count = sorted_dates[0]
    cases.append(TestCase(
        case_id=f"dense_{dense_date.replace('-', '_')}",
        date=dense_date,
        legal_text="",
        scenario="dense",
        description=f"政策最多的日期（{dense_count} 条）",
    ))

    # Sparse 场景：取 1-3 条政策的日期
    sparse_candidate = None
    for d, count in sorted_dates:
        if 1 <= count <= 3:
            sparse_candidate = (d, count)
            break
    if sparse_candidate:
        s_date, s_count = sparse_candidate
        cases.append(TestCase(
            case_id=f"sparse_{s_date.replace('-', '_')}",
            date=s_date,
            legal_text="",
            scenario="sparse",
            description=f"政策稀疏日期（{s_count} 条）",
        ))

    # Duplicate 场景：检测有标题高度相似对的日期
    for d, count in sorted_dates:
        if _has_duplicate_titles(d):
            cases.append(TestCase(
                case_id=f"duplicate_{d.replace('-', '_')}",
                date=d,
                legal_text="",
                scenario="duplicate",
                description=f"含标题高度相似政策对的日期（{count} 条）",
            ))
            break

    # Partial missing 场景：检测有空内容/空字段政策的日期
    for d, count in sorted_dates:
        if _has_partial_missing(d):
            cases.append(TestCase(
                case_id=f"partial_{d.replace('-', '_')}",
                date=d,
                legal_text="",
                scenario="partial_missing",
                description=f"含空内容/空字段政策的日期（{count} 条）",
            ))
            break

    # Empty 场景：取一个不可能有政策的日期
    cases.append(TestCase(
        case_id="empty_2099_01_01",
        date="2099-01-01",
        legal_text="",
        scenario="empty",
        description="不存在的日期，验证空数据处理",
    ))

    # With legal 场景：dense 日期 + legal_text
    sample_legal = (
        "2025年7月，财政部发布《关于增值税法实施若干问题的公告》，"
        "明确增值税征收率、抵扣链条等关键问题。企业需关注进项税额抵扣凭证的合规性，"
        "避免因凭证不合规导致的税务风险。"
    )
    cases.append(TestCase(
        case_id=f"with_legal_{dense_date.replace('-', '_')}",
        date=dense_date,
        legal_text=sample_legal,
        scenario="with_legal",
        description="政策最多的日期 + 合规资讯正文",
    ))

    return cases
