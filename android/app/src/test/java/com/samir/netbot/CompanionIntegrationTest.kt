package com.samir.netbot

import org.junit.Test
import org.junit.Assert.*
import org.json.JSONObject
import okhttp3.OkHttpClient
import java.io.File
import java.security.KeyStore
import java.security.cert.CertificateFactory
import javax.net.ssl.*

class CompanionIntegrationTest {
    @Test fun rejectsCleartext() { assertThrows(IllegalArgumentException::class.java) { BridgeClient("http://example.com") } }
    @Test fun protocolProofWithSimulatedTelephony() {
        val base=System.getenv("INTEGRATION_BASE") ?: return
        val ca=CertificateFactory.getInstance("X.509").generateCertificate(File(System.getenv("INTEGRATION_CERT")).inputStream())
        val keys=KeyStore.getInstance(KeyStore.getDefaultType()).apply { load(null,null); setCertificateEntry("test",ca) }
        val tmf=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(keys) }
        val trust=tmf.trustManagers.filterIsInstance<X509TrustManager>().single()
        val ssl=SSLContext.getInstance("TLS").apply { init(null,arrayOf(trust),null) }
        // Trust only the ephemeral CI CA here; production has no trust override or fake USSD backend.
        val http=OkHttpClient.Builder().sslSocketFactory(ssl.socketFactory,trust).build()
        val token=BridgeClient(base,"",http).register(File(System.getenv("PAIR_CODE_FILE")).readText().trim())
        File(System.getenv("COMPANION_READY_FILE")).writeText("registered")
        val c=BridgeClient(base,token,http).poll()!!
        assertEquals("*000*000#",c.ussd)
        val fakeNetworkReply="SIMULATED_ACTIVATION_OK — no mobile network contacted"
        val state=BridgeClient(base,token,http).result(c.id,"response",fakeNetworkReply)
        assertEquals("success",state)
        File(System.getenv("PROOF_FILE")).writeText(JSONObject().put("simulation",true).put("environment","Kotlin JVM companion client + real HTTPS FastAPI; simulated telephony, NOT Android device/emulator").put("command_id",c.id).put("ussd",c.ussd).put("response",fakeNetworkReply).put("state",state).toString(2))
    }
}
