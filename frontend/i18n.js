// SkyZen Centralized Internationalization (i18n) Engine
// Supports English (en), Tamil (ta), and Hindi (hi)
// Centralized translation dictionary & dynamic string localizer

const I18N_DICT = {
  "en": {
    // Navigation
    "nav.home": "Home",
    "nav.chat": "WeatherGPT",
    "nav.ai": "AI",
    "nav.map": "Live Map",
    "nav.alerts": "Alerts",
    "nav.locations": "Saved",
    "nav.settings": "Settings",
    "nav.more": "More",
    "nav.back_to_home": "Back to Home",
    "nav.back_to_hub": "Back to Hub",

    // Welcome & Auth
    "auth.welcome.title": "SkyZen.",
    "auth.welcome.tagline": "Clearer Skies. Brighter Days.",
    "auth.welcome.desc": "AI-powered weather intelligence, severe alerts from IMD, and precision forecasts.",
    "auth.welcome.signin": "Sign In",
    "auth.welcome.signup": "Create Account",
    "auth.welcome.footer": "Official MoES & IMD Decision Engine (WeatherGPT)",
    "auth.login.title": "Welcome Back",
    "auth.login.subtitle": "Sign in to your SkyZen account",
    "auth.login.email": "Email Address",
    "auth.login.password": "Password",
    "auth.login.submit": "Sign In",
    "auth.login.forgot": "Forgot?",
    "auth.login.switch": "Don't have an account?",
    "auth.login.create_one": "Create one",
    "auth.signup.title": "Create Account",
    "auth.signup.subtitle": "Join SkyZen for real-time weather intelligence",
    "auth.signup.name": "Full Name",
    "auth.signup.email": "Email Address",
    "auth.signup.password": "Password",
    "auth.signup.confirm": "Confirm Password",
    "auth.signup.submit": "Create Account",
    "auth.signup.switch": "Already have an account?",
    "auth.reset.title": "Reset Password",
    "auth.reset.subtitle": "Enter your registered email address to receive a password reset code.",
    "auth.reset.submit": "Generate Reset Code",
    "auth.reset.remember": "Remember your password? Sign In",
    "auth.reset_new.title": "Set New Password",
    "auth.reset_new.subtitle": "Enter your reset code and set a strong new password.",
    "auth.reset_new.token": "Reset Token / Code",
    "auth.reset_new.password": "New Password",
    "auth.reset_new.confirm": "Confirm New Password",
    "auth.reset_new.submit": "Update Password",
    "auth.reset_new.return": "Return to Sign In",

    // Onboarding
    "onboarding.title": "Welcome to SkyZen",
    "onboarding.subtitle": "Set up your profile to personalize meteorological intelligence and advisories.",
    "onboarding.name": "Full Name",
    "onboarding.role": "Primary Role / Persona",
    "onboarding.lang": "Preferred Language / மொழி",
    "onboarding.alerts": "Enable severe meteorological alerts & advisories",
    "onboarding.submit": "Complete Setup & Enter SkyZen",

    // Dashboard & Weather Cards
    "dashboard.weather": "Weather Intelligence",
    "dashboard.current": "Current Observations",
    "dashboard.live_weather": "LIVE WEATHER",
    "dashboard.rain_prob": "Rain Chance",
    "dashboard.wind": "Wind Speed",
    "dashboard.humidity": "Humidity",
    "dashboard.uv_index": "UV Index",
    "dashboard.consensus": "Forecast Consensus",
    "dashboard.forecast": "Hourly Forecast",
    "dashboard.hourly_next24": "Next 24 Hours",
    "dashboard.daily_7day": "7-Day Forecast",
    "dashboard.imd_model": "IMD Numerical Model",
    "dashboard.advisories": "AI Advisories",
    "dashboard.ask_skyzen": "Ask SkyZen",
    "dashboard.ask_sub": "Get weather-aware answers for your daily plans",
    "dashboard.start_convo": "Start Conversation",
    "dashboard.tools_title": "Weather Intelligence Tools",
    "dashboard.tools_sub": "Real-time Telemetry",
    "dashboard.tool_aqi": "Air Quality",
    "dashboard.tool_map": "Weather Map",
    "dashboard.tool_alerts": "Alerts & Radar",
    "dashboard.tool_saved": "Saved Cities",
    "dashboard.retry": "Retry Connection",
    "dashboard.loading_telemetry": "Fetching Live Meteorological Telemetry...",
    "dashboard.error_telemetry": "Failed to retrieve weather data.",
    "dashboard.feels_like": "Feels like",
    "dashboard.observed_at": "Observed at",
    "dashboard.sources_title": "WEATHER SOURCES",

    // Location Permission Prompt
    "location.prompt_title": "Personal Weather & Warning Intelligence",
    "location.prompt_text": "Allow SkyZen to use your location for local weather and alerts.",
    "location.prompt_allow": "Allow Location",
    "location.prompt_dismiss": "Not Now",

    // AI Chat Screen
    "chat.title": "SkyZen AI Assistant",
    "chat.subtitle": "WeatherGPT Decision Assistant • Grounded on Official IMD Telemetry",
    "chat.reset": "Reset",
    "chat.placeholder": "Ask SkyZen about your plans... (e.g. Will it rain at 5 PM?)",
    "chat.send": "Send",
    "chat.disclaimer": "AI responses can be inaccurate. Official IMD alerts take precedence.",
    "chat.architecture_title": "Reasoning Architecture",
    "chat.architecture_sub": "SkyZen strictly adheres to safety-first meteorological validation:",
    "chat.arch_1": "1. Official Live Disaster Warnings (Top Priority)",
    "chat.arch_2": "2. Verified IMD & Multi-Source Agreement",
    "chat.arch_3": "3. Deterministic Hazard Decision Rules",
    "chat.arch_4": "4. Anti-Hallucination Guardrails",
    "chat.why_answer": "Why this answer? (Verification)",
    "chat.chip_rain": "Will it rain tomorrow?",
    "chat.chip_college": "College today?",
    "chat.chip_bike": "Take my bike?",
    "chat.chip_umbrella": "Need umbrella?",
    "chat.new": "New Chat",
    "chat.persona.student": "Student",
    "chat.persona.commuter": "Commuter",
    "chat.persona.farmer": "Farmer",
    "chat.persona.fisherman": "Fisherman",
    "chat.persona.traveller": "Traveller",
    "chat.persona.disaster_response": "Disaster Response",
    "chat.persona.general": "General User",

    // Extended Weather & Trends Screen
    "weather.today_hourly": "Today's Hourly Forecast",
    "weather.today_sub": "24-Hour Horizon",
    "weather.tomorrow_hourly": "Tomorrow's Hourly Forecast",
    "weather.extended_future": "Extended Future Forecast",
    "weather.climate_archive": "Climate Trend Archive (NASA POWER / IMD)",
    "weather.offline": "Network Offline. Displaying cached weather telemetry.",

    // Alerts Screen
    "alerts.title": "Official IMD Warnings & Risk Register",
    "alerts.subtitle": "Real-time Emergency Feeds",
    "alerts.tab_all": "All Alerts",
    "alerts.tab_severe": "Severe",
    "alerts.tab_rain": "Heavy Rain",
    "alerts.tab_heat": "Heatwave",
    "alerts.tab_wind": "Squall & Wind",
    "alerts.source_label": "Source: IMD (India Meteorological Department)",
    "alerts.valid_until": "Valid until",
    "alerts.official_warning": "OFFICIAL IMD WARNING",

    // Map Screen
    "map.title": "Geospatial Weather & Radar Map",
    "map.recenter": "Recenter",
    "map.toggle_alerts": "Toggle Alerts",
    "map.search_placeholder": "Search city, district, or coordinates...",
    "map.my_location": "My Location",
    "map.weather_here": "Weather Here",
    "map.refresh": "Refresh",
    "map.layer_weather": "Weather",
    "map.layer_rain_risk": "Rain Risk",
    "map.layer_wind_risk": "Wind Risk",
    "map.layer_heat_risk": "Heat Risk",
    "map.layer_warnings": "Official Warnings",
    "map.selected_location": "Selected Location",
    "map.tap_hint": "Tap anywhere on the map to inspect live weather & alerts",
    "map.ask_ai": "Ask AI About This Place",
    "map.set_home": "Set as Home",
    "map.save_location": "Save Location",
    "map.compare_locations": "Compare Locations",
    "map.compare_sub": "Real-time backend comparison across locations",
    "map.no_warning": "No active IMD meteorological warnings for this location.",
    "map.cpcb_aqi": "CPCB Ground AQI",
    "map.model_aqi": "Modelled Air Quality (Open-Meteo)",
    "map.layer_rainfall": "Rainfall",
    "map.layer_temp": "Temperature",
    "map.layer_wind": "Wind",
    "map.layer_clouds": "Clouds",
    "map.timeline": "Timeline:",
    "map.now": "Now",
    "map.offline_title": "Interactive Map Tiles Offline / Unavailable",
    "map.offline_desc": "Displaying coordinate weather telemetry below.",

    // Air Quality Screen
    "aqi.title": "Air Quality Index (AQI)",
    "aqi.subtitle": "Real-time Ambient Air Monitoring",
    "aqi.model_label": "Air Quality Model:",
    "aqi.cpcb_unconfigured": "CPCB OFFICIAL API ACCESS NOT CONFIGURED",
    "aqi.pollutants_title": "Key Pollutants Breakdown",
    "aqi.health_title": "Health & Activity Recommendations",
    "aqi.rec_fitness": "Safe for jogging and regular outdoor fitness.",
    "aqi.rec_ventilation": "Normal home and office ventilation recommended.",

    // Saved Locations Screen
    "locations.title": "Saved Locations",
    "locations.add_city": "Add City",
    "locations.modal_title": "Add Weather Location",
    "locations.modal_desc": "Select popular metropolitan or coastal cities, or enter a custom location name:",
    "locations.custom_placeholder": "Type city name (e.g. Ooty)...",
    "locations.add_btn": "Add",

    // More Screen Hub
    "more.tools_heading": "Weather Intelligence Tools",
    "more.aqi_item": "Air Quality Index & Pollutants",
    "more.map_item": "Geospatial Radar & Alert Map",
    "more.forecast_item": "Detailed Forecast & Climate Trends",
    "more.saved_item": "Manage Saved Cities",
    "more.ai_heading": "AI Advisory Engines",
    "more.ai_chat_item": "Ask SkyZen Conversational Assistant",
    "more.travel_item": "Inter-District Travel Advisory",
    "more.agri_item": "Agricultural & Crop Protection",
    "more.pref_heading": "Preferences & Account",
    "more.profile_item": "User Profile & Authentication",
    "more.settings_item": "Application Settings & Language",

    // Profile Screen
    "profile.title": "User Profile & Account",
    "profile.verified": "Verified",
    "profile.account_role": "Account Role:",
    "profile.status": "Status:",
    "profile.active": "Active",
    "profile.edit_heading": "Personalize Profile & Persona",
    "profile.full_name": "Full Name",
    "profile.role_label": "Role / Meteorological Persona",
    "profile.lang_label": "Preferred Language / மொழி",
    "profile.alerts_checkbox": "Severe meteorological alert notifications",
    "profile.save_btn": "Save Profile Changes",
    "profile.signout_btn": "Sign Out of SkyZen",
    "profile.guest_prompt": "Sign in to sync your saved locations, telemetry, and meteorological preferences.",
    "profile.guest_login_btn": "Sign In / Create Account",
    "profile.saved_summary": "Saved Cities Summary",

    // Settings Screen
    "settings.title": "Application Settings",
    "settings.profile_persona": "Profile & Role Persona",
    "settings.profile_desc": "Manage name, role persona & language",
    "settings.language": "Language / மொழி",
    "settings.language.en": "English (English)",
    "settings.language.ta": "தமிழ் (Tamil)",
    "settings.language.hi": "हिन्दी (Hindi)",
    "settings.notifications": "Emergency Warnings & FCM Notifications",
    "settings.push_channel": "Push Alerts Channel",
    "settings.push_active": "Active (FCM)",
    "settings.test_alert_btn": "Send Controlled Test Alert",
    "settings.units": "Preferred Measurement Units",
    "settings.env_server": "API Environment Server",
    "settings.save": "Save Settings",
    "settings.logout": "Sign Out",

    // Accessibility & UI Controls
    "btn.gps": "GPS",
    "btn.refresh": "Refresh",
    "btn.retry": "Retry",
    "btn.close": "Close",
    "btn.listen": "Listen",
    "btn.stop": "Stop",
    "btn.send": "Send"
  },

  "ta": {
    // Navigation
    "nav.home": "முகப்பு",
    "nav.chat": "WeatherGPT",
    "nav.ai": "செயற்கை நுண்ணறிவு",
    "nav.map": "நேரடி வரைபடம்",
    "nav.alerts": "எச்சரிக்கைகள்",
    "nav.locations": "சேமிக்கப்பட்டவை",
    "nav.settings": "அமைப்புகள்",
    "nav.more": "மேலும்",
    "nav.back_to_home": "முகப்பிற்கு செல்",
    "nav.back_to_hub": "ஹப் பகுதிக்கு செல்",

    // Welcome & Auth
    "auth.welcome.title": "SkyZen.",
    "auth.welcome.tagline": "தெளிவான வானம். பிரகாசமான நாட்கள்.",
    "auth.welcome.desc": "செயற்கை நுண்ணறிவு வானிலை தரவுகள், IMD கடுமையான எச்சரிக்கைகள் மற்றும் துல்லியமான முன்னறிவிப்புகள்.",
    "auth.welcome.signin": "உள்நுழைக",
    "auth.welcome.signup": "கணக்கை உருவாக்கு",
    "auth.welcome.footer": "அதிகாரப்பூர்வ MoES & IMD முடிவு இயந்திரம் (WeatherGPT)",
    "auth.login.title": "மீண்டும் வருக",
    "auth.login.subtitle": "உங்கள் SkyZen கணக்கில் உள்நுழையவும்",
    "auth.login.email": "மின்னஞ்சல் முகவரி",
    "auth.login.password": "கடவுச்சொல்",
    "auth.login.submit": "உள்நுழைக",
    "auth.login.forgot": "மறந்துவிட்டதா?",
    "auth.login.switch": "கணக்கு இல்லையா?",
    "auth.login.create_one": "புதிய கணக்கு உருவாக்கு",
    "auth.signup.title": "கணக்கை உருவாக்கு",
    "auth.signup.subtitle": "உண்மையான நேர வானிலை தகவல்களுக்கு SkyZen-இல் சேரவும்",
    "auth.signup.name": "முழு பெயர்",
    "auth.signup.email": "மின்னஞ்சல் முகவரி",
    "auth.signup.password": "கடவுச்சொல்",
    "auth.signup.confirm": "கடவுச்சொல்லை உறுதிப்படுத்து",
    "auth.signup.submit": "கணக்கை உருவாக்கு",
    "auth.signup.switch": "ஏற்கனவே கணக்கு உள்ளதா?",
    "auth.reset.title": "கடவுச்சொல்லை மீட்டமை",
    "auth.reset.subtitle": "உங்கள் பதிவுசெய்த மின்னஞ்சல் முகவரியை உள்ளிடவும்.",
    "auth.reset.submit": "மீட்டமைப்பு குறியீட்டை உருவாக்கு",
    "auth.reset.remember": "கடவுச்சொல் நினைவிருக்கிறதா? உள்நுழைக",
    "auth.reset_new.title": "புதிய கடவுச்சொல் அமை",
    "auth.reset_new.subtitle": "உங்கள் மீட்டமைப்பு குறியீட்டை உள்ளிட்டு புதிய கடவுச்சொல்லை அமைக்கவும்.",
    "auth.reset_new.token": "மீட்டமைப்பு டோக்கன் / குறியீடு",
    "auth.reset_new.password": "புதிய கடவுச்சொல்",
    "auth.reset_new.confirm": "புதிய கடவுச்சொல்லை உறுதிப்படுத்து",
    "auth.reset_new.submit": "கடவுச்சொல்லை புதுப்பி",
    "auth.reset_new.return": "உள்நுழைவிற்கு திரும்பு",

    // Onboarding
    "onboarding.title": "SkyZen-க்கு வரவேற்கிறோம்",
    "onboarding.subtitle": "வானிலை தகவல்கள் மற்றும் ஆலோசனைகளை தனிப்பயனாக்க உங்கள் சுயவிவரத்தை அமைக்கவும்.",
    "onboarding.name": "முழு பெயர்",
    "onboarding.role": "முதன்மை பங்கு / பயனர் வகை",
    "onboarding.lang": "விருப்ப மொழி / Language",
    "onboarding.alerts": "கடுமையான வானிலை எச்சரிக்கைகள் மற்றும் ஆலோசனைகளை இயக்கு",
    "onboarding.submit": "அமைப்பை முடித்து SkyZen-க்குள் நுழையவும்",

    // Dashboard & Weather Cards
    "dashboard.weather": "வானிலை தரவுகள்",
    "dashboard.current": "தற்போதைய நிலை",
    "dashboard.live_weather": "நேரடி வானிலை",
    "dashboard.rain_prob": "மழை வாய்ப்பு",
    "dashboard.wind": "காற்றின் வேகம்",
    "dashboard.humidity": "ஈரப்பதம்",
    "dashboard.uv_index": "யுவி குறியீடு",
    "dashboard.consensus": "முன்னறிவிப்பு ஒருமித்த கருத்து",
    "dashboard.forecast": "மணிநேர முன்னறிவிப்பு",
    "dashboard.hourly_next24": "அடுத்த 24 மணிநேரம்",
    "dashboard.daily_7day": "7-நாள் முன்னறிவிப்பு",
    "dashboard.imd_model": "IMD எண் கணித மாதிரி",
    "dashboard.advisories": "AI ஆலோசனைகள்",
    "dashboard.ask_skyzen": "SkyZen-இடம் கேளுங்கள்",
    "dashboard.ask_sub": "உங்கள் தினசரி திட்டங்களுக்கான வானிலை பதில்களைப் பெறுங்கள்",
    "dashboard.start_convo": "உரையாடலைத் தொடங்கு",
    "dashboard.tools_title": "வானிலை கருவிகள்",
    "dashboard.tools_sub": "நேரடி தொலை அளவீடு",
    "dashboard.tool_aqi": "காற்று தரம்",
    "dashboard.tool_map": "வானிலை வரைபடம்",
    "dashboard.tool_alerts": "எச்சரிக்கைகள் & ரேடார்",
    "dashboard.tool_saved": "சேமிக்கப்பட்ட நகரங்கள்",
    "dashboard.retry": "மீண்டும் இணைக்க முயல்க",
    "dashboard.loading_telemetry": "நேரடி வானிலை தரவுகள் பெறப்படுகின்றன...",
    "dashboard.error_telemetry": "வானிலை தரவைப் பெற முடியவில்லை.",
    "dashboard.feels_like": "உணரப்படும் வெப்பநிலை",
    "dashboard.observed_at": "கணிக்கப்பட்ட நேரம்",
    "dashboard.sources_title": "வானிலை தகவல் மூலங்கள்",

    // Location Permission Prompt
    "location.prompt_title": "தனிப்பயன் வானிலை & எச்சரிக்கை நுண்ணறிவு",
    "location.prompt_text": "உள்ளூர் வானிலை மற்றும் எச்சரிக்கைகளுக்காக SkyZen உங்கள் இருப்பிடத்தைப் பயன்படுத்த அனுமதிக்கவும்.",
    "location.prompt_allow": "இருப்பிடத்தை அனுமதி",
    "location.prompt_dismiss": "இப்போது இல்லை",

    // AI Chat Screen
    "chat.title": "SkyZen AI உதவியாளர்",
    "chat.subtitle": "WeatherGPT முடிவு உதவியாளர் • அதிகாரப்பூர்வ IMD தரவுகளின் அடிப்படையில்",
    "chat.reset": "மீட்டமை",
    "chat.placeholder": "உங்கள் திட்டங்களைப் பற்றி கேளுங்கள்... (உதா: மாலை 5 மணிக்கு மழை பெய்யுமா?)",
    "chat.send": "அனுப்பு",
    "chat.disclaimer": "AI பதில்கள் மாறுபடலாம். அதிகாரப்பூர்வ IMD எச்சரிக்கைகளுக்கே முன்னுரிமை.",
    "chat.architecture_title": "காரண பகுப்பாய்வு கட்டமைப்பு",
    "chat.architecture_sub": "SkyZen பாதுகாப்புக்கு முதலிடம் தரும் வானிலை சோதனையை பின்பற்றுகிறது:",
    "chat.arch_1": "1. அதிகாரப்பூர்வ நேரடி பேரிடர் எச்சரிக்கைகள் (முதல் முன்னுரிமை)",
    "chat.arch_2": "2. சரிபார்க்கப்பட்ட IMD & பல மூலங்களின் உடன்பாடு",
    "chat.arch_3": "3. துல்லியமான ஆபத்து முடிவு விதிகள்",
    "chat.arch_4": "4. தவறான தகவல்களைத் தடுக்கும் பாதுகாப்பு வேலி",
    "chat.why_answer": "ஏன் இந்த பதில்? (சரிபார்ப்பு விவரங்கள்)",
    "chat.chip_rain": "நாளை மழை பெய்யுமா?",
    "chat.chip_college": "இன்று கல்லூரி செல்லலாமா?",
    "chat.chip_bike": "பைக் எடுக்கலாமா?",
    "chat.chip_umbrella": "குடை தேவையா?",
    "chat.new": "புதிய அரட்டை",
    "chat.persona.student": "மாணவர்",
    "chat.persona.commuter": "பயணி",
    "chat.persona.farmer": "விவசாயி",
    "chat.persona.fisherman": "மீனவர்",
    "chat.persona.traveller": "சுற்றுலா பயணி",
    "chat.persona.disaster_response": "பேரிடர் மேலாண்மை",
    "chat.persona.general": "பொது பயனர்",

    // Extended Weather & Trends Screen
    "weather.today_hourly": "இன்றைய மணிநேர முன்னறிவிப்பு",
    "weather.today_sub": "24-மணிநேர எல்லை",
    "weather.tomorrow_hourly": "நாளைக்கான மணிநேர முன்னறிவிப்பு",
    "weather.extended_future": "நீட்டிக்கப்பட்ட எதிர்கால முன்னறிவிப்பு",
    "weather.climate_archive": "காலநிலை போக்கு காப்பகம் (NASA POWER / IMD)",
    "weather.offline": "இணைய இணைப்பு இல்லை. சேமிக்கப்பட்ட வானிலை காட்டப்படுகிறது.",

    // Alerts Screen
    "alerts.title": "அதிகாரப்பூர்வ IMD எச்சரிக்கைகள் & ஆபத்து பதிவு",
    "alerts.subtitle": "நேரடி அவசரகால ஊட்டம்",
    "alerts.tab_all": "அனைத்து எச்சரிக்கைகளும்",
    "alerts.tab_severe": "கடுமையானவை",
    "alerts.tab_rain": "கனமழை",
    "alerts.tab_heat": "வெப்ப அலை",
    "alerts.tab_wind": "சூறாவளி & பலத்த காற்று",
    "alerts.source_label": "தகவல் மூலம்: இந்திய வானிலை ஆய்வு மையம் (IMD)",
    "alerts.valid_until": "செல்லுபடியாகும் நேரம்",
    "alerts.official_warning": "அதிகாரப்பூர்வ IMD எச்சரிக்கை",

    // Map Screen
    "map.title": "புவியியல் வானிலை & ரேடார் வரைபடம்",
    "map.recenter": "மையப்படுத்து",
    "map.toggle_alerts": "எச்சரிக்கைகளை மாற்று",
    "map.search_placeholder": "நகரம், மாவட்டம் அல்லது ஒருங்கிணைப்புகளைத் தேடுக...",
    "map.my_location": "என் இருப்பிடம்",
    "map.weather_here": "இங்குள்ள வானிலை",
    "map.refresh": "புதுப்பி",
    "map.layer_weather": "வானிலை",
    "map.layer_rain_risk": "மழை ஆபத்து",
    "map.layer_wind_risk": "காற்று ஆபத்து",
    "map.layer_heat_risk": "வெப்ப ஆபத்து",
    "map.layer_warnings": "அதிகாரப்பூர்வ எச்சரிக்கைகள்",
    "map.selected_location": "தேர்ந்தெடுக்கப்பட்ட இடம்",
    "map.tap_hint": "வானிலை மற்றும் எச்சரிக்கைகளைக் காண வரைபடத்தில் எங்கு வேண்டுமானாலும் தட்டவும்",
    "map.ask_ai": "இந்த இடத்தை பற்றி AI-யிடம் கேள்",
    "map.set_home": "முதன்மை இடமாக அமை",
    "map.save_location": "இடத்தைச் சேமி",
    "map.compare_locations": "இடங்களை ஒப்பிடுக",
    "map.compare_sub": "இடங்களுக்கிடையேயான நேரடி ஒப்பீடு",
    "map.no_warning": "இந்த இடத்திற்கு தீவிர IMD வானிலை எச்சரிக்கைகள் இல்லை.",
    "map.cpcb_aqi": "CPCB தரைவழி AQI",
    "map.model_aqi": "மாதிரி காற்று தரம் (Open-Meteo)",
    "map.layer_rainfall": "மழைப்பொழிவு",
    "map.layer_temp": "வெப்பநிலை",
    "map.layer_wind": "காற்று",
    "map.layer_clouds": "மேகங்கள்",
    "map.timeline": "காலவரிசை:",
    "map.now": "இப்போது",
    "map.offline_title": "வரைபட அடுக்குகள் ஆஃப்லைனில் உள்ளன / கிடைக்கவில்லை",
    "map.offline_desc": "கீழே ஒருங்கிணைந்த வானிலை தரவு காட்டப்படுகிறது.",

    // Air Quality Screen
    "aqi.title": "காற்று தரக் குறியீடு (AQI)",
    "aqi.subtitle": "நேரடி சுற்றுச்சூழல் காற்று கண்காணிப்பு",
    "aqi.model_label": "காற்று தர மாதிரி:",
    "aqi.cpcb_unconfigured": "CPCB அதிகாரப்பூர்வ API அணுகல் கட்டமைக்கப்படவில்லை",
    "aqi.pollutants_title": "முக்கிய மாசு அளவுகள் விவரம்",
    "aqi.health_title": "உடல்நலம் & செயல்பாட்டு பரிந்துரைகள்",
    "aqi.rec_fitness": "நடைப்பயிற்சி மற்றும் வழக்கமான வெளிப்புற உடற்பயிற்சிக்கு பாதுகாப்பானது.",
    "aqi.rec_ventilation": "வீடு மற்றும் அலுவலகத்திற்கு சாதாரண காற்றோட்டம் பரிந்துரைக்கப்படுகிறது.",

    // Saved Locations Screen
    "locations.title": "சேமிக்கப்பட்ட இடங்கள்",
    "locations.add_city": "நகரத்தை சேர்",
    "locations.modal_title": "வானிலை இடத்தை சேர்",
    "locations.modal_desc": "பிரபலமான பெருநகரங்கள் அல்லது கடலோர நகரங்களைத் தேர்ந்தெடுக்கவும் அல்லது புதிய நகர பெயரை உள்ளிடவும்:",
    "locations.custom_placeholder": "நகரப் பெயரை உள்ளிடவும் (உதா: ஊட்டி)...",
    "locations.add_btn": "சேர்",

    // More Screen Hub
    "more.tools_heading": "வானிலை நுண்ணறிவு கருவிகள்",
    "more.aqi_item": "காற்று தரக் குறியீடு & மாசுபடுத்திகள்",
    "more.map_item": "புவியியல் ரேடார் & எச்சரிக்கை வரைபடம்",
    "more.forecast_item": "விரிவான முன்னறிவிப்பு & காலநிலை போக்குகள்",
    "more.saved_item": "சேமிக்கப்பட்ட நகரங்களை நிர்வகி",
    "more.ai_heading": "AI ஆலோசனை இயந்திரங்கள்",
    "more.ai_chat_item": "SkyZen உரையாடல் உதவியாளரிடம் கேளுங்கள்",
    "more.travel_item": "மாவட்டங்களுக்கு இடையிலான பயண ஆலோசனை",
    "more.agri_item": "விவசாயம் & பயிர் பாதுகாப்பு",
    "more.pref_heading": "விருப்பங்கள் & கணக்கு",
    "more.profile_item": "பயனர் சுயவிவரம் & அங்கீகாரம்",
    "more.settings_item": "பயன்பாட்டு அமைப்புகள் & மொழி",

    // Profile Screen
    "profile.title": "பயனர் சுயவிவரம் & கணக்கு",
    "profile.verified": "சரிபார்க்கப்பட்டது",
    "profile.account_role": "கணக்கு பங்கு:",
    "profile.status": "நிலை:",
    "profile.active": "செயலில்",
    "profile.edit_heading": "சுயவிவரம் & பாத்திரத்தை தனிப்பயனாக்கு",
    "profile.full_name": "முழு பெயர்",
    "profile.role_label": "பங்கு / வானிலை பயனர் வகை",
    "profile.lang_label": "விருப்ப மொழி / Language",
    "profile.alerts_checkbox": "கடுமையான வானிலை எச்சரிக்கை அறிவிப்புகள்",
    "profile.save_btn": "மாற்றங்களைச் சேமி",
    "profile.signout_btn": "SkyZen-லிருந்து வெளியேறு",
    "profile.guest_prompt": "சேமித்த நகரங்கள் மற்றும் விருப்பங்களை ஒத்திசைக்க உள்நுழையவும்.",
    "profile.guest_login_btn": "உள்நுழைக / கணக்கை உருவாக்கு",
    "profile.saved_summary": "சேமிக்கப்பட்ட நகரங்கள் சுருக்கம்",

    // Settings Screen
    "settings.title": "பயன்பாட்டு அமைப்புகள்",
    "settings.profile_persona": "சுயவிவரம் & பயனர் வகை",
    "settings.profile_desc": "பெயர், பயனர் வகை & மொழியை நிர்வகி",
    "settings.language": "மொழி / Language",
    "settings.language.en": "English (English)",
    "settings.language.ta": "தமிழ் (Tamil)",
    "settings.language.hi": "हिन्दी (Hindi)",
    "settings.notifications": "அவசரகால எச்சரிக்கைகள் & FCM அறிவிப்புகள்",
    "settings.push_channel": "புஷ் எச்சரிக்கை தளம்",
    "settings.push_active": "செயலில் உள்ளது (FCM)",
    "settings.test_alert_btn": "சோதனை எச்சரிக்கையை அனுப்பு",
    "settings.units": "விருப்ப அளவீட்டு அலகுகள்",
    "settings.env_server": "API சூழல் சேவையகம்",
    "settings.save": "சேமி",
    "settings.logout": "வெளியேறு",

    // Accessibility & UI Controls
    "btn.gps": "GPS",
    "btn.refresh": "புதுப்பி",
    "btn.retry": "மீண்டும் முயல்க",
    "btn.close": "மூடு",
    "btn.listen": "கேட்க",
    "btn.stop": "நிறுத்து",
    "btn.send": "அனுப்பு"
  },

  "hi": {
    // Navigation
    "nav.home": "होम",
    "nav.chat": "WeatherGPT",
    "nav.ai": "एआई",
    "nav.map": "लाइव मैप",
    "nav.alerts": "अलर्ट",
    "nav.locations": "सहेजे गए",
    "nav.settings": "सेटिंग्स",
    "nav.more": "अधिक",
    "nav.back_to_home": "होम पर वापस जाएं",
    "nav.back_to_hub": "हब पर वापस जाएं",

    // Welcome & Auth
    "auth.welcome.title": "SkyZen.",
    "auth.welcome.tagline": "साफ आसमान। उज्जवल दिन।",
    "auth.welcome.desc": "एआई-संचालित मौसम जानकारी, IMD के गंभीर अलर्ट और सटीक पूर्वानुमान।",
    "auth.welcome.signin": "साइन इन करें",
    "auth.welcome.signup": "खाता बनाएं",
    "auth.welcome.footer": "आधिकारिक MoES और IMD निर्णय इंजन (WeatherGPT)",
    "auth.login.title": "वापसी पर स्वागत है",
    "auth.login.subtitle": "अपने SkyZen खाते में साइन इन करें",
    "auth.login.email": "ईमेल पता",
    "auth.login.password": "पासवर्ड",
    "auth.login.submit": "साइन इन करें",
    "auth.login.forgot": "भूल गए?",
    "auth.login.switch": "खाता नहीं है?",
    "auth.login.create_one": "नया बनाएं",
    "auth.signup.title": "खाता बनाएं",
    "auth.signup.subtitle": "वास्तविक समय के मौसम के लिए SkyZen से जुड़ें",
    "auth.signup.name": "पूरा नाम",
    "auth.signup.email": "ईमेल पता",
    "auth.signup.password": "पासवर्ड",
    "auth.signup.confirm": "पासवर्ड की पुष्टि करें",
    "auth.signup.submit": "खाता बनाएं",
    "auth.signup.switch": "क्या पहले से खाता है?",
    "auth.reset.title": "पासवर्ड रीसेट करें",
    "auth.reset.subtitle": "पासवर्ड रीसेट कोड प्राप्त करने के लिए अपना पंजीकृत ईमेल पता दर्ज करें।",
    "auth.reset.submit": "रीसेट कोड बनाएं",
    "auth.reset.remember": "पासवर्ड याद है? साइन इन करें",
    "auth.reset_new.title": "नया पासवर्ड सेट करें",
    "auth.reset_new.subtitle": "अपना रीसेट कोड दर्ज करें और एक मजबूत नया पासवर्ड सेट करें।",
    "auth.reset_new.token": "रीसेट टोकन / कोड",
    "auth.reset_new.password": "नया पासवर्ड",
    "auth.reset_new.confirm": "नए पासवर्ड की पुष्टि करें",
    "auth.reset_new.submit": "पासवर्ड अपडेट करें",
    "auth.reset_new.return": "साइन इन पर वापस जाएं",

    // Onboarding
    "onboarding.title": "SkyZen में आपका स्वागत है",
    "onboarding.subtitle": "मौसम संबंधी सलाह को अनुकूलित करने के लिए अपनी प्रोफ़ाइल सेट करें।",
    "onboarding.name": "पूरा नाम",
    "onboarding.role": "मुख्य भूमिका / व्यक्तित्व",
    "onboarding.lang": "पसंदीदा भाषा / மொழி",
    "onboarding.alerts": "गंभीर मौसम अलर्ट और सलाह सक्षम करें",
    "onboarding.submit": "सेटअप पूरा करें और SkyZen में प्रवेश करें",

    // Dashboard & Weather Cards
    "dashboard.weather": "मौसम जानकारी",
    "dashboard.current": "वर्तमान अवलोकन",
    "dashboard.live_weather": "लाइव मौसम",
    "dashboard.rain_prob": "बारिश की संभावना",
    "dashboard.wind": "हवा की गति",
    "dashboard.humidity": "नमी",
    "dashboard.uv_index": "यूवी इंडेक्स",
    "dashboard.consensus": "पूर्वानुमान सहमति",
    "dashboard.forecast": "घंटे का पूर्वानुमान",
    "dashboard.hourly_next24": "अगले 24 घंटे",
    "dashboard.daily_7day": "7-दिवसीय पूर्वानुमान",
    "dashboard.imd_model": "IMD सांख्यिकीय मॉडल",
    "dashboard.advisories": "AI सलाह",
    "dashboard.ask_skyzen": "SkyZen से पूछें",
    "dashboard.ask_sub": "अपनी दैनिक योजनाओं के लिए मौसम संबंधी उत्तर प्राप्त करें",
    "dashboard.start_convo": "बातचीत शुरू करें",
    "dashboard.tools_title": "मौसम उपकरण",
    "dashboard.tools_sub": "रीयल-टाइम टेलीमेट्री",
    "dashboard.tool_aqi": "वायु गुणवत्ता",
    "dashboard.tool_map": "मौसम का नक्शा",
    "dashboard.tool_alerts": "अलर्ट और रडार",
    "dashboard.tool_saved": "सहेजे गए शहर",
    "dashboard.retry": "पुनः प्रयास करें",
    "dashboard.loading_telemetry": "लाइव मौसम टेलीमेट्री प्राप्त की जा रही है...",
    "dashboard.error_telemetry": "मौसम डेटा प्राप्त करने में विफल।",
    "dashboard.feels_like": "महसूस होता है",
    "dashboard.observed_at": "अवलोकन समय",
    "dashboard.sources_title": "मौसम स्रोत",

    // Location Permission Prompt
    "location.prompt_title": "व्यक्तिगत मौसम और चेतावनी बुद्धिमत्ता",
    "location.prompt_text": "स्थानीय मौसम और चेतावनियों के लिए SkyZen को अपने स्थान का उपयोग करने की अनुमति दें।",
    "location.prompt_allow": "स्थान की अनुमति दें",
    "location.prompt_dismiss": "अभी नहीं",

    // AI Chat Screen
    "chat.title": "SkyZen AI सहायक",
    "chat.subtitle": "WeatherGPT निर्णय सहायक • आधिकारिक IMD टेलीमेट्री पर आधारित",
    "chat.reset": "रीसेट करें",
    "chat.placeholder": "अपनी योजनाओं के बारे में पूछें... (उदा: क्या शाम 5 बजे बारिश होगी?)",
    "chat.send": "भेजें",
    "chat.disclaimer": "AI प्रतिक्रियाएं भिन्न हो सकती हैं। आधिकारिक IMD अलर्ट को प्राथमिकता दी जाती है।",
    "chat.architecture_title": "तर्क वास्तुकला",
    "chat.architecture_sub": "SkyZen सुरक्षा-प्रथम मौसम सत्यापन का पालन करता है:",
    "chat.arch_1": "1. आधिकारिक लाइव आपदा चेतावनियाँ (सर्वोच्च प्राथमिकता)",
    "chat.arch_2": "2. सत्यापित IMD और बहु-स्रोत समझौता",
    "chat.arch_3": "3. सटीक खतरा निर्णय नियम",
    "chat.arch_4": "4. भ्रामक जानकारी रोकने वाले सुरक्षा उपाय",
    "chat.why_answer": "यह उत्तर क्यों? (सत्यापन विवरण)",
    "chat.chip_rain": "क्या कल बारिश होगी?",
    "chat.chip_college": "आज कॉलेज जा सकते हैं?",
    "chat.chip_bike": "क्या बाइक ले जाऊं?",
    "chat.chip_umbrella": "क्या छाते की जरूरत है?",
    "chat.new": "नयी चैट",
    "chat.persona.student": "छात्र",
    "chat.persona.commuter": "दैनिक यात्री",
    "chat.persona.farmer": "किसान",
    "chat.persona.fisherman": "मछुआरा",
    "chat.persona.traveller": "यात्री",
    "chat.persona.disaster_response": "आपदा प्रतिक्रिया",
    "chat.persona.general": "सामान्य उपयोगकर्ता",

    // Extended Weather & Trends Screen
    "weather.today_hourly": "आज का प्रति घंटा पूर्वानुमान",
    "weather.today_sub": "24-घंटे का क्षितिज",
    "weather.tomorrow_hourly": "कल का प्रति घंटा पूर्वानुमान",
    "weather.extended_future": "विस्तारित भविष्य पूर्वानुमान",
    "weather.climate_archive": "जलवायु रुझान पुरालेख (NASA POWER / IMD)",
    "weather.offline": "नेटवर्क ऑफ़लाइन है। सहेजा गया मौसम डेटा दिखा रहा है।",

    // Alerts Screen
    "alerts.title": "आधिकारिक IMD चेतावनियाँ और जोखिम रजिस्टर",
    "alerts.subtitle": "रीयल-टाइम आपातकालीन फ़ीड",
    "alerts.tab_all": "सभी अलर्ट",
    "alerts.tab_severe": "गंभीर",
    "alerts.tab_rain": "भारी बारिश",
    "alerts.tab_heat": "लू / हीटवेव",
    "alerts.tab_wind": "आंधी और तेज हवा",
    "alerts.source_label": "स्रोत: भारत मौसम विज्ञान विभाग (IMD)",
    "alerts.valid_until": "मान्य समय",
    "alerts.official_warning": "आधिकारिक IMD चेतावनी",

    // Map Screen
    "map.title": "भू-स्थानिक मौसम और रडार मानचित्र",
    "map.recenter": "पुनः केंद्रित करें",
    "map.toggle_alerts": "अलर्ट टॉगल करें",
    "map.search_placeholder": "शहर, ज़िला या निर्देशांक खोजें...",
    "map.my_location": "मेरा स्थान",
    "map.weather_here": "यहाँ का मौसम",
    "map.refresh": "रिफ्रेश",
    "map.layer_weather": "मौसम",
    "map.layer_rain_risk": "बारिश का जोखिम",
    "map.layer_wind_risk": "हवा का जोखिम",
    "map.layer_heat_risk": "गर्मी का जोखिम",
    "map.layer_warnings": "आधिकारिक चेतावनियाँ",
    "map.selected_location": "चयनित स्थान",
    "map.tap_hint": "लाइव मौसम और अलर्ट देखने के लिए मानचित्र पर कहीं भी टैप करें",
    "map.ask_ai": "इस स्थान के बारे में AI से पूछें",
    "map.set_home": "होम स्थान बनाएं",
    "map.save_location": "स्थान सहेजें",
    "map.compare_locations": "स्थानों की तुलना करें",
    "map.compare_sub": "स्थानों के बीच रीयल-टाइम तुलना",
    "map.no_warning": "इस स्थान के लिए कोई सक्रिय IMD चेतावनी नहीं है।",
    "map.cpcb_aqi": "CPCB ज़मीनी AQI",
    "map.model_aqi": "मॉडल वायु गुणवत्ता (Open-Meteo)",
    "map.layer_rainfall": "वर्षा",
    "map.layer_temp": "तापमान",
    "map.layer_wind": "हवा",
    "map.layer_clouds": "बादल",
    "map.timeline": "समयरेखा:",
    "map.now": "अभी",
    "map.offline_title": "मानचित्र टाइलें ऑफ़लाइन / अनुपलब्ध हैं",
    "map.offline_desc": "नीचे समन्वित मौसम टेलीमेट्री प्रदर्शित हो रही है।",

    // Air Quality Screen
    "aqi.title": "वायु गुणवत्ता सूचकांक (AQI)",
    "aqi.subtitle": "वास्तविक समय परिवेश वायु निगरानी",
    "aqi.model_label": "वायु गुणवत्ता मॉडल:",
    "aqi.cpcb_unconfigured": "CPCB आधिकारिक API एक्सेस कॉन्फ़िगर नहीं है",
    "aqi.pollutants_title": "प्रमुख प्रदूषक विवरण",
    "aqi.health_title": "स्वास्थ्य और गतिविधि अनुशंसाएं",
    "aqi.rec_fitness": "जॉगिंग और नियमित बाहरी गतिविधियों के लिए सुरक्षित।",
    "aqi.rec_ventilation": "सामान्य घर और कार्यालय वेंटिलेशन की सिफारिश की जाती है।",

    // Saved Locations Screen
    "locations.title": "सहेजे गए स्थान",
    "locations.add_city": "शहर जोड़ें",
    "locations.modal_title": "मौसम स्थान जोड़ें",
    "locations.modal_desc": "महानगरीय या तटीय शहर चुनें, या नया शहर नाम दर्ज करें:",
    "locations.custom_placeholder": "शहर का नाम टाइप करें (उदा: ऊटी)...",
    "locations.add_btn": "जोड़ें",

    // More Screen Hub
    "more.tools_heading": "मौसम खुफिया उपकरण",
    "more.aqi_item": "वायु गुणवत्ता सूचकांक और प्रदूषक",
    "more.map_item": "भू-स्थानिक रडार और अलर्ट मानचित्र",
    "more.forecast_item": "विस्तृत पूर्वानुमान और जलवायु रुझान",
    "more.saved_item": "सहेजे गए शहरों का प्रबंधन करें",
    "more.ai_heading": "AI सलाहकार इंजन",
    "more.ai_chat_item": "SkyZen संवादात्मक सहायक से पूछें",
    "more.travel_item": "अंतर-जिला यात्रा सलाह",
    "more.agri_item": "कृषि और फसल सुरक्षा",
    "more.pref_heading": "प्राथमिकताएं और खाता",
    "more.profile_item": "उपयोगकर्ता प्रोफ़ाइल और प्रमाणीकरण",
    "more.settings_item": "एप्लिकेशन सेटिंग्स और भाषा",

    // Profile Screen
    "profile.title": "उपयोगकर्ता प्रोफ़ाइल और खाता",
    "profile.verified": "सत्यापित",
    "profile.account_role": "खाता भूमिका:",
    "profile.status": "स्थिति:",
    "profile.active": "सक्रिय",
    "profile.edit_heading": "प्रोफ़ाइल और व्यक्तित्व को अनुकूलित करें",
    "profile.full_name": "पूरा नाम",
    "profile.role_label": "भूमिका / मौसम व्यक्तित्व",
    "profile.lang_label": "पसंदीदा भाषा / மொழி",
    "profile.alerts_checkbox": "गंभीर मौसम चेतावनी सूचनाएं",
    "profile.save_btn": "प्रोफ़ाइल परिवर्तन सहेजें",
    "profile.signout_btn": "SkyZen से साइन आउट करें",
    "profile.guest_prompt": "सहेजे गए स्थानों और प्राथमिकताओं को समन्वयित करने के लिए साइन इन करें।",
    "profile.guest_login_btn": "साइन इन करें / खाता बनाएं",
    "profile.saved_summary": "सहेजे गए शहरों का सारांश",

    // Settings Screen
    "settings.title": "एप्लिकेशन सेटिंग्स",
    "settings.profile_persona": "प्रोफ़ाइल और भूमिका",
    "settings.profile_desc": "नाम, भूमिका और भाषा प्रबंधित करें",
    "settings.language": "भाषा / Language",
    "settings.language.en": "English (English)",
    "settings.language.ta": "தமிழ் (Tamil)",
    "settings.language.hi": "हिन्दी (Hindi)",
    "settings.notifications": "आपातकालीन चेतावनियां और FCM सूचनाएं",
    "settings.push_channel": "पुश अलर्ट चैनल",
    "settings.push_active": "सक्रिय (FCM)",
    "settings.test_alert_btn": "परीक्षण अलर्ट भेजें",
    "settings.units": "पसंदीदा माप इकाइयां",
    "settings.env_server": "API पर्यावरण सर्वर",
    "settings.save": "सेटिंग्स सहेजें",
    "settings.logout": "साइन आउट",

    // Accessibility & UI Controls
    "btn.gps": "GPS",
    "btn.refresh": "रिफ्रेश",
    "btn.retry": "पुनः प्रयास करें",
    "btn.close": "बंद करें",
    "btn.listen": "सुनें",
    "btn.stop": "रोकें",
    "btn.send": "भेजें"
  }
};

// Dynamic Labels Localizer Dictionary for factual values preserved
const DYNAMIC_LABELS = {
  "Rain Chance": { "ta": "மழை வாய்ப்பு", "hi": "बारिश की संभावना" },
  "Wind Speed": { "ta": "காற்றின் வேகம்", "hi": "हवा की गति" },
  "Humidity": { "ta": "ஈரப்பதம்", "hi": "नमी" },
  "UV Index": { "ta": "யுவி குறியீடு", "hi": "यूवी इंडेक्स" },
  "Pressure": { "ta": "வளிமண்டல அழுத்தம்", "hi": "वायुदाब" },
  "Precipitation": { "ta": "மழைப்பொழிவு", "hi": "वर्षा" },
  "Feels Like": { "ta": "உணரப்படும் வெப்பநிலை", "hi": "महसूस होता है" },
  "Feels like": { "ta": "உணரப்படும் வெப்பநிலை", "hi": "महसूस होता है" },
  "Observed at": { "ta": "கணிக்கப்பட்ட நேரம்", "hi": "अवलोकन समय" },
  "Updated": { "ta": "புதுப்பிக்கப்பட்டது", "hi": "अपडेट किया गया" },
  "Forecast Consensus": { "ta": "முன்னறிவிப்பு ஒருமித்த கருத்து", "hi": "पूर्वानुमान सहमति" },
  "High Agreement": { "ta": "அதிக உடன்பாடு", "hi": "उच्च सहमति" },
  "Medium Agreement": { "ta": "நடுத்தர உடன்பாடு", "hi": "मध्यम सहमति" },
  "Cautious": { "ta": "எச்சரிக்கையான", "hi": "सतर्क" },
  "Disagreement": { "ta": "மாறுபட்ட கருத்து", "hi": "असहमति" },
  "Live Weather": { "ta": "நேரடி வானிலை", "hi": "लाइव मौसम" },
  "LIVE WEATHER": { "ta": "நேரடி வானிலை", "hi": "लाइव मौसम" },
  "Degraded": { "ta": "குறைந்த தரம்", "hi": "सीमित" },
  "Offline": { "ta": "இணைப்பற்ற நிலை", "hi": "ऑफ़लाइन" },
  "Data Stale": { "ta": "பழைய தரவு", "hi": "पुराना डेटा" },
  "Service Unavailable": { "ta": "சேவை கிடைக்கவில்லை", "hi": "सेवा अनुपलब्ध" },
  "Cached": { "ta": "சேமிக்கப்பட்டவை", "hi": "कैश्ड" },
  "Official IMD Warning": { "ta": "அதிகாரப்பூர்வ IMD எச்சரிக்கை", "hi": "आधिकारिक IMD चेतावनी" },
  "OFFICIAL IMD WARNING": { "ta": "அதிகாரப்பூர்வ IMD எச்சரிக்கை", "hi": "आधिकारिक IMD चेतावनी" },
  "Valid until": { "ta": "செல்லுபடியாகும் நேரம்", "hi": "मान्य समय" },
  "Authoritative Source": { "ta": "அதிகாரப்பூர்வ மூலம்", "hi": "आधिकारिक स्रोत" },
  "AQI Source": { "ta": "AQI மூலம்", "hi": "AQI स्रोत" },
  "Air-quality model": { "ta": "காற்று தர மாதிரி", "hi": "वायु गुणवत्ता मॉडल" },
  "Air Quality Model:": { "ta": "காற்று தர மாதிரி:", "hi": "वायु गुणवत्ता मॉडल:" },
  "Fresh Telemetry": { "ta": "புதிய தரவு", "hi": "ताज़ा डेटा" },
  "Data Stale (Cached)": { "ta": "பழைய தரவு (சேமிக்கப்பட்டது)", "hi": "पुराना डेटा (कैश्ड)" },
  "Cached Telemetry (Offline)": { "ta": "சேமிக்கப்பட்ட தரவு (ஆஃப்லைன்)", "hi": "कैश्ड डेटा (ऑफ़लाइन)" },
  "Degraded Telemetry": { "ta": "குறைந்த தரவு", "hi": "सीमित डेटा" },
  "Single Provider Active": { "ta": "ஒற்றை மூலம் செயலில்", "hi": "एकल प्रदाता सक्रिय" },
  "Single Provider": { "ta": "ஒற்றை மூலம்", "hi": "एकल प्रदाता" },
  "WEATHER SOURCES": { "ta": "வானிலை தகவல் மூலங்கள்", "hi": "मौसम स्रोत" },
  "Key Pollutants Breakdown": { "ta": "முக்கிய மாசு அளவுகள்", "hi": "प्रमुख प्रदूषक" },
  "Health & Activity Recommendations": { "ta": "உடல்நலம் & செயல்பாட்டு பரிந்துரைகள்", "hi": "स्वास्थ्य और गतिविधि अनुशंसाएं" },
  "Good": { "ta": "நன்று", "hi": "अच्छा" },
  "Moderate": { "ta": "மிதமானது", "hi": "मध्यम" },
  "Poor": { "ta": "மோசமானது", "hi": "खराब" },
  "Very Poor": { "ta": "மிக மோசமானது", "hi": "बहुत खराब" },
  "Severe": { "ta": "கடுமையானது", "hi": "गंभीर" },
  "CPCB OFFICIAL API ACCESS NOT CONFIGURED": {
    "ta": "CPCB அதிகாரப்பூர்வ API அணுகல் கட்டமைக்கப்படவில்லை",
    "hi": "CPCB आधिकारिक API एक्सेस कॉन्फ़िगर नहीं है"
  },
  "CPCB Ground Monitoring API Not Configured": {
    "ta": "CPCB தரை கண்காணிப்பு API கட்டமைக்கப்படவில்லை",
    "hi": "CPCB ग्राउंड मॉनिटरिंग API कॉन्फ़िगर नहीं है"
  }
};

window.I18N = {
  currentLanguage: localStorage.getItem("skyzen_lang") || "en",

  init: function(lang) {
    if (lang && ["en", "ta", "hi"].includes(lang)) {
      this.currentLanguage = lang;
      localStorage.setItem("skyzen_lang", lang);
    }
    this.applyTranslations();
  },

  setLanguage: function(lang, skipApiCall = false) {
    if (!["en", "ta", "hi"].includes(lang)) return;
    this.currentLanguage = lang;
    localStorage.setItem("skyzen_lang", lang);
    this.applyTranslations();
    
    // Update global reference if used in app.js
    if (typeof window.currentLanguage !== 'undefined') {
      window.currentLanguage = lang;
    }
    
    // Trigger callback to re-render dynamic weather components if available
    if (typeof window.onLanguageChanged === 'function') {
      window.onLanguageChanged(lang);
    }

    if (!skipApiCall && typeof window.updateUserLanguage === 'function') {
      window.updateUserLanguage(lang);
    }
  },

  t: function(key) {
    return this.getTranslation(key);
  },

  getTranslation: function(key) {
    const dict = I18N_DICT[this.currentLanguage] || I18N_DICT["en"];
    return dict[key] || I18N_DICT["en"][key] || key;
  },

  localizeDynamic: function(label) {
    if (!label) return "";
    const lang = this.currentLanguage;
    if (lang === "en") return label;
    
    const entry = DYNAMIC_LABELS[label];
    if (entry && entry[lang]) {
      return entry[lang];
    }
    return label;
  },

  applyTranslations: function() {
    const lang = this.currentLanguage;
    const dict = I18N_DICT[lang] || I18N_DICT["en"];
    
    // Update html lang attribute for screen readers & native fonts
    document.documentElement.lang = lang;

    // Text elements with data-i18n
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const text = dict[key] || I18N_DICT["en"][key];
      if (text) {
        // Check if there's a material icon inside to preserve
        const iconSpan = el.querySelector('.material-symbols-rounded');
        if (iconSpan) {
          let textNodeChanged = false;
          el.childNodes.forEach(child => {
            if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) {
              child.textContent = " " + text;
              textNodeChanged = true;
            }
          });
          if (!textNodeChanged) {
            const innerSpan = Array.from(el.querySelectorAll('span')).find(s => !s.classList.contains('material-symbols-rounded'));
            if (innerSpan) {
              innerSpan.textContent = text;
            }
          }
        } else {
          el.textContent = text;
        }
      }
    });

    // Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const text = dict[key] || I18N_DICT["en"][key];
      if (text) {
        el.setAttribute('placeholder', text);
      }
    });

    // Aria labels
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      const key = el.getAttribute('data-i18n-aria');
      const text = dict[key] || I18N_DICT["en"][key];
      if (text) {
        el.setAttribute('aria-label', text);
      }
    });

    // Tooltips / Titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const text = dict[key] || I18N_DICT["en"][key];
      if (text) {
        el.setAttribute('title', text);
      }
    });
  }
};

document.addEventListener("DOMContentLoaded", () => {
  window.I18N.init();
});
