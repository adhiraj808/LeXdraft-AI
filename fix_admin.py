with open('C:/Users/madhi/Desktop/Legal-Draft-System/frontend/src/pages/AdminPage.jsx', 'rb') as f:
    content = f.read()

end_pos = content.rfind(b'function ')
new_end = b'timeStr(iso) {\n  if (!iso) return "-"\n  try { return new Date(iso).toLocaleString() } catch { return iso }\n}\n\nexport default AdminPage\n'
content = content[:end_pos] + new_end

with open('C:/Users/madhi/Desktop/Legal-Draft-System/frontend/src/pages/AdminPage.jsx', 'wb') as f:
    f.write(content)

print('Fixed AdminPage.jsx')