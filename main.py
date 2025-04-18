from astrbot.api.all import *
from datetime import datetime, timedelta
import random
import os
import re
import json
import requests


# 设置插件主目录
PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_AnimeWife')
os.makedirs(PLUGIN_DIR, exist_ok=True)

# 配置文件目录
CONFIG_DIR = os.path.join(PLUGIN_DIR, 'config')
os.makedirs(CONFIG_DIR, exist_ok=True)

# 本地图片目录
IMG_DIR = os.path.join(PLUGIN_DIR, 'img', 'wife')
os.makedirs(IMG_DIR, exist_ok=True)

# NTR 状态文件路径
NTR_STATUS_FILE = os.path.join(CONFIG_DIR, 'ntr_status.json')

# 换老婆记录文件路径
MAX_CHANGES_PER_DAY = 3  # 每天最多换3次
CHANGE_RECORDS_FILE = os.path.join(CONFIG_DIR, 'change_records.json')

# 图片的基础 URL
IMAGE_BASE_URL = 'http://127.0.0.1:7788/?/img/'


# 新增函数：获取上海时区当日日期
def get_today():
    utc_now = datetime.utcnow()
    shanghai_time = utc_now + timedelta(hours=8)
    return shanghai_time.date().isoformat()


# 载入 NTR 状态
def load_ntr_statuses():
    global ntr_statuses
    if not os.path.exists(NTR_STATUS_FILE):
        with open(NTR_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        ntr_statuses = {}
    else:
        with open(NTR_STATUS_FILE, 'r', encoding='utf-8') as f:
            ntr_statuses = json.load(f)


# 载入换老婆记录
def load_change_records():
    global change_records
    if os.path.exists(CHANGE_RECORDS_FILE):
        with open(CHANGE_RECORDS_FILE, 'r', encoding='utf-8') as f:
            old_records = json.load(f)
            # 数据格式转换
            change_records = {}
            for group_id, users in old_records.items():
                change_records[group_id] = {}
                for user_id, record in users.items():
                    if isinstance(record, str):  # 旧格式（仅日期）
                        change_records[group_id][user_id] = {
                            'date': record,
                            'count': 1
                        }
                    else:  # 新格式（带次数）
                        change_records[group_id][user_id] = record
    else:
        change_records = {}


# 初始化加载数据
load_ntr_statuses()
load_change_records()


def save_ntr_statuses():
    with open(NTR_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(ntr_statuses, f, ensure_ascii=False, indent=4)


def save_change_records():
    with open(CHANGE_RECORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(change_records, f, ensure_ascii=False, indent=4)


@register("wife_plugin", "monbed", "群二次元老婆插件", "1.1.0", "https://github.com/monbed/astrbot_plugin_AnimeWifeX")
class WifePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.commands = {
            "抽老婆": self.animewife,
            "牛老婆": self.ntr_wife,
            "查老婆": self.search_wife,
            "切换ntr开关状态": self.switch_ntr,
            "换老婆": self.change_wife, # 新增换老婆命令
            "重置牛": self.reset_ntr  # 新增重置牛老婆命令
        }
        self.admins = self.load_admins()

    def load_admins(self):
        try:
            with open(os.path.join('data', 'cmd_config.json'), 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
                return config.get('admins_id', [])
        except Exception as e:
            self.context.logger.error(f"加载管理员列表失败: {str(e)}")
            return []

    def parse_at_target(self, event):
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event):
        target_id = self.parse_at_target(event)
        if target_id:
            return target_id
        msg = event.message_str.strip()
        if msg.startswith("牛老婆") or msg.startswith("查老婆"):
            target_name = msg[len(msg.split()[0]):].strip()
            if target_name:
                group_id = str(event.message_obj.group_id)
                config = load_group_config(group_id)
                if config:
                    for user_id, user_data in config.items():
                        try:
                            nick_name = event.get_sender_name()
                            if re.search(re.escape(target_name), nick_name, re.IGNORECASE):
                                return user_id
                        except Exception as e:
                            self.context.logger.error(f'获取群成员信息出错: {e}')
        return None

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        if not hasattr(event.message_obj, "group_id"):
            return

        group_id = event.message_obj.group_id
        message_str = event.message_str.strip()

        for command, func in self.commands.items():
            if command in message_str:
                async for result in func(event):
                    yield result
                break

    async def animewife(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            return

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID，请检查消息事件对象。')
            return

        wife_name = None
        today = get_today()
        config = load_group_config(group_id)

        if config and user_id in config:
            if config[user_id][1] == today:
                wife_name = config[user_id][0]
            else:
                del config[user_id]

        if wife_name is None:
            if config:
                for record_id in list(config):
                    if config[record_id][1] != today:
                        del config[record_id]
            local_images = os.listdir(IMG_DIR)
            if local_images:
                wife_name = random.choice(local_images)
            else:
                try:
                    response = requests.get(IMAGE_BASE_URL)
                    if response.status_code == 200:
                        image_list = response.text.splitlines()
                        wife_name = random.choice(image_list)
                    else:
                        yield event.plain_result('无法获取图片列表，请稍后再试。')
                        return
                except Exception as e:
                    yield event.plain_result(f'获取图片时发生错误: {str(e)}')
                    return

        name = wife_name.split('.')[0]
        text_message = f'{nickname}，你今天的二次元老婆是{name}哒~'

        if os.path.exists(os.path.join(IMG_DIR, wife_name)):
            image_path = os.path.join(IMG_DIR, wife_name)
            chain = [
                Plain(text_message),
                Image.fromFileSystem(image_path)
            ]
        else:
            image_url = IMAGE_BASE_URL + wife_name
            chain = [
                Plain(text_message),
                Image.fromURL(image_url)
            ]

        try:
            yield event.chain_result(chain)
        except Exception as e:
            self.context.logger.error(f'发送图片错误: {type(e)}')
            yield event.plain_result(text_message)

        write_group_config(group_id, user_id, wife_name, get_today(), nickname, config)

    # 每人每天可牛老婆次数
    _ntr_max = 3
    ntr_lmt = {}  # 结构改为 {user_id: {'date': 'YYYY-MM-DD', 'count': int}}
    ntr_max_notice = f'每日最多{_ntr_max}次，明天再来~'
    ntr_possibility = 0.20
    ntr_statuses = {}

    async def ntr_wife(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result('该功能仅支持群聊。')
            return

        if not ntr_statuses.get(str(group_id), True):
            yield event.plain_result('牛老婆功能未开启！')
            return

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID。')
            return

        today = get_today()  # 获取当前日期
        # 初始化或重置次数
        if user_id not in ntr_lmt or ntr_lmt[user_id].get('date') != today:
            ntr_lmt[user_id] = {'date': today, 'count': 0}

        current_count = ntr_lmt[user_id]['count']
        if current_count >= _ntr_max:
            yield event.plain_result(f'{nickname}，{ntr_max_notice}')
            return

        target_id = self.parse_target(event)
        if not target_id:
            yield event.plain_result(f'{nickname}，请指定目标')
            return

        if user_id == target_id:
            yield event.plain_result(f'{nickname}，不能牛自己')
            return

        config = load_group_config(group_id)
        if not config:
            yield event.plain_result('没有婚姻登记信息')
            return

        if target_id not in config:
            yield event.plain_result('对方没有老婆')
            return

        today = get_today()
        if config[target_id][1] != today:
            yield event.plain_result('对方老婆已过期')
            return

        # 增加牛次数
        ntr_lmt[user_id]['count'] += 1

        if random.random() < ntr_possibility:
            target_wife = config[target_id][0]
            del config[target_id]
            config.pop(user_id, None)
            write_group_config(group_id, user_id, target_wife, today, nickname, config)
            yield event.plain_result(f'{nickname}，牛老婆成功！')
        else:
            remaining = _ntr_max - ntr_lmt[user_id]['count']
            yield event.plain_result(
                f'{nickname}，失败！剩余次数{remaining}')

    async def search_wife(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result('该功能仅支持群聊。')
            return

        target_id = self.parse_target(event)
        today = get_today()

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID。')
            return

        target_id = target_id or user_id

        config = load_group_config(group_id)
        if not config:
            yield event.plain_result('没有登记信息！')
            return

        if target_id not in config:
            yield event.plain_result('没有找到信息！')
            return

        if config[target_id][1] != today:
            yield event.plain_result('老婆已过期')
            return

        wife_name = config[target_id][0]
        name = wife_name.split('.')[0]
        target_nickname = config.get(target_id, [None, None, target_id])[2]

        text_message = f'{target_nickname}的老婆是{name}~'

        if os.path.exists(os.path.join(IMG_DIR, wife_name)):
            image_path = os.path.join(IMG_DIR, wife_name)
            chain = [
                Plain(text_message),
                Image.fromFileSystem(image_path)
            ]
        else:
            image_url = IMAGE_BASE_URL + wife_name
            chain = [
                Plain(text_message),
                Image.fromURL(image_url)
            ]

        try:
            yield event.chain_result(chain)
        except Exception as e:
            self.context.logger.error(f'发送图片错误: {type(e)}')
            yield event.plain_result(text_message)

    async def switch_ntr(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result('该功能仅支持群聊。')
            return

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID。')
            return

        if user_id not in self.admins:
            yield event.plain_result(f'{nickname}，无权限')
            return

        ntr_statuses[str(group_id)] = not ntr_statuses.get(str(group_id), False)
        save_ntr_statuses()
        load_ntr_statuses()
        status_text = '开启' if ntr_statuses[str(group_id)] else '关闭'
        yield event.plain_result(f'{nickname}，NTR已{status_text}')

    async def change_wife(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result('该功能仅支持群聊。')
            return

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID。')
            return

        today = get_today()
        group_id_str = str(group_id)
        user_id_str = str(user_id)

        config = load_group_config(group_id)
        
        # 获取当前记录
        current_record = change_records.get(group_id_str, {}).get(user_id_str, {})
        if current_record.get('date') == today:
            if current_record['count'] >= MAX_CHANGES_PER_DAY:
                yield event.plain_result(
                    f'{nickname}，今天已经换过{MAX_CHANGES_PER_DAY}次老婆啦！'
                )
                return

        # 检查是否有可重置的数据
        if not config or user_id_str not in config or config[user_id_str][1] != today:
            yield event.plain_result(f'{nickname}，今天还没有老婆可以换哦！')
            return

        # 删除原有记录
        del config[user_id_str]
        config_file = os.path.join(CONFIG_DIR, f'{group_id}.json')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False)

        # 更新换老婆记录
        if group_id_str not in change_records:
            change_records[group_id_str] = {}
        
        # 初始化或更新记录
        if change_records[group_id_str].get(user_id_str, {}).get('date') != today:
            change_records[group_id_str][user_id_str] = {
                'date': today,
                'count': 1
            }
        else:
            change_records[group_id_str][user_id_str]['count'] += 1
        
        save_change_records()

        # 直接触发抽老婆流程
        async for result in self.animewife(event):
            yield result
            
    async def reset_ntr(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result('该功能仅支持群聊。')
            return

        try:
            user_id = str(event.get_sender_id())
            nickname = event.get_sender_name()
        except AttributeError:
            yield event.plain_result('无法获取用户 ID。')
            return

        # 检查管理员权限
        if user_id not in self.admins:
            yield event.plain_result(f'{nickname}，无权限执行此操作。')
            return

        # 解析被@的目标用户
        target_id = self.parse_at_target(event)
        if not target_id:
            yield event.plain_result(f'{nickname}，请@要重置的用户。')
            return

        # 重置牛次数
        if target_id in ntr_lmt:
            del ntr_lmt[target_id]

        # 构造包含@用户的回复消息
        chain = [
            Plain('已重置'),
            At(qq=int(target_id)),  # 显式指定参数名并确保类型为int
            Plain('的牛老婆次数。')
        ]
        
        try:
            yield event.chain_result(chain)
        except Exception as e:
            self.context.logger.error(f'发送消息失败: {e}')
            yield event.plain_result(f'已重置用户{target_id}的牛老婆次数。')

# 加载 JSON 数据
def load_group_config(group_id: str):
    filename = os.path.join(CONFIG_DIR, f'{group_id}.json')
    try:
        with open(filename, encoding='utf8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_group_config(group_id: str, link_id: str, wife_name: str, date: str, nickname: str, config):
    config_file = os.path.join(CONFIG_DIR, f'{group_id}.json')
    if config is not None:
        config[link_id] = [wife_name, date, nickname]
    else:
        config = {link_id: [wife_name, date, nickname]}
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
