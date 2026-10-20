package com.samir.netbot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.telephony.SubscriptionManager
import android.widget.*
import kotlinx.coroutines.*

class MainActivity : Activity() {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main)
    private val prefs by lazy { getSharedPreferences("netbot",MODE_PRIVATE) }
    private lateinit var status: TextView
    private lateinit var pendingText: TextView
    private lateinit var url: EditText
    private lateinit var code: EditText
    private lateinit var sims: Spinner
    private var subIds=listOf<Int>()
    private var shownId=""
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(28,32,28,20) }
        val scroll=ScrollView(this).apply { addView(layout) }; setContentView(scroll)
        fun label(t:String)=TextView(this).also { it.text=t; it.textSize=18f; layout.addView(it) }
        fun button(t:String,f:()->Unit)=Button(this).also { it.text=t; it.setOnClickListener { f() }; layout.addView(it) }
        label("سمير نت — ربط هاتفك / Lier votre téléphone")
        label("لا نطلب رقمك ولا OTP. تختار الشريحة وتوافق على كل USSD. قد يخصم المشغل رصيداً. التطبيق لا يضمن تفعيل عرض دون كود رسمي ورد مؤكد.\nAucun numéro ni OTP. Autorisation pour chaque opération, frais opérateur possibles.")
        url=EditText(this).apply { hint="https://api.example.org"; setText(prefs.getString("url","")); inputType=17 }; layout.addView(url)
        code=EditText(this).apply { hint="كود الربط 6 أرقام / Code de liaison"; inputType=2; filters=arrayOf(android.text.InputFilter.LengthFilter(6)) }; layout.addView(code)
        status=label("غير متصل / Déconnecté")
        button("ربط الجهاز / Lier") {
            val base=url.text.toString().trim(); val value=code.text.toString()
            if(prefs.getString("pending",null)!=null || prefs.getString("outbox",null)!=null) { status.text="أنه العملية الحالية أولاً / Terminez la demande"; return@button }
            scope.launch {
                try {
                    val token=withContext(Dispatchers.IO) { BridgeClient(base).register(value) }
                    Vault(this@MainActivity).saveToken(token)
                    prefs.edit().putString("url",base).commit(); code.setText(""); status.text="تم الربط. ابدأ الاتصال / Lié, démarrez la connexion"
                } catch (_: Exception) { status.text="فشل الربط: راجع HTTPS والكود / Vérifiez HTTPS et le code" }
            }
        }
        button("منح الصلاحيات واختيار SIM / Autorisations SIM") { permissions() }
        sims=Spinner(this); layout.addView(sims); loadSims()
        button("بدء الاتصال / Démarrer") {
            if(Vault(this).token().isEmpty()) { status.text="اربط الجهاز أولاً / Liez d’abord"; return@button }
            val i=Intent(this,BridgeService::class.java)
            startForegroundService(i)
        }
        button("إيقاف وإلغاء التفويض / Arrêter") {
            stopService(Intent(this,BridgeService::class.java))
            status.text="تم الإيقاف؛ أي عملية أرسلت للشبكة قد لا يمكن إلغاؤها. / Arrêté ; USSD déjà envoyé non annulable."
        }
        pendingText=label("لا توجد عملية / Aucune demande")
        button("مراجعة وموافقة العملية / Examiner et autoriser") {
            val raw=prefs.getString("pending",null) ?: return@button
            val command=PendingCommand.parse(org.json.JSONObject(raw))
            if(command.expires<=System.currentTimeMillis()/1000) { status.text="انتهت المهلة / Expirée"; return@button }
            if(subIds.isEmpty() || checkSelfPermission(Manifest.permission.CALL_PHONE)!=PackageManager.PERMISSION_GRANTED) { permissions(); return@button }
            val sub=subIds[sims.selectedItemPosition]
            AlertDialog.Builder(this).setTitle("موافقة صريحة / Consentement explicite")
                .setMessage("${command.offer}\nUSSD: ${command.ussd}\nSIM: ${sims.selectedItem}\nقد توجد تكلفة من المشغل. تحقق من العرض والتكلفة. لن يتم طلب رقم أو OTP. / Des frais peuvent s’appliquer.")
                .setNegativeButton("إلغاء / Annuler") { _,_ -> startService(Intent(this,BridgeService::class.java).setAction("reject").putExtra("id",command.id)) }
                .setPositiveButton("أوافق وأرسل / Autoriser") { _,_ -> startService(Intent(this,BridgeService::class.java).setAction("execute").putExtra("id",command.id).putExtra("sub",sub)) }.show()
        }
        scope.launch {
            while(isActive) {
                status.text=prefs.getString("status","غير متصل / Déconnecté")
                val raw=prefs.getString("pending",null)
                pendingText.text=if(raw==null) "لا توجد عملية / Aucune demande" else try { val c=PendingCommand.parse(org.json.JSONObject(raw)); "${c.offer}\n${c.ussd}\nانتظار موافقتك / En attente de votre accord" } catch (_: Exception) { "" }
                delay(1000)
            }
        }
    }
    private fun permissions() {
        val list=mutableListOf(Manifest.permission.CALL_PHONE,Manifest.permission.READ_PHONE_STATE)
        if(Build.VERSION.SDK_INT>=33) list.add(Manifest.permission.POST_NOTIFICATIONS)
        requestPermissions(list.toTypedArray(),10)
    }
    private fun loadSims() {
        if(checkSelfPermission(Manifest.permission.READ_PHONE_STATE)!=PackageManager.PERMISSION_GRANTED) return
        try {
            val list=getSystemService(SubscriptionManager::class.java).activeSubscriptionInfoList ?: emptyList()
            subIds=list.map { it.subscriptionId }
            sims.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,list.map { "SIM ${it.simSlotIndex+1}: ${it.carrierName}" })
        } catch (_: SecurityException) { status.text="صلاحية SIM غير متاحة / Permission SIM manquante" }
    }
    override fun onRequestPermissionsResult(requestCode:Int,permissions:Array<out String>,grantResults:IntArray) { super.onRequestPermissionsResult(requestCode,permissions,grantResults); loadSims() }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
