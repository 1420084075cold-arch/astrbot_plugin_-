# main.py
import json
import os
from typing import Dict, Set

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain, Node, Nodes, Reply


@register(
    "astrbot_plugin_qq_forward",
    "your_name",
    "QQ群消息转发插件 - 支持跨群消息转发、关键词过滤",
    "1.0.0",
    "https://github.com/your/astrbot_plugin_qq_forward"
)
class QQForwardPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 数据文件路径（AstrBot data目录）
        self.data_file = os.path.join("data", "qq_forward_config.json")
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "forward_rules": {},  # {源群ID: {"target_groups": [群ID列表], "keywords": []}}
            "enabled": True
        }
    
    def _save_config(self):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    @filter.command("add_forward")
    async def add_forward_rule(self, event: AstrMessageEvent):
        """添加转发规则：/add_forward <源群ID> <目标群ID> [关键词(可选)]"""
        args = event.message_str.strip().split()
        
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/add_forward <源群ID> <目标群ID> [关键词(用|分隔)]")
            return
        
        source_group = args[1]
        target_group = args[2]
        keywords = args[3].split('|') if len(args) >= 4 else []
        
        # 初始化源群配置
        if source_group not in self.config["forward_rules"]:
            self.config["forward_rules"][source_group] = {
                "target_groups": [],
                "keywords": []
            }
        
        rule = self.config["forward_rules"][source_group]
        
        # 添加目标群（避免重复）
        if target_group not in rule["target_groups"]:
            rule["target_groups"].append(target_group)
        
        # 合并关键词
        for kw in keywords:
            if kw and kw not in rule["keywords"]:
                rule["keywords"].append(kw)
        
        self._save_config()
        
        result_msg = f"✅ 已添加转发规则：群 {source_group} → {target_group}"
        if keywords:
            result_msg += f"\n📌 关键词过滤：{'、'.join(keywords)}"
        yield event.plain_result(result_msg)
    
    @filter.command("remove_forward")
    async def remove_forward_rule(self, event: AstrMessageEvent):
        """删除转发规则：/remove_forward <源群ID> <目标群ID>"""
        args = event.message_str.strip().split()
        
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/remove_forward <源群ID> <目标群ID>")
            return
        
        source_group = args[1]
        target_group = args[2]
        
        if source_group in self.config["forward_rules"]:
            rule = self.config["forward_rules"][source_group]
            if target_group in rule["target_groups"]:
                rule["target_groups"].remove(target_group)
                
                # 如果目标群列表为空，删除整个规则
                if not rule["target_groups"]:
                    del self.config["forward_rules"][source_group]
                
                self._save_config()
                yield event.plain_result(f"✅ 已删除转发规则：群 {source_group} → {target_group}")
                return
        
        yield event.plain_result(f"❌ 未找到转发规则：群 {source_group} → {target_group}")
    
    @filter.command("list_forward")
    async def list_forward_rules(self, event: AstrMessageEvent):
        """列出所有转发规则：/list_forward"""
        if not self.config["forward_rules"]:
            yield event.plain_result("📭 当前没有配置任何转发规则")
            return
        
        result = "📋 **当前转发规则列表**\n\n"
        for source, rule in self.config["forward_rules"].items():
            targets = "、".join(rule["target_groups"])
            keywords = "、".join(rule["keywords"]) if rule["keywords"] else "无限制"
            result += f"📤 源群：{source}\n"
            result += f"   📥 目标群：{targets}\n"
            result += f"   🔑 关键词过滤：{keywords}\n\n"
        
        yield event.plain_result(result)
    
    @filter.command("forward_on")
    async def enable_forward(self, event: AstrMessageEvent):
        """启用转发功能：/forward_on"""
        self.config["enabled"] = True
        self._save_config()
        yield event.plain_result("✅ 消息转发功能已启用")
    
    @filter.command("forward_off")
    async def disable_forward(self, event: AstrMessageEvent):
        """禁用转发功能：/forward_off"""
        self.config["enabled"] = False
        self._save_config()
        yield event.plain_result("⏸️ 消息转发功能已禁用")
    
    # 监听所有群消息
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息，执行转发逻辑"""
        # 检查是否启用转发
        if not self.config.get("enabled", True):
            return
        
        # 只处理群消息（Group）
        if not event.message_obj.group_id:
            return
        
        source_group_id = str(event.message_obj.group_id)
        sender_name = event.get_sender_name()
        message_text = event.message_str
        
        # 检查是否有匹配的转发规则
        if source_group_id not in self.config["forward_rules"]:
            return
        
        rule = self.config["forward_rules"][source_group_id]
        
        # 关键词过滤
        if rule["keywords"]:
            matched = any(kw in message_text for kw in rule["keywords"])
            if not matched:
                return
        
        # 构建转发消息
        forward_text = f"📨 **[转发] 来自群 {source_group_id}**\n"
        forward_text += f"👤 **{sender_name}**：\n"
        forward_text += f"💬 {message_text}"
        
        # 如果有图片，尝试获取图片URL（可选功能）
        image_urls = []
        for comp in event.message_obj.message:
            if hasattr(comp, 'type') and comp.type == "image":
                if hasattr(comp, 'file') and comp.file:
                    image_urls.append(comp.file)
        
        # 转发到每个目标群
        for target_group in rule["target_groups"]:
            try:
                # 使用统一消息接口发送
                message_chain = [Plain(forward_text)]
                
                # 添加图片（如果有）
                for img_url in image_urls:
                    from astrbot.api.message_components import Image
                    message_chain.append(Image(file=img_url))
                
                # 发送消息到目标群
                await self.context.send_message(
                    target_group,
                    message_chain,
                    True  # 群聊消息
                )
                logger.info(f"已转发消息：{source_group_id} → {target_group}")
            except Exception as e:
                logger.error(f"转发消息失败 {source_group_id} → {target_group}: {e}")
    
    async def terminate(self):
        """插件卸载时调用"""
        logger.info("QQ转发插件已卸载")
