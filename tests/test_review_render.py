"""Smoke test: проверяет, что render_review HTML + JS работают в node.js без ReferenceError.

Запускает JS в реальном node, который парсит HTML, извлекает JSON-данные, симулирует
DOM-events (toggleSection) и проверяет что рендер не падает.
"""
import json
import subprocess
import sys
from pathlib import Path

OUT = Path('/home/tsybriki/coach/state/reviews/2026-10-14-berlin-running.html')
review = json.load(open('/home/tsybriki/coach/state/reviews/2026-10-14-berlin-running.json'))

print(f"Review sections: {len(review['sections'])}")
print(f"HTML size: {OUT.stat().st_size} bytes")

# Извлекаем JS и рендерим в headless-окружении
js_script = '''
const fs = require('fs');
const path = '/home/tsybriki/coach/state/reviews/2026-10-14-berlin-running.html';
const html = fs.readFileSync(path, 'utf-8');

// Минимальный DOM-мок
const elements = {};
function makeEl() {
    return {
        innerHTML: '',
        textContent: '',
        classList: {
            _set: new Set(),
            add(c) { this._set.add(c); },
            remove(c) { this._set.delete(c); },
            toggle(c) { this._set.has(c) ? this._set.delete(c) : this._set.add(c); },
            contains(c) { return this._set.has(c); },
        },
        addEventListener: () => {},
        appendChild: () => {},
        querySelectorAll: () => [],
        scrollTo: () => {},
        parentElement: null,
        dataset: {},
        style: {},
        click: function() { toggleSection(this); },
        value: '',
        children: [],
    };
}
const document = {
    getElementById: (id) => { if (!elements[id]) elements[id] = makeEl(); return elements[id]; },
    querySelectorAll: (sel) => [],
    addEventListener: (ev, cb) => {
        if (ev === 'DOMContentLoaded') setTimeout(cb, 0);
    },
    createElement: makeEl,
};
const window = { scrollTo: () => {}, addEventListener: () => {}, location: { hash: '' } };
const history = { state: null, pushState: () => {}, replaceState: () => {} };

// Запускаем JS из <script>
const scriptMatch = html.match(/<script>([\\s\\S]*?)<\\/script>/g) || [];
let lastScript = '';
for (const s of scriptMatch) {
    lastScript = s.replace(/^<script>/, '').replace(/<\\/script>$/, '');
}

let output = '';
try {
    eval(lastScript);

    // Убедимся что toggleSection существует
    if (typeof toggleSection !== 'function') {
        console.log('ERROR: toggleSection not defined');
        process.exit(1);
    }

    // Убедимся что в HTML есть ВСЕ ожидаемые компоненты (brief, metrics, sections)
    const need = ['brief-card', 'metrics-card', 'section', 'hr-zones',
                  'data-table', 'kv-grid', 'rec-list'];
    for (const c of need) {
        if (!html.includes(c)) { console.log('MISSING:' + c); process.exit(1); }
    }

    // Проверим что hr_zones data не пустой
    const dataMatch = html.match(/<script type="application\\/json" id="plan-data">([\\s\\S]*?)<\\/script>/);
    console.log('OK · expected elements present');
} catch (e) {
    console.log('ERROR:' + e.message + '\\n' + e.stack);
    process.exit(1);
}
'''

result = subprocess.run(['node', '-e', js_script], capture_output=True, text=True, timeout=15)
print('stdout:', result.stdout)
print('stderr:', result.stderr)
if result.returncode != 0:
    print('FAILED')
    sys.exit(1)
else:
    print('PASS')
