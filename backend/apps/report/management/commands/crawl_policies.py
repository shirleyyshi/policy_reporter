"""
轻量级政策爬虫（Django management command）。

用法：
  python manage.py crawl_policies --all              # 爬所有配置的站点
  python manage.py crawl_policies --site gov_cn      # 只爬指定站
  python manage.py crawl_policies --all --dry-run    # 试运行（不写 DB）
  python manage.py crawl_policies --all --max-pages 3 # 覆盖配置的页数

设计要点：
- 配置驱动（crawl_config.json），每站可配 page_url_pattern 实现翻页
- 发布时间用 Asia/Shanghai 时区（与 gov.cn / shanghai.gov.cn 一致）
- source_url 去重，title_filter 关键词白名单过滤
- 失败统计用 list_failed 布尔字段，不污染 failed 计数
"""
import json
import re
import time
import logging
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
from lxml import html
from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone

from report.models import CentralPolicy, LocalPolicy

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "crawl_config.json"
DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 政府站点都是北京时间
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def parse_date(date_str):
    """解析多种日期格式，返回 Asia/Shanghai 时区的 datetime 对象。"""
    if not date_str:
        return None
    date_str = date_str.strip()
    # 清理特殊字符
    date_str = date_str.replace("∶", ":").replace("：", ":")
    # 常见格式
    patterns = [
        r"(\d{4})-(\d{2})-(\d{2})[T\s-](\d{2}):(\d{2}):(\d{2})",
        r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})",
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})\.(\d{2})\.(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, date_str)
        if m:
            groups = m.groups()
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])
            hour = int(groups[3]) if len(groups) > 3 else 0
            minute = int(groups[4]) if len(groups) > 4 else 0
            second = int(groups[5]) if len(groups) > 5 else 0
            try:
                return datetime(year, month, day, hour, minute, second, tzinfo=SHANGHAI_TZ)
            except ValueError:
                continue
    return None


def fetch_page(url, encoding="utf-8", timeout=DEFAULT_TIMEOUT):
    """抓取页面，返回 lxml tree。失败返回 None。"""
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    r.encoding = encoding
    if r.status_code != 200:
        return None
    return html.fromstring(r.text)


def extract_title(tree, config):
    """从详情页提取标题。"""
    xpath = config.get("detail_title_xpath", "")
    if not xpath:
        return ""
    result = tree.xpath(xpath)
    if not result:
        return ""
    title = result[0] if isinstance(result[0], str) else result[0].text_content()
    title = title.strip()
    # 分割处理（如 gov.cn 的 "标题_分类_网站名"）
    split_char = config.get("detail_title_split")
    if split_char:
        parts = title.split(split_char)
        idx = config.get("detail_title_index", 0)
        title = parts[idx].strip() if idx < len(parts) else title
    return title


def extract_content(tree, config):
    """从详情页提取正文。"""
    xpath = config.get("detail_content_xpath", "")
    if not xpath:
        return ""
    nodes = tree.xpath(xpath)
    if not nodes:
        return ""
    node = nodes[0]
    # 排除标题区域（上海站的 Article-title-zw）
    exclude_class = config.get("detail_content_exclude")
    if exclude_class:
        # 克隆节点并移除不需要的子节点
        node_copy = deepcopy(node)
        for excluded in node_copy.xpath(f'.//*[contains(@class,"{exclude_class}")]'):
            excluded.getparent().remove(excluded)
        return node_copy.text_content().strip()
    return node.text_content().strip()


def extract_date(tree, config):
    """从详情页提取发布日期。"""
    xpath = config.get("detail_date_xpath", "")
    if not xpath:
        return None
    result = tree.xpath(xpath)
    if not result:
        return None
    date_str = result[0] if isinstance(result[0], str) else result[0].text_content()
    return parse_date(date_str)


def crawl_site(config, dry_run=False, max_pages_override=None):
    """
    爬取单个站点，返回统计。
    stats["list_failed"] = True 表示列表页抓取失败（不累加进 failed 计数）。
    stats["failed"] 是真实的失败条数（>=0）。
    """
    name = config["name"]
    site_id = config["site_id"]
    policy_type = config["policy_type"]
    list_url = config["list_url"]
    encoding = config.get("encoding", "utf-8")
    delay = config.get("delay_seconds", 1.0)
    max_pages = max_pages_override or config.get("max_pages", 1)
    title_filter = config.get("title_filter", [])
    page_url_pattern = config.get("page_url_pattern", "")

    stats = {
        "crawled": 0, "new": 0, "skipped": 0, "filtered": 0,
        "failed": 0, "list_failed": False, "pages_fetched": 0,
    }
    print(f"\n[{name}] 开始抓取，计划最多 {max_pages} 页...")

    # 翻页循环
    for page_num in range(1, max_pages + 1):
        # 构造当前页 URL
        if page_num == 1:
            url = list_url
        elif page_url_pattern:
            url = page_url_pattern.replace("{page}", str(page_num))
        else:
            # 没配置翻页 pattern，只抓首页
            break

        # 1. 抓列表页
        try:
            tree = fetch_page(url, encoding)
            if tree is None:
                print(f"  [第 {page_num} 页] 列表页抓取失败 (HTTP 非 200): {url}")
                if page_num == 1:
                    stats["list_failed"] = True
                break  # 列表页失败就停止翻页
        except Exception as e:
            print(f"  [第 {page_num} 页] 列表页抓取异常: {e}")
            if page_num == 1:
                stats["list_failed"] = True
            break

        stats["pages_fetched"] += 1
        print(f"  [第 {page_num} 页] 抓取成功: {url}")

        # 2. 提取政策链接
        link_xpath = config.get("list_link_xpath", "")
        links = tree.xpath(link_xpath) if link_xpath else []
        print(f"  [第 {page_num} 页] 找到 {len(links)} 个链接")

        # 过滤：标题包含 title_filter 中的关键词
        page_new_links = []
        for a in links:
            title_text = a.text_content().strip()
            href = a.get("href", "")
            if not title_text or not href:
                continue
            if title_filter and not any(kw in title_text for kw in title_filter):
                stats["filtered"] += 1
                continue
            full_url = urljoin(list_url, href)
            page_new_links.append((title_text, full_url))

        print(f"  [第 {page_num} 页] 过滤后 {len(page_new_links)} 条")

        # 如果本页没有有效链接，可能是末页，停止翻页
        if not page_new_links and page_num > 1:
            print(f"  [第 {page_num} 页] 无有效链接，停止翻页")
            break

        # 3. 逐条抓详情页
        for title_hint, detail_url in page_new_links:
            stats["crawled"] += 1
            try:
                detail_tree = fetch_page(detail_url, encoding)
                if detail_tree is None:
                    print(f"  [失败] {title_hint[:40]}... (HTTP 错误)")
                    stats["failed"] += 1
                    time.sleep(delay)
                    continue

                # 提取字段
                title = extract_title(detail_tree, config) or title_hint
                content = extract_content(detail_tree, config)
                pub_date = extract_date(detail_tree, config)

                if not content:
                    print(f"  [跳过] {title[:40]}... (正文为空)")
                    stats["failed"] += 1
                    time.sleep(delay)
                    continue

                if not pub_date:
                    pub_date = django_timezone.now()

                if dry_run:
                    print(f"  [试运行] {title[:50]}  date={pub_date.strftime('%Y-%m-%d')}  content={len(content)}字")
                    stats["new"] += 1
                else:
                    # 去重 + 写入
                    Model = CentralPolicy if policy_type == "central" else LocalPolicy
                    if Model.objects.filter(source_url=detail_url).exists():
                        stats["skipped"] += 1
                        time.sleep(delay)
                        continue

                    create_kwargs = {
                        "title": title[:500],
                        "content": content,
                        "publish_time": pub_date,
                        "source_url": detail_url,
                        "crawled_at": django_timezone.now(),
                    }
                    if policy_type == "central":
                        create_kwargs["type"] = config.get("default_category", "")
                    else:
                        create_kwargs["province"] = config.get("default_province", "")

                    Model.objects.create(**create_kwargs)
                    stats["new"] += 1
                    print(f"  [新增] {title[:50]}")

            except Exception as e:
                print(f"  [异常] {title_hint[:40]}... : {e}")
                stats["failed"] += 1

            time.sleep(delay)

        # 翻页间隔
        if page_num < max_pages:
            time.sleep(delay)

    return stats


class Command(BaseCommand):
    help = "轻量级政策爬虫：从政府网站抓取政策入库"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="爬取所有配置的站点")
        parser.add_argument("--site", type=str, help="只爬指定 site_id")
        parser.add_argument("--dry-run", action="store_true", help="试运行（不写 DB）")
        parser.add_argument("--max-pages", type=int, help="覆盖配置的页数")

    def handle(self, *args, **options):
        # 读取配置
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            configs = json.load(f)

        # 筛选要爬的站点
        if options["site"]:
            configs = [c for c in configs if c["site_id"] == options["site"]]
            if not configs:
                self.stdout.write(self.style.ERROR(f"未找到 site_id={options['site']}"))
                return
        elif not options["all"]:
            self.stdout.write(self.style.ERROR("请指定 --all 或 --site <id>"))
            return

        dry_run = options["dry_run"]
        max_pages_override = options.get("max_pages")

        self.stdout.write(self.style.SUCCESS(f"开始爬取 {len(configs)} 个站点{'（试运行）' if dry_run else ''}"))

        total_stats = {
            "crawled": 0, "new": 0, "skipped": 0, "filtered": 0,
            "failed": 0, "pages_fetched": 0,
        }
        start_time = time.time()

        for config in configs:
            stats = crawl_site(config, dry_run, max_pages_override)
            if stats["list_failed"]:
                self.stdout.write(self.style.ERROR(f"[{config['name']}] 列表页抓取失败，跳过该站"))
                continue
            for k in total_stats:
                total_stats[k] += stats.get(k, 0)
            self.stdout.write(
                f"[{config['name']}] "
                f"抓取 {stats['pages_fetched']} 页 / {stats['crawled']} 条，"
                f"新增 {stats['new']} 条，跳过 {stats['skipped']} 条，"
                f"过滤 {stats['filtered']} 条，失败 {stats['failed']} 条"
            )

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n合计：抓取 {total_stats['pages_fetched']} 页 / {total_stats['crawled']} 条，"
            f"新增 {total_stats['new']} 条，跳过 {total_stats['skipped']} 条，"
            f"过滤 {total_stats['filtered']} 条，失败 {total_stats['failed']} 条"
        ))
        self.stdout.write(f"耗时：{elapsed:.1f} 秒")
