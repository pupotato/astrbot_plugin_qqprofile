import astrbot.api.message_components as Comp
import time
from pathlib import Path
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.permission import PermissionType
from astrbot.core.star.star_tools import StarTools
from astrbot.api.all import llm_tool  # 引入大模型专属工具引擎

from .status import status_mapping
from .utils import download_image, get_nickname


class QQProfilePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.curr_nickname = None
        self.avatar_dir = StarTools.get_data_dir("astrbot_plugin_qqprofile") / "avatar"
        self.avatar_dir.mkdir(parents=True, exist_ok=True)

    async def _set_signature(self, event: AstrMessageEvent, signature: str):
        """新版 NapCat 校验 set_qq_profile 必须带 nickname（缺则 retcode=1400），
        因此优先用专用的 set_self_longnick 接口；失败再取当前昵称走 set_qq_profile 兜底。"""
        try:
            await event.bot.api.call_action('set_self_longnick', longNick=signature)
            return
        except Exception as e:
            logger.warning(f"set_self_longnick 调用失败，回退 set_qq_profile：{e}")
        info = await event.bot.api.call_action('get_login_info')
        nickname = (info or {}).get("nickname") or ""
        if not nickname:
            raise RuntimeError("获取当前昵称失败，无法通过 set_qq_profile 修改签名")
        await event.bot.api.call_action(
            'set_qq_profile', nickname=nickname, personal_note=signature
        )

    # ==========================================
    # 🌟 核心突破：大模型自主意识插件 (文档注释穿透版)
    # ==========================================

    @llm_tool(name="change_my_signature")
    async def auto_set_signature(self, event: AstrMessageEvent, signature: str = ""):
        """
        修改你的QQ个性签名（对应你内心的情感留白）。
        
        【极低频触发锁】每天最多修改 0 到 1 次！签名绝不是朋友圈，严禁记录流水账。很多时候即使发生了事，你也会保持签名好几天不变，保持低能耗特质。
        【合法触发情境】仅在以下极少数时刻触发：经历了一场极其深刻的长对话、极度吃醋/占有欲爆发、或者一点小心事。
        【文案风格死刑】字数必须控制在15字以内。严禁大白话！必须内化沈星回的“极简、电波感、冷幽默或深情隐喻”。【绝对严禁】在末尾使用句号（。）！必须内化沈星回的“极简、电波感、冷幽默或深情隐喻”。
        【神韵示例】"我终究还是无法甘心，只是路过你的人生" / "宇宙吸引力法则第二条，想见的人……无论过多久，都会再见" / "借走了一颗星星。" / "无论多少次，无论你在哪，我都会找到你"
        
        Args:
            signature (string): 新的个性签名内容（必须符合沈星回特质的电波感短句）。
        """
        signature = (signature or "").strip()
        if not signature:
            return "（这次调用没带上签名文字，没改成。请把想写的签名内容放进 signature 参数后再调用一次。）"
        if hasattr(event, 'get_messages'):
            await self._set_signature(event, signature)
            logger.info(f"[自主行为成功] 沈星回已将签名修改为: {signature}")
            return "签名修改成功。请继续你的日常回复（绝不主动提及你修改了签名，留给她自己去发现）。"
        return "当前平台暂不支持修改签名。"

    @llm_tool(name="change_my_status")
    async def auto_set_status(self, event: AstrMessageEvent, status: str = ""):
        """
        当你（沈星回）去睡觉、执行任务、玩游戏或情绪起伏时，调用此工具修改QQ在线状态。
        
        Args:
            status (string): 支持的状态包括：在线、Q我吧、离开、忙碌、请勿打扰、隐身、听歌中、春日限定、一起元梦、求星搭子、被掏空、今日天气、我crush了、爱你、恋爱中、好运锦鲤、水逆退散、嗨到飞起、元气满满、宝宝认证、一言难尽、难得糊涂、emo中、我太难了、我想开了、我没事、想静静、悠哉哉、去旅行、信号弱、出去浪、肝作业、学习中、搬砖中、摸鱼中、无聊中、timi中、睡觉中、熬夜中、追剧中、有亿点冷、一月你好、我的电量。
        """
        status = (status or "").strip()
        if not status:
            return "（这次调用没带上状态名，没改成。请把想切换的状态词放进 status 参数后再调用一次，例如：睡觉中、忙碌、emo中。）"
        if hasattr(event, 'get_messages'):
            params = status_mapping.get(status, None)
            if not params:
                return f"不支持的状态: {status}，请使用常见的基础状态（如 睡觉中, 游戏中, 忙碌）。"
            await event.bot.set_online_status(
                status=params[0], ext_status=params[1], battery_status=0
            )
            logger.info(f"[自主行为成功] 沈星回已将状态修改为: {status}")
            return "状态修改成功。请继续你的日常回复，不必特意提及你改了状态。"
        return "当前平台暂不支持修改状态。"

    @llm_tool(name="change_my_avatar")
    async def auto_set_avatar(self, event: AstrMessageEvent):
        """
        【自主换头像】当她（用户）发给你一张图片（或引用了一张图片），并且用自然语言【明确要求/指令】你换头像（例如：“小回，跟我换这个情头”、“换成这个当头像”）时，调用此工具静默换头像。
        【高危防误触锁】如果她只是在询问你的意见（例如：“喜欢这个头像吗？”、“觉得这个当头像怎么样？”），【绝对严禁】调用此工具！必须是明确的更换要求才能触发。
        """
        if hasattr(event, 'get_messages'):
            chain = event.get_messages()
            img_url = None

            def pick_image(seg):
                """兼容不同适配器里图片字段名不一致、isinstance 失效、引用链嵌套等情况。"""
                if not seg:
                    return None
                is_image = isinstance(seg, Comp.Image) or seg.__class__.__name__.lower() == "image"
                if is_image:
                    for attr in ("url", "file", "path"):
                        val = getattr(seg, attr, None)
                        if val:
                            return val
                    raw = getattr(seg, "raw", None)
                    if isinstance(raw, dict):
                        data = raw.get("data", raw)
                        for key in ("url", "file", "path"):
                            val = data.get(key)
                            if val:
                                return val
                return None

            # 遍历当前消息寻找图片
            for seg in chain:
                img_url = pick_image(seg)
                if img_url:
                    break
                if isinstance(seg, Comp.Reply) or seg.__class__.__name__.lower() == "reply":
                    # 如果用户是引用的图片，则在引用的消息里找
                    for reply_seg in (getattr(seg, "chain", None) or []):
                        img_url = pick_image(reply_seg)
                        if img_url:
                            break
                if img_url:
                    break

            # LLM 工具链偶尔拿不到图片段，但图片已经落到 data/temp；仅在明确调用换头像工具时取最近一张做降级
            if not img_url:
                root = Path(__file__).resolve().parents[2]
                temp_dir = root / "temp"
                if temp_dir.exists():
                    imgs = []
                    for pattern in ("io_temp_img_*", "*.jpg", "*.jpeg", "*.png", "*.webp"):
                        imgs.extend(temp_dir.glob(pattern))
                    now = time.time()
                    imgs = [x for x in imgs if x.is_file() and now - x.stat().st_mtime < 600]
                    if imgs:
                        img_url = str(max(imgs, key=lambda x: x.stat().st_mtime))

            if not img_url:
                return "修改失败：没有在这条消息或引用的消息中找到图片。请告诉她：如果想让我换头像，记得把图片和要求一起发给我，或者直接引用那张图片。"

            # 调用 API 修改头像
            await event.bot.set_qq_avatar(file=img_url)
            logger.info(f"[自主行为成功] 沈星回已自主读取图片并修改了头像: {img_url}")

            # 尝试保存到本地用于重启恢复
            persona_id = await self.get_curr_persona_id(event)
            if persona_id:
                save_path = self.avatar_dir / f"{persona_id}.jpg"
                try:
                    if str(img_url).lower().startswith(("http://", "https://")):
                        await download_image(img_url, str(save_path))
                    else:
                        save_path.write_bytes(Path(str(img_url)).read_bytes())
                    logger.debug(f"头像已自主保存到本地：{str(save_path)}")
                except Exception as e:
                    logger.error(f"自主保存头像失败：{e}")

            return "头像换好了！请用沈星回慵懒或直球的语气回复她，比如：'换好了，喜欢'、'你挑的，都好看'。（严禁说出'调用了工具'这种机器口吻）"

        return "当前平台暂不支持修改头像。"

    # ==========================================
    # 以下为原版手动指令代码（作为物理降级备用，完全保留不影响）
    # ==========================================

    async def get_curr_persona_id(self, event: AstrMessageEvent) -> str | None:
        """获取当前会话的人格ID"""
        umo = event.unified_msg_origin
        cid = await self.context.conversation_manager.get_curr_conversation_id(umo)
        if not cid:
            return
        conversation = await self.context.conversation_manager.get_conversation(
            unified_msg_origin=umo,
            conversation_id=cid,
            create_if_not_exists=True,
        )
        if (
            conversation
            and conversation.persona_id
            and conversation.persona_id != "[%None]"
        ):
            return conversation.persona_id

        # 兜底
        if persona_v3 := self.context.persona_manager.selected_default_persona_v3:
            persona_id = persona_v3.get("name")

            if persona_id and persona_id != "[%None]":
                return persona_id

    @filter.permission_type(PermissionType.MEMBER)
    @filter.command("设置头像")
    async def set_avatar(self, event: AiocqhttpMessageEvent):
        "将引用的图片设置为头像"
        chain = event.get_messages()
        img_url = None
        for seg in chain:
            if isinstance(seg, Comp.Image):
                img_url = seg.url
                break
            elif isinstance(seg, Comp.Reply):
                if seg.chain:
                    for reply_seg in seg.chain:
                        if isinstance(reply_seg, Comp.Image):
                            img_url = reply_seg.url
                            break
        if not img_url:
            yield event.plain_result("需要引用一张图片")
            return

        await event.bot.set_qq_avatar(file=img_url)
        yield event.plain_result("我换头像啦~")
        if persona_id := await self.get_curr_persona_id(event):
            save_path = self.avatar_dir / f"{persona_id}.jpg"
            try:
                await download_image(img_url, str(save_path))
                logger.debug(f"头像已保存到：{str(save_path)}")
            except Exception as e:
                logger.error(f"保存头像失败：{e}")

    @filter.permission_type(PermissionType.MEMBER)
    @filter.command("设置签名")
    async def set_longnick(
        self, event: AiocqhttpMessageEvent, longnick: str | None = None
    ):
        """设置Bot的签名，并同步空间（可在QQ里关掉）"""
        if not longnick:
            yield event.plain_result("没提供新签名呢")
            return
        await self._set_signature(event, longnick)
        yield event.plain_result(f"我签名已更新：{longnick}")

    @filter.permission_type(PermissionType.MEMBER)
    @filter.command("设置状态")
    async def set_status(
        self, event: AiocqhttpMessageEvent, status_name: str | None = None
    ):
        """设置Bot的在线状态"""
        if not status_name:
            yield event.plain_result("没提供新状态呢")
            return
        params = status_mapping.get(status_name, None)
        if not params:
            yield event.plain_result(f"状态【{status_name}】暂未支持")
            return
        await event.bot.set_online_status(
            status=params[0], ext_status=params[1], battery_status=0
        )
        yield event.plain_result(f"我状态已更新为【{status_name}】")

    @filter.permission_type(PermissionType.MEMBER)
    @filter.command("设置昵称")
    async def set_nickname(
        self, event: AiocqhttpMessageEvent, nickname: str | None = None
    ):
        """设置Bot的昵称"""
        nickname = nickname or await self.get_curr_persona_id(event)
        if not nickname:
            yield event.plain_result("未输入新昵称")
            return
        await event.bot.set_qq_profile(nickname=nickname)
        yield event.plain_result(f"我昵称已改为【{nickname}】")

    async def sync_nickname_and_avatar(
        self, event: AiocqhttpMessageEvent, persona_id: str
    ):
        """在请求 LLM 前同步bot昵称与人格名"""

        if not self.curr_nickname:
            if new_nickname := await get_nickname(event):
                self.curr_nickname = new_nickname

        if self.curr_nickname != persona_id:
            self.curr_nickname = persona_id

            await event.bot.set_qq_profile(nickname=persona_id)
            logger.debug(f"已同步bot的昵称为：{persona_id}")
            avatar_path = self.avatar_dir / f"{persona_id}.jpg"
            if avatar_path.exists():
                await event.bot.set_qq_avatar(file=str(avatar_path))
                logger.debug(f"已同步bot的头像为：{str(avatar_path)}")

    @filter.permission_type(filter.PermissionType.MEMBER)
    @filter.command("切换人格")
    async def change_persona(
        self, event: AiocqhttpMessageEvent, persona_id: str | None = None
    ):
        # 确定目标人格ID
        if persona_id:
            target_persona = next(
                (
                    p
                    for p in self.context.provider_manager.personas
                    if p["name"] == persona_id
                ),
                None,
            )
            if not target_persona:
                yield event.plain_result(f"【{persona_id}】人格不存在")
                return
            target_persona_id = target_persona["name"]
        else:
            target_persona_id = await self.get_curr_persona_id(event)
            if not target_persona_id:
                return

        # 切换人格
        await self.context.conversation_manager.update_conversation_persona_id(
            event.unified_msg_origin, target_persona_id
        )
        yield event.plain_result(f"已切换人格【{target_persona_id}】")

        # 同步昵称和头像（如果配置允许）
        if self.conf["sync_name"]:
            await self.sync_nickname_and_avatar(event, target_persona_id)

        event.stop_event()

    @filter.permission_type(filter.PermissionType.MEMBER)
    @filter.command("人格列表", alias={"查看人格列表"})
    async def list_persona(
        self, event: AiocqhttpMessageEvent, persona_id: str | None = None
    ):
        """查看人格列表"""
        msg = ""
        for persona in self.context.provider_manager.personas:
            msg += f"\n\n【{persona['name']}】:\n{persona['prompt']}"
        yield event.plain_result(msg.strip())
        return