// SkyZen Centralized Internationalization (i18n) Engine
// Supports English (en), Tamil (ta), and Hindi (hi)
// Strict Pure-Language Architecture: 0 mixed glyphs or leakage

const I18N_DICT = {
  "en": {
    "alerts.coastal_warning_desc": "Coastal warning issued. Fishermen advised not to venture into deep sea.",
    "alerts.coastal_warning_zone": "Coastal Warning Zone",
    "alerts.heavy_rain_warning": "Heavy Rain & Squally Wind Warning",
    "alerts.official_warning": "WEATHER WARNING",
    "alerts.source_label": "Source: OpenWeather & Multi-Source Telemetry",
    "alerts.subtitle": "Real-time Emergency Feeds",
    "alerts.tab_all": "All Alerts",
    "alerts.tab_heat": "Heatwave",
    "alerts.tab_rain": "Heavy Rain",
    "alerts.tab_severe": "Severe",
    "alerts.tab_wind": "Squall & Wind",
    "alerts.title": "Severe Weather Warnings & Risk Register",
    "alerts.valid_until": "Valid until",
    "alerts.valid_until_sample": "Valid until 08:00 PM",
    "alerts.view_alert_link": "View alert",
    "app.page_title": "SkyZen — Weather Intelligence | MoES & IMD Decision Engine (WeatherGPT)",
    "aqi.cpcb_unconfigured": "CPCB OFFICIAL API ACCESS NOT CONFIGURED",
    "aqi.fetching_station": "Fetching verified station telemetry...",
    "aqi.health_title": "Health & Activity Recommendations",
    "aqi.loading_aqi": "Loading AQI...",
    "aqi.model_label": "Air Quality Model:",
    "aqi.pollutants_title": "Key Pollutants Breakdown",
    "aqi.rec_fitness": "Safe for jogging and regular outdoor fitness.",
    "aqi.rec_ventilation": "Normal home and office ventilation recommended.",
    "aqi.source_cpcb": "Source: CPCB",
    "aqi.subtitle": "Real-time Ambient Air Monitoring",
    "aqi.title": "Air Quality Index (AQI)",
    "aqi.view_full_analysis": "View Full AQI Analysis",
    "auth.enter_verify_code": "Enter verification code",
    "auth.login.create_one": "Create one",
    "auth.login.demo": "1-Click Demo Sign In",
    "auth.login.email": "Email Address",
    "auth.login.forgot": "Forgot?",
    "auth.login.password": "Password",
    "auth.login.submit": "Sign In",
    "auth.login.subtitle": "Sign in to your SkyZen account",
    "auth.login.switch": "Don't have an account?",
    "auth.login.title": "Welcome Back",
    "auth.register_btn": "Register",
    "auth.reset.email_label": "Registered Email Address",
    "auth.reset.remember": "Remember your password? Sign In",
    "auth.reset.submit": "Generate Reset Code",
    "auth.reset.subtitle": "Enter your registered email address to receive a password reset code.",
    "auth.reset.title": "Reset Password",
    "auth.reset_new.confirm": "Confirm New Password",
    "auth.reset_new.password": "New Password",
    "auth.reset_new.return": "Return to Sign In",
    "auth.reset_new.submit": "Update Password",
    "auth.reset_new.subtitle": "Enter your reset code and set a strong new password.",
    "auth.reset_new.title": "Set New Password",
    "auth.reset_new.token": "Reset Token / Code",
    "auth.signup.confirm": "Confirm Password",
    "auth.signup.email": "Email Address",
    "auth.signup.name": "Full Name",
    "auth.signup.password": "Password",
    "auth.signup.submit": "Create Account",
    "auth.signup.subtitle": "Join SkyZen for real-time weather intelligence",
    "auth.signup.switch": "Already have an account?",
    "auth.signup.title": "Create Account",
    "auth.step_auth": "Authentication",
    "auth.step_new_pass": "New Password",
    "auth.step_recovery": "Password Recovery",
    "auth.step_signup": "New Account",
    "auth.step_verify": "Email Verification",
    "auth.strength_min": "Minimum 6 characters",
    "auth.unverified_notice": "Your email is not verified yet.",
    "auth.verify.label": "6-Digit Verification Code",
    "auth.verify.not_received": "Didn't receive the code?",
    "auth.verify.resend": "Resend Code",
    "auth.verify.return_login": "Return to Sign In",
    "auth.verify.submit": "Verify Email",
    "auth.verify.subtitle": "Enter the 6-digit code issued to your email:",
    "auth.verify.title": "Verify Your Email",
    "auth.welcome.desc": "AI-powered weather intelligence, severe weather alerts, and precision forecasts.",
    "auth.welcome.footer": "Official MoES & IMD Decision Engine (WeatherGPT)",
    "auth.welcome.signin": "Sign In",
    "auth.welcome.signup": "Create Account",
    "auth.welcome.tagline": "Clearer Skies. Brighter Days.",
    "auth.welcome.title": "SkyZen.",
    "brand.grounded": "Weather Intelligence Active",
    "brand.name": "SkyZen",
    "brand.subtitle": "WeatherGPT MoES IMD Decision Engine",
    "brand.tagline": "Personal Weather Intelligence",
    "btn.close": "Close",
    "btn.gps": "GPS",
    "btn.listen": "Listen",
    "btn.refresh": "Refresh",
    "btn.retry": "Retry",
    "btn.send": "Send",
    "btn.stop": "Stop",
    "chat.arch_1": "1. Official Live Disaster Warnings (Top Priority)",
    "chat.arch_2": "2. Verified OpenWeather & Multi-Source Agreement",
    "chat.arch_3": "3. Deterministic Hazard Decision Rules",
    "chat.arch_4": "4. Anti-Hallucination Guardrails",
    "chat.architecture_sub": "SkyZen strictly adheres to safety-first meteorological validation:",
    "chat.architecture_title": "Reasoning Architecture",
    "chat.chip_bike": "Take my bike?",
    "chat.chip_college": "College today?",
    "chat.chip_rain": "Will it rain tomorrow?",
    "chat.chip_umbrella": "Need umbrella?",
    "chat.confidence_desc": "Verified real-time multi-source weather telemetry",
    "chat.confidence_high": "Confidence: High",
    "chat.decision_engine_badge": "SkyZen Decision Engine",
    "chat.disclaimer": "AI responses can be inaccurate. Official emergency alerts take precedence.",
    "chat.lang_btn": "Language",
    "chat.new": "New Chat",
    "chat.persona.commuter": "Commuter",
    "chat.persona.disaster_response": "Disaster Response",
    "chat.persona.farmer": "Farmer",
    "chat.persona.fisherman": "Fisherman",
    "chat.persona.general": "General User",
    "chat.persona.student": "Student",
    "chat.persona.traveller": "Traveller",
    "chat.placeholder": "Ask SkyZen about your plans... (e.g. Will it rain at 5 PM?)",
    "chat.quick_alerts": "Active weather alerts?",
    "chat.quick_fitness": "Outdoor fitness safety?",
    "chat.quick_laundry": "Will laundry dry?",
    "chat.quick_spray": "Safe for crop spray?",
    "chat.quick_umbrella": "Need umbrella today?",
    "chat.reset": "Reset",
    "chat.send": "Send",
    "chat.sources_multi": "Sources: Multi-Source Telemetry Engine",
    "chat.subtitle": "WeatherGPT Decision Assistant • Grounded on OpenWeather & Multi-Source Telemetry",
    "chat.telemetry_grounded": "Telemetry Grounded",
    "chat.title": "SkyZen AI Assistant",
    "chat.welcome_bubble": "Welcome! I am SkyZen, your personal AI weather decision assistant. Ask me questions about your travel, commute, outdoor plans, or farming operations.",
    "chat.why_answer": "Why this answer? (Verification)",
    "chip.all": "All",
    "chip.commute": "Commute",
    "chip.farmer": "Farmer",
    "chip.fitness": "Fitness",
    "chip.home_daily": "Home & Daily",
    "climate.avg_rain": "Avg Rain:",
    "climate.max_rain": "Max 1-Day:",
    "climate.source": "Source:",
    "climate.source_val": "NASA POWER",
    "climate.trend_desc_1": "Average annual temperature has increased by",
    "climate.trend_desc_2": "over the decade with an increase in high-intensity monsoonal precipitation events.",
    "climate.trend_title": "10-Year Temperature Trend (2015 – 2025)",
    "common.save": "Save",
    "dashboard.advisories": "AI Advisories",
    "dashboard.ask_skyzen": "Ask SkyZen",
    "dashboard.ask_sub": "Get weather-aware answers for your daily plans",
    "dashboard.checking": "Checking...",
    "dashboard.consensus": "Forecast Consensus",
    "dashboard.consensus_checking": "Consensus checking...",
    "dashboard.current": "Current Observations",
    "dashboard.daily_7day": "7-Day Forecast",
    "dashboard.disagreement_warning": "Weather sources currently disagree on conditions.",
    "dashboard.dry": "Dry",
    "dashboard.error_telemetry": "Failed to retrieve weather data.",
    "dashboard.feels_like": "Feels like",
    "dashboard.forecast": "Hourly Forecast",
    "dashboard.heavy": "Heavy",
    "dashboard.hourly_next24": "Next 24 Hours",
    "dashboard.humidity": "Humidity",
    "dashboard.imd_model": "Numerical Weather Model",
    "dashboard.init_telemetry": "Initializing weather telemetry...",
    "dashboard.lifestyle_sub": "Real-time AI feasibility indices computed from live telemetry",
    "dashboard.lifestyle_title": "Smart Lifestyle & Persona Insights",
    "dashboard.light": "Light",
    "dashboard.live_location_badge": "CURRENT LIVE LOCATION",
    "dashboard.live_weather": "LIVE WEATHER",
    "dashboard.loading_cond": "Loading...",
    "dashboard.loading_telemetry": "Loading Telemetry",
    "dashboard.med": "Med",
    "dashboard.minute_rain_summary": "Analyzing precipitation projection...",
    "dashboard.minute_rain_title": "Next 60 Minutes Precipitation",
    "dashboard.multi_source": "Multi-Source",
    "dashboard.nowcast_badge": "MODELLED NOWCAST",
    "dashboard.observed_at": "Observed at",
    "dashboard.rain_prob": "Rain Chance",
    "dashboard.retry": "Retry Connection",
    "dashboard.source_telemetry": "Source: Telemetry",
    "dashboard.sources_title": "WEATHER SOURCES",
    "dashboard.start_convo": "Start Conversation",
    "dashboard.tool_alerts": "Alerts & Radar",
    "dashboard.tool_aqi": "Air Quality",
    "dashboard.tool_map": "Weather Map",
    "dashboard.tool_saved": "Saved Cities",
    "dashboard.tools_sub": "Real-time Telemetry",
    "dashboard.tools_title": "Weather Intelligence Tools",
    "dashboard.updating_obs": "Updating observation...",
    "dashboard.uv_index": "UV Index",
    "dashboard.visibility": "Visibility",
    "dashboard.weather": "Weather Intelligence",
    "dashboard.wind": "Wind Speed",
    "footer.legal": "SkyZen — Ministry of Earth Sciences (MoES) / India Meteorological Department (IMD) | WeatherGPT SIH26068",
    "loc.bengaluru": "Bengaluru, Karnataka",
    "loc.chennai": "Chennai, Tamil Nadu",
    "loc.coimbatore": "Coimbatore, Tamil Nadu",
    "loc.delhi": "Delhi NCR",
    "loc.madurai": "Madurai, Tamil Nadu",
    "loc.nagapattinam": "Nagapattinam (Coastal Warning Zone)",
    "loc.trichy": "Trichy, Tamil Nadu",
    "location.prompt_allow": "Allow Location",
    "location.prompt_dismiss": "Not Now",
    "location.prompt_text": "Allow SkyZen to use your location for local weather and alerts.",
    "location.prompt_title": "Personal Weather & Warning Intelligence",
    "locations.add_btn": "Add",
    "locations.add_city": "Add City",
    "locations.custom_placeholder": "Type city name (e.g. Ooty)...",
    "locations.modal_desc": "Select popular metropolitan or coastal cities, or enter a custom location name:",
    "locations.modal_title": "Add Weather Location",
    "locations.title": "Saved Locations",
    "map.aqi_label": "AQI",
    "map.ask_ai": "Ask AI About This Place",
    "map.compare_locations": "Compare Locations",
    "map.compare_sub": "Real-time backend comparison across locations",
    "map.cpcb_aqi": "CPCB Ground AQI",
    "map.cpcb_unconfigured": "CPCB Ground Monitoring Station API: Not Configured",
    "map.just_now": "Just now",
    "map.layer_clouds": "Clouds",
    "map.layer_heat_risk": "Heat Risk",
    "map.layer_rain_risk": "Rain Risk",
    "map.layer_rainfall": "Rainfall",
    "map.layer_temp": "Temperature",
    "map.layer_warnings": "Severe Alerts",
    "map.layer_weather": "Weather",
    "map.layer_wind": "Wind",
    "map.layer_wind_risk": "Wind Risk",
    "map.live_badge": "LIVE",
    "map.live_radar_title": "Live Radar",
    "map.loading_ambient": "Loading verified ambient air quality telemetry...",
    "map.loc_coimbatore": "Coimbatore",
    "map.model_aqi": "Modelled Air Quality (Open-Meteo)",
    "map.multi_source_verified": "Multi-Source Verified",
    "map.my_location": "My Location",
    "map.no_warning": "No active meteorological warnings for this location.",
    "map.now": "Now",
    "map.official_warning_title": "WEATHER WARNING",
    "map.offline_desc": "Displaying coordinate weather telemetry below.",
    "map.offline_title": "Interactive Map Tiles Offline / Unavailable",
    "map.pending_telemetry": "Pending Telemetry",
    "map.prov_aqi_source": "Air Quality:",
    "map.prov_weather_source": "Weather Source:",
    "map.recenter": "Recenter",
    "map.refresh": "Refresh",
    "map.sample_alert_area": "Area: Coimbatore District",
    "map.sample_alert_valid": "Valid until: Today 18:00",
    "map.save_location": "Save Location",
    "map.search_placeholder": "Search city, district, or coordinates...",
    "map.select_loc_prompt": "Select a location",
    "map.selected_location": "Selected Location",
    "map.set_home": "Set as Home",
    "map.tap_hint": "Tap anywhere on the map to inspect live weather & alerts",
    "map.timeline": "Timeline:",
    "map.title": "Geospatial Weather & Radar Map",
    "map.toggle_alerts": "Toggle Alerts",
    "map.updated_prefix": "Updated:",
    "map.verified_badge": "LIVE VERIFIED",
    "map.view_live_radar": "View Live Radar Map",
    "map.tile_clouds": "Clouds",
    "map.tile_radar": "Radar",
    "map.tile_rain": "Rain",
    "map.tile_temp": "Temp",
    "map.tile_waves": "Waves",
    "map.tile_wind": "Wind",
    "map.weather_here": "Weather Here",
    "more.agri_item": "Agricultural & Crop Protection",
    "more.ai_chat_item": "Ask SkyZen Conversational Assistant",
    "more.ai_heading": "AI Advisory Engines",
    "more.aqi_item": "Air Quality Index & Pollutants",
    "more.forecast_item": "Detailed Forecast & Climate Trends",
    "more.map_item": "Geospatial Radar & Alert Map",
    "more.pref_heading": "Preferences & Account",
    "more.profile_item": "User Profile & Authentication",
    "more.saved_item": "Manage Saved Cities",
    "more.settings_item": "Application Settings & Language",
    "more.tools_heading": "Weather Intelligence Tools",
    "more.travel_item": "Inter-District Travel Advisory",
    "nav.ai": "AI",
    "nav.alerts": "Alerts",
    "nav.aqi": "AQI",
    "nav.back_to_home": "Back to Home",
    "nav.back_to_hub": "Back to Hub",
    "nav.chat": "WeatherGPT",
    "nav.forecast": "Forecast",
    "nav.home": "Home",
    "nav.language_toggle": "Language",
    "nav.locations": "Saved",
    "nav.map": "Live Map",
    "nav.more": "More",
    "nav.radar": "Radar",
    "nav.radar_map": "Radar Map",
    "nav.settings": "Settings",
    "onboarding.alerts": "Enable severe meteorological alerts & advisories",
    "onboarding.lang": "Preferred Language",
    "onboarding.name": "Full Name",
    "onboarding.role": "Primary Role / Persona",
    "onboarding.submit": "Complete Setup & Enter SkyZen",
    "onboarding.subtitle": "Set up your profile to personalize meteorological intelligence and advisories.",
    "onboarding.title": "Welcome to SkyZen",
    "pollutant.co": "CO (Carbon Monoxide)",
    "pollutant.no2": "NO₂ (Nitrogen Dioxide)",
    "pollutant.o3": "O₃ (Ozone)",
    "pollutant.pm10": "PM10 (Respirable)",
    "pollutant.pm25": "PM2.5 (Fine Particles)",
    "pollutant.so2": "SO₂ (Sulfur Dioxide)",
    "profile.account_role": "Account Role:",
    "profile.active": "Active",
    "profile.alerts_checkbox": "Severe meteorological alert notifications",
    "profile.edit_heading": "Personalize Profile & Persona",
    "profile.full_name": "Full Name",
    "profile.guest_login_btn": "Sign In / Create Account",
    "profile.guest_prompt": "Sign in to sync your saved locations, telemetry, and meteorological preferences.",
    "profile.lang_label": "Preferred Language",
    "profile.role_label": "Account Role:",
    "profile.save_btn": "Save Profile Changes",
    "profile.saved_summary": "Saved Cities Summary",
    "profile.sign_in_sync_prompt": "Sign in to synchronize saved locations.",
    "profile.signout_btn": "Sign Out of SkyZen",
    "profile.status": "Status:",
    "profile.status_label": "Status:",
    "profile.summary_heading": "User Profile",
    "profile.title": "User Profile & Account",
    "profile.user_title": "SkyZen User",
    "profile.verified": "Verified",
    "pwa.install_btn": "Install Now",
    "pwa.install_desc": "Add to your Home Screen for instant alerts, full-screen view, and offline weather telemetry.",
    "pwa.install_title": "Install SkyZen App",
    "pwa.later": "Maybe Later",
    "role.commuter_desc": "Commuter — Public transit, road & rain alerts",
    "role.disaster": "Disaster / Emergency",
    "role.disaster_desc": "Disaster / Emergency — Early warning & cyclone relief",
    "role.disaster_resp": "Disaster Response",
    "role.farmer_desc": "Farmer — Agricultural rainfall & harvest planning",
    "role.fisherman_desc": "Fisherman — Marine wind & coastal safety",
    "role.general_desc": "General User — Everyday weather overview",
    "role.student_desc": "Student — Daily commute & campus weather",
    "role.traveller": "Traveller",
    "search.clear": "Clear search",
    "search.placeholder": "Search city or district (e.g. Coimbatore, Chennai)...",
    "search.recent_popular": "Popular Cities",
    "settings.about_title": "About SkyZen v1.0.0",
    "settings.custom_backend_label": "Custom Backend URL (e.g. https://api.example.com/api/v1)",
    "settings.env_custom_server": "Custom Production Server (HTTPS)...",
    "settings.env_emulator": "Android Emulator (10.0.2.2:8000)",
    "settings.env_localhost": "Local Dev Server (localhost:8000)",
    "settings.env_server": "API Environment Server",
    "settings.env_web_shell": "Production Web Shell (/api/v1)",
    "settings.language": "Language",
    "settings.language.en": "English",
    "settings.language.hi": "Hindi",
    "settings.language.ta": "Tamil",
    "settings.logout": "Sign Out",
    "settings.moes_imd_full": "Ministry of Earth Sciences (MoES) / India Meteorological Department (IMD)",
    "settings.notifications": "Emergency Warnings & FCM Notifications",
    "settings.persona_hint": "Tailors lifestyle insights, chat advisories, and weather impact recommendations.",
    "settings.persona_label": "Role / Meteorological Persona",
    "settings.profile_desc": "Manage name, role persona & language",
    "settings.profile_persona": "Profile & Role Persona",
    "settings.push_active": "Active (FCM)",
    "settings.push_channel": "Push Alerts Channel",
    "settings.save": "Save Settings",
    "settings.sih_core": "SIH26068 WeatherGPT Intelligence Core",
    "settings.test_alert_btn": "Send Controlled Test Alert",
    "settings.title": "Application Settings",
    "settings.unit_imperial": "Imperial (°F, mph, in, inHg)",
    "settings.unit_metric": "Metric (°C, km/h, mm, hPa)",
    "settings.theme": "Appearance Theme",
    "settings.themeDesc": "Choose Light, Dark, or System theme",
    "settings.units": "Preferred Measurement Units",
    "severity.high": "HIGH",
    "sidebar.brand_sub": "Weather Intelligence",
    "sidebar.brand_title": "SkyZen",
    "splash.launch_demo": "Launch Presentation Demo",
    "splash.status": "Initializing Meteorological Intelligence...",
    "system.offline_notice": "You're offline. Reconnect to refresh weather.",
    "weather.climate_archive": "Climate Trend Archive (NASA POWER)",
    "weather.extended_future": "Extended Future Forecast",
    "weather.offline": "Network Offline. Displaying cached weather telemetry.",
    "weather.today_hourly": "Today's Hourly Forecast",
    "weather.today_sub": "24-Hour Horizon",
    "weather.tomorrow_hourly": "Tomorrow's Hourly Forecast",
    "dashboard.now": "Now",
    "chat.reasoning": "SkyZen is reasoning over weather data",
    "chat.chip_rain_query": "Will it rain tomorrow?",
    "chat.chip_college_query": "Can I go to college today?",
    "chat.chip_bike_query": "Should I take my bike?",
    "chat.chip_umbrella_query": "Do I need an umbrella?",
    "lifestyle.unavailable": "Lifestyle insights are unavailable due to degraded weather telemetry.",
    "lifestyle.cat_home_daily": "Home & Daily",
    "lifestyle.cat_agriculture": "Agriculture",
    "lifestyle.cat_commute": "Commute",
    "lifestyle.cat_transit": "Transit",
    "lifestyle.cat_fitness": "Fitness & Sport",
    "lifestyle.cat_farming": "Farming",
    "lifestyle.cat_daily_life": "Daily Life",
    "lifestyle.title_laundry": "Outdoor Laundry Drying",
    "lifestyle.title_spray": "Pesticide Spray Window",
    "lifestyle.title_bike": "Two-Wheeler & Bike Safety",
    "lifestyle.title_flood": "Road Flooding & Subways",
    "lifestyle.title_fitness": "Outdoor Running & Jogging",
    "lifestyle.title_harvest": "Crop Harvest & Sun-Drying",
    "lifestyle.title_umbrella": "Umbrella Necessity Score",
    "lifestyle.status_fast_dry": "Fast Dry",
    "lifestyle.status_indoor_drying": "Indoor Drying Advised",
    "lifestyle.status_slow_dry": "Slow Dry (~4-5h)",
    "lifestyle.status_ideal_spray": "Ideal Spray Window",
    "lifestyle.status_no_spray": "Do Not Spray Today",
    "lifestyle.status_drift_caution": "Moderate Drift Caution",
    "lifestyle.status_smooth_ride": "Smooth Ride",
    "lifestyle.status_skid_risk": "High Skidding Risk",
    "lifestyle.status_wet_asphalt": "Wet Asphalt Caution",
    "lifestyle.status_clear_roads": "Clear Roads",
    "lifestyle.status_waterlogging": "Waterlogging Probable",
    "lifestyle.status_spot_puddles": "Spot Puddles",
    "lifestyle.status_great_workout": "Great Workout Window",
    "lifestyle.status_indoor_cardio": "Indoor Cardio Recommended",
    "lifestyle.status_hydration_caution": "Hydration Caution",
    "lifestyle.status_safe_harvest": "Safe for Harvest",
    "lifestyle.status_delay_harvest": "Delay Harvest / Cover Produce",
    "lifestyle.status_monitor_grain": "Monitor Grain Moisture",
    "lifestyle.status_not_needed": "Not Needed",
    "lifestyle.status_keep_in_bag": "Keep in Bag",
    "lifestyle.status_must_carry": "Must Carry",
    "lifestyle.metric_drying_index": "Drying Index",
    "lifestyle.metric_wind_runoff": "Wind & Runoff",
    "lifestyle.metric_road_traction": "Road Traction",
    "lifestyle.metric_drainage_risk": "Drainage Risk",
    "lifestyle.metric_heat_index": "Heat Index",
    "lifestyle.metric_solar_radiation": "Solar Radiation",
    "lifestyle.metric_rain_prob": "Rain Probability",
    "lifestyle.unit_hrs": "hrs",
    "lifestyle.unit_rain": "rain",
    "lifestyle.unit_wind": "wind",
    "lifestyle.unit_hum": "hum",
    "lifestyle.val_high_severe": "High (Severe Alert)",
    "lifestyle.val_normal": "Normal",
    "lifestyle.desc_laundry_opt": "Optimal outdoor drying conditions. Clothes will dry in approximately {h} hours.",
    "lifestyle.desc_laundry_rain": "Precipitation expected. Hang clothes indoors or under sheltered balcony.",
    "lifestyle.desc_laundry_slow": "High ambient moisture. Drying takes longer (~4-5 hours); good air circulation needed.",
    "lifestyle.desc_spray_opt": "Low wind and zero rain hazard. Ideal morning window for crop spraying.",
    "lifestyle.desc_spray_rain": "High runoff and drift hazard. Postpone chemical spray to prevent loss.",
    "lifestyle.desc_spray_caution": "Breezy conditions. Use drift-reduction nozzles or spray during early morning.",
    "lifestyle.desc_commute_opt": "Dry asphalt and favorable visibility. Safe two-wheeler riding conditions.",
    "lifestyle.desc_commute_rain": "Slick pavement and low friction. Reduce speed and maintain safe distance.",
    "lifestyle.desc_commute_caution": "Damp road surfaces. Take caution at turns and sudden braking.",
    "lifestyle.desc_flood_opt": "Subways and major road corridors clear. Normal traffic flow expected.",
    "lifestyle.desc_flood_alert": "Severe alert active: Potential low-lying subway inundation. Plan alternate routes.",
    "lifestyle.desc_flood_heavy": "Heavy downpour risk. Avoid arterial underpasses prone to quick water accumulation.",
    "lifestyle.desc_flood_caution": "Scattered roadside puddles. Watch out for potholes hidden beneath water.",
    "lifestyle.desc_fitness_opt": "Pleasant outdoor running window ({t}°C). Excellent air quality and thermal comfort.",
    "lifestyle.desc_fitness_heat": "Excessive heat and thermal strain. Switch to air-conditioned gym or indoor cardio.",
    "lifestyle.desc_fitness_caution": "Warm and humid. Hydrate adequately before, during, and after your workout.",
    "lifestyle.desc_harvest_opt": "Dry weather with strong sunlight. Safe window for harvesting and open-field grain drying.",
    "lifestyle.desc_harvest_rain": "Rain risk detected. Cover harvested crops immediately with tarpaulins to prevent mold.",
    "lifestyle.desc_harvest_caution": "Elevated humidity may slow drying. Turn grain piles frequently for uniform sun-drying.",
    "lifestyle.desc_umbrella_low": "Minimal precipitation chance. No umbrella required for regular outdoor errands.",
    "lifestyle.desc_umbrella_mid": "Isolated showers possible. Keep a compact folding umbrella in your backpack.",
    "lifestyle.desc_umbrella_high": "High probability of rain. Carry a sturdy umbrella and water-resistant footwear."
  },
  "ta": {
    "alerts.coastal_warning_desc": "கடலோர எச்சரிக்கை விடுக்கப்பட்டுள்ளது. மீனவர்கள் ஆழ்கடலுக்குச் செல்ல வேண்டாம் என அறிவுறுத்தப்படுகிறார்கள்.",
    "alerts.coastal_warning_zone": "கடலோர எச்சரிக்கை மண்டலம்",
    "alerts.heavy_rain_warning": "கனமழை & பலத்த காற்று எச்சரிக்கை",
    "alerts.official_warning": "வானிலை எச்சரிக்கை",
    "alerts.source_label": "தகவல் மூலம்: ஓபன்வெதர் & பல மூல தொலைத்தொடர்பு",
    "alerts.subtitle": "நேரடி அவசரகால ஊட்டம்",
    "alerts.tab_all": "அனைத்து எச்சரிக்கைகளும்",
    "alerts.tab_heat": "வெப்ப அலை",
    "alerts.tab_rain": "கனமழை",
    "alerts.tab_severe": "கடுமையானவை",
    "alerts.tab_wind": "சூறாவளி & பலத்த காற்று",
    "alerts.title": "வானிலை எச்சரிக்கைகள் & ஆபத்து பதிவு",
    "alerts.valid_until": "செல்லுபடியாகும் நேரம்",
    "alerts.valid_until_sample": "இரவு 08:00 மணி வரை செல்லுபடியாகும்",
    "alerts.view_alert_link": "எச்சரிக்கையைக் காண்க",
    "app.page_title": "ஸ்கைசென் — வானிலை நுண்ணறிவு | புவி அறிவியல் அமைச்சகம் & ஐஎம்டி முடிவு இயந்திரம்",
    "aqi.cpcb_unconfigured": "சிபிசிபி அதிகாரப்பூர்வ ஏபிஐ அணுகல் கட்டமைக்கப்படவில்லை",
    "aqi.fetching_station": "சரிபார்க்கப்பட்ட நிலையத் தரவு பெறப்படுகிறது...",
    "aqi.health_title": "உடல்நலம் & செயல்பாட்டு பரிந்துரைகள்",
    "aqi.loading_aqi": "காற்று தரம் ஏற்றப்படுகிறது...",
    "aqi.model_label": "காற்று தர மாதிரி:",
    "aqi.pollutants_title": "முக்கிய மாசு அளவுகள் விவரம்",
    "aqi.rec_fitness": "நடைப்பயிற்சி மற்றும் வழக்கமான வெளிப்புற உடற்பயிற்சிக்கு பாதுகாப்பானது.",
    "aqi.rec_ventilation": "வீடு மற்றும் அலுவலகத்திற்கு சாதாரண காற்றோட்டம் பரிந்துரைக்கப்படுகிறது.",
    "aqi.source_cpcb": "மூலம்: சிபிசிபி",
    "aqi.subtitle": "நேரடி சுற்றுச்சூழல் காற்று கண்காணிப்பு",
    "aqi.title": "காற்று தரக் குறியீடு (காற்று தரம்)",
    "aqi.view_full_analysis": "முழு காற்று தர பகுப்பாய்வைக் காண்க",
    "auth.enter_verify_code": "சரிபார்ப்புக் குறியீட்டை உள்ளிடவும்",
    "auth.login.create_one": "புதிய கணக்கு உருவாக்கு",
    "auth.login.demo": "1-கிளிக் டெமோ உள்நுழைவு",
    "auth.login.email": "மின்னஞ்சல் முகவரி",
    "auth.login.forgot": "மறந்துவிட்டதா?",
    "auth.login.password": "கடவுச்சொல்",
    "auth.login.submit": "உள்நுழைக",
    "auth.login.subtitle": "உங்கள் ஸ்கைசென் கணக்கில் உள்நுழையவும்",
    "auth.login.switch": "கணக்கு இல்லையா?",
    "auth.login.title": "மீண்டும் வருக",
    "auth.register_btn": "பதிவு செய்க",
    "auth.reset.email_label": "பதிவுசெய்யப்பட்ட மின்னஞ்சல் முகவரி",
    "auth.reset.remember": "கடவுச்சொல் நினைவிருக்கிறதா? உள்நுழைக",
    "auth.reset.submit": "மீட்டமைப்பு குறியீட்டை உருவாக்கு",
    "auth.reset.subtitle": "உங்கள் பதிவுசெய்த மின்னஞ்சல் முகவரியை உள்ளிடவும்.",
    "auth.reset.title": "கடவுச்சொல்லை மீட்டமை",
    "auth.reset_new.confirm": "புதிய கடவுச்சொல்லை உறுதிப்படுத்து",
    "auth.reset_new.password": "புதிய கடவுச்சொல்",
    "auth.reset_new.return": "உள்நுழைவிற்கு திரும்பு",
    "auth.reset_new.submit": "கடவுச்சொல்லை புதுப்பி",
    "auth.reset_new.subtitle": "உங்கள் மீட்டமைப்பு குறியீட்டை உள்ளிட்டு புதிய கடவுச்சொல்லை அமைக்கவும்.",
    "auth.reset_new.title": "புதிய கடவுச்சொல் அமை",
    "auth.reset_new.token": "மீட்டமைப்பு டோக்கன் / குறியீடு",
    "auth.signup.confirm": "கடவுச்சொல்லை உறுதிப்படுத்து",
    "auth.signup.email": "மின்னஞ்சல் முகவரி",
    "auth.signup.name": "முழு பெயர்",
    "auth.signup.password": "கடவுச்சொல்",
    "auth.signup.submit": "கணக்கை உருவாக்கு",
    "auth.signup.subtitle": "உண்மையான நேர வானிலை தகவல்களுக்கு ஸ்கைசென்-இல் சேரவும்",
    "auth.signup.switch": "ஏற்கனவே கணக்கு உள்ளதா?",
    "auth.signup.title": "கணக்கை உருவாக்கு",
    "auth.step_auth": "அங்கீகாரம்",
    "auth.step_new_pass": "புதிய கடவுச்சொல்",
    "auth.step_recovery": "கடவுச்சொல் மீட்பு",
    "auth.step_signup": "புதிய கணக்கு",
    "auth.step_verify": "மின்னஞ்சல் சரிபார்ப்பு",
    "auth.strength_min": "குறைந்தபட்சம் 6 எழுத்துக்கள்",
    "auth.unverified_notice": "உங்கள் மின்னஞ்சல் இன்னும் சரிபார்க்கப்படவில்லை.",
    "auth.verify.label": "6-இலக்க சரிபார்ப்புக் குறியீடு",
    "auth.verify.not_received": "குறியீடு கிடைக்கவில்லையா?",
    "auth.verify.resend": "குறியீட்டை மீண்டும் அனுப்பவும்",
    "auth.verify.return_login": "உள்நுழைவிற்குத் திரும்பவும்",
    "auth.verify.submit": "மின்னஞ்சலை சரிபார்க்கவும்",
    "auth.verify.subtitle": "உங்கள் மின்னஞ்சலுக்கு அனுப்பப்பட்ட 6 இலக்கக் குறியீட்டை உள்ளிடவும்:",
    "auth.verify.title": "உங்கள் மின்னஞ்சலை சரிபார்க்கவும்",
    "auth.welcome.desc": "செயற்கை நுண்ணறிவு வானிலை தரவுகள், கடுமையான எச்சரிக்கைகள் மற்றும் துல்லியமான முன்னறிவிப்புகள்.",
    "auth.welcome.footer": "அதிகாரப்பூர்வ புவி அறிவியல் அமைச்சகம் & ஐஎம்டி முடிவு இயந்திரம் (வானிலை ஜிபிடி)",
    "auth.welcome.signin": "உள்நுழைக",
    "auth.welcome.signup": "கணக்கை உருவாக்கு",
    "auth.welcome.tagline": "தெளிவான வானம். பிரகாசமான நாட்கள்.",
    "auth.welcome.title": "ஸ்கைசென்.",
    "brand.grounded": "வானிலை நுண்ணறிவு செயல்படுகிறது",
    "brand.name": "ஸ்கைசென்",
    "brand.subtitle": "வானிலை ஜிபிடி புவி அறிவியல் அமைச்சகம் ஐஎம்டி முடிவு இயந்திரம்",
    "brand.tagline": "தனிப்பயனாக்கப்பட்ட வானிலை நுண்ணறிவு",
    "btn.close": "மூடு",
    "btn.gps": "ஜிபிஎஸ்",
    "btn.listen": "கேட்க",
    "btn.refresh": "புதுப்பி",
    "btn.retry": "மீண்டும் முயல்க",
    "btn.send": "அனுப்பு",
    "btn.stop": "நிறுத்து",
    "chat.arch_1": "1. அதிகாரப்பூர்வ நேரடி பேரிடர் எச்சரிக்கைகள் (முதல் முன்னுரிமை)",
    "chat.arch_2": "2. சரிபார்க்கப்பட்ட ஓபன்வெதர் & பல மூலங்களின் உடன்பாடு",
    "chat.arch_3": "3. துல்லியமான ஆபத்து முடிவு விதிகள்",
    "chat.arch_4": "4. தவறான தகவல்களைத் தடுக்கும் பாதுகாப்பு வேலி",
    "chat.architecture_sub": "ஸ்கைசென் பாதுகாப்புக்கு முதலிடம் தரும் வானிலை சோதனையை பின்பற்றுகிறது:",
    "chat.architecture_title": "காரண பகுப்பாய்வு கட்டமைப்பு",
    "chat.chip_bike": "பைக் எடுக்கலாமா?",
    "chat.chip_college": "இன்று கல்லூரி செல்லலாமா?",
    "chat.chip_rain": "நாளை மழை பெய்யுமா?",
    "chat.chip_umbrella": "குடை தேவையா?",
    "chat.confidence_desc": "சரிபார்க்கப்பட்ட நேரலை பல மூல வானிலை தரவு",
    "chat.confidence_high": "நம்பகத்தன்மை: அதிகம்",
    "chat.decision_engine_badge": "ஸ்கைசென் முடிவு இயந்திரம்",
    "chat.disclaimer": "செயற்கை நுண்ணறிவு பதில்கள் மாறுபடலாம். அதிகாரப்பூர்வ அவசர எச்சரிக்கைகளுக்கே முன்னுரிமை.",
    "chat.lang_btn": "மொழி",
    "chat.new": "புதிய அரட்டை",
    "chat.persona.commuter": "பயணி",
    "chat.persona.disaster_response": "பேரிடர் மேலாண்மை",
    "chat.persona.farmer": "விவசாயி",
    "chat.persona.fisherman": "மீனவர்",
    "chat.persona.general": "பொது பயனர்",
    "chat.persona.student": "மாணவர்",
    "chat.persona.traveller": "சுற்றுலா பயணி",
    "chat.placeholder": "உங்கள் திட்டங்களைப் பற்றி கேளுங்கள்... (உதா: மாலை 5 மணிக்கு மழை பெய்யுமா?)",
    "chat.quick_alerts": "செயலில் உள்ள வானிலை எச்சரிக்கைகள்?",
    "chat.quick_fitness": "வெளியே உடற்பயிற்சி செய்யலாமா?",
    "chat.quick_laundry": "துணிகள் காய்ந்துவிடுமா?",
    "chat.quick_spray": "பயிர் தெளிக்க பாதுகாப்பானதா?",
    "chat.quick_umbrella": "இன்று குடை தேவையா?",
    "chat.reset": "மீட்டமை",
    "chat.send": "அனுப்பு",
    "chat.sources_multi": "மூலங்கள்: பல மூல தொலைஅளவியல் இயந்திரம்",
    "chat.subtitle": "வானிலை ஜிபிடி முடிவு உதவியாளர் • ஓபன்வெதர் மற்றும் பல மூல தரவுகளின் அடிப்படையில்",
    "chat.telemetry_grounded": "தரவு அடிப்படையிலானது",
    "chat.title": "ஸ்கைசென் செயற்கை நுண்ணறிவு உதவியாளர்",
    "chat.welcome_bubble": "வணக்கம்! நான் ஸ்கைசென், உங்கள் தனிப்பட்ட வானிலை முடிவெடுக்கும் செயற்கை நுண்ணறிவு உதவியாளர். உங்கள் பயணம், கல்லூரி, வெளிப்புற திட்டங்கள் அல்லது விவசாய பணிகள் குறித்த கேள்விகளை என்னிடம் கேட்கலாம்.",
    "chat.why_answer": "ஏன் இந்த பதில்? (சரிபார்ப்பு விவரங்கள்)",
    "chip.all": "அனைத்தும்",
    "chip.commute": "பயணம்",
    "chip.farmer": "விவசாயி",
    "chip.fitness": "உடற்பயிற்சி",
    "chip.home_daily": "வீடு & தினசரி",
    "climate.avg_rain": "சராசரி மழை:",
    "climate.max_rain": "அதிகபட்ச 1-நாள்:",
    "climate.source": "மூலம்:",
    "climate.source_val": "நாசா பவர்",
    "climate.trend_desc_1": "சராசரி ஆண்டு வெப்பநிலை அதிகரித்துள்ளது",
    "climate.trend_desc_2": "கடந்த தசாப்தத்தில் அதிக தீவிர பருவமழை நிகழ்வுகளின் அதிகரிப்புடன்.",
    "climate.trend_title": "10 ஆண்டு வெப்பநிலை போக்கு (2015 – 2025)",
    "common.save": "சேமி",
    "dashboard.advisories": "செயற்கை நுண்ணறிவு ஆலோசனைகள்",
    "dashboard.ask_skyzen": "ஸ்கைசென்-இடம் கேளுங்கள்",
    "dashboard.ask_sub": "உங்கள் தினசரி திட்டங்களுக்கான வானிலை பதில்களைப் பெறுங்கள்",
    "dashboard.checking": "சரிபார்க்கப்படுகிறது...",
    "dashboard.consensus": "முன்னறிவிப்பு ஒருமித்த கருத்து",
    "dashboard.consensus_checking": "ஒருமித்த கருத்து சரிபார்க்கப்படுகிறது...",
    "dashboard.current": "தற்போதைய நிலை",
    "dashboard.daily_7day": "7-நாள் முன்னறிவிப்பு",
    "dashboard.disagreement_warning": "வானிலை தகவல் மூலங்களுக்கிடையே தற்போது மாறுபட்ட கருத்துக்கள் உள்ளன.",
    "dashboard.dry": "வறண்டது",
    "dashboard.error_telemetry": "வானிலை தரவைப் பெற முடியவில்லை.",
    "dashboard.feels_like": "உணரப்படும் வெப்பநிலை",
    "dashboard.forecast": "மணிநேர முன்னறிவிப்பு",
    "dashboard.heavy": "கனமழை",
    "dashboard.hourly_next24": "அடுத்த 24 மணிநேரம்",
    "dashboard.humidity": "ஈரப்பதம்",
    "dashboard.imd_model": "எண் கணித வானிலை மாதிரி",
    "dashboard.init_telemetry": "வானிலை தொலைஅளவியல் தொடங்குகிறது...",
    "dashboard.lifestyle_sub": "நேரலை தரவுகளிலிருந்து கணக்கிடப்படும் செயற்கை நுண்ணறிவு சாத்தியக்கூறு குறியீடுகள்",
    "dashboard.lifestyle_title": "ஸ்மார்ட் வாழ்க்கை முறை & தனிப்பயன் நுண்ணறிவு",
    "dashboard.light": "லேசான",
    "dashboard.live_location_badge": "தற்போதைய நேரலை இருப்பிடம்",
    "dashboard.live_weather": "நேரலை வானிலை",
    "dashboard.loading_cond": "ஏற்றுகிறது...",
    "dashboard.loading_telemetry": "தொலைஅளவியல் ஏற்றப்படுகிறது",
    "dashboard.med": "மிதமான",
    "dashboard.minute_rain_summary": "மழைப்பொழிவு முன்னறிவிப்பு பகுப்பாய்வு செய்யப்படுகிறது...",
    "dashboard.minute_rain_title": "அடுத்த 60 நிமிட மழைப்பொழிவு",
    "dashboard.multi_source": "பல தகவல் மூலங்கள்",
    "dashboard.nowcast_badge": "மாதிரி உடனடி முன்னறிவிப்பு",
    "dashboard.observed_at": "கணிக்கப்பட்ட நேரம்",
    "dashboard.rain_prob": "மழை வாய்ப்பு",
    "dashboard.retry": "மீண்டும் இணைக்க முயல்க",
    "dashboard.source_telemetry": "மூலம்: நேரடி தரவு",
    "dashboard.sources_title": "வானிலை தகவல் மூலங்கள்",
    "dashboard.start_convo": "உரையாடலைத் தொடங்கு",
    "dashboard.tool_alerts": "எச்சரிக்கைகள் & ரேடார்",
    "dashboard.tool_aqi": "காற்று தரம்",
    "dashboard.tool_map": "வானிலை வரைபடம்",
    "dashboard.tool_saved": "சேமிக்கப்பட்ட நகரங்கள்",
    "dashboard.tools_sub": "நேரடி தொலை அளவீடு",
    "dashboard.tools_title": "வானிலை கருவிகள்",
    "dashboard.updating_obs": "வானிலை அவதானிப்பு புதுப்பிக்கப்படுகிறது...",
    "dashboard.uv_index": "யுவி குறியீடு",
    "dashboard.visibility": "பார்வை தூரம்",
    "dashboard.weather": "வானிலை தரவுகள்",
    "dashboard.wind": "காற்றின் வேகம்",
    "footer.legal": "ஸ்கைசென் — புவி அறிவியல் அமைச்சகம் / இந்திய வானிலை ஆய்வு மையம் | வானிலை ஜிபிடி எஸ்ஐஎச்26068",
    "loc.bengaluru": "பெங்களூரு, கர்நாடகா",
    "loc.chennai": "சென்னை, தமிழ்நாடு",
    "loc.coimbatore": "கோயம்புத்தூர், தமிழ்நாடு",
    "loc.delhi": "டெல்லி என்சிஆர்",
    "loc.madurai": "மதுரை, தமிழ்நாடு",
    "loc.nagapattinam": "நாகப்பட்டினம் (கடலோர எச்சரிக்கை மண்டலம்)",
    "loc.trichy": "திருச்சி, தமிழ்நாடு",
    "location.prompt_allow": "இருப்பிடத்தை அனுமதி",
    "location.prompt_dismiss": "இப்போது இல்லை",
    "location.prompt_text": "உள்ளூர் வானிலை மற்றும் எச்சரிக்கைகளுக்காக ஸ்கைசென் உங்கள் இருப்பிடத்தைப் பயன்படுத்த அனுமதிக்கவும்.",
    "location.prompt_title": "தனிப்பயன் வானிலை & எச்சரிக்கை நுண்ணறிவு",
    "locations.add_btn": "சேர்",
    "locations.add_city": "நகரத்தை சேர்",
    "locations.custom_placeholder": "நகரப் பெயரை உள்ளிடவும் (உதா: ஊட்டி)...",
    "locations.modal_desc": "பிரபலமான பெருநகரங்கள் அல்லது கடலோர நகரங்களைத் தேர்ந்தெடுக்கவும் அல்லது புதிய நகர பெயரை உள்ளிடவும்:",
    "locations.modal_title": "வானிலை இடத்தை சேர்",
    "locations.title": "சேமிக்கப்பட்ட இடங்கள்",
    "map.aqi_label": "காற்று தரம்",
    "map.ask_ai": "இந்த இடத்தை பற்றி செயற்கை நுண்ணறிவு-யிடம் கேள்",
    "map.compare_locations": "இடங்களை ஒப்பிடுக",
    "map.compare_sub": "இடங்களுக்கிடையேயான நேரடி ஒப்பீடு",
    "map.cpcb_aqi": "சிபிசிபி தரைவழி காற்று தரம்",
    "map.cpcb_unconfigured": "சிபிசிபி தரை கண்காணிப்பு நிலைய ஏபிஐ: கட்டமைக்கப்படவில்லை",
    "map.just_now": "சற்று முன்",
    "map.layer_clouds": "மேகங்கள்",
    "map.layer_heat_risk": "வெப்ப ஆபத்து",
    "map.layer_rain_risk": "மழை ஆபத்து",
    "map.layer_rainfall": "மழைப்பொழிவு",
    "map.layer_temp": "வெப்பநிலை",
    "map.layer_warnings": "தீவிர எச்சரிக்கைகள்",
    "map.layer_weather": "வானிலை",
    "map.layer_wind": "காற்று",
    "map.layer_wind_risk": "காற்று ஆபத்து",
    "map.live_badge": "நேரலை",
    "map.live_radar_title": "நேரலை ரேடார்",
    "map.loading_ambient": "சரிபார்க்கப்பட்ட காற்று தரவு ஏற்றப்படுகிறது...",
    "map.loc_coimbatore": "கோயம்புத்தூர்",
    "map.model_aqi": "மாதிரி காற்று தரம் (ஓபன்-மீட்டியோ)",
    "map.multi_source_verified": "பல மூலங்களால் சரிபார்க்கப்பட்டது",
    "map.my_location": "என் இருப்பிடம்",
    "map.no_warning": "இந்த இடத்திற்கு தீவிர வானிலை எச்சரிக்கைகள் இல்லை.",
    "map.now": "இப்போது",
    "map.official_warning_title": "வானிலை எச்சரிக்கை",
    "map.offline_desc": "கீழே ஒருங்கிணைந்த வானிலை தரவு காட்டப்படுகிறது.",
    "map.offline_title": "வரைபட அடுக்குகள் ஆஃப்லைனில் உள்ளன / கிடைக்கவில்லை",
    "map.pending_telemetry": "தரவு நிலுவையில் உள்ளது",
    "map.prov_aqi_source": "காற்று தரம்:",
    "map.prov_weather_source": "வானிலை தகவல் மூலம்:",
    "map.recenter": "மையப்படுத்து",
    "map.refresh": "புதுப்பி",
    "map.sample_alert_area": "பகுதி: கோயம்புத்தூர் மாவட்டம்",
    "map.sample_alert_valid": "செல்லுபடியாகும்: இன்று 18:00",
    "map.save_location": "இடத்தைச் சேமி",
    "map.search_placeholder": "நகரம், மாவட்டம் அல்லது ஒருங்கிணைப்புகளைத் தேடுக...",
    "map.select_loc_prompt": "ஒரு இடத்தைத் தேர்ந்தெடுக்கவும்",
    "map.selected_location": "தேர்ந்தெடுக்கப்பட்ட இடம்",
    "map.set_home": "முதன்மை இடமாக அமை",
    "map.tap_hint": "வானிலை மற்றும் எச்சரிக்கைகளைக் காண வரைபடத்தில் எங்கு வேண்டுமானாலும் தட்டவும்",
    "map.timeline": "காலவரிசை:",
    "map.title": "புவியியல் வானிலை & ரேடார் வரைபடம்",
    "map.toggle_alerts": "எச்சரிக்கைகளை மாற்று",
    "map.updated_prefix": "புதுப்பிக்கப்பட்டது:",
    "map.verified_badge": "நேரலை சரிபார்க்கப்பட்டது",
    "map.view_live_radar": "நேரலை ரேடார் வரைபடத்தைக் காண்க",
    "map.tile_clouds": "மேகங்கள்",
    "map.tile_radar": "ரேடார்",
    "map.tile_rain": "மழை",
    "map.tile_temp": "வெப்பநிலை",
    "map.tile_waves": "அலைகள்",
    "map.tile_wind": "காற்று",
    "map.weather_here": "இங்குள்ள வானிலை",
    "more.agri_item": "விவசாயம் & பயிர் பாதுகாப்பு",
    "more.ai_chat_item": "ஸ்கைசென் உரையாடல் உதவியாளரிடம் கேளுங்கள்",
    "more.ai_heading": "செயற்கை நுண்ணறிவு ஆலோசனை இயந்திரங்கள்",
    "more.aqi_item": "காற்று தரக் குறியீடு & மாசுபடுத்திகள்",
    "more.forecast_item": "விரிவான முன்னறிவிப்பு & காலநிலை போக்குகள்",
    "more.map_item": "புவியியல் ரேடார் & எச்சரிக்கை வரைபடம்",
    "more.pref_heading": "விருப்பங்கள் & கணக்கு",
    "more.profile_item": "பயனர் சுயவிவரம் & அங்கீகாரம்",
    "more.saved_item": "சேமிக்கப்பட்ட நகரங்களை நிர்வகி",
    "more.settings_item": "பயன்பாட்டு அமைப்புகள் & மொழி",
    "more.tools_heading": "வானிலை நுண்ணறிவு கருவிகள்",
    "more.travel_item": "மாவட்டங்களுக்கு இடையிலான பயண ஆலோசனை",
    "nav.ai": "செயற்கை நுண்ணறிவு",
    "nav.alerts": "எச்சரிக்கைகள்",
    "nav.aqi": "காற்று தரம்",
    "nav.back_to_home": "முகப்பிற்கு செல்",
    "nav.back_to_hub": "ஹப் பகுதிக்கு செல்",
    "nav.chat": "வானிலை ஜிபிடி",
    "nav.forecast": "முன்னறிவிப்பு",
    "nav.home": "முகப்பு",
    "nav.language_toggle": "மொழி",
    "nav.locations": "சேமிக்கப்பட்டவை",
    "nav.map": "நேரடி வரைபடம்",
    "nav.more": "மேலும்",
    "nav.radar": "ரேடார்",
    "nav.radar_map": "ரேடார் வரைபடம்",
    "nav.settings": "அமைப்புகள்",
    "onboarding.alerts": "கடுமையான வானிலை எச்சரிக்கைகள் மற்றும் ஆலோசனைகளை இயக்கு",
    "onboarding.lang": "விருப்ப மொழி",
    "onboarding.name": "முழு பெயர்",
    "onboarding.role": "முதன்மை பங்கு / பயனர் வகை",
    "onboarding.submit": "அமைப்பை முடித்து ஸ்கைசென்-க்குள் நுழையவும்",
    "onboarding.subtitle": "வானிலை தகவல்கள் மற்றும் ஆலோசனைகளை தனிப்பயனாக்க உங்கள் சுயவிவரத்தை அமைக்கவும்.",
    "onboarding.title": "ஸ்கைசென்-க்கு வரவேற்கிறோம்",
    "pollutant.co": "கார்பன் மோனாக்சைடு",
    "pollutant.no2": "நைட்ரஜன் டை ஆக்சைடு",
    "pollutant.o3": "ஓசோன்",
    "pollutant.pm10": "பிஎம் 10 (சுவாசிக்கக்கூடிய துகள்கள்)",
    "pollutant.pm25": "பிஎம் 2.5 (நுண் துகள்கள்)",
    "pollutant.so2": "சல்பர் டை ஆக்சைடு",
    "profile.account_role": "கணக்கு பங்கு:",
    "profile.active": "செயலில்",
    "profile.alerts_checkbox": "கடுமையான வானிலை எச்சரிக்கை அறிவிப்புகள்",
    "profile.edit_heading": "சுயவிவரம் & பாத்திரத்தை தனிப்பயனாக்கு",
    "profile.full_name": "முழு பெயர்",
    "profile.guest_login_btn": "உள்நுழைக / கணக்கை உருவாக்கு",
    "profile.guest_prompt": "சேமித்த நகரங்கள் மற்றும் விருப்பங்களை ஒத்திசைக்க உள்நுழையவும்.",
    "profile.lang_label": "விருப்ப மொழி",
    "profile.role_label": "கணக்கு பங்கு:",
    "profile.save_btn": "மாற்றங்களைச் சேமி",
    "profile.saved_summary": "சேமிக்கப்பட்ட நகரங்கள் சுருக்கம்",
    "profile.sign_in_sync_prompt": "சேமிக்கப்பட்ட இடங்களை ஒத்திசைக்க உள்நுழையவும்.",
    "profile.signout_btn": "ஸ்கைசென்-லிருந்து வெளியேறு",
    "profile.status": "நிலை:",
    "profile.status_label": "நிலை:",
    "profile.summary_heading": "பயனர் சுயவிவரம்",
    "profile.title": "பயனர் சுயவிவரம் & கணக்கு",
    "profile.user_title": "ஸ்கைசென் பயனர்",
    "profile.verified": "சரிபார்க்கப்பட்டது",
    "pwa.install_btn": "இப்போதே நிறுவுக",
    "pwa.install_desc": "உடனடி எச்சரிக்கைகள், முழுத்திரை காட்சி மற்றும் ஆஃப்லைன் வானிலை தகவல்களுக்கு முகப்புத் திரையில் சேர்க்கவும்.",
    "pwa.install_title": "ஸ்கைசென் செயலியை நிறுவுக",
    "pwa.later": "பிறகு பார்க்கலாம்",
    "role.commuter_desc": "பயணி — பொதுப் போக்குவரத்து, சாலை & மழை எச்சரிக்கைகள்",
    "role.disaster": "பேரிடர் / அவசரநிலை",
    "role.disaster_desc": "பேரிடர் / அவசரநிலை — முன்கூட்டிய எச்சரிக்கை & புயல் நிவாரணம்",
    "role.disaster_resp": "பேரிடர் மீட்பு",
    "role.farmer_desc": "விவசாயி — விவசாய மழைப்பொழிவு & அறுவடை திட்டமிடல்",
    "role.fisherman_desc": "மீனவர் — கடல் காற்று & கடலோர பாதுகாப்பு",
    "role.general_desc": "பொதுப் பயனர் — அன்றாட வானிலை கண்ணோட்டம்",
    "role.student_desc": "மாணவர் — தினசரி பயணம் & வளாக வானிலை",
    "role.traveller": "பயணி",
    "search.clear": "தேடலை அழி",
    "search.placeholder": "நகரம் அல்லது மாவட்டத்தைத் தேடுங்கள்...",
    "search.recent_popular": "பிரபல நகரங்கள்",
    "settings.about_title": "ஸ்கைசென் பதிப்பு 1.0.0 பற்றி",
    "settings.custom_backend_label": "தனிப்பயன் பின்நிலை முகவரி",
    "settings.env_custom_server": "தனிப்பயன் உற்பத்தி சேவையகம் (பாதுகாப்பான)...",
    "settings.env_emulator": "ஆண்ட்ராய்டு எமுலேட்டர்",
    "settings.env_localhost": "உள்ளூர் உருவாக்க சேவையகம்",
    "settings.env_server": "ஏபிஐ சூழல் சேவையகம்",
    "settings.env_web_shell": "உற்பத்தி வலை ஷெல்",
    "settings.language": "மொழி",
    "settings.language.en": "ஆங்கிலம்",
    "settings.language.hi": "இந்தி",
    "settings.language.ta": "தமிழ்",
    "settings.logout": "வெளியேறு",
    "settings.moes_imd_full": "புவி அறிவியல் அமைச்சகம் (புவி அறிவியல் அமைச்சகம்) / இந்திய வானிலை ஆய்வு மையம் (ஐஎம்டி)",
    "settings.notifications": "அவசரகால எச்சரிக்கைகள் & எஃப்சிஎம் அறிவிப்புகள்",
    "settings.persona_hint": "வாழ்க்கை முறை மற்றும் வானிலை பரிந்துரைகளைத் தனிப்பயனாக்குகிறது.",
    "settings.persona_label": "பங்கு / வானிலை நபர் முறை",
    "settings.profile_desc": "பெயர், பயனர் வகை & மொழியை நிர்வகி",
    "settings.profile_persona": "சுயவிவரம் & பயனர் வகை",
    "settings.push_active": "செயலில் உள்ளது (எஃப்சிஎம்)",
    "settings.push_channel": "புஷ் எச்சரிக்கை தளம்",
    "settings.save": "சேமி",
    "settings.sih_core": "எஸ்ஐஎச்26068 வானிலை ஜிபிடி நுண்ணறிவு மையம்",
    "settings.test_alert_btn": "சோதனை எச்சரிக்கையை அனுப்பு",
    "settings.title": "பயன்பாட்டு அமைப்புகள்",
    "settings.unit_imperial": "இம்பீரியல் (°பாரன்ஹீட், மைல்/மணி, அங்குலம்)",
    "settings.unit_metric": "மெட்ரிக் (°செல்சியஸ், கிமீ/மணி, மிமீ, எச்பிஏ)",
    "settings.theme": "தோற்ற தீம்",
    "settings.themeDesc": "வெளிச்சம், இருள் அல்லது முறைமை தீமைத் தேர்ந்தெடுக்கவும்",
    "settings.units": "விருப்ப அளவீட்டு அலகுகள்",
    "severity.high": "அதிகம்",
    "sidebar.brand_sub": "வானிலை நுண்ணறிவு",
    "sidebar.brand_title": "ஸ்கைசென்",
    "splash.launch_demo": "விளக்கக் காட்சியைத் தொடங்கவும்",
    "splash.status": "வானிலை நுண்ணறிவு தொடங்குகிறது...",
    "system.offline_notice": "நீங்கள் ஆஃப்லைனில் உள்ளீர்கள். வானிலையைப் புதுப்பிக்க மீண்டும் இணையவும்.",
    "weather.climate_archive": "காலநிலை போக்கு காப்பகம் (நாசா பவர்)",
    "weather.extended_future": "நீட்டிக்கப்பட்ட எதிர்கால முன்னறிவிப்பு",
    "weather.offline": "இணைய இணைப்பு இல்லை. சேமிக்கப்பட்ட வானிலை காட்டப்படுகிறது.",
    "weather.today_hourly": "இன்றைய மணிநேர முன்னறிவிப்பு",
    "weather.today_sub": "24-மணிநேர எல்லை",
    "weather.tomorrow_hourly": "நாளைக்கான மணிநேர முன்னறிவிப்பு",
    "dashboard.now": "இப்போது",
    "chat.reasoning": "ஸ்கைசென் வானிலை தரவுகளை ஆய்வு செய்கிறது",
    "chat.chip_rain_query": "நாளை மழை பெய்யுமா?",
    "chat.chip_college_query": "இன்று கல்லூரி செல்லலாமா?",
    "chat.chip_bike_query": "பைக் எடுக்கலாமா?",
    "chat.chip_umbrella_query": "குடை தேவையா?",
    "lifestyle.unavailable": "வானிலை தொலைத்தொடர்பு குறைவு காரணமாக வாழ்க்கைமுறை நுண்ணறிவு கிடைக்கவில்லை.",
    "lifestyle.cat_home_daily": "வீடு & தினசரி",
    "lifestyle.cat_agriculture": "விவசாயம்",
    "lifestyle.cat_commute": "பயணம்",
    "lifestyle.cat_transit": "போக்குவரத்து",
    "lifestyle.cat_fitness": "உடற்பயிற்சி & விளையாட்டு",
    "lifestyle.cat_farming": "பண்ணை & விவசாயம்",
    "lifestyle.cat_daily_life": "தினசரி வாழ்க்கை",
    "lifestyle.title_laundry": "வெளியில் துணி உலர்த்துதல்",
    "lifestyle.title_spray": "பூச்சிக்கொல்லி தெளிப்பு நேரம்",
    "lifestyle.title_bike": "இருசக்கர வாகன பாதுகாப்பு",
    "lifestyle.title_flood": "சாலை வெள்ளம் & சுரங்கப்பாதைகள்",
    "lifestyle.title_fitness": "வெளியில் ஓட்டம் & நடைபயிற்சி",
    "lifestyle.title_harvest": "பயிர் அறுவடை & களம் உலர்த்துதல்",
    "lifestyle.title_umbrella": "குடை தேவை மதிப்பீடு",
    "lifestyle.status_fast_dry": "விரைவில் உலரும்",
    "lifestyle.status_indoor_drying": "உள்ளே உலர்த்த பரிந்துரை",
    "lifestyle.status_slow_dry": "மெதுவாக உலரும் (~4-5 மணி)",
    "lifestyle.status_ideal_spray": "தெளிக்க உகந்த நேரம்",
    "lifestyle.status_no_spray": "இன்று தெளிக்க வேண்டாம்",
    "lifestyle.status_drift_caution": "மிதமான காற்று எச்சரிக்கை",
    "lifestyle.status_smooth_ride": "சீரான பயணம்",
    "lifestyle.status_skid_risk": "வழுக்கும் அபாயம் அதிகம்",
    "lifestyle.status_wet_asphalt": "ஈரமான சாலை எச்சரிக்கை",
    "lifestyle.status_clear_roads": "தெளிவான சாலைகள்",
    "lifestyle.status_waterlogging": "நீர் தேங்க வாய்ப்பு",
    "lifestyle.status_spot_puddles": "சாலைகளில் சிறு நீர்நிலைகள்",
    "lifestyle.status_great_workout": "சிறந்த உடற்பயிற்சி நேரம்",
    "lifestyle.status_indoor_cardio": "உள்ளரங்க உடற்பயிற்சி சிறந்தது",
    "lifestyle.status_hydration_caution": "நீரேற்ற எச்சரிக்கை",
    "lifestyle.status_safe_harvest": "அறுவடைக்கு பாதுகாப்பானது",
    "lifestyle.status_delay_harvest": "அறுவடையை தள்ளிப்போடுக / பயிரை மூடுக",
    "lifestyle.status_monitor_grain": "தானிய ஈரப்பதத்தை கண்காணிக்கவும்",
    "lifestyle.status_not_needed": "தேவையில்லை",
    "lifestyle.status_keep_in_bag": "பையில் வைத்திருக்கவும்",
    "lifestyle.status_must_carry": "கட்டாயம் எடுத்துச் செல்லவும்",
    "lifestyle.metric_drying_index": "உலர்த்தல் குறியீடு",
    "lifestyle.metric_wind_runoff": "காற்று & மழைநீர் ஓட்டம்",
    "lifestyle.metric_road_traction": "சாலை பிடிப்பு",
    "lifestyle.metric_drainage_risk": "வடிகால் ஆபத்து",
    "lifestyle.metric_heat_index": "வெப்பக் குறியீடு",
    "lifestyle.metric_solar_radiation": "சூரிய கதிர்வீச்சு",
    "lifestyle.metric_rain_prob": "மழை சாத்தியக்கூறு",
    "lifestyle.unit_hrs": "மணி",
    "lifestyle.unit_rain": "மழை",
    "lifestyle.unit_wind": "காற்று",
    "lifestyle.unit_hum": "ஈரப்பதம்",
    "lifestyle.val_high_severe": "அதிகம் (தீவிர எச்சரிக்கை)",
    "lifestyle.val_normal": "இயல்பு",
    "lifestyle.desc_laundry_opt": "சிறந்த வெளிப்புற உலர்த்தும் சூழல். துணிகள் சுமார் {h} மணி நேரத்தில் உலர்ந்துவிடும்.",
    "lifestyle.desc_laundry_rain": "மழை பெய்ய வாய்ப்புள்ளது. துணிகளை உள்ளே அல்லது கூரையுள்ள பால்கனியில் உலர்த்தவும்.",
    "lifestyle.desc_laundry_slow": "காற்றில் அதிக ஈரப்பதம். துணிகள் உலர அதிக நேரம் எடுக்கும் (~4-5 மணி); நல்ல காற்றோட்டம் தேவை.",
    "lifestyle.desc_spray_opt": "குறைந்த காற்று மற்றும் மழை ஆபத்து இல்லை. பயிர்களுக்கு மருந்து தெளிக்க உகந்த காலை நேரம்.",
    "lifestyle.desc_spray_rain": "அதிக மழைநீர் ஓட்டம் மற்றும் காற்று வீச்சு ஆபத்து. மருந்து வீணாவதைத் தவிர்க்க தெளிப்பை தள்ளிப்போடவும்.",
    "lifestyle.desc_spray_caution": "மிதமான காற்று வீசுகிறது. மருந்து சிதறலைத் தடுக்கும் முனைகளைப் பயன்படுத்தவும் அல்லது அதிகாலையில் தெளிக்கவும்.",
    "lifestyle.desc_commute_opt": "உலர்ந்த சாலை மற்றும் சிறந்த பார்வை தூரம். இருசக்கர வாகனம் ஓட்ட பாதுகாப்பான நிலை.",
    "lifestyle.desc_commute_rain": "வழுக்கும் சாலை மற்றும் குறைந்த பிடிப்பு. வேகத்தைக் குறைத்து பாதுகாப்பான இடைவெளியை பராமரிக்கவும்.",
    "lifestyle.desc_commute_caution": "ஈரமான சாலைப் பகுதிகள். திருப்பங்களிலும் திடீர் பிரேக்கிங்கிலும் எச்சரிக்கையாக இருக்கவும்.",
    "lifestyle.desc_flood_opt": "சுரங்கப்பாதைகள் மற்றும் முக்கிய சாலைகள் சீராக உள்ளன. சாதாரண போக்குவரத்து எதிர்பார்க்கப்படுகிறது.",
    "lifestyle.desc_flood_alert": "கடுமையான எச்சரிக்கை செயலில்: தாழ்வான சுரங்கப்பாதைகளில் நீர் தேங்க வாய்ப்பு. மாற்று வழிகளைத் திட்டமிடுங்கள்.",
    "lifestyle.desc_flood_heavy": "கனமழை ஆபத்து. விரைவாக நீர் தேங்கக்கூடிய முக்கிய சுரங்கப்பாதைகளைத் தவிர்க்கவும்.",
    "lifestyle.desc_flood_caution": "சாலையோரங்களில் ஆங்காங்கே நீர் தேக்கம். தண்ணீரில் மறைந்துள்ள பள்ளங்கள் குறித்து எச்சரிக்கையாக இருக்கவும்.",
    "lifestyle.desc_fitness_opt": "வெளியில் ஓட இனிமையான சூழல் ({t}°C). சிறந்த காற்று தரம் மற்றும் வசதியான வெப்பநிலை.",
    "lifestyle.desc_fitness_heat": "அதிக வெப்பம் மற்றும் உடல் சோர்வு அபாயம். உட்புற உடற்பயிற்சி அல்லது குளிர்சாதன ஜிம்மிற்கு மாறவும்.",
    "lifestyle.desc_fitness_caution": "மிதமான வெப்பம் மற்றும் ஈரப்பதம். உடற்பயிற்சிக்கு முன்னும் பின்னும் போதுமான அளவு தண்ணீர் குடிக்கவும்.",
    "lifestyle.desc_harvest_opt": "வறண்ட வானிலை மற்றும் நல்ல சூரிய ஒளி. பயிர் அறுவடை மற்றும் களம் உலர்த்துவதற்கு பாதுகாப்பான நேரம்.",
    "lifestyle.desc_harvest_rain": "மழை பெய்ய வாய்ப்புள்ளது. தானியங்கள் பாழாகாமல் இருக்க அறுவடை செய்த பயிர்களை உடனடியாக தார்பாய் கொண்டு மூடவும்.",
    "lifestyle.desc_harvest_caution": "அதிக ஈரப்பதம் உலர்தலை மெதுவாக்கலாம். சீராக உலர தானியக் குவியல்களை அடிக்கடி திருப்பிவிடவும்.",
    "lifestyle.desc_umbrella_low": "மழை பெய்ய மிகக் குறைந்த வாய்ப்பு. வழக்கமான வெளிப்புற பணிகளுக்கு குடை தேவையில்லை.",
    "lifestyle.desc_umbrella_mid": "ஆங்காங்கே லேசான மழை பெய்ய வாய்ப்புள்ளது. பையில் ஒரு சிறிய மடிப்பு குடையை வைத்திருக்கவும்.",
    "lifestyle.desc_umbrella_high": "மழை பெய்ய அதிக சாத்தியக்கூறு. உறுதியான குடை மற்றும் மழைக்கால காலணிகளை எடுத்துச் செல்லவும்."
  },
  "hi": {
    "alerts.coastal_warning_desc": "तटीय चेतावनी जारी। मछुआरों को गहरे समुद्र में न जाने की सलाह दी गई है।",
    "alerts.coastal_warning_zone": "तटीय चेतावनी क्षेत्र",
    "alerts.heavy_rain_warning": "भारी बारिश और तूफानी हवा की चेतावनी",
    "alerts.official_warning": "मौसम चेतावनी",
    "alerts.source_label": "स्रोत: ओपनवेदर और बहु-स्रोत टेलीमेट्री",
    "alerts.subtitle": "रीयल-टाइम आपातकालीन फ़ीड",
    "alerts.tab_all": "सभी अलर्ट",
    "alerts.tab_heat": "लू / हीटवेव",
    "alerts.tab_rain": "भारी बारिश",
    "alerts.tab_severe": "गंभीर",
    "alerts.tab_wind": "आंधी और तेज हवा",
    "alerts.title": "मौसम चेतावनियाँ और जोखिम रजिस्टर",
    "alerts.valid_until": "मान्य समय",
    "alerts.valid_until_sample": "रात 08:00 बजे तक मान्य",
    "alerts.view_alert_link": "अलर्ट देखें",
    "app.page_title": "स्काईज़ेन — मौसम बुद्धिमत्ता | पृथ्वी विज्ञान मंत्रालय और आईएमडी निर्णय इंजन",
    "aqi.cpcb_unconfigured": "सीपीसीबी आधिकारिक एपीआई एक्सेस कॉन्फ़िगर नहीं है",
    "aqi.fetching_station": "सत्यापित स्टेशन टेलीमेट्री प्राप्त की जा रही है...",
    "aqi.health_title": "स्वास्थ्य और गतिविधि अनुशंसाएं",
    "aqi.loading_aqi": "एक्यूआई लोड हो रहा है...",
    "aqi.model_label": "वायु गुणवत्ता मॉडल:",
    "aqi.pollutants_title": "प्रमुख प्रदूषक विवरण",
    "aqi.rec_fitness": "जॉगिंग और नियमित बाहरी गतिविधियों के लिए सुरक्षित।",
    "aqi.rec_ventilation": "सामान्य घर और कार्यालय वेंटिलेशन की सिफारिश की जाती है।",
    "aqi.source_cpcb": "स्रोत: सीपीसीबी",
    "aqi.subtitle": "वास्तविक समय परिवेश वायु निगरानी",
    "aqi.title": "वायु गुणवत्ता सूचकांक (एक्यूआई)",
    "aqi.view_full_analysis": "पूर्ण वायु गुणवत्ता विश्लेषण देखें",
    "auth.enter_verify_code": "सत्यापन कोड दर्ज करें",
    "auth.login.create_one": "नया बनाएं",
    "auth.login.demo": "1-क्लिक डेमो साइन इन",
    "auth.login.email": "ईमेल पता",
    "auth.login.forgot": "भूल गए?",
    "auth.login.password": "पासवर्ड",
    "auth.login.submit": "साइन इन करें",
    "auth.login.subtitle": "अपने स्काईज़ेन खाते में साइन इन करें",
    "auth.login.switch": "खाता नहीं है?",
    "auth.login.title": "वापसी पर स्वागत है",
    "auth.register_btn": "पंजीकरण करें",
    "auth.reset.email_label": "पंजीकृत ईमेल पता",
    "auth.reset.remember": "पासवर्ड याद है? साइन इन करें",
    "auth.reset.submit": "रीसेट कोड बनाएं",
    "auth.reset.subtitle": "पासवर्ड रीसेट कोड प्राप्त करने के लिए अपना पंजीकृत ईमेल पता दर्ज करें।",
    "auth.reset.title": "पासवर्ड रीसेट करें",
    "auth.reset_new.confirm": "नए पासवर्ड की पुष्टि करें",
    "auth.reset_new.password": "नया पासवर्ड",
    "auth.reset_new.return": "साइन इन पर वापस जाएं",
    "auth.reset_new.submit": "पासवर्ड अपडेट करें",
    "auth.reset_new.subtitle": "अपना रीसेट कोड दर्ज करें और एक मजबूत नया पासवर्ड सेट करें।",
    "auth.reset_new.title": "नया पासवर्ड सेट करें",
    "auth.reset_new.token": "रीसेट टोकन / कोड",
    "auth.signup.confirm": "पासवर्ड की पुष्टि करें",
    "auth.signup.email": "ईमेल पता",
    "auth.signup.name": "पूरा नाम",
    "auth.signup.password": "पासवर्ड",
    "auth.signup.submit": "खाता बनाएं",
    "auth.signup.subtitle": "वास्तविक समय के मौसम के लिए स्काईज़ेन से जुड़ें",
    "auth.signup.switch": "क्या पहले से खाता है?",
    "auth.signup.title": "खाता बनाएं",
    "auth.step_auth": "प्रमाणीकरण",
    "auth.step_new_pass": "नया पासवर्ड",
    "auth.step_recovery": "पासवर्ड पुनर्प्राप्ति",
    "auth.step_signup": "नया खाता",
    "auth.step_verify": "ईमेल सत्यापन",
    "auth.strength_min": "न्यूनतम 6 अक्षर",
    "auth.unverified_notice": "आपका ईमेल अभी सत्यापित नहीं हुआ है।",
    "auth.verify.label": "6-अंकीय सत्यापन कोड",
    "auth.verify.not_received": "कोड प्राप्त नहीं हुआ?",
    "auth.verify.resend": "कोड पुनः भेजें",
    "auth.verify.return_login": "साइन इन पर वापस लौटें",
    "auth.verify.submit": "ईमेल सत्यापित करें",
    "auth.verify.subtitle": "अपने ईमेल पर भेजा गया 6-अंकीय कोड दर्ज करें:",
    "auth.verify.title": "अपना ईमेल सत्यापित करें",
    "auth.welcome.desc": "एआई-संचालित मौसम जानकारी, गंभीर मौसम अलर्ट और सटीक पूर्वानुमान।",
    "auth.welcome.footer": "आधिकारिक पृथ्वी विज्ञान मंत्रालय और आईएमडी निर्णय इंजन (मौसम जीपीटी)",
    "auth.welcome.signin": "साइन इन करें",
    "auth.welcome.signup": "खाता बनाएं",
    "auth.welcome.tagline": "साफ आसमान। उज्जवल दिन।",
    "auth.welcome.title": "स्काईज़ेन.",
    "brand.grounded": "मौसम बुद्धिमत्ता सक्रिय",
    "brand.name": "स्काईज़ेन",
    "brand.subtitle": "मौसम जीपीटी पृथ्वी विज्ञान मंत्रालय आईएमडी निर्णय इंजन",
    "brand.tagline": "व्यक्तिगत मौसम बुद्धिमत्ता",
    "btn.close": "बंद करें",
    "btn.gps": "जीपीएस",
    "btn.listen": "सुनें",
    "btn.refresh": "रिफ्रेश",
    "btn.retry": "पुनः प्रयास करें",
    "btn.send": "भेजें",
    "btn.stop": "रोकें",
    "chat.arch_1": "1. आधिकारिक लाइव आपदा चेतावनियाँ (सर्वोच्च प्राथमिकता)",
    "chat.arch_2": "2. सत्यापित ओपनवेदर और बहु-स्रोत समझौता",
    "chat.arch_3": "3. सटीक खतरा निर्णय नियम",
    "chat.arch_4": "4. भ्रामक जानकारी रोकने वाले सुरक्षा उपाय",
    "chat.architecture_sub": "स्काईज़ेन सुरक्षा-प्रथम मौसम सत्यापन का पालन करता है:",
    "chat.architecture_title": "तर्क वास्तुकला",
    "chat.chip_bike": "क्या बाइक ले जाऊं?",
    "chat.chip_college": "आज कॉलेज जा सकते हैं?",
    "chat.chip_rain": "क्या कल बारिश होगी?",
    "chat.chip_umbrella": "क्या छाते की जरूरत है?",
    "chat.confidence_desc": "सत्यापित वास्तविक समय बहु-स्रोत मौसम टेलीमेट्री",
    "chat.confidence_high": "विश्वसनीयता: उच्च",
    "chat.decision_engine_badge": "स्काईज़ेन निर्णय इंजन",
    "chat.disclaimer": "एआई प्रतिक्रियाएं भिन्न हो सकती हैं। आधिकारिक आपातकालीन अलर्ट को प्राथमिकता दी जाती है।",
    "chat.lang_btn": "भाषा",
    "chat.new": "नयी चैट",
    "chat.persona.commuter": "दैनिक यात्री",
    "chat.persona.disaster_response": "आपदा प्रतिक्रिया",
    "chat.persona.farmer": "किसान",
    "chat.persona.fisherman": "मछुआरा",
    "chat.persona.general": "सामान्य उपयोगकर्ता",
    "chat.persona.student": "छात्र",
    "chat.persona.traveller": "यात्री",
    "chat.placeholder": "अपनी योजनाओं के बारे में पूछें... (उदा: क्या शाम 5 बजे बारिश होगी?)",
    "chat.quick_alerts": "सक्रिय मौसम अलर्ट?",
    "chat.quick_fitness": "क्या बाहरी व्यायाम सुरक्षित है?",
    "chat.quick_laundry": "क्या कपड़े सूख जाएंगे?",
    "chat.quick_spray": "क्या फसल छिड़काव सुरक्षित है?",
    "chat.quick_umbrella": "क्या आज छाते की जरूरत है?",
    "chat.reset": "रीसेट करें",
    "chat.send": "भेजें",
    "chat.sources_multi": "स्रोत: बहु-स्रोत टेलीमेट्री इंजन",
    "chat.subtitle": "मौसम जीपीटी निर्णय सहायक • ओपनवेदर और बहु-स्रोत टेलीमेट्री पर आधारित",
    "chat.telemetry_grounded": "टेलीमेट्री आधारित",
    "chat.title": "स्काईज़ेन एआई सहायक",
    "chat.welcome_bubble": "नमस्ते! मैं स्काईज़ेन हूँ, आपका व्यक्तिगत एआई मौसम निर्णय सहायक। मुझसे अपनी यात्रा, आवागमन, बाहरी योजनाओं या कृषि कार्यों के बारे में प्रश्न पूछें।",
    "chat.why_answer": "यह उत्तर क्यों? (सत्यापन विवरण)",
    "chip.all": "सभी",
    "chip.commute": "यात्रा",
    "chip.farmer": "किसान",
    "chip.fitness": "फिटनेस",
    "chip.home_daily": "घर और दैनिक",
    "climate.avg_rain": "औसत बारिश:",
    "climate.max_rain": "अधिकतम 1-दिन:",
    "climate.source": "स्रोत:",
    "climate.source_val": "नासा पावर",
    "climate.trend_desc_1": "औसत वार्षिक तापमान में वृद्धि हुई है",
    "climate.trend_desc_2": "दशक भर में उच्च तीव्रता वाले मानसूनी वर्षा की घटनाओं में वृद्धि के साथ।",
    "climate.trend_title": "10-वर्षीय तापमान रुझान (2015 – 2025)",
    "common.save": "सहेजें",
    "dashboard.advisories": "एआई सलाह",
    "dashboard.ask_skyzen": "स्काईज़ेन से पूछें",
    "dashboard.ask_sub": "अपनी दैनिक योजनाओं के लिए मौसम संबंधी उत्तर प्राप्त करें",
    "dashboard.checking": "जांच जारी...",
    "dashboard.consensus": "पूर्वानुमान सहमति",
    "dashboard.consensus_checking": "सहमति जांची जा रही है...",
    "dashboard.current": "वर्तमान अवलोकन",
    "dashboard.daily_7day": "7-दिवसीय पूर्वानुमान",
    "dashboard.disagreement_warning": "मौसम स्रोत वर्तमान में स्थितियों पर असहमत हैं।",
    "dashboard.dry": "शुष्क",
    "dashboard.error_telemetry": "मौसम डेटा प्राप्त करने में विफल।",
    "dashboard.feels_like": "महसूस होता है",
    "dashboard.forecast": "घंटे का पूर्वानुमान",
    "dashboard.heavy": "भारी",
    "dashboard.hourly_next24": "अगले 24 घंटे",
    "dashboard.humidity": "नमी",
    "dashboard.imd_model": "संख्यात्मक मौसम मॉडल",
    "dashboard.init_telemetry": "मौसम टेलीमेट्री प्रारंभ हो रही है...",
    "dashboard.lifestyle_sub": "लाइव टेलीमेट्री से परिकलित वास्तविक समय एआई व्यवहार्यता सूचकांक",
    "dashboard.lifestyle_title": "स्मार्ट जीवनशैली और व्यक्तित्व अंतर्दृष्टि",
    "dashboard.light": "हल्की",
    "dashboard.live_location_badge": "वर्तमान लाइव स्थान",
    "dashboard.live_weather": "लाइव मौसम",
    "dashboard.loading_cond": "लोड हो रहा है...",
    "dashboard.loading_telemetry": "टेलीमेट्री लोड हो रही है",
    "dashboard.med": "मध्यम",
    "dashboard.minute_rain_summary": "वर्षा प्रक्षेपण का विश्लेषण किया जा रहा है...",
    "dashboard.minute_rain_title": "अगले 60 मिनट की वर्षा",
    "dashboard.multi_source": "बहु-स्रोत",
    "dashboard.nowcast_badge": "मॉडल आधारित तात्कालिक पूर्वानुमान",
    "dashboard.observed_at": "अवलोकन समय",
    "dashboard.rain_prob": "बारिश की संभावना",
    "dashboard.retry": "पुनः प्रयास करें",
    "dashboard.source_telemetry": "स्रोत: टेलीमेट्री",
    "dashboard.sources_title": "मौसम स्रोत",
    "dashboard.start_convo": "बातचीत शुरू करें",
    "dashboard.tool_alerts": "अलर्ट और रडार",
    "dashboard.tool_aqi": "वायु गुणवत्ता",
    "dashboard.tool_map": "मौसम का नक्शा",
    "dashboard.tool_saved": "सहेजे गए शहर",
    "dashboard.tools_sub": "रीयल-टाइम टेलीमेट्री",
    "dashboard.tools_title": "मौसम उपकरण",
    "dashboard.updating_obs": "अवलोकन अपडेट हो रहा है...",
    "dashboard.uv_index": "यूवी इंडेक्स",
    "dashboard.visibility": "दृश्यता",
    "dashboard.weather": "मौसम जानकारी",
    "dashboard.wind": "हवा की गति",
    "footer.legal": "स्काईज़ेन — पृथ्वी विज्ञान मंत्रालय / भारत मौसम विज्ञान विभाग | मौसम जीपीटी एसआईएच26068",
    "loc.bengaluru": "बेंगलुरु, कर्नाटक",
    "loc.chennai": "चेन्नई, तमिलनाडु",
    "loc.coimbatore": "कोयंबटूर, तमिलनाडु",
    "loc.delhi": "दिल्ली एनसीआर",
    "loc.madurai": "मदुरै, तमिलनाडु",
    "loc.nagapattinam": "नागापट्टिनम (तटीय चेतावनी क्षेत्र)",
    "loc.trichy": "त्रिची, तमिलनाडु",
    "location.prompt_allow": "स्थान की अनुमति दें",
    "location.prompt_dismiss": "अभी नहीं",
    "location.prompt_text": "स्थानीय मौसम और चेतावनियों के लिए स्काईज़ेन को अपने स्थान का उपयोग करने की अनुमति दें।",
    "location.prompt_title": "व्यक्तिगत मौसम और चेतावनी बुद्धिमत्ता",
    "locations.add_btn": "जोड़ें",
    "locations.add_city": "शहर जोड़ें",
    "locations.custom_placeholder": "शहर का नाम टाइप करें (उदा: ऊटी)...",
    "locations.modal_desc": "महानगरीय या तटीय शहर चुनें, या नया शहर नाम दर्ज करें:",
    "locations.modal_title": "मौसम स्थान जोड़ें",
    "locations.title": "सहेजे गए स्थान",
    "map.aqi_label": "एक्यूआई",
    "map.ask_ai": "इस स्थान के बारे में एआई से पूछें",
    "map.compare_locations": "स्थानों की तुलना करें",
    "map.compare_sub": "स्थानों के बीच रीयल-टाइम तुलना",
    "map.cpcb_aqi": "सीपीसीबी ज़मीनी एक्यूआई",
    "map.cpcb_unconfigured": "सीपीसीबी ग्राउंड मॉनिटरिंग स्टेशन एपीआई: कॉन्फ़िगर नहीं है",
    "map.just_now": "अभी-अभी",
    "map.layer_clouds": "बादल",
    "map.layer_heat_risk": "गर्मी का जोखिम",
    "map.layer_rain_risk": "बारिश का जोखिम",
    "map.layer_rainfall": "वर्षा",
    "map.layer_temp": "तापमान",
    "map.layer_warnings": "गंभीर अलर्ट",
    "map.layer_weather": "मौसम",
    "map.layer_wind": "हवा",
    "map.layer_wind_risk": "हवा का जोखिम",
    "map.live_badge": "लाइव",
    "map.live_radar_title": "लाइव रडार",
    "map.loading_ambient": "सत्यापित परिवेशी वायु गुणवत्ता टेलीमेट्री लोड हो रही है...",
    "map.loc_coimbatore": "कोयंबटूर",
    "map.model_aqi": "मॉडल वायु गुणवत्ता (ओपन-मेटियो)",
    "map.multi_source_verified": "बहु-स्रोत सत्यापित",
    "map.my_location": "मेरा स्थान",
    "map.no_warning": "इस स्थान के लिए कोई सक्रिय मौसम चेतावनी नहीं है।",
    "map.now": "अभी",
    "map.official_warning_title": "मौसम चेतावनी",
    "map.offline_desc": "नीचे समन्वित मौसम टेलीमेट्री प्रदर्शित हो रही है।",
    "map.offline_title": "मानचित्र टाइलें ऑफ़लाइन / अनुपलब्ध हैं",
    "map.pending_telemetry": "टेलीमेट्री लंबित",
    "map.prov_aqi_source": "वायु गुणवत्ता:",
    "map.prov_weather_source": "मौसम स्रोत:",
    "map.recenter": "पुनः केंद्रित करें",
    "map.refresh": "रिफ्रेश",
    "map.sample_alert_area": "क्षेत्र: कोयंबटूर जिला",
    "map.sample_alert_valid": "मान्य: आज 18:00",
    "map.save_location": "स्थान सहेजें",
    "map.search_placeholder": "शहर, ज़िला या निर्देशांक खोजें...",
    "map.select_loc_prompt": "एक स्थान चुनें",
    "map.selected_location": "चयनित स्थान",
    "map.set_home": "होम स्थान बनाएं",
    "map.tap_hint": "लाइव मौसम और अलर्ट देखने के लिए मानचित्र पर कहीं भी टैप करें",
    "map.timeline": "समयरेखा:",
    "map.title": "भू-स्थानिक मौसम और रडार मानचित्र",
    "map.toggle_alerts": "अलर्ट टॉगल करें",
    "map.updated_prefix": "अपडेट किया गया:",
    "map.verified_badge": "लाइव सत्यापित",
    "map.view_live_radar": "लाइव रडार मानचित्र देखें",
    "map.tile_clouds": "बादल",
    "map.tile_radar": "रडार",
    "map.tile_rain": "बारिश",
    "map.tile_temp": "तापमान",
    "map.tile_waves": "लहरें",
    "map.tile_wind": "हवा",
    "map.weather_here": "यहाँ का मौसम",
    "more.agri_item": "कृषि और फसल सुरक्षा",
    "more.ai_chat_item": "स्काईज़ेन संवादात्मक सहायक से पूछें",
    "more.ai_heading": "एआई सलाहकार इंजन",
    "more.aqi_item": "वायु गुणवत्ता सूचकांक और प्रदूषक",
    "more.forecast_item": "विस्तृत पूर्वानुमान और जलवायु रुझान",
    "more.map_item": "भू-स्थानिक रडार और अलर्ट मानचित्र",
    "more.pref_heading": "प्राथमिकताएं और खाता",
    "more.profile_item": "उपयोगकर्ता प्रोफ़ाइल और प्रमाणीकरण",
    "more.saved_item": "सहेजे गए शहरों का प्रबंधन करें",
    "more.settings_item": "एप्लिकेशन सेटिंग्स और भाषा",
    "more.tools_heading": "मौसम खुफिया उपकरण",
    "more.travel_item": "अंतर-जिला यात्रा सलाह",
    "nav.ai": "एआई",
    "nav.alerts": "अलर्ट",
    "nav.aqi": "एक्यूआई",
    "nav.back_to_home": "होम पर वापस जाएं",
    "nav.back_to_hub": "हब पर वापस जाएं",
    "nav.chat": "मौसम जीपीटी",
    "nav.forecast": "पूर्वानुमान",
    "nav.home": "होम",
    "nav.language_toggle": "भाषा",
    "nav.locations": "सहेजे गए",
    "nav.map": "लाइव मैप",
    "nav.more": "अधिक",
    "nav.radar": "रडार",
    "nav.radar_map": "रडार मानचित्र",
    "nav.settings": "सेटिंग्स",
    "onboarding.alerts": "गंभीर मौसम अलर्ट और सलाह सक्षम करें",
    "onboarding.lang": "पसंदीदा भाषा /",
    "onboarding.name": "पूरा नाम",
    "onboarding.role": "मुख्य भूमिका / व्यक्तित्व",
    "onboarding.submit": "सेटअप पूरा करें और स्काईज़ेन में प्रवेश करें",
    "onboarding.subtitle": "मौसम संबंधी सलाह को अनुकूलित करने के लिए अपनी प्रोफ़ाइल सेट करें।",
    "onboarding.title": "स्काईज़ेन में आपका स्वागत है",
    "pollutant.co": "कार्बन मोनोऑक्साइड",
    "pollutant.no2": "नाइट्रोजन डाइऑक्साइड",
    "pollutant.o3": "ओजोन",
    "pollutant.pm10": "पीएम 10 (श्वसनीय कण)",
    "pollutant.pm25": "पीएम 2.5 (महीन कण)",
    "pollutant.so2": "सल्फर डाइऑक्साइड",
    "profile.account_role": "खाता भूमिका:",
    "profile.active": "सक्रिय",
    "profile.alerts_checkbox": "गंभीर मौसम चेतावनी सूचनाएं",
    "profile.edit_heading": "प्रोफ़ाइल और व्यक्तित्व को अनुकूलित करें",
    "profile.full_name": "पूरा नाम",
    "profile.guest_login_btn": "साइन इन करें / खाता बनाएं",
    "profile.guest_prompt": "सहेजे गए स्थानों और प्राथमिकताओं को समन्वयित करने के लिए साइन इन करें।",
    "profile.lang_label": "पसंदीदा भाषा /",
    "profile.role_label": "खाता भूमिका:",
    "profile.save_btn": "प्रोफ़ाइल परिवर्तन सहेजें",
    "profile.saved_summary": "सहेजे गए शहरों का सारांश",
    "profile.sign_in_sync_prompt": "सहेजे गए स्थानों को सिंक करने के लिए साइन इन करें।",
    "profile.signout_btn": "स्काईज़ेन से साइन आउट करें",
    "profile.status": "स्थिति:",
    "profile.status_label": "स्थिति:",
    "profile.summary_heading": "उपयोगकर्ता प्रोफ़ाइल",
    "profile.title": "उपयोगकर्ता प्रोफ़ाइल और खाता",
    "profile.user_title": "स्काईज़ेन उपयोगकर्ता",
    "profile.verified": "सत्यापित",
    "pwa.install_btn": "अभी इंस्टॉल करें",
    "pwa.install_desc": "त्वरित अलर्ट, पूर्ण स्क्रीन दृश्य और ऑफ़लाइन मौसम जानकारी के लिए होम स्क्रीन पर जोड़ें।",
    "pwa.install_title": "स्काईज़ेन ऐप इंस्टॉल करें",
    "pwa.later": "बाद में",
    "role.commuter_desc": "यात्री — सार्वजनिक परिवहन, सड़क और बारिश अलर्ट",
    "role.disaster": "आपदा / आपातकाल",
    "role.disaster_desc": "आपदा / आपातकाल — पूर्व चेतावनी और चक्रवात राहत",
    "role.disaster_resp": "आपदा प्रतिक्रिया",
    "role.farmer_desc": "किसान — कृषि वर्षा और फसल कटाई योजना",
    "role.fisherman_desc": "मछुआरा — समुद्री हवा और तटीय सुरक्षा",
    "role.general_desc": "सामान्य उपयोगकर्ता — दैनिक मौसम अवलोकन",
    "role.student_desc": "छात्र — दैनिक आवागमन और परिसर का मौसम",
    "role.traveller": "यात्री",
    "search.clear": "खोज साफ़ करें",
    "search.placeholder": "शहर या जिला खोजें (जैसे कोयंबटूर, दिल्ली)...",
    "search.recent_popular": "प्रमुख शहर",
    "settings.about_title": "स्काईज़ेन संस्करण 1.0.0 के बारे में",
    "settings.custom_backend_label": "कस्टम बैकएंड यूआरएल",
    "settings.env_custom_server": "कस्टम उत्पादन सर्वर (सुरक्षित)...",
    "settings.env_emulator": "एंड्रॉइड एमुलेटर",
    "settings.env_localhost": "स्थानीय देव सर्वर",
    "settings.env_server": "एपीआई पर्यावरण सर्वर",
    "settings.env_web_shell": "उत्पादन वेब शेल",
    "settings.language": "भाषा",
    "settings.language.en": "अंग्रेज़ी",
    "settings.language.hi": "हिंदी",
    "settings.language.ta": "तमिल",
    "settings.logout": "साइन आउट",
    "settings.moes_imd_full": "पृथ्वी विज्ञान मंत्रालय (पृथ्वी विज्ञान मंत्रालय) / भारत मौसम विज्ञान विभाग (आईएमडी)",
    "settings.notifications": "आपातकालीन चेतावनियां और एफसीएम सूचनाएं",
    "settings.persona_hint": "जीवनशैली सुझावों और मौसम अनुशंसाओं को अनुकूलित करता है।",
    "settings.persona_label": "भूमिका / मौसम व्यक्तित्व",
    "settings.profile_desc": "नाम, भूमिका और भाषा प्रबंधित करें",
    "settings.profile_persona": "प्रोफ़ाइल और भूमिका",
    "settings.push_active": "सक्रिय (एफसीएम)",
    "settings.push_channel": "पुश अलर्ट चैनल",
    "settings.save": "सेटिंग्स सहेजें",
    "settings.sih_core": "एसआईएच26068 मौसम जीपीटी बुद्धिमत्ता कोर",
    "settings.test_alert_btn": "परीक्षण अलर्ट भेजें",
    "settings.title": "एप्लिकेशन सेटिंग्स",
    "settings.unit_imperial": "इंपीरियल (°फ़ारेनहाइट, मील/घंटा, इंच)",
    "settings.unit_metric": "मीट्रिक (°सेल्सियस, किमी/घंटा, मिमी, हेक्टोपास्कल)",
    "settings.theme": "दिखावट थीम",
    "settings.themeDesc": "लाइट, डार्क या सिस्टम थीम चुनें",
    "settings.units": "पसंदीदा माप इकाइयां",
    "severity.high": "उच्च",
    "sidebar.brand_sub": "मौसम बुद्धिमत्ता",
    "sidebar.brand_title": "स्काईज़ेन",
    "splash.launch_demo": "प्रस्तुति डेमो शुरू करें",
    "splash.status": "मौसम बुद्धिमत्ता प्रारंभ हो रही है...",
    "system.offline_notice": "आप ऑफ़लाइन हैं। मौसम ताज़ा करने के लिए पुनः कनेक्ट करें।",
    "weather.climate_archive": "जलवायु रुझान पुरालेख (नासा पावर)",
    "weather.extended_future": "विस्तारित भविष्य पूर्वानुमान",
    "weather.offline": "नेटवर्क ऑफ़लाइन है। सहेजा गया मौसम डेटा दिखा रहा है।",
    "weather.today_hourly": "आज का प्रति घंटा पूर्वानुमान",
    "weather.today_sub": "24-घंटे का क्षितिज",
    "weather.tomorrow_hourly": "कल का प्रति घंटा पूर्वानुमान",
    "dashboard.now": "अब",
    "chat.reasoning": "स्काईज़ेन मौसम डेटा का विश्लेषण कर रहा है",
    "chat.chip_rain_query": "क्या कल बारिश होगी?",
    "chat.chip_college_query": "क्या आज कॉलेज जा सकते हैं?",
    "chat.chip_bike_query": "क्या बाइक ले जाऊं?",
    "chat.chip_umbrella_query": "क्या छाते की जरूरत है?",
    "lifestyle.unavailable": "सीमित मौसम टेलीमेट्री के कारण जीवनशैली संबंधी सुझाव उपलब्ध नहीं हैं।",
    "lifestyle.cat_home_daily": "घर और दैनिक",
    "lifestyle.cat_agriculture": "कृषि",
    "lifestyle.cat_commute": "आवागमन",
    "lifestyle.cat_transit": "पारगमन",
    "lifestyle.cat_fitness": "फिटनेस और खेल",
    "lifestyle.cat_farming": "खेती",
    "lifestyle.cat_daily_life": "दैनिक जीवन",
    "lifestyle.title_laundry": "बाहर कपड़े सुखाना",
    "lifestyle.title_spray": "कीटनाशक छिड़काव समय",
    "lifestyle.title_bike": "दोपहिया और बाइक सुरक्षा",
    "lifestyle.title_flood": "सड़क जलभराव और सबवे",
    "lifestyle.title_fitness": "बाहरी दौड़ और जॉगिंग",
    "lifestyle.title_harvest": "फसल कटाई और धूप में सुखाना",
    "lifestyle.title_umbrella": "छाता आवश्यकता स्कोर",
    "lifestyle.status_fast_dry": "तेज़ी से सूखेंगे",
    "lifestyle.status_indoor_drying": "अंदर सुखाने की सलाह",
    "lifestyle.status_slow_dry": "धीमी सुखाई (~4-5 घंटे)",
    "lifestyle.status_ideal_spray": "छिड़काव के लिए आदर्श समय",
    "lifestyle.status_no_spray": "आज छिड़काव न करें",
    "lifestyle.status_drift_caution": "मध्यम हवा बहाव सावधानी",
    "lifestyle.status_smooth_ride": "सुगम यात्रा",
    "lifestyle.status_skid_risk": "फिसलन का उच्च जोखिम",
    "lifestyle.status_wet_asphalt": "गीली सड़क सावधानी",
    "lifestyle.status_clear_roads": "साफ़ सड़कें",
    "lifestyle.status_waterlogging": "जलभराव की संभावना",
    "lifestyle.status_spot_puddles": "सड़क पर छोटे गड्ढे/पानी",
    "lifestyle.status_great_workout": "उत्कृष्ट वर्कआउट समय",
    "lifestyle.status_indoor_cardio": "घर के अंदर व्यायाम अनुशंसित",
    "lifestyle.status_hydration_caution": "जलयोजन सावधानी",
    "lifestyle.status_safe_harvest": "कटाई के लिए सुरक्षित",
    "lifestyle.status_delay_harvest": "कटाई स्थगित करें / उपज ढकें",
    "lifestyle.status_monitor_grain": "अनाज की नमी की निगरानी करें",
    "lifestyle.status_not_needed": "आवश्यकता नहीं",
    "lifestyle.status_keep_in_bag": "बैग में रखें",
    "lifestyle.status_must_carry": "अवश्य साथ रखें",
    "lifestyle.metric_drying_index": "सुखाने का सूचकांक",
    "lifestyle.metric_wind_runoff": "हवा और बहाव",
    "lifestyle.metric_road_traction": "सड़क कर्षण",
    "lifestyle.metric_drainage_risk": "जल निकासी जोखिम",
    "lifestyle.metric_heat_index": "ताप सूचकांक",
    "lifestyle.metric_solar_radiation": "सौर विकिरण",
    "lifestyle.metric_rain_prob": "बारिश की संभावना",
    "lifestyle.unit_hrs": "घंटे",
    "lifestyle.unit_rain": "बारिश",
    "lifestyle.unit_wind": "हवा",
    "lifestyle.unit_hum": "नमी",
    "lifestyle.val_high_severe": "उच्च (गंभीर चेतावनी)",
    "lifestyle.val_normal": "सामान्य",
    "lifestyle.desc_laundry_opt": "कपड़े बाहर सुखाने के लिए आदर्श स्थिति। कपड़े लगभग {h} घंटे में सूख जाएंगे।",
    "lifestyle.desc_laundry_rain": "बारिश की संभावना है। कपड़े घर के अंदर या ढकी हुई बालकनी में सुखाएं।",
    "lifestyle.desc_laundry_slow": "हवा में अधिक नमी। सूखने में अधिक समय लगेगा (~4-5 घंटे); अच्छे वेंटिलेशन की आवश्यकता है।",
    "lifestyle.desc_spray_opt": "धीमी हवा और बारिश का कोई खतरा नहीं। फसल पर छिड़काव के लिए आदर्श समय।",
    "lifestyle.desc_spray_rain": "तेज़ बहाव और बहाव का जोखिम। दवा की बर्बादी रोकने के लिए छिड़काव टालें।",
    "lifestyle.desc_spray_caution": "हवा चल रही है। बहाव-रोधी नोजल का उपयोग करें या सुबह जल्दी छिड़काव करें।",
    "lifestyle.desc_commute_opt": "सूखी सड़कें और अच्छा दृश्य। दोपहिया वाहन चलाने के लिए सुरक्षित स्थिति।",
    "lifestyle.desc_commute_rain": "फिसलन भरी सड़क और कम घर्षण। गति धीमी रखें और सुरक्षित दूरी बनाए रखें।",
    "lifestyle.desc_commute_caution": "सड़क की सतह गीली है। मोड़ों पर और अचानक ब्रेक लगाने में सावधानी बरतें।",
    "lifestyle.desc_flood_opt": "सबवे और प्रमुख सड़कें साफ हैं। सामान्य यातायात की उम्मीद है।",
    "lifestyle.desc_flood_alert": "गंभीर चेतावनी सक्रिय: निचले इलाकों और सबवे में जलभराव की संभावना। वैकल्पिक मार्ग चुनें।",
    "lifestyle.desc_flood_heavy": "भारी बारिश का जोखिम। जलभराव वाले अंडरपास से बचें।",
    "lifestyle.desc_flood_caution": "सड़क किनारे पानी जमा हो सकता है। पानी में छिपे गड्ढों से सावधान रहें।",
    "lifestyle.desc_fitness_opt": "दौड़ने के लिए सुखद मौसम ({t}°C)। उत्तम वायु गुणवत्ता और अनुकूल तापमान।",
    "lifestyle.desc_fitness_heat": "अत्यधिक गर्मी और थकान का जोखिम। इनडोर वर्कआउट या जिम का विकल्प चुनें।",
    "lifestyle.desc_fitness_caution": "गर्म और उमस भरा मौसम। कसरत से पहले, दौरान और बाद में पर्याप्त पानी पिएं।",
    "lifestyle.desc_harvest_opt": "शुष्क मौसम और तेज धूप। फसल कटाई और अनाज को धूप में सुखाने के लिए सुरक्षित समय।",
    "lifestyle.desc_harvest_rain": "बारिश का खतरा। फसल को भीगने से बचाने के लिए तिरपाल से तुरंत ढकें।",
    "lifestyle.desc_harvest_caution": "अधिक नमी के कारण सूखने में समय लग सकता है। अनाज को बराबर सुखाने के लिए पलटते रहें।",
    "lifestyle.desc_umbrella_low": "बारिश की बहुत कम संभावना। सामान्य बाहरी कामों के लिए छाते की जरूरत नहीं है।",
    "lifestyle.desc_umbrella_mid": "कहीं-कहीं हल्की बारिश संभव है। अपने बैग में एक छोटा छाता जरूर रखें।",
    "lifestyle.desc_umbrella_high": "बारिश की अधिक संभावना। मजबूत छाता साथ रखें और वाटरप्रूफ जूते पहनें।"
  }
};

// Dynamic Labels Localizer Dictionary for factual values preserved
const DYNAMIC_LABELS = {
  "Rain Chance": {
    "ta": "மழை வாய்ப்பு",
    "hi": "बारिश की संभावना"
  },
  "Wind Speed": {
    "ta": "காற்றின் வேகம்",
    "hi": "हवा की गति"
  },
  "Humidity": {
    "ta": "ஈரப்பதம்",
    "hi": "नमी"
  },
  "UV Index": {
    "ta": "யுவி குறியீடு",
    "hi": "यूवी इंडेक्स"
  },
  "Pressure": {
    "ta": "வளிமண்டல அழுத்தம்",
    "hi": "वायुदाब"
  },
  "Precipitation": {
    "ta": "மழைப்பொழிவு",
    "hi": "वर्षा"
  },
  "Feels Like": {
    "ta": "உணரப்படும் வெப்பநிலை",
    "hi": "महसूस होता है"
  },
  "Feels like": {
    "ta": "உணரப்படும் வெப்பநிலை",
    "hi": "महसूस होता है"
  },
  "Observed at": {
    "ta": "கணிக்கப்பட்ட நேரம்",
    "hi": "अवलोकन समय"
  },
  "Updated": {
    "ta": "புதுப்பிக்கப்பட்டது",
    "hi": "अपडेट किया गया"
  },
  "Forecast Consensus": {
    "ta": "முன்னறிவிப்பு ஒருமித்த கருத்து",
    "hi": "पूर्वानुमान सहमति"
  },
  "High Agreement": {
    "ta": "அதிக உடன்பாடு",
    "hi": "उच्च सहमति"
  },
  "Medium Agreement": {
    "ta": "நடுத்தர உடன்பாடு",
    "hi": "मध्यम सहमति"
  },
  "Cautious": {
    "ta": "எச்சரிக்கையான",
    "hi": "सतर्क"
  },
  "Disagreement": {
    "ta": "மாறுபட்ட கருத்து",
    "hi": "असहमति"
  },
  "Live Weather": {
    "ta": "நேரலை வானிலை",
    "hi": "लाइव मौसम"
  },
  "LIVE WEATHER": {
    "ta": "நேரலை வானிலை",
    "hi": "लाइव मौसम"
  },
  "Degraded": {
    "ta": "குறைந்த தரம்",
    "hi": "सीमित"
  },
  "Offline": {
    "ta": "இணைப்பற்ற நிலை",
    "hi": "ऑफ़लाइन"
  },
  "Data Stale": {
    "ta": "பழைய தரவு",
    "hi": "पुराना डेटा"
  },
  "Service Unavailable": {
    "ta": "சேவை கிடைக்கவில்லை",
    "hi": "सेवा अनुपलब्ध"
  },
  "Cached": {
    "ta": "சேமிக்கப்பட்டவை",
    "hi": "कैश्ड"
  },
  "Official IMD Warning": {
    "ta": "அதிகாரப்பூர்வ ஐஎம்டி எச்சரிக்கை",
    "hi": "आधिकारिक आईएमडी चेतावनी"
  },
  "OFFICIAL IMD WARNING": {
    "ta": "அதிகாரப்பூர்வ ஐஎம்டி எச்சரிக்கை",
    "hi": "आधिकारिक आईएमडी चेतावनी"
  },
  "Weather Warning": {
    "ta": "வானிலை எச்சரிக்கை",
    "hi": "मौसम चेतावनी"
  },
  "WEATHER WARNING": {
    "ta": "வானிலை எச்சரிக்கை",
    "hi": "मौसम चेतावनी"
  },
  "Valid until": {
    "ta": "செல்லுபடியாகும் நேரம்",
    "hi": "मान्य समय"
  },
  "Authoritative Source": {
    "ta": "அதிகாரப்பூர்வ மூலம்",
    "hi": "आधिकारिक स्रोत"
  },
  "AQI Source": {
    "ta": "காற்று தர மூலம்",
    "hi": "एक्यूआई स्रोत"
  },
  "Air-quality model": {
    "ta": "காற்று தர மாதிரி",
    "hi": "वायु गुणवत्ता मॉडल"
  },
  "Air Quality Model:": {
    "ta": "காற்று தர மாதிரி:",
    "hi": "वायु गुणवत्ता मॉडल:"
  },
  "CURRENT LIVE LOCATION": {
    "ta": "தற்போதைய நேரலை இருப்பிடம்",
    "hi": "वर्तमान लाइव स्थान"
  },
  "LAST KNOWN LOCATION": {
    "ta": "கடைசியாக அறியப்பட்ட இருப்பிடம்",
    "hi": "अंतिम ज्ञात स्थान"
  },
  "PERMISSION DENIED": {
    "ta": "அனுமதி மறுக்கப்பட்டது",
    "hi": "अनुमति अस्वीकृत"
  },
  "GPS UNAVAILABLE": {
    "ta": "ஜிபிஎஸ் கிடைக்கவில்லை",
    "hi": "जीपीएस अनुपलब्ध"
  },
  "GPS TIMEOUT": {
    "ta": "ஜிபிஎஸ் காலாவதியானது",
    "hi": "जीपीएस समय समाप्त"
  },
  "COORDINATES ONLY": {
    "ta": "ஒருங்கிணைப்புகள் மட்டும்",
    "hi": "केवल निर्देशांक"
  },
  "MANUAL LOCATION": {
    "ta": "கைமுறை இருப்பிடம்",
    "hi": "मैन्युअल स्थान"
  },
  "Visibility": {
    "ta": "பார்வை தூரம்",
    "hi": "दृश्यता"
  },
  "Fresh Telemetry": {
    "ta": "புதிய தரவு",
    "hi": "ताज़ा डेटा"
  },
  "Data Stale (Cached)": {
    "ta": "பழைய தரவு (சேமிக்கப்பட்டது)",
    "hi": "पुराना डेटा (कैश्ड)"
  },
  "Cached Telemetry (Offline)": {
    "ta": "சேமிக்கப்பட்ட தரவு (ஆஃப்லைன்)",
    "hi": "कैश्ड डेटा (ऑफ़लाइन)"
  },
  "Degraded Telemetry": {
    "ta": "குறைந்த தரவு",
    "hi": "सीमित डेटा"
  },
  "Single Provider Active": {
    "ta": "ஒற்றை மூலம் செயலில்",
    "hi": "एकल प्रदाता सक्रिय"
  },
  "Single Provider": {
    "ta": "ஒற்றை மூலம்",
    "hi": "एकल प्रदाता"
  },
  "WEATHER SOURCES": {
    "ta": "வானிலை தகவல் மூலங்கள்",
    "hi": "मौसम स्रोत"
  },
  "Key Pollutants Breakdown": {
    "ta": "முக்கிய மாசு அளவுகள்",
    "hi": "प्रमुख प्रदूषक"
  },
  "Health & Activity Recommendations": {
    "ta": "உடல்நலம் & செயல்பாட்டு பரிந்துரைகள்",
    "hi": "स्वास्थ्य और गतिविधि अनुशंसाएं"
  },
  "Good": {
    "ta": "நன்று",
    "hi": "अच्छा"
  },
  "Moderate": {
    "ta": "மிதமானது",
    "hi": "मध्यम"
  },
  "Poor": {
    "ta": "மோசமானது",
    "hi": "खराब"
  },
  "Very Poor": {
    "ta": "மிக மோசமானது",
    "hi": "बहुत खराब"
  },
  "Severe": {
    "ta": "கடுமையானது",
    "hi": "गंभीर"
  },
  "CPCB OFFICIAL API ACCESS NOT CONFIGURED": {
    "ta": "சிபிசிபி அதிகாரப்பூர்வ ஏபிஐ அணுகல் கட்டமைக்கப்படவில்லை",
    "hi": "सीपीसीबी आधिकारिक एपीआई एक्सेस कॉन्फ़िगर नहीं है"
  },
  "CPCB Ground Monitoring API Not Configured": {
    "ta": "சிபிசிபி தரை கண்காணிப்பு ஏபிஐ கட்டமைக்கப்படவில்லை",
    "hi": "सीपीसीबी ग्राउंड मॉनिटरिंग एपीआई कॉन्फ़िगर नहीं है"
  },
  "Today": {
    "ta": "இன்று",
    "hi": "आज"
  },
  "Tomorrow": {
    "ta": "நாளை",
    "hi": "कल"
  },
  "Wednesday": {
    "ta": "புதன்",
    "hi": "बुधवार"
  },
  "Thursday": {
    "ta": "வியாழன்",
    "hi": "गुरुवार"
  },
  "Friday": {
    "ta": "வெள்ளி",
    "hi": "शुक्रवार"
  },
  "Saturday": {
    "ta": "சனி",
    "hi": "शनिवार"
  },
  "Sunday": {
    "ta": "ஞாயிறு",
    "hi": "रविवार"
  },
  "Monday": {
    "ta": "திங்கள்",
    "hi": "सोमवार"
  },
  "Tuesday": {
    "ta": "செவ்வாய்",
    "hi": "मंगलवार"
  },
  "Partly Cloudy": {
    "ta": "பகுதி மேகமூட்டம்",
    "hi": "आंशिक रूप से बादल"
  },
  "Moderate Rain": {
    "ta": "மிதமான மழை",
    "hi": "मध्यम बारिश"
  },
  "Scattered Showers": {
    "ta": "சிதறிய மழை",
    "hi": "छिटपुट बौछारें"
  },
  "Sunny": {
    "ta": "வெயில்",
    "hi": "धूप"
  },
  "Thunderstorm": {
    "ta": "இடியுடன் கூடிய மழை",
    "hi": "गरज के साथ बारिश"
  },
  "Cloudy": {
    "ta": "மேகமூட்டம்",
    "hi": "बादल छाए रहेंगे"
  },
  "Clear Skies": {
    "ta": "தெளிவான வானம்",
    "hi": "साफ़ आसमान"
  },
  "Clear": {
    "ta": "தெளிவான வானம்",
    "hi": "साफ़"
  },
  "Rain": {
    "ta": "மழை",
    "hi": "बारिश"
  },
  "Heavy Rain": {
    "ta": "கனமழை",
    "hi": "भारी बारिश"
  },
  "Drizzle": {
    "ta": "தூறல்",
    "hi": "बूंदाबांदी"
  },
  "Light Rain": {
    "ta": "லேசான மழை",
    "hi": "हल्की बारिश"
  },
  "Overcast": {
    "ta": "முழு மேகமூட்டம்",
    "hi": "घने बादल"
  },
  "Mist": {
    "ta": "பனிமூட்டம்",
    "hi": "धुंध"
  },
  "Haze": {
    "ta": "புகைமூட்டம்",
    "hi": "धुंध"
  },
  "Heavy Rain Underway": {
    "ta": "கனமழை பெய்து கொண்டிருக்கிறது",
    "hi": "भारी बारिश जारी है"
  },
  "Light Rain Continuing": {
    "ta": "லேசான மழை தொடர்கிறது",
    "hi": "हल्की बारिश जारी है"
  },
  "Rain Expected in ~18 Min": {
    "ta": "~18 நிமிடங்களில் மழை எதிர்பார்க்கப்படுகிறது",
    "hi": "~18 मिनट में बारिश की संभावना"
  },
  "Low Chance of Light Drizzle": {
    "ta": "லேசான தூறலுக்கான குறைந்த வாய்ப்பு",
    "hi": "हल्की बूंदाबांदी की कम संभावना"
  },
  "Clear & Dry Next 60 Minutes": {
    "ta": "அடுத்த 60 நிமிடங்களுக்கு தெளிவான வானிலை",
    "hi": "अगले 60 मिनट साफ़ और शुष्क"
  },
  "MODELLED NOWCAST PROJECTION": {
    "ta": "கணிக்கப்பட்ட நேரடி முன்னறிவிப்பு",
    "hi": "मॉडल किया गया नाउकास्ट प्रक्षेपण"
  },
  "IMD WARNING ACTIVE": {
    "ta": "ஐஎம்டி எச்சரிக்கை செயலில் உள்ளது",
    "hi": "आईएमडी चेतावनी सक्रिय"
  },
  "WEATHER WARNING ACTIVE": {
    "ta": "வானிலை எச்சரிக்கை செயலில் உள்ளது",
    "hi": "मौसम चेतावनी सक्रिय"
  },
  "Home & Daily": {
    "ta": "வீடு & தினசரி",
    "hi": "घर और दैनिक"
  },
  "Agriculture": {
    "ta": "விவசாயம்",
    "hi": "कृषि"
  },
  "Commute": {
    "ta": "பயணம்",
    "hi": "आवागमन"
  },
  "Transit": {
    "ta": "போக்குவரத்து",
    "hi": "पारगमन"
  },
  "Fitness & Sport": {
    "ta": "உடற்பயிற்சி & விளையாட்டு",
    "hi": "फिटनेस और खेल"
  },
  "Farming": {
    "ta": "பண்ணை & விவசாயம்",
    "hi": "खेती"
  },
  "Daily Life": {
    "ta": "தினசரி வாழ்க்கை",
    "hi": "दैनिक जीवन"
  },
  "Outdoor Laundry Drying": {
    "ta": "வெளியில் துணி உலர்த்துதல்",
    "hi": "बाहर कपड़े सुखाना"
  },
  "Pesticide Spray Window": {
    "ta": "பூச்சிக்கொல்லி தெளிப்பு நேரம்",
    "hi": "कीटनाशक छिड़काव समय"
  },
  "Two-Wheeler & Bike Safety": {
    "ta": "இருசக்கர வாகன பாதுகாப்பு",
    "hi": "दोपहिया और बाइक सुरक्षा"
  },
  "Road Flooding & Subways": {
    "ta": "சாலை வெள்ளம் & சுரங்கப்பாதைகள்",
    "hi": "सड़क जलभराव और सबवे"
  },
  "Outdoor Running & Jogging": {
    "ta": "வெளியில் ஓட்டம் & நடைபயிற்சி",
    "hi": "बाहरी दौड़ और जॉगिंग"
  },
  "Crop Harvest & Sun-Drying": {
    "ta": "பயிர் அறுவடை & களம் உலர்த்துதல்",
    "hi": "फसल कटाई और धूप में सुखाना"
  },
  "Umbrella Necessity Score": {
    "ta": "குடை தேவை மதிப்பீடு",
    "hi": "छाता आवश्यकता स्कोर"
  },
  "Fast Dry": {
    "ta": "விரைவில் உலரும்",
    "hi": "तेज़ी से सूखेंगे"
  },
  "Indoor Drying Advised": {
    "ta": "உள்ளே உலர்த்த பரிந்துரை",
    "hi": "अंदर सुखाने की सलाह"
  },
  "Slow Dry (~4-5h)": {
    "ta": "மெதுவாக உலரும் (~4-5 மணி)",
    "hi": "धीमी सुखाई (~4-5 घंटे)"
  },
  "Ideal Spray Window": {
    "ta": "தெளிக்க உகந்த நேரம்",
    "hi": "छिड़काव के लिए आदर्श समय"
  },
  "Do Not Spray Today": {
    "ta": "இன்று தெளிக்க வேண்டாம்",
    "hi": "आज छिड़काव न करें"
  },
  "Moderate Drift Caution": {
    "ta": "மிதமான காற்று எச்சரிக்கை",
    "hi": "मध्यम हवा बहाव सावधानी"
  },
  "Smooth Ride": {
    "ta": "சீரான பயணம்",
    "hi": "सुगम यात्रा"
  },
  "High Skidding Risk": {
    "ta": "வழுக்கும் அபாயம் அதிகம்",
    "hi": "फिसलन का उच्च जोखिम"
  },
  "Wet Asphalt Caution": {
    "ta": "ஈரமான சாலை எச்சரிக்கை",
    "hi": "गीली सड़क सावधानी"
  },
  "Clear Roads": {
    "ta": "தெளிவான சாலைகள்",
    "hi": "साफ़ सड़कें"
  },
  "Waterlogging Probable": {
    "ta": "நீர் தேங்க வாய்ப்பு",
    "hi": "जलभराव की संभावना"
  },
  "Spot Puddles": {
    "ta": "சாலைகளில் சிறு நீர்நிலைகள்",
    "hi": "सड़क पर छोटे गड्ढे/पानी"
  },
  "Great Workout Window": {
    "ta": "சிறந்த உடற்பயிற்சி நேரம்",
    "hi": "उत्कृष्ट वर्कआउट समय"
  },
  "Indoor Cardio Recommended": {
    "ta": "உள்ளரங்க உடற்பயிற்சி சிறந்தது",
    "hi": "घर के अंदर व्यायाम अनुशंसित"
  },
  "Hydration Caution": {
    "ta": "நீரேற்ற எச்சரிக்கை",
    "hi": "जलयोजन सावधानी"
  },
  "Safe for Harvest": {
    "ta": "அறுவடைக்கு பாதுகாப்பானது",
    "hi": "कटाई के लिए सुरक्षित"
  },
  "Delay Harvest / Cover Produce": {
    "ta": "அறுவடையை தள்ளிப்போடுக / பயிரை மூடுக",
    "hi": "कटाई स्थगित करें / उपज ढकें"
  },
  "Monitor Grain Moisture": {
    "ta": "தானிய ஈரப்பதத்தை கண்காணிக்கவும்",
    "hi": "अनाज की नमी की निगरानी करें"
  },
  "Not Needed": {
    "ta": "தேவையில்லை",
    "hi": "आवश्यकता नहीं"
  },
  "Keep in Bag": {
    "ta": "பையில் வைத்திருக்கவும்",
    "hi": "बैग में रखें"
  },
  "Must Carry": {
    "ta": "கட்டாயம் எடுத்துச் செல்லவும்",
    "hi": "अवश्य साथ रखें"
  },
  "Drying Index": {
    "ta": "உலர்த்தல் குறியீடு",
    "hi": "सुखाने का सूचकांक"
  },
  "Wind & Runoff": {
    "ta": "காற்று & மழைநீர் ஓட்டம்",
    "hi": "हवा और बहाव"
  },
  "Road Traction": {
    "ta": "சாலை பிடிப்பு",
    "hi": "सड़क कर्षण"
  },
  "Drainage Risk": {
    "ta": "வடிகால் ஆபத்து",
    "hi": "जल निकासी जोखिम"
  },
  "Heat Index": {
    "ta": "வெப்பக் குறியீடு",
    "hi": "ताप सूचकांक"
  },
  "Solar Radiation": {
    "ta": "சூரிய கதிர்வீச்சு",
    "hi": "सौर विकिरण"
  },
  "Rain Probability": {
    "ta": "மழை சாத்தியக்கூறு",
    "hi": "बारिश की संभावना"
  },
  "hrs": {
    "ta": "மணி",
    "hi": "घंटे"
  },
  "rain": {
    "ta": "மழை",
    "hi": "बारिश"
  },
  "wind": {
    "ta": "காற்று",
    "hi": "हवा"
  },
  "hum": {
    "ta": "ஈரப்பதம்",
    "hi": "नमी"
  },
  "High (Severe Alert)": {
    "ta": "அதிகம் (தீவிர எச்சரிக்கை)",
    "hi": "उच्च (गंभीर चेतावनी)"
  },
  "Normal": {
    "ta": "இயல்பு",
    "hi": "सामान्य"
  },
  "Active": {
    "ta": "செயலில்",
    "hi": "सक्रिय"
  },
  "Offline Cached Record": {
    "ta": "ஆஃப்லைன் சேமிக்கப்பட்ட பதிவு",
    "hi": "ऑफ़लाइन सहेजा गया रिकॉर्ड"
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
    return dict[key] || (I18N_DICT["en"] ? I18N_DICT["en"][key] : "") || key;
  },

  localizeDynamic: function(label) {
    if (!label) return "";
    const lang = this.currentLanguage;
    if (lang === "en") return label;
    
    const trimmed = String(label).trim();
    if (DYNAMIC_LABELS[trimmed] && DYNAMIC_LABELS[trimmed][lang]) {
      return DYNAMIC_LABELS[trimmed][lang];
    }
    const lower = trimmed.toLowerCase();
    for (const [k, v] of Object.entries(DYNAMIC_LABELS)) {
      if (k.toLowerCase() === lower && v[lang]) {
        return v[lang];
      }
    }
    return label;
  },

  applyTranslations: function() {
    const lang = this.currentLanguage;
    const dict = I18N_DICT[lang] || I18N_DICT["en"];
    
    // Update html lang attribute for screen readers & native fonts
    document.documentElement.lang = lang;

    // Update document title
    if (dict["app.page_title"]) {
      document.title = dict["app.page_title"];
    }

    // Text elements with data-i18n
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const text = dict[key] || (I18N_DICT["en"] ? I18N_DICT["en"][key] : "");
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
          const dot = el.querySelector('.accent-dot');
          if (dot) {
            let changed = false;
            el.childNodes.forEach(child => {
              if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) {
                child.textContent = text;
                changed = true;
              }
            });
          } else {
            el.textContent = text;
          }
        }
      }
    });

    // Ensure all bottom navigation and sidebar items are guaranteed translated by data-screen
    const screenKeyMap = {
      'home': 'nav.home',
      'map': 'nav.radar',
      'alerts': 'nav.alerts',
      'weather': 'nav.forecast',
      'chat': 'nav.ai',
      'air-quality': 'nav.aqi',
      'settings': 'nav.settings'
    };
    document.querySelectorAll('.app-bottom-nav [data-screen], .sidebar-nav-group [data-screen]').forEach(btn => {
      const screen = btn.getAttribute('data-screen');
      const key = screenKeyMap[screen];
      if (key && dict[key]) {
        const label = btn.querySelector('.nav-label') || Array.from(btn.querySelectorAll('span')).find(s => !s.classList.contains('material-symbols-rounded'));
        if (label) {
          label.textContent = dict[key];
        }
      }
    });

    // Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const text = dict[key] || (I18N_DICT["en"] ? I18N_DICT["en"][key] : "");
      if (text) {
        el.setAttribute('placeholder', text);
      }
    });

    // Aria labels
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      const key = el.getAttribute('data-i18n-aria');
      const text = dict[key] || (I18N_DICT["en"] ? I18N_DICT["en"][key] : "");
      if (text) {
        el.setAttribute('aria-label', text);
      }
    });

    // Tooltips / Titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const text = dict[key] || (I18N_DICT["en"] ? I18N_DICT["en"][key] : "");
      if (text) {
        el.setAttribute('title', text);
      }
    });
  }
};

document.addEventListener("DOMContentLoaded", () => {
  window.I18N.init();
});
