package com.samir.mobile

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer

class CoreTest {
 @Test fun whitelist() {assertTrue(Rules.allowed(OWNER,OWNER,true));assertFalse(Rules.allowed(42,OWNER,true));assertFalse(Rules.allowed(OWNER,42,true));assertFalse(Rules.allowed(OWNER,OWNER,false))}
 @Test fun pointsEvery24h() {assertTrue(Rules.giftAllowed(0,100));assertFalse(Rules.giftAllowed(100,100+DAY-1));assertTrue(Rules.giftAllowed(100,100+DAY));assertFalse(Rules.giftAllowed(100,99))}
 @Test fun codeParser() {assertNotNull(Rules.parseCode("هدية | مشغل | *123#"));assertTrue(Rules.parseCode("عرض | مشغل | *123*1# | خاص")!!.special);assertNull(Rules.parseCode("x|y|tel:123"));assertNull(Rules.parseCode("x|y|*1#;rm"));assertNull(Rules.parseCode("x|y|*1#|wrong"))}
 @Test fun messageAndCallbackParser() {
  val json=JSONObject("""{"update_id":5,"message":{"from":{"id":8178411819},"chat":{"id":8178411819,"type":"private"},"date":1,"text":"/start"}}""")
  val u=Parser.parse(json)!!;assertEquals(OWNER,u.user);assertEquals("/start",u.text)
  val cb=JSONObject("""{"update_id":6,"callback_query":{"id":"cb","from":{"id":42},"data":"offer:1","message":{"from":{"id":8178411819},"chat":{"id":8178411819,"type":"private"},"date":1}}}""")
  assertFalse(Rules.allowed(Parser.parse(cb)!!.user,OWNER,true));assertNull(Parser.parse(JSONObject("{\"update_id\":7}")))
 }
 @Test fun sanitizer() {assertFalse(Rules.sanitize("رقم +213 555-123-456 و ٠٥٥٥١٢٣٤٥٦").contains("555"));assertEquals("10 نقاط",Rules.sanitize("10 نقاط"))}
 @Test fun mockTelegramReceivesReply() {
  MockWebServer().use {server ->
   server.enqueue(MockResponse().setBody("""{"ok":true,"result":[{"update_id":1,"message":{"from":{"id":8178411819},"chat":{"id":8178411819,"type":"private"},"date":1,"text":"رصيدي"}}]}"""))
   server.enqueue(MockResponse().setBody("""{"ok":true,"result":{"message_id":2}}"""))
   val api=BotApi("test-token-not-real",server.url("/").toString())
   val incoming=Parser.parse(api.updates(1).getJSONObject(0))!!
   assertTrue(Rules.allowed(incoming.user,incoming.chat,incoming.privateChat))
   api.send(incoming.chat,"رد USSD: +213555123456",BotApi.menu())
   assertEquals("/bottest-token-not-real/getUpdates",server.takeRequest().path)
   val sent=server.takeRequest();assertEquals("/bottest-token-not-real/sendMessage",sent.path)
   val body=JSONObject(sent.body.readUtf8());assertEquals(OWNER,body.getLong("chat_id"));assertFalse(body.getString("text").contains("213555"));assertTrue(body.has("reply_markup"));api.close()
  }
 }
 @Test fun botApiRejectsFailure() {
  MockWebServer().use {server ->server.enqueue(MockResponse().setBody("""{"ok":false}"""));val api=BotApi("fake",server.url("/").toString());try {api.send(OWNER,"x");fail("must reject")}catch(_: IllegalStateException){}finally{api.close()}}
 }
}
