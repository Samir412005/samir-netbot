package com.samir.netbot

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class PendingCommand(val id: String, val ussd: String, val offer: String, val expires: Long) {
    fun json() = JSONObject().put("id",id).put("ussd",ussd).put("offer_name",offer).put("expires_at",expires).toString()
    companion object { fun parse(j: JSONObject) = PendingCommand(j.getString("id"),j.getString("ussd"),j.getString("offer_name"),j.getLong("expires_at")) }
}

/** Shared by actual Android service and JVM companion-protocol integration test. No phone number field. */
class BridgeClient(private val base: String, private val token: String = "", private val http: OkHttpClient = OkHttpClient.Builder().readTimeout(30,TimeUnit.SECONDS).build()) {
    init { require(base.startsWith("https://") && !base.contains('@')) { "HTTPS only; no embedded credentials" } }
    private fun request(path: String, body: JSONObject? = null): JSONObject {
        val builder = Request.Builder().url(base.trimEnd('/')+path)
        if(token.isNotEmpty()) builder.header("Authorization","Bearer $token")
        if(body != null) builder.post(body.toString().toRequestBody("application/json".toMediaType()))
        http.newCall(builder.build()).execute().use {
            check(it.isSuccessful) { "HTTP ${it.code}" }
            return JSONObject(it.body!!.string())
        }
    }
    fun register(code: String): String {
        require(code.matches(Regex("[0-9]{6}")))
        return request("/device/register",JSONObject().put("code",code).put("name","Android companion")).getString("device_token")
    }
    fun learn(name: String, operator: String, ussd: String, key: String): Int = request("/device/offers",JSONObject().put("name",name).put("operator",operator).put("ussd",ussd).put("idempotency_key",key).put("consent",true)).getInt("bid")
    fun poll(): PendingCommand? { val j=request("/device/commands"); return if(j.isNull("command")) null else PendingCommand.parse(j.getJSONObject("command")) }
    fun result(id: String, outcome: String, text: String): String = request("/device/result",JSONObject().put("command_id",id).put("outcome",outcome).put("response",text.take(4000))).getString("state")
}
