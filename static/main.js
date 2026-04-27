/* ==========================================================================
   GridStack Dashboard Engine
   Full integration: init, layout persistence, aspect-ratio lock,
   live clock, sunrise/sunset
   ========================================================================== */

(function () {
    'use strict';

    // --- GridStack Init ---
    var gridEl = document.getElementById('dashboard-grid');
    if (!gridEl) return;

    var colWidth = gridEl.offsetWidth / 18;

    var grid = GridStack.init({
        column: 18,
        cellHeight: Math.round(colWidth),
        margin: 8,
        float: true,
        animate: true,
        resizable: {
            handles: 'se, s, e'
        },
        draggable: {
            handle: '.widget-item'
        }
    }, '#dashboard-grid');

    // Recalculate cell height whenever the grid element itself changes size.
    // ResizeObserver catches DevTools open/close that window 'resize' misses.
    var _rhTimer = null;
    var _ro = new ResizeObserver(function () {
        clearTimeout(_rhTimer);
        _rhTimer = setTimeout(function () {
            var w = gridEl.offsetWidth / 18;
            grid.cellHeight(Math.round(w));
        }, 60);
    });
    _ro.observe(gridEl);

    // --- Aspect Ratio Lock (1:1) ---
    var prevSizes = {};
    grid.on('resizestart', function (_event, el) {
        var node = el.gridstackNode;
        if (node && el.getAttribute('data-lock-ratio')) {
            prevSizes[node.id || el.getAttribute('gs-id')] = { w: node.w, h: node.h };
        }
    });
    grid.on('resizestop', function (_event, el) {
        if (!el.getAttribute('data-lock-ratio')) return;
        var node = el.gridstackNode;
        if (!node) return;
        var id = node.id || el.getAttribute('gs-id');
        var prev = prevSizes[id] || { w: node.w, h: node.h };
        var dw = Math.abs(node.w - prev.w);
        var dh = Math.abs(node.h - prev.h);
        var size = dw >= dh ? node.w : node.h;
        grid.update(el, { w: size, h: size });
        delete prevSizes[id];
    });

    // --- Layout Persistence ---
    var saveTimeout = null;

    function saveLayout(items) {
        if (!items || items.length === 0) return;
        var updates = items.map(function (item) {
            return {
                id: item.el.getAttribute('gs-id'),
                x: item.x, y: item.y,
                w: item.w, h: item.h
            };
        });
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(function () {
            fetch('/api/update_layout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.status !== 'success') console.warn('Layout save:', data);
            })
            .catch(function (err) { console.error('Layout sync error:', err); });
        }, 400);
    }

    grid.on('change', function (_event, items) { saveLayout(items); });

    // --- Lock / Unlock Toggle ---
    var LOCK_KEY = 'dashboard_locked';
    var locked = localStorage.getItem(LOCK_KEY) !== 'false'; // default locked

    var lockBtn  = document.getElementById('lock-toggle-btn');
    var lockIcon = document.getElementById('lock-icon');

    var LOCKED_SRC   = lockIcon.src; // already set to locked.png in template
    var UNLOCKED_SRC = LOCKED_SRC.replace('locked.png', 'unlocked.png');

    function applyLockState() {
        grid.setStatic(locked);
        lockIcon.src = locked ? LOCKED_SRC : UNLOCKED_SRC;
        lockBtn.title = locked ? 'Unlock layout' : 'Lock layout';
        lockBtn.classList.toggle('header-lock-btn--unlocked', !locked);
    }

    applyLockState();

    lockBtn.addEventListener('click', function () {
        locked = !locked;
        localStorage.setItem(LOCK_KEY, locked ? 'true' : 'false');
        applyLockState();
    });

})();
