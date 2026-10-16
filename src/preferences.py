"""Portable preferences, validated on read and saved atomically."""
import json
from pathlib import Path

DEFAULTS = dict(language='zh', mode='window', poop_mode='food', meals=3,
                chance=40, minutes=5, username='团团', breed='calico',
                sound=True, volume=70, sleep_minutes=5, standoff_min=45)
values = DEFAULTS.copy()
path = Path('settings.json')

def load():
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return
        for key, choices in [('language', ('zh', 'en')), ('mode', ('window', 'desktop', 'top')),
                             ('poop_mode', ('food', 'timer', 'off')),
                             ('breed', ('calico', 'black', 'white', 'tabby', 'orange', 'siamese', 'ragdoll'))]:
            if raw.get(key) in choices:
                values[key] = raw[key]
        for key in ('sound',):
            if type(raw.get(key)) is bool:
                values[key] = raw[key]
        for key, low, high in [('meals', 1, 100), ('chance', 0, 100), ('minutes', 1, 1440),
                               ('volume', 0, 100), ('sleep_minutes', 1, 240), ('standoff_min', 5, 600)]:
            value = raw.get(key)
            if type(value) is int:
                values[key] = max(low, min(high, value))
        if isinstance(raw.get('username'), str) and raw['username'].strip():
            values['username'] = raw['username'].strip()[:32]
    except (OSError, ValueError):
        pass

def save():
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def tr(zh, en):
    return zh if values['language'] == 'zh' else en
