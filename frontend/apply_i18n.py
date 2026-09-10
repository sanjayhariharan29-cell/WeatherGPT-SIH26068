import os
import re

html_path = r"c:\WeatherGPT-SIH26068\frontend\index.html"

with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    # Navigation
    (r"<span>Map</span>", r"<span data-i18n=\"nav.map\">Map</span>"),
    (r"<span>Alerts</span>", r"<span data-i18n=\"nav.alerts\">Alerts</span>"),
    (r"<span>More</span>", r"<span data-i18n=\"nav.settings\">More</span>"),
    # Auth Welcome
    (r"<h2 class=\"auth-brand-title\">SkyZen<span class=\"accent-dot\">\.</span></h2>", r"<h2 class=\"auth-brand-title\" data-i18n=\"auth.welcome.title\">SkyZen<span class=\"accent-dot\">.</span></h2>"),
    (r"<p class=\"auth-brand-tagline\">Clearer Skies\. Brighter Days\.</p>", r"<p class=\"auth-brand-tagline\" data-i18n=\"auth.welcome.tagline\">Clearer Skies. Brighter Days.</p>"),
    (r"<p class=\"auth-brand-desc\">AI-powered weather intelligence, severe alerts from IMD, and precision forecasts\.</p>", r"<p class=\"auth-brand-desc\" data-i18n=\"auth.welcome.desc\">AI-powered weather intelligence, severe alerts from IMD, and precision forecasts.</p>"),
    (r"<span>Sign In</span>", r"<span data-i18n=\"auth.welcome.signin\">Sign In</span>"),
    (r"<span>Create Account</span>", r"<span data-i18n=\"auth.welcome.signup\">Create Account</span>"),
    # Dashboard Weather
    (r"<h3 class=\"section-title\">\s*<span[^>]*>monitoring</span>\s*<span>Current Observations</span>", r"<h3 class=\"section-title\">\n              <span class=\"material-symbols-rounded\" style=\"color:var(--primary-blue);\">monitoring</span>\n              <span data-i18n=\"dashboard.current\">Current Observations</span>"),
    (r"<span class=\"stat-label\">Rain Probability</span>", r"<span class=\"stat-label\" data-i18n=\"dashboard.rain_prob\">Rain Probability</span>"),
    (r"<span class=\"stat-label\">Humidity</span>", r"<span class=\"stat-label\" data-i18n=\"dashboard.humidity\">Humidity</span>"),
    (r"<span class=\"stat-label\">Wind</span>", r"<span class=\"stat-label\" data-i18n=\"dashboard.wind\">Wind</span>"),
    (r"<span>Hourly Forecast</span>", r"<span data-i18n=\"dashboard.forecast\">Hourly Forecast</span>"),
    (r"<span>AI Advisories</span>", r"<span data-i18n=\"dashboard.advisories\">AI Advisories</span>"),
    # Chat Placeholder
    (r"id=\"chatInput\" class=\"chat-input\" placeholder=\"Ask about the weather\.\.\.\"", r"id=\"chatInput\" class=\"chat-input\" placeholder=\"Ask about the weather...\" data-i18n-placeholder=\"chat.placeholder\""),
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Applied i18n tags to index.html")
