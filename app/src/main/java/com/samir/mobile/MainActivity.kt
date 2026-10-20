package com.samir.mobile

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.telephony.SubscriptionManager
import android.text.InputType
import android.widget.*

class MainActivity: Activity() {
 private lateinit var root: LinearLayout
 private lateinit var store: Store
 override fun onCreate(state: Bundle?) {super.onCreate(state);store=Store(this);BotService.channels(this);render()}
 override fun onResume() {super.onResume();if(::root.isInitialized) render()}
 private fun button(text: String, action: ()->Unit) {root.addView(Button(this).apply {this.text=text;setOnClickListener {action()}})}
 private fun label(text: String) {root.addView(TextView(this).apply {this.text=text;textSize=17f;setPadding(8,12,8,12)})}
 private fun toast(t: String) {Toast.makeText(this,t,Toast.LENGTH_LONG).show()}
 private fun permissions() {
  val list=mutableListOf(Manifest.permission.CALL_PHONE,Manifest.permission.READ_PHONE_STATE)
  if(Build.VERSION.SDK_INT>=33) list.add(Manifest.permission.POST_NOTIFICATIONS)
  val missing=list.filter {checkSelfPermission(it)!=PackageManager.PERMISSION_GRANTED}
  if(missing.isNotEmpty()) requestPermissions(missing.toTypedArray(),1)
 }
 private fun render() {
  root=LinearLayout(this).apply {orientation=LinearLayout.VERTICAL;setPadding(24,24,24,24)}
  setContentView(ScrollView(this).apply {addView(root)})
  label("Samir Netbot — 0.3.0-preview3\nبلا سيرفر: الهاتف لازم يبقى متصل بالإنترنت.\nالمالك الوحيد: 8178411819\nالحالة: ${if(BotService.running) BotService.status else "متوقف"}")
  val token=EditText(this).apply {hint="الصق توكن BotFather هنا";inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD;setSingleLine();importantForAutofill=android.view.View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS}
  root.addView(token)
  label(if(Vault.token(this).isBlank()) "التوكن غير محفوظ" else "التوكن محفوظ ومشفر، ما نعرضوهش")
  button("حفظ التوكن") {
   if(BotService.running) {toast("وقف البوت قبل تبديل التوكن");return@button}
   val value=token.text.toString().trim()
   if(!Regex("[0-9]+:[A-Za-z0-9_-]{20,}").matches(value)) {toast("صيغة التوكن غير صحيحة");return@button}
   try {Vault.save(this,value);getSharedPreferences("bot_state",MODE_PRIVATE).edit().clear().commit();token.text.clear();render()} catch(_: Exception) {toast("تعذر الحفظ الآمن؛ ما حفظناش التوكن كنص عادي")}
  }
  button(if(BotService.running) "إيقاف البوت" else "تشغيل البوت") {
   if(BotService.running) {stopService(Intent(this,BotService::class.java));BotService.running=false;render()}
   else {if(Vault.token(this).isBlank()) {toast("احفظ التوكن أولاً");return@button};permissions();startForegroundService(Intent(this,BotService::class.java));toast("جار تشغيل البوت");root.postDelayed({render()},700)}
  }
  button("منح صلاحيات الاتصال والإشعارات") {permissions()}
  button("تحديث الحالة والطلبات") {render()}
  label("طلبات الموافقة (دقيقتان):")
  store.pending().forEach {p ->
   label("${p.offer.name} — ${p.offer.operator}\nالكود: ${p.offer.code}\nقد يخصم المشغل رصيداً. راجع الكود قبل الموافقة.")
   button("مراجعة واختيار SIM") {approve(p)}
   button("رفض الطلب") {if(store.consume(p))store.finish(p.chat,"مرفوض","رفضت التنفيذ محلياً؛ لم نرسل الكود.");render()}
  }
  button("إضافة كود من الهاتف") {
   val field=EditText(this).apply {hint="اسم | مشغل | *123# | خاص (اختياري)"}
   AlertDialog.Builder(this).setTitle("حفظ فقط بلا تنفيذ").setView(field).setPositiveButton("حفظ") {_,_->val n=Rules.parseCode(field.text.toString());if(n==null) toast("صيغة غير صحيحة") else {store.add(n);render()}}.setNegativeButton("إلغاء",null).show()
  }
  label("الأكواد المحفوظة: ${store.offers().size} | النقاط: ${store.balance()}\nآخر 50 عملية (الأرقام منقحة):\n${store.logs()}")
  label("التوكن مشفر بـ Android Keystore. أي شخص يمسك هاتفك مفتوح يقدر يتحكم في البوت. لا تشارك التوكن، ولا رقم هاتف ولا OTP. بعد إعادة التشغيل افتح التطبيق وشغل البوت. قيود البطارية أو Force stop توقفه؛ الخدمة الأمامية ما تضمنش تشغيل 24/24.")
 }
 private fun approve(p: Pending) {
  if(checkSelfPermission(Manifest.permission.CALL_PHONE)!=PackageManager.PERMISSION_GRANTED || checkSelfPermission(Manifest.permission.READ_PHONE_STATE)!=PackageManager.PERMISSION_GRANTED) {permissions();toast("امنح الصلاحيات ثم عاود الموافقة");return}
  val sims=try {getSystemService(SubscriptionManager::class.java).activeSubscriptionInfoList ?: emptyList()}catch(_: Exception){emptyList()}
  if(sims.isEmpty()) {toast("ما كاش SIM نشطة أو ما نقدرش نقراها");return}
  AlertDialog.Builder(this).setTitle("اختار الشريحة")
   .setItems(sims.map {"SIM ${it.simSlotIndex+1} — ${it.carrierName}"}.toTypedArray()) {_,which ->
    val sim=sims[which]
    AlertDialog.Builder(this).setTitle("تأكيد محلي — قد يكون مدفوع")
     .setMessage("${p.offer.name}\n${p.offer.code}\nSIM ${sim.simSlotIndex+1}\nهل توافق على الإرسال الآن؟ مهلة الرد 30 ثانية؛ انتهاء المهلة لا يلغي العملية عند المشغل.")
     .setPositiveButton("أوافق وأنفذ") {_,_->if(!Ussd.execute(applicationContext,sim.subscriptionId,p,store)) toast("الطلب انتهى أو عملية أخرى جارية") else toast("تم إرسال الطلب، النتيجة في السجل وTelegram");render()}
     .setNegativeButton("إلغاء",null).show()
   }.setNegativeButton("إلغاء",null).show()
 }
}
