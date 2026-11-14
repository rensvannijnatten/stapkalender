/* Wandeltochten — vanilla JS, geen build-stap. */
(function () {
  "use strict";

  // ---------- Hulpjes ----------
  var WD_SHORT = ["zo", "ma", "di", "wo", "do", "vr", "za"];
  var WD_LONG = ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"];
  var MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"];
  var MONTHS_SHORT = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  var PROMOTER_LABEL = {
    "KWbN": "Wandel.nl (KWbN)",
    "Wandelsport Vlaanderen": "Wandel.be (Wandelsport Vlaanderen)",
    "Adeps": "Adeps (Points Verts)"
  };
  var CHANGE_KEY = "wt.home";
  var KM_KEY = "wt.km";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function iso(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function parseIso(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function addDays(s, n) { var d = parseIso(s); d.setDate(d.getDate() + n); return iso(d); }
  function todayIso() { return iso(new Date()); }

  function storageGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function storageSet(k, v) { try { if (v == null) window.localStorage.removeItem(k); else window.localStorage.setItem(k, v); } catch (e) { /* privé-modus */ } }

  function haversineKm(lat1, lon1, lat2, lon2) {
    var R = 6371, toRad = Math.PI / 180;
    var dLat = (lat2 - lat1) * toRad, dLon = (lon2 - lon1) * toRad;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function fmtShort(s) { var d = parseIso(s); return cap(WD_SHORT[d.getDay()]) + " " + d.getDate() + " " + MONTHS_SHORT[d.getMonth()]; }
  function fmtLong(s) { var d = parseIso(s); return WD_LONG[d.getDay()] + " " + d.getDate() + " " + MONTHS[d.getMonth()]; }
  function fmtMid(s) { var d = parseIso(s); return WD_SHORT[d.getDay()] + " " + d.getDate() + " " + MONTHS[d.getMonth()]; }
  function plural(n) { return n + (n === 1 ? " tocht" : " tochten"); }

  function rangeText(dist) {
    if (!dist || !dist.length) return "";
    var f = function (x) { return String(x).replace(".", ","); };
    if (dist.length === 1) return f(dist[0]) + " km";
    return f(dist[0]) + " tot " + f(dist[dist.length - 1]) + " km";
  }
  function kmText(t) { return t.km == null ? "? km" : t.km + " km"; }
  function telHref(p) { return "tel:" + String(p).replace(/\(0\)/g, "").replace(/[^\d+]/g, ""); }
  function byDistance(a, b) {
    if (a.km == null && b.km == null) return a.city.localeCompare(b.city);
    if (a.km == null) return 1;
    if (b.km == null) return -1;
    return a.km - b.km || a.city.localeCompare(b.city);
  }
  function landTag(t) { return '<span class="tag" aria-label="' + (t.land === "NL" ? "Nederland" : "België") + '">' + esc(t.land) + "</span>"; }
  function cancelTag(t) { return t.cancelled ? ' <span class="tag tag--cancel">Afgelast</span>' : ""; }

  // ---------- Toestand ----------
  var state = {
    config: null,
    meta: null,
    all: [],
    byId: {},
    byDate: {},
    dates: [],
    home: null,
    km: 30,
    day: null,
    calMonth: null,
    navigated: false,
    maps: {},
    allRendered: 0
  };

  function loadHome() {
    var raw = storageGet(CHANGE_KEY);
    if (raw) {
      try {
        var h = JSON.parse(raw);
        if (h && typeof h.lat === "number" && typeof h.lon === "number" && h.name) return h;
      } catch (e) { /* negeren */ }
    }
    return state.config.home;
  }

  function computeDistances() {
    var h = state.home;
    state.all.forEach(function (t) {
      t.km = (t.lat == null || t.lon == null) ? null : Math.round(haversineKm(h.lat, h.lon, t.lat, t.lon));
    });
    $all(".js-home-name").forEach(function (el) { el.textContent = h.name; });
  }

  function indexData(json) {
    state.meta = json;
    var today = todayIso();
    state.all = (json.tochten || []).filter(function (t) { return t.date >= today; });
    state.byId = {};
    state.byDate = {};
    state.all.forEach(function (t) {
      state.byId[t.id] = t;
      (state.byDate[t.date] = state.byDate[t.date] || []).push(t);
    });
    var start = today, end = json.until || today;
    var lastData = state.all.length ? state.all[state.all.length - 1].date : today;
    if (lastData > end) end = lastData;
    state.dates = [];
    for (var d = start; d <= end; d = addDays(d, 1)) state.dates.push(d);
  }

  function dayItems(date, maxKm) {
    var items = (state.byDate[date] || []).filter(function (t) {
      return !maxKm || (t.km != null && t.km <= maxKm);
    });
    return items.slice().sort(byDistance);
  }

  // ---------- Kaarten ----------
  function makeMap(id) {
    var map = L.map(id, { zoomControl: true, attributionControl: true, tap: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-bijdragers</a>'
    }).addTo(map);
    map.attributionControl.setPrefix(false);
    var homeLayer = L.layerGroup().addTo(map);
    return { map: map, home: homeLayer, layer: null };
  }

  function drawHome(m) {
    m.home.clearLayers();
    var h = state.home;
    L.marker([h.lat, h.lon], {
      icon: L.divIcon({ className: "", html: '<div class="home-pin"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }),
      keyboard: false,
      zIndexOffset: 1000,
      title: "Thuis"
    }).bindTooltip("Thuis", { permanent: true, direction: "right", offset: [12, 0], className: "home-label" }).addTo(m.home);
  }

  function popupHtml(t, prefix) {
    return '<strong>' + esc(prefix || "") + esc(t.city) + "</strong>" + (t.cancelled ? " (afgelast)" : "") +
      "<br>" + esc(t.name) + "<br>" + kmText(t) +
      '<br><a href="#tocht-' + esc(t.id) + '">Bekijk tocht</a>';
  }

  function ensureMap(key, id) {
    if (!state.maps[key]) state.maps[key] = makeMap(id);
    var m = state.maps[key];
    setTimeout(function () { m.map.invalidateSize(); }, 0);
    return m;
  }

  function fit(m, points) {
    var h = state.home;
    var pts = points.concat([[h.lat, h.lon]]);
    if (pts.length === 1) { m.map.setView(pts[0], 10); return; }
    m.map.fitBounds(L.latLngBounds(pts), { padding: [36, 36], maxZoom: 12 });
  }

  // ---------- Per dag ----------
  function renderDag() {
    if (!state.day || state.dates.indexOf(state.day) < 0) state.day = state.dates[0];
    var day = state.day;
    var near = state.config.nearKm || 30;

    // segmentknop
    $all(".segmented button").forEach(function (b) {
      b.setAttribute("aria-checked", String(+b.dataset.km === state.km));
    });

    // dagenstrook
    var strip = $("#day-strip");
    strip.innerHTML = state.dates.map(function (d) {
      var dd = parseIso(d), n = dayItems(d, state.km).length;
      return '<button type="button" role="tab" class="day-btn' + (n ? "" : " is-empty") + '" data-date="' + d + '" aria-selected="' + (d === day) + '"' +
        ' aria-label="' + esc(fmtLong(d) + ", " + plural(n)) + '">' +
        '<span class="wd">' + (d === todayIso() ? "Vandaag" : cap(WD_SHORT[dd.getDay()])) + "</span>" +
        '<span class="dm">' + dd.getDate() + " " + MONTHS_SHORT[dd.getMonth()] + "</span>" +
        '<span class="n">' + (n ? n : "–") + "</span></button>";
    }).join("");
    var sel = strip.querySelector('[aria-selected="true"]');
    if (sel) strip.scrollLeft = Math.max(0, sel.offsetLeft - strip.clientWidth / 2 + sel.clientWidth / 2);

    var items = dayItems(day, state.km);
    $("#day-summary").textContent = fmtShort(day) + " · " + plural(items.length);

    var list = $("#day-list");
    if (!items.length) {
      var total = (state.byDate[day] || []).length;
      list.innerHTML = '<li class="empty">' + (total
        ? "Geen tochten binnen " + state.km + " km. Kies ‘Alles’ om alle " + plural(total) + " te zien."
        : "Geen tochten op deze dag.") + "</li>";
    } else {
      list.innerHTML = items.map(function (t, i) {
        var far = t.km == null || t.km > near;
        return '<li><a class="card' + (t.cancelled ? " is-cancelled" : "") + '" href="#tocht-' + esc(t.id) + '">' +
          '<span class="num' + (far ? " num--far" : "") + '" aria-hidden="true">' + (i + 1) + "</span>" +
          '<span class="card-main"><span class="card-title"><span class="city">' + esc(t.city) + "</span> " + landTag(t) + cancelTag(t) + "</span>" +
          '<span class="card-sub">' + esc(t.name) + (t.distances.length ? " · " + rangeText(t.distances) : "") + "</span></span>" +
          '<span class="card-dist">' + kmText(t) + "</span></a></li>";
      }).join("");
    }

    // kaart
    var m = ensureMap("dag", "map-dag");
    drawHome(m);
    if (m.layer) m.map.removeLayer(m.layer);
    m.layer = L.layerGroup();
    var pts = [];
    items.forEach(function (t, i) {
      if (t.lat == null) return;
      var far = t.km > near;
      L.marker([t.lat, t.lon], {
        icon: L.divIcon({
          className: "",
          html: '<div class="pin' + (far ? " pin--far" : "") + (t.cancelled ? " pin--cancelled" : "") + '">' + (i + 1) + "</div>",
          iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -14]
        }),
        title: (i + 1) + ". " + t.city,
        zIndexOffset: far ? 0 : 500
      }).bindPopup(popupHtml(t, (i + 1) + ". ")).addTo(m.layer);
      pts.push([t.lat, t.lon]);
    });
    m.layer.addTo(m.map);
    fit(m, pts);
  }

  // ---------- Alle tochten ----------
  var allObserver = null;

  function allHeader(d, n) {
    var today = todayIso();
    var label = d === today ? "Vandaag · " + fmtMid(d) : d === addDays(today, 1) ? "Morgen · " + fmtMid(d) : cap(fmtMid(d));
    return '<h2 class="all-day-head"><span class="dot' + (d === today ? " dot--today" : "") + '" aria-hidden="true"></span>' +
      "<span>" + esc(label) + '</span><span class="count">' + plural(n) + "</span></h2>";
  }

  function renderAllChunk(count) {
    var box = $("#all-list");
    var days = state.dates.filter(function (d) { return (state.byDate[d] || []).length; });
    var end = Math.min(days.length, state.allRendered + count);
    var html = "";
    for (var i = state.allRendered; i < end; i++) {
      var d = days[i];
      var items = dayItems(d, 0);
      html += '<section class="all-day">' + allHeader(d, items.length) + '<ul class="rows">' +
        items.map(function (t) {
          return '<li><a class="row' + (t.cancelled ? " is-cancelled" : "") + '" href="#tocht-' + esc(t.id) + '">' +
            '<span><span class="row-title"><span class="city">' + esc(t.city) + "</span> " + landTag(t) + cancelTag(t) + "</span>" +
            '<span class="row-sub card-sub">' + esc(t.name) + "</span></span>" +
            '<span class="row-dist">' + kmText(t) + "</span></a></li>";
        }).join("") + "</ul></section>";
    }
    box.insertAdjacentHTML("beforeend", html);
    state.allRendered = end;
    if (end >= days.length && allObserver) { allObserver.disconnect(); allObserver = null; }
    if (!days.length) box.innerHTML = '<p class="empty">Geen tochten gevonden.</p>';
  }

  function renderAlle(rebuild) {
    var m = ensureMap("alle", "map-alle");
    drawHome(m);
    if (!rebuild && state.allRendered) return;

    $("#all-list").innerHTML = "";
    state.allRendered = 0;
    renderAllChunk(4);
    if (allObserver) allObserver.disconnect();
    if ("IntersectionObserver" in window) {
      allObserver = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) renderAllChunk(4);
      }, { rootMargin: "800px 0px" });
      allObserver.observe($("#all-more"));
    } else {
      renderAllChunk(1000);
    }

    if (m.layer) m.map.removeLayer(m.layer);
    m.layer = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45, spiderfyOnMaxZoom: true });
    var today = todayIso(), pts = [];
    state.all.forEach(function (t) {
      if (t.lat == null) return;
      L.marker([t.lat, t.lon], {
        icon: L.divIcon({ className: "", html: '<div class="dot' + (t.date === today ? " dot--today" : "") + '"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }),
        title: t.city + ", " + fmtShort(t.date)
      }).bindPopup('<strong>' + esc(fmtShort(t.date)) + "</strong><br>" + popupHtml(t)).addTo(m.layer);
      if (t.km != null && t.km <= 60) pts.push([t.lat, t.lon]);
    });
    m.layer.addTo(m.map);
    fit(m, pts);
  }

  // ---------- Kalender ----------
  function renderKalender() {
    var first = state.dates[0], last = state.dates[state.dates.length - 1];
    var minM = first.slice(0, 7), maxM = last.slice(0, 7);
    if (!state.calMonth || state.calMonth < minM) state.calMonth = minM;
    if (state.calMonth > maxM) state.calMonth = maxM;
    var y = +state.calMonth.slice(0, 4), mo = +state.calMonth.slice(5, 7) - 1;
    var km = state.config.calendarKm || 40;
    $all(".js-cal-km").forEach(function (el) { el.textContent = km; });
    $("#cal-month").textContent = MONTHS[mo] + " " + y;
    $("#cal-prev").disabled = state.calMonth <= minM;
    $("#cal-next").disabled = state.calMonth >= maxM;

    var start = new Date(y, mo, 1);
    var offset = (start.getDay() + 6) % 7; // maandag = 0
    var daysInMonth = new Date(y, mo + 1, 0).getDate();
    var today = todayIso();
    var html = "";
    for (var i = 0; i < offset; i++) html += '<span class="cal-day blank"></span>';
    for (var dnum = 1; dnum <= daysInMonth; dnum++) {
      var d = iso(new Date(y, mo, dnum));
      var inRange = d >= first && d <= last;
      var n = inRange ? dayItems(d, km).filter(function (t) { return !t.cancelled; }).length : 0;
      var cls = "cal-day" + (n ? " has" : "") + (d === today ? " is-today" : "") + (inRange ? "" : " is-out");
      var label = fmtLong(d) + (inRange ? ", " + (n ? plural(n) + " binnen " + km + " km" : "geen tochten binnen " + km + " km") : "");
      var inner = '<span class="d">' + dnum + "</span>" + (n ? '<span class="c">' + plural(n) + "</span>" : "");
      html += inRange
        ? '<a class="' + cls + '" href="#dag/' + d + '" aria-label="' + esc(label) + '">' + inner + "</a>"
        : '<span class="' + cls + '" aria-label="' + esc(label) + '">' + inner + "</span>";
    }
    $("#cal-grid").innerHTML = html;
  }

  function shiftMonth(delta) {
    var y = +state.calMonth.slice(0, 4), mo = +state.calMonth.slice(5, 7) - 1 + delta;
    var d = new Date(y, mo, 1);
    location.hash = "#kalender/" + d.getFullYear() + "-" + pad(d.getMonth() + 1);
  }

  // ---------- Detail ----------
  var ICON_BACK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
  var ICON_ROUTE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l18-8-8 18-2-8-8-2z"/></svg>';
  var ICON_PHONE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>';
  var ICON_WEB = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>';

  function renderTocht(id) {
    var t = state.byId[id];
    var box = $("#tocht");
    var back = '<button type="button" class="back js-back">' + ICON_BACK + "Terug</button>";
    if (!t) {
      box.innerHTML = back + '<p class="status-msg">Deze tocht staat niet (meer) in de lijst.</p>';
      return;
    }
    var website = t.website || t.source_url;
    var html = back;
    if (t.cancelled) html += '<p class="notice notice--cancel" role="alert">Afgelast — deze tocht gaat niet door.</p>';
    if (t.warning) html += '<p class="notice" role="note">Let op: ' + esc(t.warning) + "</p>";
    html += '<p class="t-meta">' + esc(cap(fmtLong(t.date))) + " · " + esc(PROMOTER_LABEL[t.promoter] || t.promoter) + "</p>";
    html += '<h1 class="t-name" id="t-name">' + esc(t.name) + (t.cancelled ? ' <span class="tag tag--cancel">Afgelast</span>' : "") + "</h1>";
    html += '<p class="t-where"><strong>' + esc(t.city) + "</strong> " + landTag(t) +
      (t.km != null ? " · " + t.km + " km hemelsbreed" : "") + "</p>";
    if (t.lat != null) {
      html += '<a class="btn btn--primary btn--block t-route" href="https://www.google.com/maps/dir/?api=1&amp;destination=' +
        t.lat + "," + t.lon + '" target="_blank" rel="noopener">' + ICON_ROUTE + "Route naar de start</a>";
    }
    html += '<section class="block" aria-label="Start"><dl class="kv">' +
      "<div><dt>Startplaats</dt><dd>" + esc(t.address || t.city) + "</dd></div>" +
      "<div><dt>Starttijd</dt><dd>" + (t.start_time ? esc(t.start_time) : "Niet opgegeven, zie website") + "</dd></div>" +
      "<div><dt>Afstanden</dt><dd>" + (t.distances.length
        ? '<div class="chips">' + t.distances.map(function (d) { return '<span class="chip">' + String(d).replace(".", ",") + " km</span>"; }).join("") + "</div>"
        : "Niet opgegeven") + "</dd></div>" +
      "</dl></section>";
    html += '<section class="block"><h2>Over deze tocht</h2>' +
      (t.description ? '<p class="t-desc">' + esc(t.description) + "</p>" : '<p class="t-desc">Geen beschrijving. Kijk op de website voor meer informatie.</p>') +
      (t.organizer ? '<p class="t-org">Organisator: ' + esc(t.organizer) + "</p>" : "") +
      '<div class="t-actions">' +
      (t.phone1 ? '<a class="btn btn--secondary" href="' + esc(telHref(t.phone1)) + '">' + ICON_PHONE + "Bellen</a>" : "") +
      '<a class="btn btn--secondary" href="' + esc(website) + '" target="_blank" rel="noopener">' + ICON_WEB + "Website</a>" +
      "</div>" +
      (t.phone2 ? '<p class="t-source">Tweede nummer: <a href="' + esc(telHref(t.phone2)) + '">' + esc(t.phone2) + "</a></p>" : "") +
      (t.email ? '<p class="t-source">E-mail: <a href="mailto:' + esc(t.email) + '">' + esc(t.email) + "</a></p>" : "") +
      "</section>";
    html += '<p class="t-source">Bron: <a href="' + esc(t.source_url) + '" target="_blank" rel="noopener">' + esc(PROMOTER_LABEL[t.promoter] || t.promoter) + "</a>" +
      (t.promoter === "Adeps" ? " · open data via ODWB (CC BY)" : "") + "</p>";
    box.innerHTML = html;
    window.scrollTo(0, 0);
  }

  // ---------- Bronvermelding ----------
  function renderSources() {
    var m = state.meta || {};
    var txt = "";
    if (m.generated) {
      var g = new Date(m.generated);
      if (!isNaN(g)) txt += "Bijgewerkt: " + fmtShort(iso(g)) + " " + pad(g.getHours()) + ":" + pad(g.getMinutes()) + ". ";
    }
    txt += 'Gegevens: <a href="https://www.wandel.be/wandelkalender/">wandel.be</a>, ' +
      '<a href="https://www.wandel.nl/evenementen/">wandel.nl</a> en Adeps ' +
      '(<a href="https://www.odwb.be/explore/dataset/points-verts-de-ladeps/">open data ODWB</a>, CC BY). ' +
      "Afstanden zijn hemelsbreed.";
    var failed = Object.keys(m.sources || {}).filter(function (k) { return !m.sources[k].ok; });
    if (failed.length) txt += " Let op: niet alle bronnen konden de laatste keer worden bijgewerkt.";
    $all(".js-sources").forEach(function (el) { el.innerHTML = txt; });
  }

  // ---------- Router ----------
  function show(view) {
    $all(".view").forEach(function (v) { v.hidden = v.id !== "view-" + view; });
    var tab = view === "tocht" ? null : view;
    $all(".tabbar a").forEach(function (a) {
      if (a.dataset.tab === tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }

  function route() {
    var h = decodeURIComponent(location.hash.replace(/^#/, ""));
    var m;
    if ((m = /^tocht-(.+)$/.exec(h))) {
      show("tocht");
      renderTocht(m[1]);
      return;
    }
    if ((m = /^kalender(?:\/(\d{4}-\d{2}))?$/.exec(h))) {
      if (m[1]) state.calMonth = m[1];
      show("kalender");
      renderKalender();
      window.scrollTo(0, 0);
      return;
    }
    if (h === "alle") {
      show("alle");
      renderAlle(false);
      return;
    }
    m = /^dag(?:\/(\d{4}-\d{2}-\d{2}))?$/.exec(h);
    if (m && m[1]) state.day = m[1];
    show("dag");
    renderDag();
  }

  // ---------- Thuisadres ----------
  function setHome(h) {
    state.home = h;
    storageSet(CHANGE_KEY, h === state.config.home ? null : JSON.stringify(h));
    computeDistances();
    state.allRendered = 0;
    if (state.maps.alle && state.maps.alle.layer) { state.maps.alle.map.removeLayer(state.maps.alle.layer); state.maps.alle.layer = null; }
    route();
    if (location.hash === "#alle") renderAlle(true);
  }

  function initHomeDialog() {
    var dlg = $("#home-dialog");
    var msg = $("#home-msg");
    $all(".js-default-home").forEach(function (el) { el.textContent = state.config.home.name; });
    $all(".js-home-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        msg.textContent = "";
        if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
      });
    });
    $("#home-reset").addEventListener("click", function () {
      setHome(state.config.home);
      msg.textContent = "Afstanden worden weer gemeten vanaf " + state.config.home.name + ".";
    });
    function search() {
      var q = $("#home-input").value.trim();
      if (!q) return;
      msg.textContent = "Zoeken…";
      var url = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&countrycodes=nl,be&q=" + encodeURIComponent(q);
      fetch(url, { headers: { "Accept-Language": "nl" } }).then(function (r) { return r.json(); }).then(function (res) {
        if (!res.length) { msg.textContent = "Niets gevonden. Probeer een plaatsnaam."; return; }
        msg.innerHTML = '<span>Kies:</span><span class="sheet-choices">' + res.map(function (r, i) {
          return '<button type="button" class="btn btn--secondary btn--block" data-i="' + i + '">' + esc(r.display_name.split(",").slice(0, 3).join(",")) + "</button>";
        }).join("") + "</span>";
        $all("button[data-i]", msg).forEach(function (b) {
          b.addEventListener("click", function () {
            var r = res[+b.dataset.i];
            setHome({ name: r.name || r.display_name.split(",")[0], lat: +r.lat, lon: +r.lon });
            msg.textContent = "Afstanden worden nu gemeten vanaf " + state.home.name + ".";
          });
        });
      }).catch(function () { msg.textContent = "Zoeken lukt nu niet. Controleer de internetverbinding."; });
    }
    $("#home-search").addEventListener("click", search);
    $("#home-input").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); search(); } });
  }

  // ---------- Start ----------
  function bindEvents() {
    $("#day-strip").addEventListener("click", function (e) {
      var b = e.target.closest(".day-btn");
      if (b) location.replace("#dag/" + b.dataset.date);
    });
    $all(".segmented button").forEach(function (b) {
      b.addEventListener("click", function () {
        state.km = +b.dataset.km;
        storageSet(KM_KEY, String(state.km));
        renderDag();
      });
    });
    $("#cal-prev").addEventListener("click", function () { shiftMonth(-1); });
    $("#cal-next").addEventListener("click", function () { shiftMonth(1); });
    document.addEventListener("click", function (e) {
      if (e.target.closest(".js-back")) {
        if (state.navigated) history.back();
        else location.hash = "#dag" + (state.day ? "/" + state.day : "");
      }
    });
    window.addEventListener("hashchange", function () { state.navigated = true; route(); });
  }

  function fail(msg) {
    var el = $("#loading");
    el.hidden = false;
    el.textContent = msg;
  }

  function start() {
    Promise.all([
      fetch("config.json", { cache: "no-cache" }).then(function (r) { return r.json(); }),
      fetch("data/tochten.json", { cache: "no-cache" }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
    ]).then(function (res) {
      state.config = res[0];
      var savedKm = storageGet(KM_KEY);
      state.km = savedKm !== null && ["0", "30", "60"].indexOf(savedKm) >= 0 ? +savedKm : (state.config.nearKm || 30);
      state.home = loadHome();
      indexData(res[1]);
      computeDistances();
      renderSources();
      initHomeDialog();
      bindEvents();
      $("#loading").hidden = true;
      if (!state.dates.length) { fail("Er zijn nu geen tochten bekend."); return; }
      route();
    }).catch(function (e) {
      fail("De tochten konden niet geladen worden. Probeer het later opnieuw.");
      if (window.console) console.error(e);
    });
  }

  if (typeof L === "undefined") {
    fail("De kaart kon niet geladen worden. Controleer de internetverbinding en probeer opnieuw.");
  } else {
    start();
  }
})();
