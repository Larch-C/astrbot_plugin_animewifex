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

# NTR 功能状态文件
NTR_STATUS_FILE = os.path.join(CONFIG_DIR, 'ntr_status.json')
# NTR 次数记录文件
NTR_RECORDS_FILE = os.path.join(CONFIG_DIR, 'ntr_records.json')
# 换老婆记录文件
CHANGE_RECORDS_FILE = os.path.join(CONFIG_DIR, 'change_records.json')

# 每人每天可牛老婆次数
_NTR_MAX = 3
# 每天换老婆最大次数
_MAX_CHANGES_PER_DAY = 3
# NTR 成功概率
ntr_possibility = 0.20
# 提示文本
NTR_NOTICE = f'每日最多{_NTR_MAX}次，明天再来~'
IMAGE_BASE_URL = 'http://127.0.0.1:7788/?/img/'

# -------- 工具函数 --------
def get_today():
    """获取当前上海时区日期字符串"""
    utc_now = datetime.utcnow()
    return (utc_now + timedelta(hours=8)).date().isoformat()


def load_json(path):
    """安全加载 JSON 文件"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_json(path, data):
    """保存数据到 JSON 文件"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# NTR 状态管理
ntr_statuses = {}
def load_ntr_statuses():
    global ntr_statuses
    ntr_statuses = load_json(NTR_STATUS_FILE)

def save_ntr_statuses():
    save_json(NTR_STATUS_FILE, ntr_statuses)

# NTR 次数管理
ntr_records = {}
def load_ntr_records():
    global ntr_records
    ntr_records = load_json(NTR_RECORDS_FILE)

def save_ntr_records():
    save_json(NTR_RECORDS_FILE, ntr_records)

# 换老婆记录管理
change_records = {}
def load_change_records():
    global change_records
    raw = load_json(CHANGE_RECORDS_FILE)
    # 兼容旧格式
    change_records.clear()
    for gid, users in raw.items():
        change_records[gid] = {}
        for uid, rec in users.items():
            if isinstance(rec, str):
                change_records[gid][uid] = {'date': rec, 'count': 1}
            else:
                change_records[gid][uid] = rec

def save_change_records():
    save_json(CHANGE_RECORDS_FILE, change_records)

# 群配置存取
def load_group_config(group_id: str):
    path = os.path.join(CONFIG_DIR, f'{group_id}.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_group_config(group_id: str, user_id: str, wife_name: str, date: str, nickname: str, config: dict):
    config[user_id] = [wife_name, date, nickname]
    path = os.path.join(CONFIG_DIR, f'{group_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# 初始化数据
load_ntr_statuses()
load_ntr_records()
load_change_records()

@register("wife_plugin", "monbed", "群二次元老婆插件", "1.2.0", "https://github.com/monbed/astrbot_plugin_AnimeWifeX")
class WifePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.commands = {
            "抽老婆": self.animewife,
            "牛老婆": self.ntr_wife,
            "查老婆": self.search_wife,
            "切换ntr开关状态": self.switch_ntr,
            "换老婆": self.change_wife,
            "重置牛": self.reset_ntr
        }
        self.admins = self.load_admins()

    def load_admins(self):
        path = os.path.join('data', 'cmd_config.json')
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                cfg = json.load(f)
                return cfg.get('admins_id', [])
        except:
            return []

    def parse_at_target(self, event):
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event):
        target = self.parse_at_target(event)
        if target:
            return target
        msg = event.message_str.strip()
        if msg.startswith("牛老婆") or msg.startswith("查老婆"):
            name = msg.split(maxsplit=1)[-1]
            if name:
                group_id = str(event.message_obj.group_id)
                cfg = load_group_config(group_id)
                for uid, data in cfg.items():
                    nick = event.get_sender_name()
                    if nick and re.search(re.escape(name), nick, re.IGNORECASE):
                        return uid
        return None

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        if not hasattr(event.message_obj, 'group_id'):
            return
        text = event.message_str.strip()
        for cmd, func in self.commands.items():
            if text.startswith(cmd):
                async for res in func(event):
                    yield res
                break

    async def animewife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        cfg = load_group_config(gid)

        # 检索或随机抽取
        if cfg.get(uid, [None, ''])[1] != today:
            if uid in cfg:
                del cfg[uid]
            local_imgs = os.listdir(IMG_DIR)
            if local_imgs:
                img = random.choice(local_imgs)
            else:
                try:
                    resp = requests.get(IMAGE_BASE_URL)
                    img = random.choice(resp.text.splitlines())
                except:
                    yield event.plain_result('获取图片失败')
                    return
            cfg[uid] = [img, today, nick]
            write_group_config(gid, uid, img, today, nick, cfg)
        else:
            img = cfg[uid][0]

        name = os.path.splitext(img)[0]
        text = f'{nick}，你今天的二次元老婆是{name}哒~'
        path = os.path.join(IMG_DIR, img)
        if os.path.exists(path):
            chain = [Plain(text), Image.fromFileSystem(path)]
        else:
            chain = [Plain(text), Image.fromURL(IMAGE_BASE_URL + img)]
        try:
            yield event.chain_result(chain)
        except:
            yield event.plain_result(text)

    async def ntr_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        if not ntr_statuses.get(gid, True):
            yield event.plain_result('牛老婆功能未开启！'); return
        uid = str(event.get_sender_id()); nick = event.get_sender_name(); today = get_today()

        # 确保记录结构
        grp = ntr_records.setdefault(gid, {})
        rec = grp.get(uid, {'date': today, 'count': 0})
        if rec['date'] != today:
            rec = {'date': today, 'count': 0}
        if rec['count'] >= _NTR_MAX:
            yield event.plain_result(f'{nick}，{NTR_NOTICE}'); return

        tid = self.parse_target(event)
        if not tid or tid == uid:
            msg = '请指定目标' if not tid else '不能牛自己'
            yield event.plain_result(f'{nick}，{msg}'); return

        cfg = load_group_config(gid)
        if tid not in cfg or cfg[tid][1] != today:
            yield event.plain_result('对方没有可牛的老婆'); return

        # 增加尝试
        rec['count'] += 1; grp[uid] = rec; save_ntr_records()
        if random.random() < ntr_possibility:
            wife = cfg[tid][0]
            del cfg[tid]; cfg.pop(uid, None)
            write_group_config(gid, uid, wife, today, nick, cfg)
            yield event.plain_result(f'{nick}，牛老婆成功！')
        else:
            rem = _NTR_MAX - rec['count']
            yield event.plain_result(f'{nick}，失败！剩余次数{rem}')

    async def search_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id); tid = self.parse_target(event) or str(event.get_sender_id()); today = get_today()
        cfg = load_group_config(gid)
        if tid not in cfg or cfg[tid][1] != today:
            yield event.plain_result('没有找到有效的老婆信息'); return
        img = cfg[tid][0]; name = os.path.splitext(img)[0]; owner = cfg[tid][2]
        text = f'{owner}的老婆是{name}~'
        path = os.path.join(IMG_DIR, img)
        chain = [Plain(text), Image.fromFileSystem(path) if os.path.exists(path) else Image.fromURL(IMAGE_BASE_URL+img)]
        try: yield event.chain_result(chain)
        except: yield event.plain_result(text)

    async def switch_ntr(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id); uid = str(event.get_sender_id()); nick = event.get_sender_name()
        if uid not in self.admins: yield event.plain_result(f'{nick}，无权限'); return
        ntr_statuses[gid] = not ntr_statuses.get(gid, False)
        save_ntr_statuses(); load_ntr_statuses()
        state = '开启' if ntr_statuses[gid] else '关闭'
        yield event.plain_result(f'{nick}，NTR已{state}')

    async def change_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id); uid = str(event.get_sender_id()); nick = event.get_sender_name(); today = get_today()
        cfg = load_group_config(gid)
        recs = change_records.setdefault(gid, {})
        rec = recs.get(uid, {'date':'','count':0})
        if rec['date'] == today and rec['count'] >= _MAX_CHANGES_PER_DAY:
            yield event.plain_result(f'{nick}，今天已经换过{_MAX_CHANGES_PER_DAY}次老婆啦！'); return
        if uid not in cfg or cfg[uid][1] != today:
            yield event.plain_result(f'{nick}，今天还没有老婆可以换哦！'); return
        # 删除旧记录
        del cfg[uid]
        with open(os.path.join(CONFIG_DIR,f'{gid}.json'),'w',encoding='utf-8') as f:
            json.dump(cfg,f,ensure_ascii=False,indent=4)
        # 更新换老婆记录
        if rec['date'] != today:
            rec = {'date': today, 'count': 1}
        else:
            rec['count'] += 1
        recs[uid] = rec; save_change_records()
        # 重新抽老婆
        async for res in self.animewife(event): yield res

    async def reset_ntr(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()

        # -------- 新增：每日重置次数记录 --------
        RESET_FILE = os.path.join(CONFIG_DIR, 'reset_ntr_records.json')
        # 载入或初始化
        try:
            reset_records = load_json(RESET_FILE)
        except:
            reset_records = {}
        grp = reset_records.setdefault(gid, {})
        rec = grp.get(uid, {'date': today, 'count': 0})
        # 如果不是同一天，重置计数
        if rec.get('date') != today:
            rec = {'date': today, 'count': 0}
        # 限制每天使用两次
        if rec['count'] >= 2:
            yield event.plain_result(f'{nick}，今天已使用过2次重置牛功能，明天再来~')
            return
        # 更新时间并保存
        rec['count'] += 1
        grp[uid] = rec
        save_json(RESET_FILE, reset_records)
        # ---------------------------------------

        # 解析目标
        tid = self.parse_at_target(event) or uid

        # 30% 成功率
        if random.random() < 0.3:
            # 成功：清除目标的 NTR 记录
            if gid in ntr_records and tid in ntr_records[gid]:
                del ntr_records[gid][tid]
                save_ntr_records()
            # 回复成功
            chain = [
                Plain('已重置'),
                At(qq=int(tid)),
                Plain('的牛老婆次数。')
            ]
            yield event.chain_result(chain)
        else:
            # 失败：禁言 300 秒
            client = event.bot
            try:
                await client.set_group_ban(
                    group_id=int(gid),
                    user_id=int(uid),
                    duration=300
                )
            except:
                pass
            yield event.plain_result(f'{nick}，重置牛失败，已被禁言300秒。')
