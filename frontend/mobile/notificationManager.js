/**
 * SkyZen Push Notification Manager (Capacitor & FCM)
 *
 * Handles:
 * - Android notification runtime permissions (Android 13+ POST_NOTIFICATIONS)
 * - FCM registration token retrieval, caching, and refresh
 * - Device association with backend authenticated user session
 * - Token removal on user sign-out
 * - Foreground notification banners and tray tap navigation
 * - Graceful degradation when permissions are denied or Push plugin is unavailable
 */

class SkyZenNotificationManager {
  constructor() {
    this.tokenStorageKey = "skyzen_fcm_token";
    this.permissionStorageKey = "skyzen_notification_permission";
    this.pushPlugin = null;
    this.currentToken = localStorage.getItem(this.tokenStorageKey) || null;
    this.isRegistered = false;
  }

  getPlugin() {
    if (this.pushPlugin) return this.pushPlugin;
    if (window.Capacitor && window.Capacitor.isPluginAvailable("PushNotifications")) {
      this.pushPlugin = window.Capacitor.Plugins.PushNotifications;
    }
    return this.pushPlugin;
  }

  /**
   * Initializes push notifications and sets up lifecycle event listeners.
   */
  async init() {
    const plugin = this.getPlugin();
    if (!plugin) {
      console.log("[SkyZen FCM] PushNotifications plugin unavailable on current platform/web browser. Running in fallback mode.");
      return { status: "unavailable" };
    }

    try {
      this._setupListeners(plugin);

      // Check current permission status
      const permStatus = await plugin.checkPermissions();
      const currentReceive = permStatus.receive || permStatus.display;

      if (currentReceive === "granted") {
        localStorage.setItem(this.permissionStorageKey, "granted");
        await plugin.register();
        return { status: "granted" };
      } else if (currentReceive === "denied") {
        localStorage.setItem(this.permissionStorageKey, "denied");
        console.log("[SkyZen FCM] Notification permission was previously denied. App functions normally.");
        return { status: "denied" };
      } else {
        // Prompt for permission if user has enabled notifications in preferences
        return await this.requestPermission();
      }
    } catch (err) {
      console.warn("[SkyZen FCM] Initialization error (non-fatal):", err.message);
      return { status: "error", error: err.message };
    }
  }

  /**
   * Requests runtime notification permission from user.
   */
  async requestPermission() {
    const plugin = this.getPlugin();
    if (!plugin) {
      return { status: "unavailable" };
    }

    try {
      const result = await plugin.requestPermissions();
      const granted = result.receive === "granted" || result.display === "granted";

      if (granted) {
        localStorage.setItem(this.permissionStorageKey, "granted");
        console.log("[SkyZen FCM] Notification permission granted by user.");
        await plugin.register();
        return { status: "granted" };
      } else {
        localStorage.setItem(this.permissionStorageKey, "denied");
        console.log("[SkyZen FCM] Notification permission denied. SkyZen will continue without push alerts.");
        return { status: "denied" };
      }
    } catch (err) {
      console.warn("[SkyZen FCM] Failed to request notification permission:", err.message);
      return { status: "denied", error: err.message };
    }
  }

  /**
   * Registers listeners for FCM registration, errors, and incoming pushes.
   */
  _setupListeners(plugin) {
    if (this.isRegistered) return;
    this.isRegistered = true;

    // 1. Successful FCM Token Registration / Refresh
    plugin.addListener("registration", async (tokenData) => {
      const fcmToken = tokenData.value;
      console.log("[SkyZen FCM] Device token received from FCM.");
      this.currentToken = fcmToken;
      localStorage.setItem(this.tokenStorageKey, fcmToken);

      // Associate device token with authenticated backend account if logged in
      await this.syncDeviceToken();
    });

    // 2. Token Registration Error Handling
    plugin.addListener("registrationError", (error) => {
      console.warn("[SkyZen FCM] Token registration failed:", error);
    });

    // 3. Foreground Notification Received
    plugin.addListener("pushNotificationReceived", (notification) => {
      console.log("[SkyZen FCM] Foreground notification received:", notification.title);
      if (typeof window.showMobileNotice === "function") {
        window.showMobileNotice(`${notification.title}: ${notification.body}`, "warning", 6000);
      }
      // Notify other views
      window.dispatchEvent(new CustomEvent("skyzen:notificationReceived", { detail: notification }));
    });

    // 4. Action Performed (User tapped notification in system tray)
    plugin.addListener("pushNotificationActionPerformed", (action) => {
      console.log("[SkyZen FCM] Notification tapped from system tray:", action);
      const notificationData = action?.notification?.data || {};
      const targetDistrict = notificationData.district || notificationData.location;

      if (targetDistrict) {
        const locSelect = document.getElementById("locationSelect");
        if (locSelect) {
          for (let i = 0; i < locSelect.options.length; i++) {
            if (locSelect.options[i].value.toLowerCase() === targetDistrict.toLowerCase()) {
              locSelect.selectedIndex = i;
              break;
            }
          }
        }
      }

      if (typeof window.navigateToScreen === "function") {
        window.navigateToScreen("alerts");
      }
      window.dispatchEvent(new CustomEvent("skyzen:notificationTapped", { detail: action }));
    });
  }

  /**
   * Syncs the current client FCM token with the backend.
   */
  async syncDeviceToken() {
    if (!this.currentToken) {
      this.currentToken = localStorage.getItem(this.tokenStorageKey);
    }
    if (!this.currentToken) return;

    if (window.apiClient && window.apiClient.isAuthenticated()) {
      try {
        const platform = (window.Capacitor && window.Capacitor.getPlatform()) || "android";
        await window.apiClient.registerDeviceToken(this.currentToken, platform, "SkyZen Android Device");
        console.log("[SkyZen FCM] Device token synced successfully with backend account.");
      } catch (err) {
        console.warn("[SkyZen FCM] Could not sync device token to backend:", err.message);
      }
    }
  }

  /**
   * Unregisters the current device token from the user account on sign out.
   */
  async unregisterOnSignOut() {
    if (this.currentToken && window.apiClient && window.apiClient.isAuthenticated()) {
      try {
        await window.apiClient.unregisterDeviceToken(this.currentToken);
        console.log("[SkyZen FCM] Device token unregistered from backend session.");
      } catch (err) {
        console.warn("[SkyZen FCM] Unregister token error on sign-out:", err.message);
      }
    }
  }

  /**
   * Dispatches a controlled test notification.
   */
  async sendTestNotification() {
    if (!window.apiClient || !window.apiClient.isAuthenticated()) {
      throw new Error("Must be signed in to dispatch a test notification.");
    }
    return await window.apiClient.sendTestNotification(
      "SkyZen Test Notification",
      "Controlled verification of IMD push notification delivery pipeline.",
      this.currentToken
    );
  }
}

// Export singleton instance
const notificationManager = new SkyZenNotificationManager();
if (typeof window !== "undefined") {
  window.notificationManager = notificationManager;
}
