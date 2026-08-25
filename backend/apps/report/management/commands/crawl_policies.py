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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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


def fetch_page(url, encoding="utf-8", timeout=DEFAULT_TIMEOUT, referer=None, retries=1):
    """抓取页面，返回 lxml tree。失败返回 None（自动重试，打印状态码便于诊断）。"""
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                r.encoding = encoding
                return html.fromstring(r.text)
            print(f"    [HTTP {r.status_code}] {url}")
        except requests.RequestException as e:
            print(f"    [{type(e).__name__}] {url}")
        if attempt < retries:
            time.sleep(3 + attempt * 3)  # 递增退避：3s, 6s, 9s...
    return None


def extract_title(tree, config):
    """从详情页提取标题。多路径按文档序取第一个非空结果。"""
    xpath = config.get("detail_title_xpath", "")
    if not xpath:
        return ""
    title = ""
    for r in tree.xpath(xpath):
        t = (r if isinstance(r, str) else r.text_content()).strip()
        if t:
            title = t
            break
    if not title:
        return ""
    # 分割处理（如 gov.cn 的 "标题_分类_网站名"）
    split_char = config.get("detail_title_split")
    if split_char:
        parts = title.split(split_char)
        idx = config.get("detail_title_index", 0)
        title = parts[idx].strip() if idx < len(parts) else title
    return title


def extract_content(tree, config):
    """从详情页提取正文。多节点匹配时取文本最长的（正文容器文本量最大）。"""
    xpath = config.get("detail_content_xpath", "")
    if not xpath:
        return ""
    nodes = tree.xpath(xpath)
    if not nodes:
        return ""
    node = max(nodes, key=lambda n: len(n.text_content()))
    # 排除特定子区域（如相关链接）
    exclude_class = config.get("detail_content_exclude")
    if exclude_class:
        # 克隆节点并移除不需要的子节点
        node_copy = deepcopy(node)
        for excluded in node_copy.xpath(f'.//*[contains(@class,"{exclude_class}")]'):
            excluded.getparent().remove(excluded)
        return node_copy.text_content().strip()
    return node.text_content().strip()


# 页面元数据区常见的日期上下文（"发布日期：2026-08-21" 等）
DATE_CONTEXT_RE = re.compile(
    r"(?:发布日期|发文日期|发布时间|成文日期|时间)\s*[：:]\s*"
    r"(\d{4}[-年.]\d{1,2}[-月.]\d{1,2})"
)
DATE_PLAIN_RE = re.compile(r"\d{4}[-年.]\d{1,2}[-月.]\d{1,2}")


def extract_date(tree, config):
    """从详情页提取发布日期。XPath 失败时从页面头部文本兜底。"""
    xpath = config.get("detail_date_xpath", "")
    if xpath:
        result = tree.xpath(xpath)
        if result:
            date_str = result[0] if isinstance(result[0], str) else result[0].text_content()
            dt = parse_date(date_str)
            if dt:
                return dt
    # 兜底：元数据区（发布日期/发文日期等）通常在页面头部
    head_text = tree.text_content()[:3000]
    m = DATE_CONTEXT_RE.search(head_text)
    if m:
        dt = parse_date(m.group(1))
        if dt:
            return dt
    m = DATE_PLAIN_RE.search(head_text)
    if m:
        return parse_date(m.group(0))
    return None


def fetch_api_list(list_api, page_num, referer, timeout):
    """从 JSON API 获取列表页 HTML（商务部 jpaas 接口：列表由 JS 渲染，直接调接口）。
    list_api 含 {page} 占位符。返回 lxml tree，失败返回 None。"""
    url = list_api.replace("{page}", str(page_num))
    headers = dict(DEFAULT_HEADERS)
    headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            print(f"    [HTTP {r.status_code}] {url}")
            return None
        data = r.json()
        html_str = (data.get("data") or {}).get("html", "")
        if not html_str:
            print(f"    [API 空响应] {url}")
            return None
        return html.fromstring(html_str)
    except (requests.RequestException, ValueError) as e:
        print(f"    [{type(e).__name__}] {url}")
        return None


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
    # 翻页偏移：财政部第 2 页是 index_1.htm（page_offset=-1），多数站是 index_2.html（0）
    page_offset = config.get("page_offset", 0)
    timeout = config.get("timeout_seconds", DEFAULT_TIMEOUT)
    retries = config.get("retries", 1)
    # API 模式：列表由 JS 渲染时直接调 JSON 接口（如商务部），含 {page} 占位符
    list_api = config.get("list_api", "")

    stats = {
        "crawled": 0, "new": 0, "skipped": 0, "filtered": 0,
        "failed": 0, "list_failed": False, "pages_fetched": 0,
    }
    print(f"\n[{name}] 开始抓取，计划最多 {max_pages} 页...")

    # 翻页循环
    for page_num in range(1, max_pages + 1):
        # 构造当前页 URL
        if list_api:
            url = list_url  # Referer 用；列表内容从 API 拿
        elif page_num == 1:
            url = list_url
        elif page_url_pattern:
            url = page_url_pattern.replace("{page}", str(page_num + page_offset))
        else:
            # 没配置翻页 pattern，只抓首页
            break

        # 1. 抓列表页
        if list_api:
            tree = fetch_api_list(list_api, page_num, list_url, timeout)
            if tree is None:
                if page_num == 1:
                    stats["list_failed"] = True
                break
        else:
            try:
                tree = fetch_page(url, encoding, timeout=timeout, retries=retries)
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
        # 去重前置：先查库，已入库的 URL 直接跳过，不再下载详情页
        # （否则每天都会把列表页上所有旧政策的详情页重新下载一遍，耗时且无意义）
        Model = CentralPolicy if policy_type == "central" else LocalPolicy
        for title_hint, detail_url in page_new_links:
            stats["crawled"] += 1
            if not dry_run and Model.objects.filter(source_url=detail_url).exists():
                stats["skipped"] += 1
                continue
            try:
                # Referer 设为列表页，模拟浏览器从列表点进详情（部分政府站防盗链）
                detail_tree = fetch_page(detail_url, encoding, timeout=timeout, referer=url, retries=retries)
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
                    # 写入（去重已在抓取前完成）
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
                        # 地方政策：province（地方属性）+ type（业务分类，与中央一致）
                        create_kwargs["province"] = config.get("default_province", "")
                        create_kwargs["type"] = config.get("default_category", "综合")

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
        # 读取配置 / Load crawler config
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                configs = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"配置文件不存在 / Config not found: {CONFIG_PATH}"))
            return
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"配置文件 JSON 解析失败 / JSON parse error: {e}"))
            return

        # 跳过禁用站点 / Skip disabled sites
        disabled = [c for c in configs if not c.get("enabled", True)]
        for c in disabled:
            reason = c.get("disabled_reason", "未知原因")
            self.stdout.write(self.style.WARNING(f"[跳过] {c['name']}（已禁用: {reason}）"))
        configs = [c for c in configs if c.get("enabled", True)]

        # 筛选要爬的站点
        if options["site"]:
            # --site 时忽略 enabled 标志，允许强制爬取禁用站点
            all_configs = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
            configs = [c for c in all_configs if c["site_id"] == options["site"]]
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
                f"新增 {stats['new']} 条，已入库跳过 {stats['skipped']} 条，"
                f"标题过滤 {stats['filtered']} 条，失败 {stats['failed']} 条"
            )

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n合计：抓取 {total_stats['pages_fetched']} 页 / {total_stats['crawled']} 条，"
            f"新增 {total_stats['new']} 条，已入库跳过 {total_stats['skipped']} 条，"
            f"标题过滤 {total_stats['filtered']} 条，失败 {total_stats['failed']} 条"
        ))
        if not dry_run and total_stats["new"] == 0:
            self.stdout.write(self.style.NOTICE(
                "本次无新增：列表页上的政策均已入库（去重跳过）或站点当日暂无新发布，属正常现象"
            ))
        self.stdout.write(f"耗时：{elapsed:.1f} 秒")
