package com.samir.mobile

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicBoolean

class BotService: Service() {
 private val active=AtomicBoolean(false)
 private var worker: Thread?=null
 private var api: BotApi?=null
 private lateinit var store: Store
 private val prefs by lazy { getSharedPreferences("bot_state",MODE_PRIVATE) }
 override fun onBind(intent: Intent?): IBinder?=null
 override fun onCreate() { super.onCreate();store=Store(this); channels(this) }
 override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
  if(intent?.action=="stop") { stopSelf(); return START_NOT_STICKY }
  val n=Notification.Builder(this,"bot").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("Samir: البوت شغال").setContentText("الهاتف هو السيرفر — اضغط لفتح التطبيق").setOngoing(true).setContentIntent(open(this)).addAction(Notification.Action.Builder(null,"إيقاف",PendingIntent.getService(this,2,Intent(this,BotService::class.java).setAction("stop"),PendingIntent.FLAG_IMMUTABLE)).build()).build()
  if(Build.VERSION.SDK_INT>=34) startForeground(1,n,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(1,n)
  if(active.compareAndSet(false,true)) { running=true;worker=Thread({ poll() },"telegram-poll").also { it.start() } }
  return START_NOT_STICKY
 }
 private fun poll() {
  try {
   val token=Vault.token(this); if(token.isBlank()) return
   val bot=BotApi(token);api=bot
   var initialized=false
   while(active.get()) {
    try {
     if(!initialized) { bot.call("deleteWebhook",JSONObject().put("drop_pending_updates",false));initialized=true }
     store.expire();store.drain(bot)
     val updates=bot.updates(prefs.getLong("offset",0))
     for(i in 0 until updates.length()) {
      if(!active.get()) break
      val raw=updates.getJSONObject(i)
      // Commit before dispatch: avoids duplicate gifts/approvals after process restart.
      check(prefs.edit().putLong("offset",raw.getLong("update_id")+1).commit())
      val u=Parser.parse(raw) ?: continue
      if(!Rules.allowed(u.user,u.chat,u.privateChat)) continue
      if(u.callback!=null) { try {bot.call("answerCallbackQuery",JSONObject().put("callback_query_id",u.callback))} catch(_: Exception) {} }
      if(u.callback==null && System.currentTimeMillis()/1000-u.date>300) continue
      handle(bot,u)
     }
    } catch(_: Exception) {
     if(active.get()) { status="تعذر الاتصال بـ Telegram؛ نحاول من جديد";try {Thread.sleep(4000)}catch(_: InterruptedException){} }
    }
   }
  } finally { if(active.get()) stopSelf() }
 }
 private fun handle(bot: BotApi,u: Incoming) {
  status="متصل بـ Telegram"
  val t=u.text
  if(t=="/cancel") {prefs.edit().putBoolean("learning",false).apply();bot.send(u.chat,"تم الإلغاء",BotApi.menu());return}
  if(t=="➕ علّم كوداً") {prefs.edit().putBoolean("learning",true).apply();bot.send(u.chat,"ابعث في رسالة وحدة: اسم العرض | المشغل | *123#\nللعروض الخاصة زيد | خاص\n/cancel للإلغاء. الحفظ وحده ما ينفذ والو.");return}
  if(prefs.getBoolean("learning",false)) {
   val code=Rules.parseCode(t)
   if(code==null) {bot.send(u.chat,"الصيغة غير صحيحة: اسم | مشغل | *123# (اختيارياً | خاص)");return}
   store.add(code);prefs.edit().putBoolean("learning",false).apply();bot.send(u.chat,"تحفظ الكود محلياً، بلا تنفيذ.",BotApi.menu());return
  }
  when {
   t=="🎁 هدية يومية" -> bot.send(u.chat,if(store.gift(System.currentTimeMillis())) "ربحت 10 نقاط محلية!" else "الهدية مرة كل 24 ساعة؛ مازال ما فاتش الوقت.")
   t=="💰 كم هو رصيدي" -> bot.send(u.chat,"رصيدك ${store.balance()} نقطة محلية، والأكواد المحفوظة ${store.offers().size}. النقاط ماشي رصيد إنترنت.")
   t=="🌐 عروض الإنترنت" || t=="⚡ عروض خاصة" -> {
    val offers=store.offers(t=="⚡ عروض خاصة")
    if(offers.isEmpty()) bot.send(u.chat,"ما كاش أكواد محفوظة هنا؛ استعمل علّم كوداً.")
    else offers.chunked(20).forEach { page -> bot.send(u.chat,"اختار عرض، والتنفيذ يحتاج موافقة من الهاتف (قد يكون مدفوع):",JSONObject().put("inline_keyboard",JSONArray(page.map { listOf(mapOf("text" to "${it.name} — ${it.operator}","callback_data" to "offer:${it.id}")) }))) }
   }
   t.startsWith("offer:") -> {
    val offer=store.offers().find { it.id==t.removePrefix("offer:").toLongOrNull() }
    if(offer==null) bot.send(u.chat,"العرض غير موجود") else {
     store.request(u.chat,offer.id);notifyApproval(this)
     bot.send(u.chat,"افتح التطبيق ووافق محلياً خلال دقيقتين. ما تم حتى تنفيذ لحد الآن.")
    }
   }
   t=="🌐 5G" || t=="👻 سناب شات" -> bot.send(u.chat,"قريباً")
   else -> bot.send(u.chat,"مرحبا! البوت يخدم من هذا الهاتف. اختار من القائمة:",BotApi.menu())
  }
 }
 override fun onDestroy() { active.set(false);running=false;api?.close();worker?.interrupt();super.onDestroy() }
 companion object {
  @Volatile var running=false
  @Volatile var status="متوقف"
  fun open(c: android.content.Context)=PendingIntent.getActivity(c,1,Intent(c,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
  fun channels(c: android.content.Context) { val nm=c.getSystemService(NotificationManager::class.java);nm.createNotificationChannel(NotificationChannel("bot","تشغيل البوت",NotificationManager.IMPORTANCE_LOW));nm.createNotificationChannel(NotificationChannel("approval","موافقة USSD المحلية",NotificationManager.IMPORTANCE_HIGH)) }
  fun notifyApproval(c: android.content.Context) { channels(c);try {c.getSystemService(NotificationManager::class.java).notify(3,Notification.Builder(c,"approval").setSmallIcon(android.R.drawable.stat_sys_warning).setContentTitle("طلب تنفيذ USSD").setContentText("اضغط لعرض الكود واختيار SIM والموافقة. ينتهي خلال دقيقتين.").setContentIntent(open(c)).setAutoCancel(true).build())}catch(_: SecurityException){} }
 }
}
