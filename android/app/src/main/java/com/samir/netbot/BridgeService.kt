package com.samir.netbot

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.os.*
import android.telephony.TelephonyManager
import kotlinx.coroutines.*
import org.json.JSONObject

class BridgeService : Service() {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main)
    private val prefs by lazy { getSharedPreferences("netbot",MODE_PRIVATE) }
    private val handler=Handler(Looper.getMainLooper())
    private var loop: Job?=null
    private var executing=""
    override fun onBind(intent:Intent?)=null
    private fun client()=BridgeClient(prefs.getString("url","")!!,Vault(this).token())
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="stop") { stopSelf(); return START_NOT_STICKY }
        val nm=getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("bridge","Netbot companion",NotificationManager.IMPORTANCE_DEFAULT))
        startForeground(1,notification("الاتصال مفعّل — افتح لمراجعة أي عملية / Connexion active"))
        if(loop==null) {
            // A process restart never reissues an attempted command.
            val raw=prefs.getString("pending",null)
            if(raw!=null) {
                val c=PendingCommand.parse(JSONObject(raw))
                if(prefs.getBoolean("attempted_"+c.id,false) && prefs.getString("outbox",null)==null) finish(c,"timeout","Process restarted: network outcome unknown, do not retry automatically")
            }
            loop=scope.launch { pollLoop() }
        }
        val raw=prefs.getString("pending",null)
        val c=if(raw==null) null else PendingCommand.parse(JSONObject(raw))
        if(c!=null && intent?.getStringExtra("id")==c.id) {
            when(intent.action) {
                "execute" -> execute(c,intent.getIntExtra("sub",-1))
                "reject" -> if(executing.isEmpty()) finish(c,"fail","User rejected operation")
            }
        }
        return START_NOT_STICKY // User starts connection; no hidden auto-start.
    }
    private fun notification(text:String):Notification {
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop=PendingIntent.getService(this,1,Intent(this,BridgeService::class.java).setAction("stop"),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this,"bridge").setSmallIcon(android.R.drawable.stat_sys_phone_call).setContentTitle("Samir Netbot").setContentText(text).setContentIntent(open).setOngoing(true).build()
    }
    private suspend fun pollLoop() {
        while(currentCoroutineContext().isActive) {
            try {
                val out=prefs.getString("outbox",null)
                if(out!=null) {
                    val j=JSONObject(out)
                    val state=withContext(Dispatchers.IO) { client().result(j.getString("command_id"),j.getString("outcome"),j.getString("response")) }
                    prefs.edit().remove("outbox").putString("status","نتيجة / Résultat: $state").commit()
                }
                val raw=prefs.getString("pending",null)
                if(raw!=null) {
                    val c=PendingCommand.parse(JSONObject(raw))
                    if(c.expires<=System.currentTimeMillis()/1000 && executing!=c.id) finish(c,"timeout","No approval before deadline")
                    delay(1000); continue
                }
                val c=withContext(Dispatchers.IO) { client().poll() }
                prefs.edit().putString("status","متصل / En ligne").apply()
                if(c!=null) {
                    if(prefs.getBoolean("attempted_"+c.id,false)) { finish(c,"timeout","Duplicate delivery suppressed"); continue }
                    prefs.edit().putString("pending",c.json()).commit()
                    getSystemService(NotificationManager::class.java).notify(1,notification("طلب USSD — افتح ووافق / Ouvrez pour autoriser"))
                }
            } catch (_: Exception) { prefs.edit().putString("status","غير متصل / Hors ligne — إعادة اتصال فقط، لا إعادة USSD").apply(); delay(5000) }
        }
    }
    private fun execute(c:PendingCommand,sub:Int) {
        if(executing.isNotEmpty() || prefs.getBoolean("attempted_"+c.id,false)) return
        if(c.expires<=System.currentTimeMillis()/1000) { finish(c,"timeout","Approval expired"); return }
        if(sub<0 || !c.ussd.matches(Regex("[*#0-9]+#"))) { finish(c,"fail","Invalid SIM or USSD"); return }
        if(checkSelfPermission(Manifest.permission.CALL_PHONE)!=PackageManager.PERMISSION_GRANTED) { finish(c,"fail","CALL_PHONE permission denied"); return }
        // Durable mark BEFORE telephony. If the process dies here, do not dial again.
        if(!prefs.edit().putBoolean("attempted_"+c.id,true).commit()) { finish(c,"fail","Cannot persist execution guard"); return }
        executing=c.id
        val timeout=Runnable { if(executing==c.id) finish(c,"timeout","Network callback timeout; actual activation unknown") }
        handler.postDelayed(timeout,45000)
        try {
            val telephony=getSystemService(TelephonyManager::class.java).createForSubscriptionId(sub)
            telephony.sendUssdRequest(c.ussd,object:TelephonyManager.UssdResponseCallback() {
                override fun onReceiveUssdResponse(manager:TelephonyManager,request:String,response:CharSequence) {
                    if(executing!=c.id) return
                    handler.removeCallbacks(timeout); finish(c,"response",response.toString())
                }
                override fun onReceiveUssdResponseFailed(manager:TelephonyManager,request:String,failureCode:Int) {
                    if(executing!=c.id) return
                    handler.removeCallbacks(timeout); finish(c,"fail","USSD transport error: $failureCode")
                }
            },handler)
        } catch (_: Exception) { handler.removeCallbacks(timeout); finish(c,"fail","USSD unavailable or permission/SIM error") }
    }
    private fun finish(c:PendingCommand,outcome:String,text:String) {
        executing=""
        // Mask before storing / sending. Response is not logged.
        val safe=Regex("\\+?\\d[\\d ()-]{6,}\\d").replace(text,"[masked-number]").take(4000)
        val out=JSONObject().put("command_id",c.id).put("outcome",outcome).put("response",safe).toString()
        prefs.edit().remove("pending").putString("outbox",out).commit()
    }
    override fun onDestroy() { scope.cancel(); handler.removeCallbacksAndMessages(null); prefs.edit().putString("status","غير متصل / Déconnecté").commit(); super.onDestroy() }
}
