#!/bin/bash
# 测试 8 个热门城市 × 4 个委办局共 32 个政府站点从新加坡服务器的可达性
# 中央 4 站(财政部/税务总局/央行/商务部)已确认可达，本脚本只测地方
# 用法：bash scripts/test_sites.sh

echo "=== 测试 8 城地方站点可达性 ==="
echo ""

# 格式：城市|财政|税务|金融|商务
sites=(
    # 北京
    "北京-财政|https://czj.beijing.gov.cn/"
    "北京-税务|http://beijing.chinatax.gov.cn/"
    "北京-金融|https://jrj.beijing.gov.cn/"
    "北京-商务|https://sw.beijing.gov.cn/"
    # 上海
    "上海-财政|https://czj.sh.gov.cn/"
    "上海-税务|https://shanghai.chinatax.gov.cn/"
    "上海-金融|https://jrj.sh.gov.cn/"
    "上海-商务|http://swt.sh.gov.cn/"
    # 天津
    "天津-财政|https://czj.tj.gov.cn/"
    "天津-税务|http://tianjin.chinatax.gov.cn/"
    "天津-金融|https://jrj.tj.gov.cn/"
    "天津-商务|http://swj.tj.gov.cn/"
    # 重庆
    "重庆-财政|https://czj.cq.gov.cn/"
    "重庆-税务|http://chongqing.chinatax.gov.cn/"
    "重庆-金融|https://jrj.cq.gov.cn/"
    "重庆-商务|https://sww.cq.gov.cn/"
    # 广州
    "广州-财政|https://czj.gz.gov.cn/"
    "广州-税务|http://guangdong.chinatax.gov.cn/"
    "广州-金融|http://jrjgj.gz.gov.cn/"
    "广州-商务|http://swj.gz.gov.cn/"
    # 深圳
    "深圳-财政|https://szfb.sz.gov.cn/"
    "深圳-税务|https://shenzhen.chinatax.gov.cn/"
    "深圳-金融|https://jr.sz.gov.cn/"
    "深圳-商务|https://commerce.sz.gov.cn/"
    # 杭州
    "杭州-财政|https://czj.hangzhou.gov.cn/"
    "杭州-税务|http://zhejiang.chinatax.gov.cn/"
    "杭州-金融|https://jrj.hangzhou.gov.cn/"
    "杭州-商务|https://sww.hangzhou.gov.cn/"
    # 南京
    "南京-财政|https://czj.nanjing.gov.cn/"
    "南京-税务|http://jiangsu.chinatax.gov.cn/"
    "南京-金融|https://jrb.nanjing.gov.cn/"
    "南京-商务|https://swj.nanjing.gov.cn/"
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
