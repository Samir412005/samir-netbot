plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
 namespace = "com.samir.mobile"
 compileSdk = 35
 defaultConfig { applicationId = "com.samir.mobile"; minSdk = 26; targetSdk = 34; versionCode = 3; versionName = "0.3.0-preview3" }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
 testOptions { unitTests.isReturnDefaultValues = true }
}
dependencies {
 implementation("com.squareup.okhttp3:okhttp:4.12.0")
 implementation("androidx.security:security-crypto:1.1.0-alpha06")
 testImplementation("junit:junit:4.13.2")
 testImplementation("org.json:json:20240303")
 testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}
