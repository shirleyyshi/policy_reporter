#!/bin/bash
# 测试政府网站从新加坡服务器的可达性
# 用法：bash scripts/test_sites.sh

echo "=== 测试政府网站可达性 ==="
echo ""

sites=(
    "财政部|https://www.mof.gov.cn/"
    "国家税务总局|http://www.chinatax.gov.cn/"
    "中国人民银行|http://www.pbc.gov.cn/"
    "商务部|http://www.mofcom.gov.cn/"
    "广州市财政局|https://czj.gz.gov.cn/"
    "广东省税务局|http://guangdong.chinatax.gov.cn/"
    "广东省地方金融局|https://www.gdjr.gov.cn/"
    "广东省商务厅|http://com.gd.gov.cn/"
)

for site in "${sites[@]}"; do
    name="${site%%|*}"
    url="${site##*|}"
    echo -n "[$name] "
    # -s 静默，-o /dev/null 丢弃内容，-w 打印状态码和耗时，--max-time 10 秒超时
    result=$(curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 10 -L "$url" 2>&1)
    code=$(echo "$result" | awk '{print $1}')
    time=$(echo "$result" | awk '{print $2}')

    if [ "$code" = "200" ]; then
        echo "[OK] $code  ${time}"
    elif [ "$code" = "000" ]; then
        echo "[FAIL] 超时或无法连接"
    else
        echo "[WARN] HTTP $code  ${time}"
    fi
done

echo ""
echo "=== 测试完成 ==="
echo ""
echo "说明："
echo "  [OK]   200 - 可正常访问"
echo "  [WARN] 非200状态码 - 可能需要调XPath或换URL"
echo "  [FAIL] 超时 - 地域限制，需换站"
echo ""
echo "清除本脚本：rm scripts/test_sites.sh"
