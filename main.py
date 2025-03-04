import aiohttp
import logging
from datetime import datetime
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

SEAT_EMOJI = {
    '硬座': '💺', '软座': '🪑', '硬卧': '🛏️',
    '软卧': '🛌', '无座': '🚶', '商务座': '💎',
    '一等座': '💺', '二等座': '🪑'
}

@register("train_ticket", "作者名", "智能火车票查询插件", "1.2.0")
class TrainTicketPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://api.lolimi.cn/API/hc/api.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_tickets(self, params: Dict) -> Optional[Dict]:
        """异步获取票务数据"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error(f"票务查询异常: {str(e)}", exc_info=True)
            return None

    def _build_list_message(self, trains: List) -> List[str]:
        """生成车次列表消息"""
        msg = ["🚄 找到以下车次（点击编号查看详情）："]
        for idx, train in enumerate(trains[:8], 1):
            msg.append(
                f"{idx}. {train['TrainNumber']} "
                f"{train['DepartTime']}→{train['DestTime']} "
                f"({train['TotalTime']})"
            )
        return msg

    def _build_detail_message(self, train: Dict) -> str:
        """生成车次详细信息"""
        msg = [
            f"🚂 车次：{train['TrainNumber']} ({train['TrainType']})",
            f"⏰ 时间：{train['DepartTime']} → {train['DestTime']}",
            f"⏳ 历时：{train['TotalTime']}",
            f"📍 车站：{train['Depart']} → {train['Dest']}",
            "\n🎟️ 票务信息："
        ]
        
        for seat in train.get('seats', []):
            emoji = SEAT_EMOJI.get(seat['name'], '🎫')
            status = "✅" if "充足" in seat['status'] else "⚠️" if "紧张" in seat['status'] else "❌"
            msg.append(f"{emoji} {seat['name']}: {status} ￥{seat['price']}")
        
        return "\n".join(msg)

    @filter.command("火车票")
    async def ticket_query(self, event: AstrMessageEvent):
        '''火车票查询，格式：/火车票 出发地 目的地 [日期] [类型]'''
        try:
            args = event.message_str.split()
            if len(args) < 3:
                yield CommandResult().error(
                    "❌ 参数不足！使用示例：\n"
                    "/火车票 北京 上海\n"
                    "/火车票 成都 重庆 2023-12-25 高铁"
                )
                return

            # 解析参数
            departure = args
            arrival = args
            date = args if len(args) >=4 else datetime.now().strftime("%Y-%m-%d")
            train_type = args if len(args) >=5 else "高铁"

            # 第一阶段：查询车次列表
            yield CommandResult().message(f"🔍 正在搜索 {departure} → {arrival} 的{train_type}信息...")
            
            params = {
                "departure": departure,
                "arrival": arrival,
                "date": date,
                "form": train_type,
                "type": "json"
            }
            
            result = await self.fetch_tickets(params)
            if not result or result.get("code") != "200":
                yield CommandResult().error("😢 查询失败，可能铁轨被小动物占领了～")
                return

            trains = result.get("data", [])
            if not trains:
                yield CommandResult().message("🤷 没有找到符合条件的列车呢～")
                return

            # 第二阶段：发送车次列表
            list_msg = self._build_list_message(trains)
            yield CommandResult().message("\n".join(list_msg))
            
            # 第三阶段：等待用户选择
            yield CommandResult().message("💡 请回复编号查看详情（输入1-8）：")

        except Exception as e:
            logger.error(f"车次查询异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 票务查询服务暂时不可用")

    @filter.on_message(regex=r"^[1-8]$")
    async def handle_choice(self, event: AstrMessageEvent):
        """处理车次选择"""
        try:
            choice = int(event.message_str.strip())
            trains = self._get_cached_data(event.user_id)  # 假设有缓存机制
            
            if 1 <= choice <= len(trains):
                detail = self._build_detail_message(trains[choice-1])
                yield CommandResult().message(detail)
            else:
                yield CommandResult().error("⚠️ 请输入有效编号哦～")
                
        except Exception as e:
            logger.error(f"详情查询异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 详情查询失败")
