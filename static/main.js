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

    var colWidth = gridEl.offsetWidth / 12;

    var grid = GridStack.init({
        column: 12,
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

    // Recalculate on window resize so cells stay square
    window.addEventListener('resize', function () {
        var w = gridEl.offsetWidth / 12;
        grid.cellHeight(Math.round(w));
    });

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


    // =================================================================
    // LIVE CLOCK — updates every second for any widget-clock
    // =================================================================

    function updateClocks() {
        var clocks = document.querySelectorAll('.widget-clock[data-timezone]');
        var localNow = new Date();

        clocks.forEach(function (el) {
            var tz = el.getAttribute('data-timezone');
            try {
                // Get time in the target timezone
                var opts = { hour: 'numeric', minute: '2-digit', hour12: false, timeZone: tz };
                var parts = new Intl.DateTimeFormat('en-GB', opts).formatToParts(localNow);
                var h = '', m = '';
                parts.forEach(function (p) {
                    if (p.type === 'hour') h = p.value;
                    if (p.type === 'minute') m = p.value;
                });
                // Remove leading zero from hour
                if (h.charAt(0) === '0') h = h.substring(1);

                var hoursEl = el.querySelector('.clock-hours');
                var minsEl = el.querySelector('.clock-minutes');
                if (hoursEl) hoursEl.textContent = h;
                if (minsEl) minsEl.textContent = m;

                // Calculate offset from local time
                var localOffset = localNow.getTimezoneOffset(); // in minutes, inverted
                var tzTime = new Date(localNow.toLocaleString('en-US', { timeZone: tz }));
                var diff = Math.round((tzTime - localNow) / 60000 + localOffset); // diff in minutes
                var diffHours = Math.round(diff / 60);
                var offsetEl = el.querySelector('.clock-offset');
                if (offsetEl) {
                    if (diffHours === 0) {
                        offsetEl.textContent = 'Local';
                    } else {
                        offsetEl.textContent = (diffHours > 0 ? '+' : '') + diffHours;
                    }
                }
            } catch (e) {
                // Invalid timezone — leave as-is
            }
        });
    }

    updateClocks();
    setInterval(updateClocks, 1000);


    // =================================================================
    // LIVE SUNRISE/SUNSET — fetches from sunrise-sunset.org API
    // =================================================================

    function updateSunrise() {
        var widgets = document.querySelectorAll('.widget-sunrise[data-lat][data-lng]');

        widgets.forEach(function (el) {
            var lat = el.getAttribute('data-lat');
            var lng = el.getAttribute('data-lng');

            fetch('https://api.sunrise-sunset.org/json?lat=' + lat + '&lng=' + lng + '&formatted=0')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.status !== 'OK') return;

                    var sunrise = new Date(data.results.sunrise);
                    var sunset = new Date(data.results.sunset);
                    var now = new Date();

                    // Format time
                    function fmt(d) {
                        var h = d.getHours();
                        var m = d.getMinutes();
                        var ampm = h >= 12 ? 'PM' : 'AM';
                        h = h % 12 || 12;
                        return { time: h + ':' + (m < 10 ? '0' : '') + m, ampm: ampm };
                    }

                    var sr = fmt(sunrise);
                    var ss = fmt(sunset);

                    var timeVal = el.querySelector('.sunrise-time-val');
                    var ampmEl = el.querySelector('.sunrise-ampm');
                    var sunsetEl = el.querySelector('.sunrise-sunset');

                    if (timeVal) timeVal.textContent = sr.time;
                    if (ampmEl) ampmEl.textContent = sr.ampm;
                    if (sunsetEl) sunsetEl.textContent = 'Sunset: ' + ss.time + ss.ampm;

                    // Position sun dot on the arc based on current time
                    var sunDot = el.querySelector('.sun-dot');
                    if (sunDot) {
                        var srMs = sunrise.getTime();
                        var ssMs = sunset.getTime();
                        var nowMs = now.getTime();
                        var progress = 0;

                        if (nowMs < srMs) {
                            progress = 0; // before sunrise
                        } else if (nowMs > ssMs) {
                            progress = 1; // after sunset
                        } else {
                            progress = (nowMs - srMs) / (ssMs - srMs);
                        }

                        // Map progress to angle on the elliptical arc
                        // Arc: center (50,30), rx=40, ry=28
                        // angle goes from PI (left) to 0 (right)
                        var angle = Math.PI * (1 - progress);
                        var cx = 50 + 40 * Math.cos(angle);
                        var cy = 30 - 28 * Math.sin(angle);

                        sunDot.setAttribute('cx', cx.toFixed(1));
                        sunDot.setAttribute('cy', cy.toFixed(1));
                    }
                })
                .catch(function (err) {
                    console.error('Sunrise API error:', err);
                });
        });
    }

    updateSunrise();
    // Refresh sunrise data every 10 minutes
    setInterval(updateSunrise, 600000);

})();
