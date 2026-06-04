# main.py
import json
import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain

@register(
    "astrbot_plugin_qq_forward",
    "forward",
    "QQ群消息转发插件",
    "1.0.0",
    "https://github.com/xxx/astrbot_plugin_qq_forward"
)
class QQForwardPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_file = "data/qq_forward_config.json"
        self.config = self._load_config()
    
    def _load_config(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"forward_rules": {}, "enabled": True}
    
    def _save_config(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    @filter.command("add_forward")
    async def add_forward(self, event: AstrMessageEvent):
        """添加转发规则：/add_forward 源群ID 目标群ID"""
        args = event.message_str.strip().split()
        if len(args) != 3:
            yield event.plain_result("用法：/add_forward 源群ID 目标群ID")
            return
        source, target = args[1], args[2]
        if source not in self.config["forward_rules"]:
            self.config["forward_rules"][source] = {"target_groups": []}
        if target not in self.config["forward_rules"][source]["target_groups"]:
            self.config["forward_rules"][source]["target_groups"].append(target)
        self._save_config()
        yield event.plain_result(f"✅ 已添加：{source} → {target}")
    
    @filter.command("del_forward")
    async def del_forward(self, event: AstrMessageEvent):
        """删除转发规则：/del_forward 源群ID 目标群ID"""
        args = event.message_str.strip().split()
        if len(args) != 3:
            yield event.plain_result("用法：/del_forward 源群ID 目标群ID")
            return
        source, target = args[1], args[2]
        if source in self.config["forward_rules"]:
            targets = self.config["forward_rules"][source]["target_groups"]
            if target in targets:
                targets.remove(target)
                if not targets:
                    del self.config["forward_rules"][source]
                self._save_config()
                yield event.plain_result(f"✅ 已删除：{source} → {target}")
                return
        yield event.plain_result("❌ 规则不存在")
    
    @filter.command("list_forward")
    async def list_forward(self, event: AstrMessageEvent):
        if not self.config["forward_rules"]:
            yield event.plain_result("暂无转发规则")
            return
        result = "转发规则：\n"
        for source, rule in self.config["forward_rules"].items():
            result += f"{source} → {', '.join(rule['target_groups'])}\n"
        yield event.plain_result(result)
    
    @filter.command("forward_on")
    async def forward_on(self, event: AstrMessageEvent):
        self.config["enabled"] = True
        self._save_config()
        yield event.plain_result("✅ 转发已开启")
    
    @filter.command("forward_off")
    async def forward_off(self, event: AstrMessageEvent):
        self.config["enabled"] = False
        self._save_config()
        yield event.plain_result("⏸️ 转发已关闭")
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_message(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return
        
        # 只处理群消息
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            return
        
        source_group = str(event.message_obj.group_id)
        
        # 检查是否有转发规则
        if source_group not in self.config["forward_rules"]:
            return
        
        targets = self.config["forward_rules"][source_group]["target_groups"]
        if not targets:
            return
        
        # 构建转发消息
        sender = event.get_sender_name()
        content = event.message_str
        forward_msg = f"【转发】{sender}：{content}"
        
        # 转发到每个目标群
        for target in targets:
            try:
                # 关键：使用字符串ID直接发送
                await self.context.send_message(
                    str(target),  # 确保是字符串
                    [Plain(forward_msg)],
                    True  # True=群聊
                )
                logger.info(f"转发成功：{source_group} → {target}")
            except Exception as e:
                logger.error(f"转发失败：{source_group} → {target}，错误：{e}")
