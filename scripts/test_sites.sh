#!/bin/bash
# 测试深圳 4 个政府站点从新加坡服务器的可达性
# 中央 4 站(财政部/税务总局/央行/商务部)已确认可达，本脚本只测地方
# 用法：bash scripts/test_sites.sh

echo "=== 测试深圳地方站点可达性 ==="
echo ""

sites=(
    "深圳市财政局|https://szfb.sz.gov.cn/"
    "深圳市税务局|https://shenzhen.chinatax.gov.cn/"
    "深圳市地方金融局|https://jr.sz.gov.cn/"
    "深圳市商务局|https://commerce.sz.gov.cn/"
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
