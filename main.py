from astrbot.api.all import *
from astrbot.api.star import StarTools
from datetime import datetime, timedelta
import random
import os
import re
import json
import aiohttp

PLUGIN_DIR = StarTools.get_data_dir("astrbot_plugin_animewifex")
CONFIG_DIR = os.path.join(PLUGIN_DIR, 'config')
IMG_DIR = os.path.join(PLUGIN_DIR, 'img', 'wife')
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

NTR_STATUS_FILE = os.path.join(CONFIG_DIR, 'ntr_status.json')
NTR_RECORDS_FILE = os.path.join(CONFIG_DIR, 'ntr_records.json')
CHANGE_RECORDS_FILE = os.path.join(CONFIG_DIR, 'change_records.json')
RESET_RECORDS_FILE = os.path.join(CONFIG_DIR, 'reset_ntr_records.json')
SWAP_REQUESTS_FILE = os.path.join(CONFIG_DIR, 'swap_requests.json')
SWAP_LIMIT_FILE = os.path.join(CONFIG_DIR, 'swap_limit_records.json')

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
ntr_records  = {}
change_records = {}
swap_requests = {}
swap_limit_records = {}
load_ntr_statuses = lambda: globals().update(ntr_statuses=load_json(NTR_STATUS_FILE))
load_ntr_records  = lambda: globals().update(ntr_records=load_json(NTR_RECORDS_FILE))


def load_change_records():
    raw = load_json(CHANGE_RECORDS_FILE)
    change_records.clear()
    for gid, users in raw.items():
        change_records[gid] = {}
        for uid, rec in users.items():
            if isinstance(rec, str):
                change_records[gid][uid] = {'date': rec, 'count': 1}
            else:
                change_records[gid][uid] = rec

save_ntr_statuses  = lambda: save_json(NTR_STATUS_FILE, ntr_statuses)
save_ntr_records   = lambda: save_json(NTR_RECORDS_FILE, ntr_records)
save_change_records = lambda: save_json(CHANGE_RECORDS_FILE, change_records)


def load_group_config(group_id: str) -> dict:
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

def load_swap_requests():
    raw = load_json(SWAP_REQUESTS_FILE)
    today = get_today()
    cleaned = {}
    for gid, reqs in raw.items():
        valid = {}
        for uid, rec in reqs.items():
            if rec.get('date') == today:
                valid[uid] = rec
        if valid:
            cleaned[gid] = valid
    globals()['swap_requests'] = cleaned
    if raw != cleaned:
        save_json(SWAP_REQUESTS_FILE, cleaned)

save_swap_requests = lambda: save_json(SWAP_REQUESTS_FILE, swap_requests)

def load_swap_limit_records():
    globals()['swap_limit_records'] = load_json(SWAP_LIMIT_FILE)

save_swap_limit_records = lambda: save_json(SWAP_LIMIT_FILE, swap_limit_records)

load_ntr_statuses()
load_ntr_records()
load_change_records()
load_swap_requests()
load_swap_limit_records()

@register("astrbot_plugin_animewifex", "monbed", "群二次元老婆插件修改版", "1.5.5", "https://github.com/monbed/astrbot_plugin_animewifex")
class WifePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 配置参数初始化
        self.ntr_max = config.get('ntr_max')
        self.ntr_possibility = config.get('ntr_possibility')
        self.change_max_per_day = config.get('change_max_per_day')
        self.reset_max_uses_per_day = config.get('reset_max_uses_per_day')
        self.reset_success_rate = config.get('reset_success_rate')
        self.reset_mute_duration = config.get('reset_mute_duration')
        self.image_base_url = config.get('image_base_url')
        self.swap_max_per_day = config.get('swap_max_per_day')

        # 命令与处理函数映射
        self.commands = {
            "抽老婆": self.animewife,
            "牛老婆": self.ntr_wife,
            "查老婆": self.search_wife,
            "切换ntr开关状态": self.switch_ntr,
            "换老婆": self.change_wife,
            "重置牛": self.reset_ntr,
            "交换老婆": self.swap_wife,
            "同意交换": self.agree_swap_wife,
            "拒绝交换": self.reject_swap_wife,
            "查看交换请求": self.view_swap_requests
        }
        self.admins = self.load_admins()

    def load_admins(self):
        # 加载管理员列表
        path = os.path.join('data', 'cmd_config.json')
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                cfg = json.load(f)
                return cfg.get('admins_id', [])
        except:
            return []

    def parse_at_target(self, event):
        # 解析@目标用户
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event):
        # 解析命令目标用户
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
        # 消息分发，根据命令调用对应方法
        if not hasattr(event.message_obj, 'group_id'):
            return
        text = event.message_str.strip()
        for cmd, func in self.commands.items():
            if text.startswith(cmd):
                async for res in func(event):
                    yield res
                break

    async def animewife(self, event: AstrMessageEvent):
        # 抽老婆主逻辑
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        cfg = load_group_config(gid)

        if cfg.get(uid, [None, ''])[1] != today:
            # 如果今天还没抽，重新抽取
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
        # 牛老婆主逻辑
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
            # 检查并取消相关交换请求
            cancel_msg = await self.cancel_swap_on_wife_change(gid, [uid, tid])
            yield event.plain_result(f'{nick}，牛老婆成功！')
            if cancel_msg:
                yield event.plain_result(cancel_msg)
            # 立即为新老婆抽取并展示
            async for res in self.animewife(event):
                yield res
        else:
            rem = self.ntr_max - rec['count']
            yield event.plain_result(f'{nick}，失败！剩余次数{rem}')

    async def search_wife(self, event: AstrMessageEvent):
        # 查老婆主逻辑
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
        # 切换NTR开关，仅管理员可用
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
        # 换老婆主逻辑
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
        # 检查并取消相关交换请求
        cancel_msg = await self.cancel_swap_on_wife_change(gid, [uid])
        if cancel_msg:
            yield event.plain_result(cancel_msg)
        # 立即为新老婆抽取并展示
        async for res in self.animewife(event):
            yield res

    async def reset_ntr(self, event: AstrMessageEvent):
        # 重置牛老婆次数
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

    async def swap_wife(self, event: AstrMessageEvent):
        # 发起交换老婆请求
        gid  = str(event.message_obj.group_id)
        uid  = str(event.get_sender_id())
        tid  = self.parse_at_target(event)
        nick = event.get_sender_name()
        today = get_today()

        grp_limit = swap_limit_records.setdefault(gid, {})
        rec_lim  = grp_limit.get(uid, {'date':'','count':0})
        if rec_lim['date'] != today:
            rec_lim = {'date': today, 'count': 0}
        if rec_lim['count'] >= self.swap_max_per_day:
            yield event.plain_result(f"{nick}，今天已发起{self.swap_max_per_day}次请求，明天再来~")
            return

        if not tid or tid == uid:
            yield event.plain_result(f'{nick}，请在命令后 @ 另一位用户。')
            return

        cfg = load_group_config(gid)
        for x in (uid, tid):
            if x not in cfg or cfg[x][1] != today:
                who = nick if x == uid else '对方'
                yield event.plain_result(f'{who}，今天还没有老婆，无法交换。')
                return

        rec_lim['count'] += 1
        grp_limit[uid] = rec_lim
        save_swap_limit_records()

        grp = swap_requests.setdefault(gid, {})
        grp[uid] = {'target': tid, 'date': today}
        save_swap_requests()

        yield event.chain_result([
            Plain(f'{nick} 请求与 '), At(qq=int(tid)),
            Plain(' 交换老婆，请对方用“同意交换 @发起者”或“拒绝交换 @发起者”。')
        ])

    async def agree_swap_wife(self, event: AstrMessageEvent):
        # 同意交换老婆
        gid  = str(event.message_obj.group_id)
        tid  = str(event.get_sender_id())
        uid  = self.parse_at_target(event)
        nick = event.get_sender_name()

        grp = swap_requests.get(gid, {})
        rec = grp.get(uid)
        if not rec or rec.get('target') != tid:
            yield event.plain_result(f'{nick}，请在命令后@发起者，或通过"查看交换请求"查看当前请求。')
            return

        cfg = load_group_config(gid)
        img_u, date_u, nick_u = cfg[uid]
        img_t, date_t, nick_t = cfg[tid]
        cfg[uid][0]  = img_t
        cfg[tid][0]  = img_u
        save_json(os.path.join(CONFIG_DIR, f'{gid}.json'), cfg)

        del grp[uid]
        save_swap_requests()

        yield event.plain_result('交换成功！')

    async def reject_swap_wife(self, event: AstrMessageEvent):
        # 拒绝交换老婆
        gid  = str(event.message_obj.group_id)
        tid  = str(event.get_sender_id())
        uid  = self.parse_at_target(event)
        nick = event.get_sender_name()

        grp = swap_requests.get(gid, {})
        rec = grp.get(uid)
        if not rec or rec.get('target') != tid:
            yield event.plain_result(f'{nick}，请在命令后@发起者，或通过"查看交换请求"查看当前请求。')
            return

        del grp[uid]
        save_swap_requests()
        yield event.chain_result([At(qq=int(uid)), Plain('，对方拒绝了交换请求。')])

    async def view_swap_requests(self, event: AstrMessageEvent):
        """
        查看当前用户发起或@到自己的交换请求：
          - 如果既没发起也没人向自己发起，提示未找到请求；
          - 否则列出所有相关请求，并提示使用“同意交换 @发起者”或“拒绝交换 @发起者”。
          发起时展示目标用户昵称，收到时展示发起者昵称。
        """
        gid = str(event.message_obj.group_id)
        me = str(event.get_sender_id())
        today = get_today()

        grp = swap_requests.get(gid, {})
        cfg = load_group_config(gid)

        sent_targets = [rec['target'] for uid, rec in grp.items() if uid == me]
        received_from = [uid for uid, rec in grp.items() if rec.get('target') == me]

        if not sent_targets and not received_from:
            yield event.plain_result('未找到交换请求')
            return

        parts = []
        for tid in sent_targets:
            name = cfg.get(tid, [None, None, '未知用户'])[2]
            parts.append(f'→ 我发起给 {name} 的请求')
        for uid in received_from:
            name = cfg.get(uid, [None, None, '未知用户'])[2]
            parts.append(f'→ {name} 发起给我的请求')

        text = (
            '当前交换请求：\n'
            + '\n'.join(parts)
            + '\n请在“同意交换”或“拒绝交换”命令后 @ 发起者'
        )
        yield event.plain_result(text)

    async def cancel_swap_on_wife_change(self, gid, user_ids):
        """
        检查并取消与user_ids相关的交换请求，返还交换次数，并返回提示文本（如有）。
        """
        changed = False
        today = get_today()
        grp = swap_requests.get(gid, {})
        grp_limit = swap_limit_records.setdefault(gid, {})
        to_cancel = []
        for req_uid, req in grp.items():
            if req_uid in user_ids or req.get('target') in user_ids:
                to_cancel.append(req_uid)
        for req_uid in to_cancel:
            # 返还次数
            rec_lim = grp_limit.get(req_uid, {'date': '', 'count': 0})
            if rec_lim.get('date') == today and rec_lim.get('count', 0) > 0:
                rec_lim['count'] = max(0, rec_lim['count'] - 1)
                grp_limit[req_uid] = rec_lim
                changed = True
            del grp[req_uid]
        if to_cancel:
            save_swap_requests()
        if changed:
            save_swap_limit_records()
        # 返回提示文本，由调用方 yield
        if to_cancel:
            return '交换对象老婆已变更，取消交换请求并返还次数。'
        return None