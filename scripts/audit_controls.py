import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    index_html = f.read()

with open('frontend/developer.html', 'r', encoding='utf-8') as f:
    dev_html = f.read()

def find_interactive(html, name):
    buttons = re.findall(r'<button[^>]*>', html)
    role_buttons = re.findall(r'<[^>]+role=[\'\"]button[\'\"][^>]*>', html)
    nav_items = re.findall(r'<[^>]+class=[\'\"][^\'\"]*nav-item[^\'\"]*[\'\"][^>]*>', html)
    inputs = re.findall(r'<input[^>]*type=[\'\"](?:button|submit|checkbox|radio)[\'\"][^>]*>', html)
    selects = re.findall(r'<select[^>]*>', html)
    
    all_elements = buttons + role_buttons + nav_items + inputs + selects
    print(f"=== {name} ===")
    print(f"Total <button>: {len(buttons)}")
    print(f"Total role=button: {len(role_buttons)}")
    print(f"Total nav items: {len(nav_items)}")
    print(f"Total inputs (btn/chk/radio): {len(inputs)}")
    print(f"Total <select>: {len(selects)}")
    
    ids = []
    classes = set()
    for el in all_elements:
        m_id = re.search(r'id=[\'\"]([^\'\"]+)[\'\"]', el)
        if m_id:
            ids.append(m_id.group(1))
        m_cls = re.search(r'class=[\'\"]([^\'\"]+)[\'\"]', el)
        if m_cls:
            for c in m_cls.group(1).split():
                classes.add(c)
                
    return ids, sorted(classes)

index_ids, index_classes = find_interactive(index_html, 'INDEX.HTML')
dev_ids, dev_classes = find_interactive(dev_html, 'DEVELOPER.HTML')

with open('frontend/app.js', 'r', encoding='utf-8') as f:
    app_js = f.read()

template_buttons = re.findall(r'<button[^>]*class=[\'"]([^\'"]+)[\'"]', app_js)
template_classes = set()
for c in template_buttons:
    for item in c.split():
        template_classes.add(item)

print("\nApp.js template button classes:", sorted(template_classes))

# Check for async action buttons that take noticeable time
print("\nAsync action checks:")
for btn_name in ['sendBtn', 'geoBtn', 'mapMyLocationBtn', 'refreshBtn', 'profileSaveBtn', 'testNotificationBtn', 'loginSubmitBtn', 'signupSubmitBtn', 'btnDeclareAlert', 'btnUploadSubmit']:
    found_in_app = btn_name in app_js
    found_in_dev = btn_name in dev_html
    print(f"  {btn_name}: in app.js={found_in_app}, in dev.html={found_in_dev}")
