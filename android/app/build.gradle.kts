import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.networkexplorer.survey"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.networkexplorer.survey"
        minSdk = 29 // Android 10: needed for separate tx/rx link speeds
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    // The app uses only the Android framework (no AndroidX) to stay small.
    testImplementation("junit:junit:4.13.2")
}
