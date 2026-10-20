plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "com.samir.netbot"
    compileSdk = 35
    defaultConfig { applicationId = "com.samir.netbot"; minSdk = 26; targetSdk = 35; versionCode = 1; versionName = "0.1.0" }
    signingConfigs {
        create("production") {
            val path = System.getenv("SIGNING_STORE")
            if (path != null) { storeFile = file(path); storePassword = System.getenv("SIGNING_PASSWORD"); keyAlias = "netbot"; keyPassword = System.getenv("SIGNING_PASSWORD") }
        }
    }
    buildTypes {
        getByName("release") { isMinifyEnabled = false; signingConfig = signingConfigs.getByName("production") }
        getByName("debug") { applicationIdSuffix = ".preview"; versionNameSuffix = "-preview" }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    testOptions { unitTests.isReturnDefaultValues = true }
}
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
