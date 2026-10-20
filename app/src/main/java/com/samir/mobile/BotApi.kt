package com.samir.mobile

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class BotApi(private val token: String, private val base: String = "https://api.telegram.org/", private val client: OkHttpClient = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(40, TimeUnit.SECONDS).callTimeout(45, TimeUnit.SECONDS).build()) {
 fun call(method: String, body: JSONObject): JSONObject {
  val req = Request.Builder().url(base + "bot" + token + "/" + method).post(body.toString().toRequestBody("application/json".toMediaType())).build()
  client.newCall(req).execute().use { response ->
   if (!response.isSuccessful) throw IllegalStateException("Bot API HTTP ${response.code}")
   val obj = JSONObject(response.body?.string() ?: "{}")
   if (!obj.optBoolean("ok")) throw IllegalStateException("Bot API rejected request")
   return obj
  }
 }
 fun updates(offset: Long): JSONArray = call("getUpdates", JSONObject().put("offset", offset).put("timeout", 25).put("allowed_updates", JSONArray(listOf("message", "callback_query")))).getJSONArray("result")
 fun send(chat: Long, text: String, markup: JSONObject? = null) {
  val body = JSONObject().put("chat_id", chat).put("text", Rules.sanitize(text))
  if (markup != null) body.put("reply_markup", markup)
  call("sendMessage", body)
 }
 fun close() { client.dispatcher.cancelAll(); client.connectionPool.evictAll() }
 companion object {
  fun menu() = JSONObject().put("resize_keyboard", true).put("keyboard", JSONArray(listOf(
   listOf("🎁 هدية يومية", "💰 كم هو رصيدي"), listOf("🌐 عروض الإنترنت", "⚡ عروض خاصة"), listOf("➕ علّم كوداً"), listOf("🌐 5G", "👻 سناب شات"))))
 }
}
