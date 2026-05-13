#!/usr/bin/env python3
"""
Binance Square K线卡片发布工具
使用内部API获取K线数据，生成Highcharts SVG卡片并发布到Square
"""

import json
import requests
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import subprocess


class BinanceSquareKlinePoster:
    """带K线卡片的Binance Square发布器"""

    def __init__(self, cookies_file: str = "~/.binance_cookies.json"):
        self.base_url = "https://www.binance.com"
        self.api_base = f"{self.base_url}/bapi/composite/v3/friendly/pgc"
        self.cookies_file = Path(cookies_file).expanduser()
        self.session = requests.Session()
        self.session.headers.update({
            "clienttype": "web",
            "lang": "zh-CN",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

        # 加载Cookie
        self._load_cookies()

    def _load_cookies(self):
        """从文件加载Cookie"""
        if self.cookies_file.exists():
            with open(self.cookies_file) as f:
                cookies = json.load(f)

                # 格式转换: [{name, value, ...}] -> {name: value}
                if isinstance(cookies, list):
                    cookie_dict = {}
                    for cookie in cookies:
                        if "name" in cookie and "value" in cookie:
                            cookie_dict[cookie["name"]] = cookie["value"]
                    self.session.cookies.update(cookie_dict)
                else:
                    self.session.cookies.update(cookies)

            print(f"✓ 已加载Cookie: {self.cookies_file}")
        else:
            print(f"⚠ Cookie文件不存在: {self.cookies_file}")
            print("  请先手动登录Binance并导出Cookie到此文件")

    def get_hot_tokens(self, limit: int = 5) -> List[Dict]:
        """
        获取热门币种 (优先从缓存,回退到主流币种)
        """
        cache_file = Path("/Users/aixx/.openclaw/workspace/cache/binance_crypto_hot_tokens.json")

        # 回退列表: 主流币种 (需加USDT后缀)
        fallback_tokens = [
            {"symbol": "BTCUSDT", "name": "Bitcoin"},
            {"symbol": "ETHUSDT", "name": "Ethereum"},
            {"symbol": "BNBUSDT", "name": "BNB"},
            {"symbol": "SOLUSDT", "name": "Solana"},
            {"symbol": "XRPUSDT", "name": "Ripple"}
        ]

        if not cache_file.exists():
            print(f"⚠ 缓存文件不存在,使用主流币种")
            return fallback_tokens[:limit]

        with open(cache_file) as f:
            data = json.load(f)

        # 适配新的数据格式
        tokens = data.get("tokens", [])

        # 过滤掉非主流币种(避免API返回404)
        # 只保留 symbol 在币安主站有交易对的
        mainstream_symbols = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "MATIC", "LINK"]

        valid_tokens = []
        for token in tokens[:limit * 2]:  # 取多一点的候选
            symbol = token.get("symbol", "").upper()
            # 检查是否是主流币种(去除USDT后缀)
            base_symbol = symbol.replace("USDT", "").replace("USD", "").replace("BUSD", "")
            if base_symbol in mainstream_symbols:
                valid_tokens.append({
                    "symbol": f"{base_symbol}USDT",  # 标准化交易对
                    "name": token.get("symbol", ""),
                    "change": token.get("percentChange24h", 0),
                    "source": token.get("source", "unknown")
                })

                if len(valid_tokens) >= limit:
                    break

        # 如果没有找到主流币种,使用回退列表
        if not valid_tokens:
            print(f"⚠ 缓存中无主流币种,使用回退列表")
            return fallback_tokens[:limit]

        print(f"✓ 筛选出 {len(valid_tokens)} 个主流币种")
        return valid_tokens

    def fetch_kline_data(self, symbol: str, days: int = 30) -> Dict:
        """
        获取币种K线数据 (使用标准API)
        注意：标准API不提供24小时迷你图数据，需要用内部API

        Args:
            symbol: 币种符号，如 "BTCUSDT"
            days: 获取多少天的数据
        """
        # 尝试使用标准K线API获取数据
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "limit": min(days * 24, 1000)  # 最多1000小时
        }

        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            klines = resp.json()

            # 转换为内部API格式
            price_change_chart = []
            for k in klines[-24:]:  # 只取最近24小时
                price_change_chart.append({
                    "dateTime": k[0],  # Open time
                    "value": float(k[4])  # Close price
                })

            # 计算涨跌幅
            if len(price_change_chart) >= 2:
                start_price = price_change_chart[0]["value"]
                end_price = price_change_chart[-1]["value"]
                price_change = ((end_price - start_price) / start_price) * 100
            else:
                price_change = 0

            return {
                "symbol": symbol,
                "price": str(price_change_chart[-1]["value"]) if price_change_chart else "0",
                "priceChange": f"{price_change:.2f}",
                "priceChangeChart": price_change_chart
            }

        except Exception as e:
            print(f"✗ 获取K线数据失败: {e}")
            return {}

    def generate_kline_svg(self, pair_data: Dict) -> str:
        """
        生成Highcharts风格的SVG卡片

        Args:
            pair_data: 包含 symbol, price, priceChange, priceChangeChart 的数据
        """
        if not pair_data.get("priceChangeChart"):
            return ""

        chart_data = pair_data["priceChangeChart"]
        if len(chart_data) < 2:
            return ""

        # 提取价格和时间
        prices = [p["value"] for p in chart_data]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price if max_price > min_price else 1

        # 标准化到0-32像素高度 (卡片高度32px)
        height = 32
        width = 88

        # 计算点坐标
        points = []
        for i, p in enumerate(chart_data):
            x = (i / (len(chart_data) - 1)) * width
            # Y轴反转 (SVG坐标系Y向下)
            y = height - ((p["value"] - min_price) / price_range) * height * 0.8 - height * 0.1
            points.append(f"{x:.2f},{y:.2f}")

        # 确定颜色 (涨为绿,跌为红)
        price_change = float(pair_data.get("priceChange", 0))
        color = "#0ECB81" if price_change >= 0 else "#F6465D"
        color_rgba = "rgba(14, 203, 129, 0.3)" if price_change >= 0 else "rgba(246, 70, 93, 0.3)"

        # 生成曲线路径 (简化版areaspline)
        # 使用贝塞尔曲线平滑
        path_d = f"M {points[0]}"
        for i in range(1, len(points)):
            x1, y1 = points[i-1].split(",")
            x2, y2 = points[i].split(",")
            # 简单的二次贝塞尔曲线
            mid_x = (float(x1) + float(x2)) / 2
            path_d += f" Q {mid_x:.2f},{y1} {x2},{y2}"

        # 封闭区域
        path_d += f" L {width},{height} L 0,{height} Z"

        # SVG模板
        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad-{pair_data['symbol']}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{color};stop-opacity:0.6" />
      <stop offset="100%" style="stop-color:{color};stop-opacity:0.05" />
    </linearGradient>
  </defs>
  <path d="{path_d}" fill="url(#grad-{pair_data['symbol']})" stroke="{color}" stroke-width="1.5"/>
</svg>'''

        return svg

    def analyze_trend(self, kline_data: Dict) -> Dict:
        """
        分析K线数据,生成技术指标和趋势预测

        Returns:
            Dict: {
                "support": 支撑位,
                "resistance": 压力位,
                "rsi": RSI值,
                "trend": 趋势("上涨"/"下跌"/"震荡"),
                "signal": 交易信号
            }
        """
        if not kline_data.get("priceChangeChart"):
            return {}

        prices = [p["value"] for p in kline_data["priceChangeChart"]]
        if len(prices) < 2:
            return {}

        # 计算支撑/压力位 (简化版)
        min_price = min(prices)
        max_price = max(prices)
        current_price = prices[-1]

        # 简单的斐波那契回撤位
        diff = max_price - min_price
        support = min_price + diff * 0.236
        resistance = min_price + diff * 0.786

        # RSI计算 (简化版)
        gains = []
        losses = []
        for i in range(1, min(15, len(prices))):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))

        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        # 趋势判断
        price_change = float(kline_data.get("priceChange", 0))
        if price_change > 1:
            trend = "上涨"
            signal = "偏多,注意回调风险"
        elif price_change < -1:
            trend = "下跌"
            signal = "偏空,谨慎抄底"
        else:
            trend = "震荡"
            signal = "区间整理,观望为主"

        return {
            "support": support,
            "resistance": resistance,
            "rsi": rsi,
            "trend": trend,
            "signal": signal,
            "volatility": diff / min_price * 100  # 波动率百分比
        }

    def compose_post_content(self, tokens: List[Dict]) -> str:
        """
        组合发布内容 (专业版 + AI分析)

        Args:
            tokens: 热门币种列表
        """
        if not tokens:
            return "📊 今日币安热门币种行情监控\n\n暂无数据"

        lines = ["📊 币安主流币种技术分析 [24h]\n"]
        lines.append("━" * 30 + "\n")

        analysis_results = []

        for i, token in enumerate(tokens, 1):
            symbol = token.get("symbol", "UNKNOWN")

            # 获取详细K线数据
            kline_data = self.fetch_kline_data(symbol)
            if not kline_data:
                continue

            price = float(kline_data.get("price", 0))
            price_change = float(kline_data.get("priceChange", 0))

            # 技术分析
            analysis = self.analyze_trend(kline_data)
            analysis_results.append({"symbol": symbol, **analysis})

            # Emoji
            emoji = "🟢" if price_change >= 0 else "🔴"
            trend_emoji = {"上涨": "📈", "下跌": "📉", "震荡": "➡️"}

            # 格式化输出
            lines.append(f"{i}. {emoji} **{symbol}** ${price:,.2f}")
            lines.append(f"   24h: {price_change:+.2f}% | RSI: {analysis.get('rsi', 50):.0f}")
            lines.append(f"   支撑: ${analysis.get('support', 0):,.2f} | 压力: ${analysis.get('resistance', 0):,.2f}")
            lines.append(f"   {trend_emoji.get(analysis.get('trend', '震荡'), '➡️')} {analysis.get('signal', '观望')}\n")

            # 生成SVG
            svg = self.generate_kline_svg(kline_data)
            if svg:
                svg_file = Path(f"/tmp/kline_{symbol}_{datetime.now().strftime('%Y%m%d')}.svg")
                with open(svg_file, "w") as f:
                    f.write(svg)
                print(f"  ✓ 生成K线卡片: {svg_file}")

        # AI 趋势预测总结
        lines.append("\n🤖 **AI趋势预测**")
        lines.append("━" * 30)

        # 统计趋势
        uptrend = sum(1 for a in analysis_results if a.get("trend") == "上涨")
        downtrend = sum(1 for a in analysis_results if a.get("trend") == "下跌")

        if uptrend > downtrend and uptrend >= 3:
            market_view = "整体偏多市场,注意追高风险"
        elif downtrend > uptrend and downtrend >= 3:
            market_view = "整体偏空市场,建议轻仓观望"
        else:
            market_view = "市场分化严重,需精选个股"

        lines.append(f"📈 市场概况: {market_view}")
        lines.append(f"💡 建议: 严格控制仓位,设置止损止盈\n")

        lines.append("\n#币安 #技术分析 #加密货币 #行情")
        return "\n".join(lines)

    def post_to_square(self, content: str, images: Optional[List[str]] = None) -> bool:
        """
        发布到Binance Square (需要登录态)

        注意: 这一步可能需要使用Chrome DevTools自动化
        """
        print("\n📝 准备发布内容:")
        print(content)

        if images:
            print(f"\n📷 附加图片: {len(images)} 张")
            for img in images:
                print(f"  - {img}")

        print("\n⚠ 发布功能需要Web自动化支持")
        print("  建议使用 baoyu-post-to-wechat 技能的Chrome CDP方式")
        print("  或手动复制内容到Binance Square发布")

        # 保存待发布内容
        output_file = Path(f"/tmp/binance_square_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, "w") as f:
            f.write(content)

        print(f"\n✓ 内容已保存: {output_file}")
        return True

    def run(self):
        """执行完整的发布流程"""
        print("=== Binance Square K线卡片发布器 ===\n")

        # 1. 获取热门币种
        tokens = self.get_hot_tokens(limit=5)

        # 2. 组合内容
        content = self.compose_post_content(tokens)

        # 3. 发布
        self.post_to_square(content)

        print("\n✓ 执行完毕")


def main():
    poster = BinanceSquareKlinePoster()
    poster.run()


if __name__ == "__main__":
    main()
