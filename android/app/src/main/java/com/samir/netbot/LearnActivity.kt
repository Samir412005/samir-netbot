package com.samir.netbot

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.widget.*
import kotlinx.coroutines.*
import java.util.UUID

class LearnActivity : Activity() {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main)
    private val requestKey=UUID.randomUUID().toString()
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        val form=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(28,32,28,20) }
        setContentView(ScrollView(this).apply { addView(form) })
        fun label(text:String)=TextView(this).also { it.text=text; it.textSize=18f; form.addView(it) }
        fun field(h:String)=EditText(this).also { it.hint=h; form.addView(it) }
        label("تعليم الكود — أضف عرضاً شخصياً / Ajouter votre code")
        label("اكتب كود USSD الذي تستعمله بنفسك. لا تكتب رقم هاتف ولا OTP. سيظهر لك وحدك في البوت. الحفظ لا ينفذ شيئاً؛ التنفيذ لاحقاً يحتاج موافقتك على الهاتف. القوائم التفاعلية متعددة الخطوات غير مدعومة.\nSaisissez votre propre code USSD, sans numéro ni OTP. Offre privée. L’ajout n’exécute rien.")
        val name=field("اسم العرض / Nom")
        val operator=field("المشغل / Opérateur")
        val ussd=field("USSD — exemple de forme seulement : *XXX#").apply { inputType=1; textDirection=android.view.View.TEXT_DIRECTION_LTR }
        val state=label("")
        val add=Button(this).apply { text="حفظ بعد الموافقة / Enregistrer" }; form.addView(add)
        add.setOnClickListener {
            val n=name.text.toString().trim(); val o=operator.text.toString().trim(); val code=ussd.text.toString().trim()
            if(n.isEmpty() || o.isEmpty() || !code.matches(Regex("[*#][*#0-9]*#")) || code.length>80) { state.text="راجع الاسم والمشغل وصيغة USSD / Vérifiez les champs"; return@setOnClickListener }
            AlertDialog.Builder(this).setTitle("الموافقة على إرسال الكود / Consentement")
                .setMessage("$n — $o\n$code\nنرسل الاسم والمشغل والكود فقط للسيرفر المرتبط، ليظهر لك في البوت. لا ننفذه الآن. / Envoi au serveur lié, aucune exécution maintenant.")
                .setNegativeButton("إلغاء / Annuler",null)
                .setPositiveButton("أوافق / Accepter") { _,_ ->
                    add.isEnabled=false
                    scope.launch {
                        try {
                            val prefs=getSharedPreferences("netbot",MODE_PRIVATE)
                            val token=Vault(this@LearnActivity).token()
                            check(token.isNotEmpty())
                            val bid=withContext(Dispatchers.IO) { BridgeClient(prefs.getString("url","")!!,token).learn(n,o,code,requestKey) }
                            state.text="حُفظ العرض #$bid. افتح عروض الإنترنت في البوت ثم وافق على الهاتف. سيظهر رد الشبكة، وليس وعداً بنجاح التفعيل. / Offre enregistrée, consultez le bot."
                        } catch (_: Exception) { state.text="تعذر الحفظ: راجع الربط وHTTPS / Vérifiez connexion et liaison"; add.isEnabled=true }
                    }
                }.show()
        }
    }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
