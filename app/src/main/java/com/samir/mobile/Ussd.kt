package com.samir.mobile

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.telephony.TelephonyManager
import java.util.concurrent.atomic.AtomicBoolean

object Ussd {
 private val busy=AtomicBoolean(false)
 fun execute(c: Context, subId: Int, p: Pending, store: Store): Boolean {
  if(c.checkSelfPermission(Manifest.permission.CALL_PHONE)!=PackageManager.PERMISSION_GRANTED) return false
  if(!busy.compareAndSet(false,true)) return false
  if(!store.consume(p)) {busy.set(false);return false}
  val done=AtomicBoolean(false);val handler=Handler(Looper.getMainLooper())
  val timeout=Runnable { if(done.compareAndSet(false,true)) { store.finish(p.chat,"مهلة انتهت","ما وصلش رد خلال 30 ثانية. العملية قد تكون تنفذت عند المشغل؛ تحقق قبل تعاود.");busy.set(false) } }
  fun finish(status: String,text: String) {if(done.compareAndSet(false,true)) {handler.removeCallbacks(timeout);store.finish(p.chat,status,text);busy.set(false)}}
  handler.postDelayed(timeout,30_000)
  try {
   val manager=c.getSystemService(TelephonyManager::class.java).createForSubscriptionId(subId)
   manager.sendUssdRequest(p.offer.code,object: TelephonyManager.UssdResponseCallback() {
    override fun onReceiveUssdResponse(t: TelephonyManager,request: String,response: CharSequence) {finish("نجاح الاتصال",response.toString())}
    override fun onReceiveUssdResponseFailed(t: TelephonyManager,request: String,failureCode: Int) {finish("فشل","فشل USSD ($failureCode). قد لا يدعم الجهاز أو المشغل هذه الطريقة.")}
   },handler)
  } catch(_: SecurityException) {finish("فشل","صلاحية الاتصال مرفوضة أو تم سحبها؛ لم نعد المحاولة.")}
    catch(_: Exception) {finish("فشل","تعذر إرسال USSD؛ راجع الشريحة والتغطية ودعم الجهاز.")}
  return true
 }
}
