import asyncio
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command as BotCommand, CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from core.db import Session
from core.models import User, Device, Offer, Command, Interest
from core import service

AR = ['🎁 هدية يومية','💰 كم هو رصيدي','🌐 عروض الإنترنت','⚡ عروض خاصة','🌐 تفعيل تقنية 5G','👻 سناب شات']
FR = ['🎁 Cadeau quotidien','💰 Mon solde','🌐 Offres Internet','⚡ Offres spéciales','🌐 Activer la 5G','👻 Snapchat']
dp = Dispatcher()
admins = {int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
def lang(uid):
    with Session() as s:
        u = s.get(User, uid)
        return u.language if u else 'ar'
def tr(uid, ar, fr): return fr if lang(uid) == 'fr' else ar
def keyboard(uid):
    a = FR if lang(uid) == 'fr' else AR
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t)] for t in a] + [[KeyboardButton(text='العربية'),KeyboardButton(text='Français')]], resize_keyboard=True)
def ok(uid):
    with Session() as s:
        u = s.get(User, uid)
        return bool(u and not u.banned)

@dp.message(CommandStart())
async def start(m: Message):
    if m.chat.type != 'private': return
    part = (m.text or '').split(maxsplit=1)
    ref = int(part[1][4:]) if len(part)>1 and part[1].startswith('ref_') and part[1][4:].isdigit() else None
    service.ensure_user(m.from_user.id, ref)
    if not ok(m.from_user.id): return
    await m.answer('مرحبا! اختار عرض، اربط هاتفك بـ /pair، ووافق على الهاتف لكل عملية. /devices /history /referral\nBienvenue ! /pair pour relier votre téléphone. Aucun numéro ou OTP demandé.', reply_markup=keyboard(m.from_user.id))

@dp.message(BotCommand('pair'))
async def pair(m: Message):
    if m.chat.type != 'private' or not ok(m.from_user.id): return
    c = service.pairing(m.from_user.id)
    await m.answer(tr(m.from_user.id, f'كود ربط الجهاز: {c}\nصالح 5 دقائق، استعمله فقط في التطبيق المرافق. هذا ليس OTP ولا كود المشغل.', f'Code de liaison : {c}\nValable 5 minutes, uniquement dans le compagnon. Ce n’est pas un OTP opérateur.'))

@dp.message(BotCommand('devices'))
async def devices(m: Message):
    if not ok(m.from_user.id): return
    with Session() as s:
        ds = s.scalars(select(Device).where(Device.user_id == m.from_user.id, Device.revoked == False)).all()
    await m.answer('\n'.join(f'{d.id}: {d.name} — '+(tr(m.from_user.id,'متصل','en ligne') if d.last_seen >= service.now()-60 else tr(m.from_user.id,'غير متصل','hors ligne')) for d in ds) or tr(m.from_user.id,'لا يوجد جهاز مرتبط. /pair','Aucun appareil. /pair'))
    if ds: await m.answer('/unlink DEVICE_ID — إلغاء الربط / révoquer')

@dp.message(BotCommand('unlink'))
async def unlink(m: Message):
    if not ok(m.from_user.id): return
    try: did = int(m.text.split()[1])
    except (ValueError, IndexError): return await m.answer('/unlink DEVICE_ID')
    service.revoke(m.from_user.id, did)
    await m.answer(tr(m.from_user.id,'تم إلغاء الجهاز إذا كان تابعاً لك.','Appareil révoqué si lié à votre compte.'))

@dp.message(BotCommand('history'))
async def history(m: Message):
    if not ok(m.from_user.id): return
    with Session.begin() as s:
        service.expire(s)
        cs = s.scalars(select(Command).where(Command.user_id==m.from_user.id).order_by(Command.created_at.desc()).limit(15)).all()
    await m.answer('\n\n'.join(f'{c.id[:8]} {c.offer_name}: {c.state}\n{c.reason}\n{c.response[:150]}' for c in cs) or tr(m.from_user.id,'السجل فارغ.','Historique vide.'))

@dp.message(BotCommand('referral'))
async def referral(m: Message, bot: Bot):
    if not ok(m.from_user.id): return
    me = await bot.get_me()
    with Session() as s: count = s.scalar(select(func.count()).select_from(User).where(User.referrer==m.from_user.id))
    await m.answer(f'https://t.me/{me.username}?start=ref_{m.from_user.id}\n'+tr(m.from_user.id, f'الإحالات: {count} (بدون مكافأة مالية)', f'Invitations : {count} (sans prime financière)'))

@dp.message(BotCommand('admin'))
async def admin(m: Message):
    if m.chat.type != 'private' or m.from_user.id not in admins: return
    raw = m.text.split(maxsplit=1)
    if len(raw)==1:
        return await m.answer('أوامر الإدارة:\n/admin add name|operator|size|price_points|internet أو special|USSD|success_regex\n/admin enable BID\n/admin disable BID\n/admin requests\n/admin ban TELEGRAM_ID\n/admin unban TELEGRAM_ID\nالعروض الجديدة معطلة افتراضياً. لا تفعل قبل التحقق من الكود الرسمي ونص النجاح والتكلفة.')
    action, _, args = raw[1].partition(' ')
    try:
        with Session.begin() as s:
            if action == 'add':
                name, operator, size, price, category, ussd, regex = args.split('|')
                if len(ussd)>160 or not re.fullmatch(r'[*#0-9]+#',ussd) or len(regex)>200 or not regex: raise ValueError('USSD / regex invalid')
                if int(price)<0 or category not in ('internet','special'): raise ValueError('price/category')
                # Keep success patterns literal/simple: avoid catastrophic regexes.
                if any(c in regex for c in '*+{}()\\'): raise ValueError('use simple literal confirmation text, no complex regex')
                re.compile(regex)
                o = Offer(name=name[:100],operator=operator[:50],size=size[:50],price_points=int(price),category=category,ussd=ussd,success_regex=regex,enabled=False)
                s.add(o); s.flush(); reply=f'BID={o.bid}. Disabled. /admin enable {o.bid}'
            elif action in ('enable','disable'):
                o=s.get(Offer,int(args))
                if not o: raise ValueError('unknown offer')
                if action=='enable' and ('PLACEHOLDER' in o.ussd or not o.success_regex): raise ValueError('placeholder cannot be enabled')
                o.enabled=action=='enable'; reply='OK'
            elif action in ('ban','unban'):
                u=s.get(User,int(args))
                if not u: raise ValueError('unknown user')
                u.banned=action=='ban'; reply='OK'
            elif action=='requests':
                service.expire(s)
                cs=s.scalars(select(Command).order_by(Command.created_at.desc()).limit(20)).all()
                reply='\n'.join(f'{c.id[:8]} user={c.user_id} {c.state} {c.reason}: {c.response[:60]}' for c in cs) or 'No requests'
            else: raise ValueError('unknown action')
            service.audit(s,m.from_user.id,'admin_'+action)
        await m.answer(reply)
    except (ValueError, TypeError) as e: await m.answer('خطأ: '+str(e))

@dp.callback_query(F.data.startswith('activate:'))
async def activate(q: CallbackQuery):
    if not ok(q.from_user.id): return await q.answer('Blocked',show_alert=True)
    bid=int(q.data.split(':')[1])
    try:
        c=service.create_command(q.from_user.id,bid,None,'tg:'+q.id)
        await q.message.answer(tr(q.from_user.id,f'تم إرسال طلب {c.offer_name}. وافق على الهاتف. الحالة: {c.state}\nلا تعاود الطلب عند المهلة قبل التأكد من المشغل.',f'Demande {c.offer_name}: {c.state}. Confirmez sur le téléphone. Ne réessayez pas après délai sans vérifier l’opérateur.'))
        await q.answer()
    except ValueError as e:
        reasons={'no_linked_device':'لا يوجد جهاز مرتبط. /pair','device_offline':'الجهاز غير متصل. افتح التطبيق وابدأ الاتصال.','offer_not_configured':'العرض لم يجهّزه المسؤول بعد.','device_busy':'عملية جارية على الهاتف.','insufficient_points':'النقاط غير كافية.','blocked':'الحساب محظور.'}
        await q.message.answer(tr(q.from_user.id,reasons.get(str(e),str(e)),str(e)))
        await q.answer()

@dp.message(F.text)
async def menu(m: Message):
    if m.chat.type != 'private' or not ok(m.from_user.id): return
    uid=m.from_user.id
    if m.text in ('العربية','Français'):
        with Session.begin() as s: s.get(User,uid).language='fr' if m.text=='Français' else 'ar'
        return await m.answer(tr(uid,'اختر عرضاً من القائمة.','Choisissez une offre.'),reply_markup=keyboard(uid))
    idx=AR.index(m.text) if m.text in AR else FR.index(m.text) if m.text in FR else -1
    if idx==0:
        claimed=service.gift(uid)
        return await m.answer(tr(uid,'تمت إضافة نقاط الهدية.' if claimed else 'الهدية مرة كل 24 ساعة.','Points ajoutés.' if claimed else 'Une fois toutes les 24 heures.'))
    if idx==1:
        with Session() as s:
            u=s.get(User,uid); count=s.scalar(select(func.count()).select_from(Device).where(Device.user_id==uid,Device.revoked==False))
        return await m.answer(tr(uid,f'نقاطك: {u.points}\nالأجهزة: {count}\nالنقاط ليست رصيد المشغل.',f'Points : {u.points}\nAppareils : {count}\nCe n’est pas le solde opérateur.'))
    if idx in (2,3):
        with Session() as s: offers=s.scalars(select(Offer).where(Offer.enabled==True,or_(Offer.owner_user_id==None,Offer.owner_user_id==uid),Offer.category==('internet' if idx==2 else 'special'))).all()
        if not offers: return await m.answer(tr(uid,'لا توجد عروض رسمية مهيأة بعد. لا نستعمل أكواداً مجهولة.','Aucune offre officielle configurée. Pas de code inconnu.'))
        rows=[[InlineKeyboardButton(text=f'{o.name} | {o.operator} | {o.size} | {o.price_points} pts',callback_data=f'activate:{o.bid}')] for o in offers]
        return await m.answer(tr(uid,'اختار العرض. قد يخصم المشغل من رصيد الشريحة؛ راجع التكلفة وSIM والكود على الهاتف قبل الموافقة.','Choisissez. Des frais opérateur peuvent s’appliquer. Vérifiez tarif, SIM et code sur le téléphone.'),reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    if idx in (4,5):
        try:
            with Session.begin() as s: s.add(Interest(user_id=uid,feature='5g' if idx==4 else 'snapchat'))
        except IntegrityError: pass
        return await m.answer(tr(uid,'قريباً — سجلنا اهتمامك فقط، لم يتم أي تفعيل.','Bientôt — intérêt enregistré, aucune activation.'))
    await m.answer(tr(uid,'اختار من القائمة. /pair /devices /history','Choisissez dans le menu. /pair /devices /history'),reply_markup=keyboard(uid))

async def notify(bot):
    while True:
        try:
            with Session.begin() as s:
                service.expire(s)
                commands=s.scalars(select(Command).where(Command.state.in_(service.TERMINAL),Command.notified==False).limit(30)).all()
            for c in commands:
                text=tr(c.user_id,'تم التفعيل حسب رد المشغل' if c.state=='success' else 'انتهت المهلة: النتيجة غير معروفة، تحقق قبل الإعادة' if c.state=='timeout' else 'فشل / لم يتأكد التفعيل','Activation confirmée par la réponse' if c.state=='success' else 'Délai expiré : résultat inconnu, vérifiez avant de réessayer' if c.state=='timeout' else 'Échec / activation non confirmée')
                try:
                    await bot.send_message(c.user_id,f'{c.offer_name}: {text}\n{c.reason}\n{c.response[:1500]}')
                except Exception:
                    continue  # Retry later; Telegram failure is not USSD failure.
                with Session.begin() as s: s.get(Command,c.id).notified=True
        except Exception:
            pass  # No tokens or network responses in logs.
        await asyncio.sleep(3)

async def main():
    token=os.environ['BOT_TOKEN']
    bot=Bot(token)
    worker=asyncio.create_task(notify(bot))
    try: await dp.start_polling(bot)
    finally: worker.cancel(); await bot.session.close()
if __name__=='__main__': asyncio.run(main())
