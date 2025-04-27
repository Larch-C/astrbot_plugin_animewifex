from astrbot.api.all import *
from datetime import datetime, timedelta
import random
import os
import re
import json
import aiohttp

PLUGIN_DIR = os.path.join('data', 'animewifexdata')
os.makedirs(PLUGIN_DIR, exist_ok=True)

CONFIG_DIR = os.path.join(PLUGIN_DIR, 'config')
os.makedirs(CONFIG_DIR, exist_ok=True)

IMG_DIR = os.path.join(PLUGIN_DIR, 'img', 'wife')
os.makedirs(IMG_DIR, exist_ok=True)

NTR_STATUS_FILE = os.path.join(CONFIG_DIR, 'ntr_status.json')
NTR_RECORDS_FILE = os.path.join(CONFIG_DIR, 'ntr_records.json')
CHANGE_RECORDS_FILE = os.path.join(CONFIG_DIR, 'change_records.json')
RESET_RECORDS_FILE = os.path.join(CONFIG_DIR, 'reset_ntr_records.json')


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

ntr_statuses = {}
ntr_records = {}
change_records = {}


def load_ntr_statuses():
    global ntr_statuses
    ntr_statuses = load_json(NTR_STATUS_FILE)


def save_ntr_statuses():
    save_json(NTR_STATUS_FILE, ntr_statuses)


def load_ntr_records():
    global ntr_records
    ntr_records = load_json(NTR_RECORDS_FILE)


def save_ntr_records():
    save_json(NTR_RECORDS_FILE, ntr_records)


def load_change_records():
    global change_records
    raw = load_json(CHANGE_RECORDS_FILE)
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

load_ntr_statuses()
load_ntr_records()
load_change_records()

@register("wife_plugin", "monbed", "群二次元老婆插件", "1.5.0", "https://github.com/monbed/astrbot_plugin_AnimeWifeX")
class WifePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.ntr_max = config.get('ntr_max')
        self.ntr_possibility = config.get('ntr_possibility')
        self.change_max_per_day = config.get('change_max_per_day')
        self.reset_max_uses_per_day = config.get('reset_max_uses_per_day')
        self.reset_success_rate = config.get('reset_success_rate')
        self.reset_mute_duration = config.get('reset_mute_duration')
        self.image_base_url = config.get('image_base_url')

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

        if cfg.get(uid, [None, ''])[1] != today:
            if uid in cfg:
                del cfg[uid]
            local_imgs = os.listdir(IMG_DIR)
            if local_imgs:
                img = random.choice(local_imgs)
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(self.image_base_url) as resp:
                            text = await resp.text()
                            img = random.choice(text.splitlines())
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
            chain = [Plain(text), Image.fromURL(self.image_base_url + img)]
        try:
            yield event.chain_result(chain)
        except:
            yield event.plain_result(text)

    async def ntr_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        if not ntr_statuses.get(gid, True):
            yield event.plain_result('牛老婆功能未开启！')
            return
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()

        grp = ntr_records.setdefault(gid, {})
        rec = grp.get(uid, {'date': today, 'count': 0})
        if rec['date'] != today:
            rec = {'date': today, 'count': 0}
        if rec['count'] >= self.ntr_max:
            yield event.plain_result(f'{nick}，每日最多{self.ntr_max}次，明天再来~')
            return

        tid = self.parse_target(event)
        if not tid or tid == uid:
            msg = '请指定目标' if not tid else '不能牛自己'
            yield event.plain_result(f'{nick}，{msg}')
            return

        cfg = load_group_config(gid)
        if tid not in cfg or cfg[tid][1] != today:
            yield event.plain_result('对方没有可牛的老婆')
            return

        rec['count'] += 1
        grp[uid] = rec
        save_ntr_records()
        if random.random() < self.ntr_possibility:
            wife = cfg[tid][0]
            del cfg[tid]
            cfg.pop(uid, None)
            write_group_config(gid, uid, wife, today, nick, cfg)
            yield event.plain_result(f'{nick}，牛老婆成功！')
        else:
            rem = self.ntr_max - rec['count']
            yield event.plain_result(f'{nick}，失败！剩余次数{rem}')

    async def search_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        tid = self.parse_target(event) or str(event.get_sender_id())
        today = get_today()
        cfg = load_group_config(gid)
        if tid not in cfg or cfg[tid][1] != today:
            yield event.plain_result('没有找到有效的老婆信息')
            return
        img = cfg[tid][0]
        name = os.path.splitext(img)[0]
        owner = cfg[tid][2]
        text = f'{owner}的老婆是{name}~'
        path = os.path.join(IMG_DIR, img)
        chain = [Plain(text), Image.fromFileSystem(path) if os.path.exists(path) else Image.fromURL(self.image_base_url + img)]
        try:
            yield event.chain_result(chain)
        except:
            yield event.plain_result(text)

    async def switch_ntr(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        if uid not in self.admins:
            yield event.plain_result(f'{nick}，无权限')
            return
        ntr_statuses[gid] = not ntr_statuses.get(gid, False)
        save_ntr_statuses()
        load_ntr_statuses()
        state = '开启' if ntr_statuses[gid] else '关闭'
        yield event.plain_result(f'{nick}，NTR已{state}')

    async def change_wife(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        cfg = load_group_config(gid)
        recs = change_records.setdefault(gid, {})
        rec = recs.get(uid, {'date':'','count':0})
        if rec['date'] == today and rec['count'] >= self.change_max_per_day:
            yield event.plain_result(f'{nick}，今天已经换过{self.change_max_per_day}次老婆啦！')
            return
        if uid not in cfg or cfg[uid][1] != today:
            yield event.plain_result(f'{nick}，今天还没有老婆可以换哦！')
            return
        del cfg[uid]
        with open(os.path.join(CONFIG_DIR, f'{gid}.json'), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        if rec['date'] != today:
            rec = {'date': today, 'count': 1}
        else:
            rec['count'] += 1
        recs[uid] = rec
        save_change_records()
        async for res in self.animewife(event):
            yield res

    async def reset_ntr(self, event: AstrMessageEvent):
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()

        if uid in self.admins:
            tid = self.parse_at_target(event) or uid
            if gid in ntr_records and tid in ntr_records[gid]:
                del ntr_records[gid][tid]
                save_ntr_records()
            chain = [Plain('管理员操作：已重置'), At(qq=int(tid)), Plain('的牛老婆次数。')]
            yield event.chain_result(chain)
            return

        reset_records = load_json(RESET_RECORDS_FILE)
        grp = reset_records.setdefault(gid, {})
        rec = grp.get(uid, {'date': today, 'count': 0})
        if rec.get('date') != today:
            rec = {'date': today, 'count': 0}
        if rec['count'] >= self.reset_max_uses_per_day:
            yield event.plain_result(f'{nick}，今天已使用过{self.reset_max_uses_per_day}次重置牛功能，明天再来~')
            return
        rec['count'] += 1
        grp[uid] = rec
        save_json(RESET_RECORDS_FILE, reset_records)

        tid = self.parse_at_target(event) or uid
        if random.random() < self.reset_success_rate:
            if gid in ntr_records and tid in ntr_records[gid]:
                del ntr_records[gid][tid]
                save_ntr_records()
            chain = [Plain('已重置'), At(qq=int(tid)), Plain('的牛老婆次数。')]
            yield event.chain_result(chain)
        else:
            try:
                await event.bot.set_group_ban(group_id=int(gid), user_id=int(uid), duration=self.reset_mute_duration)
            except:
                pass
            yield event.plain_result(f'{nick}，重置牛失败，已被禁言{self.reset_mute_duration}秒。')
