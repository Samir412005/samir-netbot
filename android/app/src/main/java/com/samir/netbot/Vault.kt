package com.samir.netbot

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class Vault(context: Context) {
    private val prefs=context.getSharedPreferences("netbot",Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if(store.containsAlias("netbot-token")) return store.getKey("netbot-token",null) as SecretKey
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder("netbot-token",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build()); generateKey()
        }
    }
    fun saveToken(token:String) {
        val c=Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.ENCRYPT_MODE,key())
        val encoded=Base64.encodeToString(c.iv+c.doFinal(token.toByteArray()),Base64.NO_WRAP)
        check(prefs.edit().putString("token",encoded).commit())
    }
    fun token(): String = try {
        val encoded=prefs.getString("token",null)
        if(encoded==null) "" else {
            val data=Base64.decode(encoded,Base64.NO_WRAP)
            val c=Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,data.copyOfRange(0,12)))
            String(c.doFinal(data.copyOfRange(12,data.size)))
        }
    } catch (_: Exception) { "" }
}
