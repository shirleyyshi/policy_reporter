from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from .models import CentralPolicy, LocalPolicy
from io import BytesIO
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx import Document
from collections import defaultdict
import datetime
from openai import OpenAI  # 使用 OpenAI SDK 兼容 DeepSeek
from django.conf import settings

# DeepSeek API 配置（从 settings 读取，密钥外置到 .env）
openai_client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)


# 辅助样式函数
def set_font(run, font_name="微软雅黑", font_size=12, bold=False):
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)


def add_hyperlink(paragraph, url, text, font_name="微软雅黑", font_size=11):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    color = OxmlElement('w:color')
    color.set(qn('w:val'), '000000')
    rPr.append(color)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), font_name)
    rFonts.set(qn('w:ascii'), font_name)
    rPr.append(rFonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), str(font_size * 2))
    rPr.append(sz)
    new_run.append(rPr)
    text_elem = OxmlElement('w:t')
    text_elem.text = text
    new_run.append(text_elem)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def call_deepseek_summarization(texts):
    prompt = (
            "假设你是一位财税专家，为公司管理层梳理每日日报热点。请阅读以下财税类政策内容，总结成每日热点资讯摘要，语言正式、简洁，适合放在财税简报的开头部分。"
            "摘要应简洁明了、语言正式、中文撰写，控制在5条以内，每条20-35字。不需要标题或者“今日财税热点摘要：”之类的开头。"
            "每条摘要前请加一个圆点（• ），并换行显示，禁止使用星号(*)、序号（如1. 2. 3.）或其他Markdown格式符号。仅返回纯文本，不要多余解释。\n\n"
            + "\n\n".join(texts[:10])
    )
    response = openai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=False
    )
    return response.choices[0].message.content.strip()


def set_heading_font(paragraph, font_name="微软雅黑", font_size=14, bold=True):
    if paragraph.runs:
        for run in paragraph.runs:
            set_font(run, font_name=font_name, font_size=font_size, bold=bold)


def generate_docx(central, local, legal_text, output_stream, summary=None, report_date=None):
    doc = Document()

    # 标题日期：优先用调用方传入的日期（前端 selectedDate），否则回退到当天
    if report_date:
        # 兼容 "2025-08-01" / "2025-08-01T00:00:00" 等格式，统一成 YYYY.MM.DD
        date_str_for_title = report_date[:10].replace("-", ".")
    else:
        date_str_for_title = datetime.datetime.now().strftime("%Y.%m.%d")

    # 摘要：若调用方传入预计算 summary（Agent 路径）则直接用；否则调 DeepSeek 生成（基线路径）
    if summary is None:
        policy_texts = [content for _, content, _, _ in central] + [content for _, content, _, _ in local]
        summary = call_deepseek_summarization(policy_texts)

    # 主标题
    h1 = doc.add_heading(f"每日财税日报（{date_str_for_title}）", 0)
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_heading_font(h1, font_size=20)

    # 今日热点资讯
    h_today = doc.add_heading("今日热点资讯", level=1)
    set_heading_font(h_today)

    # 摘要正文段落
    p_summary = doc.add_paragraph(summary)
    if not p_summary.runs:
        p_summary.add_run()
    set_font(p_summary.runs[0], font_size=11)

    # 最新发布的其他政策法规
    h_latest = doc.add_heading("最新发布的其他政策法规", level=1)
    set_heading_font(h_latest)

    # 中央政策
    h_central = doc.add_heading("中央政策", level=2)
    set_heading_font(h_central, font_size=12)

    type_group = defaultdict(list)
    for title, content, policy_type, source_url in central:
        type_group[policy_type].append((title, source_url))

    for policy_type, policies in type_group.items():
        p_type = doc.add_paragraph(style="List Bullet")
        run_type = p_type.add_run(f"【{policy_type}】")
        set_font(run_type, font_size=12)

        for title, url in policies:
            p_item = doc.add_paragraph(style="List Bullet 2")
            add_hyperlink(p_item, url, title)
            if p_item.runs:
                set_font(p_item.runs[0], font_size=11)

    # 地方法规
    h_local = doc.add_heading("地方法规", level=2)
    set_heading_font(h_local, font_size=12)

    province_group = defaultdict(list)
    for title, content, province, source_url in local:
        province_group[province].append((title, source_url))

    for province, policies in province_group.items():
        p_province = doc.add_paragraph(style="List Bullet")
        run_province = p_province.add_run(f"【{province}】")
        set_font(run_province, font_size=12)

        for title, url in policies:
            p_item = doc.add_paragraph(style="List Bullet 2")
            add_hyperlink(p_item, url, title)
            if p_item.runs:
                set_font(p_item.runs[0], font_size=11)

    # 法律法规及合规资讯
    h_legal = doc.add_heading("法律法规及合规资讯", level=1)
    set_heading_font(h_legal)

    if legal_text:
        for para in legal_text.splitlines():
            p = doc.add_paragraph(para.strip())
            run = p.runs[0] if p.runs else p.add_run()
            set_font(run, font_name="微软雅黑", font_size=11)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    else:
        p = doc.add_paragraph("无相关内容。")
        run = p.runs[0]
        set_font(run, font_name="微软雅黑", font_size=11)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 空一行
    doc.add_paragraph()

    # 分割线
    p_split = doc.add_paragraph("— — — — — — — — — —")
    p_split.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if p_split.runs:
        set_font(p_split.runs[0], font_size=10)
        p_split.runs[0].font.color.rgb = RGBColor(150, 150, 150)

    # 个人项目署名（不涉及版权声明，仅标注来源）
    p_sign = doc.add_paragraph()
    run_sign = p_sign.add_run(
        f"本日报由 Policy Reporter 个人学习项目自动生成 · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} 生成"
    )
    set_font(run_sign, font_size=9)
    run_sign.font.color.rgb = RGBColor(150, 150, 150)
    p_sign.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_disclaim = doc.add_paragraph()
    run_disclaim = p_disclaim.add_run("内容仅供个人学习与研究参考，请以官方发布原文为准。")
    set_font(run_disclaim, font_size=9)
    run_disclaim.font.color.rgb = RGBColor(150, 150, 150)
    p_disclaim.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(output_stream)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_policies(request):
    date_str = request.query_params.get('date')
    central_qs = CentralPolicy.objects.all()
    local_qs = LocalPolicy.objects.all()
    if date_str:
        try:
            central_qs = central_qs.filter(publish_time__date=date_str)
            local_qs = local_qs.filter(publish_time__date=date_str)
        except (ValueError, TypeError):
            pass
    central = list(central_qs.values('id', 'title', 'type', 'publish_time', 'source_url'))
    local = list(local_qs.values('id', 'title', 'province', 'publish_time', 'source_url'))
    for item in central:
        item['source'] = "central"
    for item in local:
        item['source'] = "local"
    return Response({'central': central, 'local': local})



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_policies(request):
    selected = request.data.get('selected_ids', [])
    legal_text = request.data.get('legal_text', '').strip()
    report_date = request.data.get('date')  # 前端 selectedDate，用于标题日期

    central_ids = [i['id'] for i in selected if i['source'] == "central"]
    local_ids = [i['id'] for i in selected if i['source'] == "local"]

    central = CentralPolicy.objects.filter(id__in=central_ids).values_list('title', 'content', 'type', 'source_url')
    local = LocalPolicy.objects.filter(id__in=local_ids).values_list('title', 'content', 'province', 'source_url')

    doc_io = BytesIO()
    generate_docx(central, local, legal_text, doc_io, report_date=report_date)
    doc_io.seek(0)
    return HttpResponse(doc_io.read(),
                        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        headers={'Content-Disposition': 'attachment; filename="政策日报.docx"'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_policy_counts(request):
    central_count = CentralPolicy.objects.count()
    local_count = LocalPolicy.objects.count()
    return Response({
        "central_count": central_count,
        "local_count": local_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """返回当前登录用户信息"""
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
    })
