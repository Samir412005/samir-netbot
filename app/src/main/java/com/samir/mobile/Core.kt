package com.samir.mobile

import org.json.JSONObject

const val OWNER = 8178411819L
const val DAY = 86_400_000L
object Rules {
 fun allowed(user: Long, chat: Long, privateChat: Boolean) = user == OWNER && chat == OWNER && privateChat
 fun giftAllowed(last: Long, now: Long) = last == 0L || (now >= last && now - last >= DAY)
 fun sanitize(text: String): String = text.map { c -> if (Character.isDigit(c)) Character.getNumericValue(c).digitToChar() else c }.joinToString("")
  .replace(Regex("\\+?\\d(?:[\\s().-]*\\d){4,}"), "[رقم مخفي]").take(3500)
 fun parseCode(text: String): NewCode? {
  val p = text.split('|').map { it.trim() }
  if (p.size !in 3..4 || p[0].length !in 1..80 || p[1].length !in 1..40) return null
  if (!Regex("\\*[0-9*]{1,40}#").matches(p[2])) return null
  if (p.size == 4 && p[3] != "خاص") return null
  return NewCode(p[0], p[1], p[2], p.size == 4)
 }
}
data class NewCode(val name: String, val operator: String, val code: String, val special: Boolean)
data class Incoming(val updateId: Long, val user: Long, val chat: Long, val privateChat: Boolean, val text: String, val date: Long, val callback: String?)
object Parser {
 fun parse(o: JSONObject): Incoming? {
  val cb = o.optJSONObject("callback_query")
  val m = cb?.optJSONObject("message") ?: o.optJSONObject("message") ?: return null
  val from = cb?.optJSONObject("from") ?: m.optJSONObject("from") ?: return null
  val chat = m.optJSONObject("chat") ?: return null
  return Incoming(o.getLong("update_id"), from.optLong("id"), chat.optLong("id"), chat.optString("type") == "private",
   cb?.optString("data") ?: m.optString("text"), m.optLong("date"), cb?.optString("id"))
 }
}
