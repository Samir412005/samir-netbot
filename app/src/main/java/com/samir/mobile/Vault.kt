package com.samir.mobile

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object Vault {
 @Synchronized fun prefs(c: Context) = EncryptedSharedPreferences.create(c, "token_vault", MasterKey.Builder(c).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(), EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV, EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
 fun token(c: Context) = prefs(c).getString("token", "") ?: ""
 fun save(c: Context, value: String) { check(prefs(c).edit().putString("token", value).commit()) }
}
