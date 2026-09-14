#!/usr/bin/env node
/**
 * Cross-platform Android Release APK build script for WeatherGPT / SkyZen.
 * 
 * Pipeline:
 * 1. Synchronizes web assets into Android project: npx cap copy android
 * 2. Compiles signed Release APK using Gradle: gradlew assembleRelease
 * 3. Verifies output APK artifact and displays file details
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');
const ANDROID_DIR = path.join(ROOT_DIR, 'android');
const IS_WIN = process.platform === 'win32';
const GRADLE_CMD = IS_WIN ? 'gradlew.bat' : './gradlew';

console.log('\n=============================================================');
console.log(' WeatherGPT / SkyZen - Android Release Build Pipeline');
console.log('=============================================================\n');

// Step 1: Copy web assets to Android
console.log('[Step 1/2] Syncing frontend web assets to Android project...');
try {
  execSync('npx cap copy android', {
    cwd: ROOT_DIR,
    stdio: 'inherit'
  });
  console.log('✔ Frontend assets successfully copied to android/app/src/main/assets/public\n');

  // Sanitize assets to remove any OneDrive reparse points
  const assetsDir = path.join(ANDROID_DIR, 'app', 'src', 'main', 'assets');
  function sanitizeAssets(dir) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        sanitizeAssets(fullPath);
      } else if (entry.isFile()) {
        try {
          const content = fs.readFileSync(fullPath);
          fs.unlinkSync(fullPath);
          fs.writeFileSync(fullPath, content);
        } catch (_) {}
      }
    }
  }
  sanitizeAssets(assetsDir);
} catch (err) {
  console.error('✖ Failed to copy web assets via Capacitor:', err.message);
  process.exit(1);
}

// Step 2: Build release APK with Gradle
console.log('[Step 2/2] Building Android Release APK via Gradle...');
try {
  execSync(`${GRADLE_CMD} assembleRelease -x lintVitalRelease`, {
    cwd: ANDROID_DIR,
    stdio: 'inherit'
  });
  console.log('\n✔ Gradle release build completed successfully!\n');
} catch (err) {
  console.error('✖ Gradle build failed:', err.message);
  process.exit(1);
}

// Step 3: Verify APK output artifact
const apkPath = path.join(
  ANDROID_DIR,
  'app',
  'build',
  'outputs',
  'apk',
  'release',
  'app-release.apk'
);

if (fs.existsSync(apkPath)) {
  const stats = fs.statSync(apkPath);
  const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
  console.log('=============================================================');
  console.log(' [BUILD SUCCESS] Release APK Generated');
  console.log('=============================================================');
  console.log(` File Path : ${apkPath}`);
  console.log(` File Size : ${sizeMB} MB (${stats.size} bytes)`);
  console.log(' Ready for direct installation on physical Android phones!');
  console.log('=============================================================\n');
} else {
  console.warn(`⚠ Warning: Expected APK not found at: ${apkPath}`);
}
