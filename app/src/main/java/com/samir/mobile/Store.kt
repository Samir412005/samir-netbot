package com.samir.mobile

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

data class Offer(val id: Long, val name: String, val operator: String, val code: String, val special: Boolean)
data class Pending(val id: Long, val chat: Long, val offer: Offer, val expires: Long)
class Store(c: Context): SQLiteOpenHelper(c.applicationContext, "local_bot.db", null, 1) {
 override fun onCreate(db: SQLiteDatabase) {
  db.execSQL("CREATE TABLE wallet(id INTEGER PRIMARY KEY, points INTEGER NOT NULL, last INTEGER NOT NULL)")
  db.execSQL("INSERT INTO wallet VALUES(1,0,0)")
  db.execSQL("CREATE TABLE offers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, operator TEXT, code TEXT, special INTEGER)")
  db.execSQL("CREATE TABLE pending(id INTEGER PRIMARY KEY AUTOINCREMENT, chat INTEGER, offer INTEGER, expires INTEGER, state TEXT)")
  db.execSQL("CREATE TABLE logs(id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER, status TEXT, reply TEXT)")
  db.execSQL("CREATE TABLE outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, chat INTEGER, text TEXT)")
 }
 override fun onUpgrade(db: SQLiteDatabase, old: Int, new: Int) {}
 @Synchronized fun gift(now: Long): Boolean {
  val db = writableDatabase; db.beginTransaction()
  try {
   val last = db.rawQuery("SELECT last FROM wallet WHERE id=1", null).use { it.moveToFirst(); it.getLong(0) }
   val ok = Rules.giftAllowed(last, now)
   if (ok) db.execSQL("UPDATE wallet SET points=points+10,last=? WHERE id=1", arrayOf(now))
   db.setTransactionSuccessful(); return ok
  } finally { db.endTransaction() }
 }
 fun balance(): Long = readableDatabase.rawQuery("SELECT points FROM wallet WHERE id=1", null).use { it.moveToFirst(); it.getLong(0) }
 fun add(c: NewCode) { writableDatabase.insertOrThrow("offers", null, ContentValues().apply { put("name", c.name); put("operator", c.operator); put("code", c.code); put("special", if(c.special) 1 else 0) }) }
 fun offers(special: Boolean = false): List<Offer> = readableDatabase.rawQuery("SELECT id,name,operator,code,special FROM offers" + if(special) " WHERE special=1 ORDER BY id" else " ORDER BY id", null).use { c -> buildList { while(c.moveToNext()) add(Offer(c.getLong(0),c.getString(1),c.getString(2),c.getString(3),c.getInt(4)==1)) } }
 fun request(chat: Long, offer: Long): Long = writableDatabase.insertOrThrow("pending", null, ContentValues().apply { put("chat",chat);put("offer",offer);put("expires",System.currentTimeMillis()+120_000);put("state","waiting") })
 fun pending(): List<Pending> {
  val all = offers().associateBy { it.id }
  return readableDatabase.rawQuery("SELECT id,chat,offer,expires FROM pending WHERE state='waiting' AND expires>?", arrayOf(System.currentTimeMillis().toString())).use { c -> buildList { while(c.moveToNext()) { val o=all[c.getLong(2)]; if(o!=null) add(Pending(c.getLong(0),c.getLong(1),o,c.getLong(3))) } } }
 }
 fun consume(p: Pending): Boolean = writableDatabase.update("pending",ContentValues().apply { put("state","consumed") },"id=? AND state='waiting' AND expires>?",arrayOf(p.id.toString(),System.currentTimeMillis().toString())) == 1
 @Synchronized fun finish(chat: Long, status: String, text: String) {
  val clean=Rules.sanitize(text); val db=writableDatabase;db.beginTransaction()
  try {
   db.insertOrThrow("logs",null,ContentValues().apply {put("at",System.currentTimeMillis());put("status",status);put("reply",clean)})
   db.execSQL("DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 50)")
   db.insertOrThrow("outbox",null,ContentValues().apply {put("chat",chat);put("text","$status: $clean")})
   db.setTransactionSuccessful()
  } finally { db.endTransaction() }
 }
 fun expire() {
  writableDatabase.execSQL("UPDATE pending SET state='expired' WHERE state='waiting' AND expires<=?",arrayOf(System.currentTimeMillis()))
 }
 fun logs(): String = readableDatabase.rawQuery("SELECT at,status,reply FROM logs ORDER BY id DESC LIMIT 50",null).use { c -> buildString { while(c.moveToNext()) append("${java.util.Date(c.getLong(0))} | ${c.getString(1)} | ${c.getString(2)}\n\n") } }
 fun drain(api: BotApi) {
  readableDatabase.rawQuery("SELECT id,chat,text FROM outbox ORDER BY id LIMIT 10",null).use { c -> while(c.moveToNext()) { api.send(c.getLong(1),c.getString(2));writableDatabase.delete("outbox","id=?",arrayOf(c.getLong(0).toString())) } }
 }
}
