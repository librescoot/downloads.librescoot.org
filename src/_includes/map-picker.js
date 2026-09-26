function matchingRegion(address) {
    var country = (address.country_code || '').toUpperCase();
    var place = [address.state, address.region, address.county, address.city, address.town, address.municipality]
        .filter(Boolean).join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ß/g, 'ss');
    function has(name) { return place.includes(name); }
    if (country === 'NL') return 'netherlands';
    if (country === 'BE') return 'belgium';
    if (country === 'LU') return 'luxembourg';
    if (country === 'DE') {
        var states = [
            ['sachsen-anhalt', ['sachsen-anhalt', 'saxony-anhalt']],
            ['mecklenburg-vorpommern', ['mecklenburg-vorpommern', 'mecklenburg-western pomerania']],
            ['nordrhein-westfalen', ['nordrhein-westfalen', 'north rhine-westphalia']],
            ['baden-wuerttemberg', ['baden-wurttemberg', 'baden-wuerttemberg']],
            ['rheinland-pfalz', ['rheinland-pfalz', 'rhineland-palatinate']],
            ['schleswig-holstein', ['schleswig-holstein']],
            ['niedersachsen', ['niedersachsen', 'lower saxony']],
            ['berlin_brandenburg', ['brandenburg', 'berlin']],
            ['thueringen', ['thuringen', 'thuringia']],
            ['bayern', ['bayern', 'bavaria']],
            ['bremen', ['bremen']],
            ['hamburg', ['hamburg']],
            ['hessen', ['hessen', 'hesse']],
            ['saarland', ['saarland']],
            ['sachsen', ['sachsen', 'saxony']],
        ];
        for (var i = 0; i < states.length; i++) {
            if (states[i][1].some(has)) return states[i][0];
        }
    }
    if (country === 'FR') {
        if (has('ile-de-france')) return 'ile-de-france';
        if (['alsace', 'bas-rhin', 'haut-rhin'].some(has)) return 'alsace';
    }
    if (country === 'ES' && ['balear', 'balearic', 'mallorca', 'majorca'].some(has)) return 'islas-baleares';
    if (country === 'AT') {
        if (has('vienna') || has('wien')) return 'vienna';
        if (has('graz')) return 'graz';
    }
    if (country === 'IT' && ['piedmont', 'piemonte', 'liguria', 'lombard', 'lombardia', 'aosta'].some(has)) {
        return 'italy-nord-ovest';
    }
    return null;
}

function mapFragment(country, region) {
    return '#maps/' + country + (region ? '/' + region : '');
}

function parseMapFragment(hash) {
    var match = /^#maps\/([a-z]{2}|other)(?:\/([a-z0-9_-]+))?$/i.exec(hash);
    if (!match) return null;
    return { country: match[1].toLowerCase() === 'other' ? 'other' : match[1].toUpperCase(), region: match[2] ? match[2].toLowerCase() : null };
}

(function() {
    if (typeof document === 'undefined') return;
    var picker = document.querySelector('.map-picker');
    if (!picker) return;
    var browser = picker.closest('.map-browser');
    var search = picker.querySelector('#map-search');
    var clear = picker.querySelector('.map-search-clear');
    var status = picker.querySelector('.map-picker-status');
    var results = document.querySelector('.map-results');
    var prompt = results.querySelector('.map-results-prompt');
    var cards = Array.from(results.querySelectorAll('.map-region'));
    var countries = Array.from(picker.querySelectorAll('.map-country-panel'));
    var tabs = Array.from(picker.querySelectorAll('.map-country-tab'));
    var countrySelect = picker.querySelector('.map-country-select');
    var locate = picker.querySelector('.map-locate');
    var active = 0;
    var restoringFragment = false;

    function clearSelection() {
        cards.forEach(function(card) { card.hidden = true; });
        picker.querySelectorAll('.map-region-choice[aria-pressed="true"]').forEach(function(choice) {
            choice.setAttribute('aria-pressed', 'false');
        });
        prompt.hidden = false;
    }
    function normalize(text) {
        return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ß/g, 'ss');
    }
    function updateFragment(region) {
        if (restoringFragment) return;
        var fragment = mapFragment(countries[active].dataset.country, region);
        if (location.hash !== fragment) history.replaceState(history.state, '', fragment);
    }
    function filter() {
        clear.hidden = !search.value;
        var query = normalize(search.value).trim();
        var counts = countries.map(function(country, index) {
            var matchCountry = normalize(tabs[index].dataset.name).includes(query);
            var count = 0;
            country.querySelectorAll('.map-region-choice').forEach(function(choice) {
                choice.hidden = !matchCountry && !normalize(choice.dataset.name).includes(query);
                if (!choice.hidden) count++;
            });
            var badge = tabs[index].querySelector('.map-country-match-count');
            badge.hidden = !query || !count;
            badge.textContent = count;
            tabs[index].classList.toggle('map-tab-no-match', Boolean(query) && !count);
            return count;
        });
        picker.querySelector('.map-search-empty').hidden = Boolean(counts[active]);
        if (!counts[active]) prompt.hidden = true;
        return counts;
    }
    function selectCountry(index, focus) {
        if (index < 0) return;
        active = index;
        tabs.forEach(function(tab, i) {
            tab.setAttribute('aria-selected', i === index ? 'true' : 'false');
            tab.tabIndex = i === index ? 0 : -1;
            countries[i].hidden = i !== index;
        });
        countrySelect.value = countries[index].dataset.country;
        status.textContent = '';
        clearSelection();
        filter();
        var choices = countries[index].querySelectorAll('.map-region-choice');
        if (choices.length === 1 && !choices[0].hidden) select(choices[0]);
        else updateFragment();
        if (focus) tabs[index].focus();
    }
    function select(choice, fromLocation) {
        var index = countries.indexOf(choice.closest('.map-country-panel'));
        if (fromLocation) search.value = '';
        if (index !== active || fromLocation) selectCountry(index, false);
        else clearSelection();
        choice.setAttribute('aria-pressed', 'true');
        var card = cards.find(function(item) { return item.dataset.region === choice.dataset.region; });
        if (card) { card.hidden = false; prompt.hidden = true; }
        status.textContent = '';
        updateFragment(choice.dataset.region);
        if (fromLocation) {
            choice.focus({ preventScroll: true });
            var panel = choice.closest('.map-country-panels');
            var top = choice.getBoundingClientRect().top - panel.getBoundingClientRect().top;
            if (top < 0) panel.scrollTop += top;
            else if (top + choice.offsetHeight > panel.clientHeight) {
                panel.scrollTop += top + choice.offsetHeight - panel.clientHeight;
            }
        }
    }
    picker.hidden = false;
    browser.classList.add('is-interactive');
    results.classList.add('is-interactive');
    clearSelection();
    var countryColumn = picker.querySelector('.map-country-column');
    var regionPanel = picker.querySelector('.map-country-panels');
    function fitRegionPanel() {
        regionPanel.style.height = countryColumn.offsetHeight ? countryColumn.offsetHeight + 'px' : '';
    }
    fitRegionPanel();
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(fitRegionPanel).observe(countryColumn);
    window.addEventListener('resize', fitRegionPanel);
    tabs.forEach(function(tab, index) {
        tab.addEventListener('click', function() { selectCountry(index, false); });
        tab.addEventListener('keydown', function(event) {
            var next = event.key === 'ArrowDown' ? (index + 1) % tabs.length
                : event.key === 'ArrowUp' ? (index + tabs.length - 1) % tabs.length
                : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
            if (next >= 0) { event.preventDefault(); selectCountry(next, true); }
        });
    });
    countrySelect.addEventListener('change', function() {
        selectCountry(countries.findIndex(function(country) { return country.dataset.country === countrySelect.value; }), false);
    });
    search.addEventListener('input', function() {
        status.textContent = '';
        clearSelection();
        var counts = filter();
        if (!counts[active]) {
            var first = counts.findIndex(function(count) { return count > 0; });
            if (first >= 0) selectCountry(first, false);
            else updateFragment();
        } else updateFragment();
    });
    clear.addEventListener('click', function() {
        search.value = '';
        search.dispatchEvent(new Event('input'));
        search.focus();
    });
    picker.querySelectorAll('.map-region-choice:not(:disabled)').forEach(function(choice) {
        choice.addEventListener('click', function() { select(choice); });
    });
    var locateLabel = locate.getAttribute('aria-label');
    function finishLocate() {
        locate.disabled = false;
        locate.classList.remove('is-locating');
        locate.setAttribute('aria-label', locateLabel);
    }
    locate.addEventListener('click', function() {
        if (!navigator.geolocation) { status.textContent = picker.dataset.locationError; return; }
        locate.disabled = true;
        locate.classList.add('is-locating');
        locate.setAttribute('aria-label', picker.dataset.locating);
        status.textContent = '';
        navigator.geolocation.getCurrentPosition(async function(position) {
            try {
                var params = new URLSearchParams({
                    format: 'jsonv2', zoom: '10', addressdetails: '1', 'accept-language': 'en',
                    lat: position.coords.latitude.toFixed(5), lon: position.coords.longitude.toFixed(5),
                });
                var response = await fetch('https://nominatim.openstreetmap.org/reverse?' + params);
                if (!response.ok) throw new Error('Geocoding failed');
                var region = matchingRegion((await response.json()).address || {});
                var choice = Array.from(picker.querySelectorAll('.map-region-choice'))
                    .find(function(item) { return item.dataset.region === region && !item.disabled; });
                if (choice) select(choice, true);
                else status.textContent = picker.dataset.noMatch;
            } catch (_) {
                status.textContent = picker.dataset.locationError;
            } finally {
                finishLocate();
            }
        }, function() {
            status.textContent = picker.dataset.locationError;
            finishLocate();
        }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
    });
    function restoreFragment() {
        var target = parseMapFragment(location.hash);
        if (!target) return;
        var index = countries.findIndex(function(country) { return country.dataset.country === target.country; });
        if (index < 0) return;
        restoringFragment = true;
        try {
            search.value = '';
            selectCountry(index, false);
            if (target.region) {
                var choice = Array.from(countries[index].querySelectorAll('.map-region-choice'))
                    .find(function(item) { return item.dataset.region === target.region; });
                if (choice) select(choice);
            }
        } finally {
            restoringFragment = false;
        }
        document.getElementById('maps').scrollIntoView({ block: 'start' });
    }
    window.addEventListener('hashchange', restoreFragment);
    restoreFragment();
})();

if (typeof module !== 'undefined') module.exports = { matchingRegion: matchingRegion, mapFragment: mapFragment, parseMapFragment: parseMapFragment };
