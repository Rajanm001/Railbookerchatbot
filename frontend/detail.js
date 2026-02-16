/**
 * Railbookers - Package Detail Page Controller
 * Renders the View Itinerary detail page matching production layout.
 */

const API_BASE = (() => {
  const origin = window.location.origin;
  if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
    return 'http://localhost:8890/api/v1';
  }
  return '/api/v1';
})();

async function loadPackageDetail() {
  const params = new URLSearchParams(window.location.search);
  const packageId = params.get('id');

  if (!packageId) { showError(); return; }

  try {
    const res = await fetch(`${API_BASE}/recommendations/package/${encodeURIComponent(packageId)}`, {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) { showError(); return; }
    const data = await res.json();
    if (!data.package) { showError(); return; }
    renderDetail(data.package);
  } catch (e) {
    console.error('Failed to load package:', e);
    showError();
  }
}

function showError() {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('error-state').style.display = 'block';
}

function escapeHtml(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, c => map[c]);
}

/** Decode HTML entities like &#39; &amp; etc */
function decodeEntities(str) {
  if (!str) return '';
  const ta = document.createElement('textarea');
  ta.innerHTML = str;
  return ta.value;
}

/** Safely extract text from raw HTML, stripping tags but keeping text */
function htmlToText(html) {
  if (!html) return '';
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  doc.querySelectorAll('script,style,iframe,object,embed,form').forEach(n => n.remove());
  return doc.body.textContent || '';
}

function renderDetail(pkg) {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('detail-content').style.display = 'block';

  // === HEADER ===
  const title = pkg.name || pkg.external_name || 'Rail Vacation';
  document.getElementById('pkg-title').textContent = title;
  document.title = 'Railbookers | ' + title;

  // Header route pills
  const routeCities = buildRouteCities(pkg);
  const routeEl = document.getElementById('pkg-route-header');
  if (routeCities.length > 0) {
    routeEl.innerHTML = routeCities.map(function(city, i) {
      const pill = '<span class="dt-hdr-city">' + escapeHtml(city) + '</span>';
      return i < routeCities.length - 1
        ? pill + '<span class="dt-hdr-arrow">\u27F6</span>'
        : pill;
    }).join(' ');
  }

  // === SALES TIPS ===
  renderSalesTips(pkg.raw_sales_tips || pkg.sales_tips || '');

  // === PROMO BANNER ===
  if (pkg.promo_savings && pkg.promo_savings > 0) {
    var banner = document.getElementById('promo-banner');
    banner.style.display = 'flex';
    document.getElementById('promo-amount').textContent = pkg.promo_savings;
    var countries = pkg.countries_display || '';
    document.getElementById('promo-title').textContent = countries
      ? 'Holidays to ' + countries
      : 'Save on this rail vacation';
    document.getElementById('promo-desc').textContent = countries
      ? 'For a limited time only, save \u00A3' + pkg.promo_savings + ' per couple on our ' + countries + ' holidays inclusive of 3 nights or more.'
      : 'For a limited time only, save \u00A3' + pkg.promo_savings + ' per couple on this rail vacation.';
  }

  // === DESCRIPTION ===
  var rawDesc = pkg.raw_description || pkg.description || '';
  if (rawDesc.trim()) {
    document.getElementById('section-description').style.display = 'block';
    // Decode HTML entities and strip tags for clean text
    var cleanDesc = decodeEntities(htmlToText(rawDesc));
    document.getElementById('pkg-description').textContent = cleanDesc;
  }

  // === DAY BY DAY ===
  renderDayByDay(pkg.raw_daybyday || pkg.daybyday || '');

  // === HIGHLIGHTS ===
  renderBulletSection('section-highlights', 'pkg-highlights',
    pkg.highlights_list, pkg.raw_highlights || pkg.highlights || '');

  // === INCLUSIONS ===
  renderBulletSection('section-inclusions', 'pkg-inclusions',
    pkg.inclusions_list, pkg.raw_inclusions || pkg.inclusions || '');

  // === TRAINS ===
  var trains = pkg.trains_display || '';
  if (trains.trim()) {
    document.getElementById('section-trains').style.display = 'block';
    var trainNames = trains.split(',').map(function(t) { return t.trim(); }).filter(function(t) { return t; });
    var trainColors = [
      ['#3a5a8c','#1a365d'], ['#4a7c59','#2d5a3e'], ['#8c3a3a','#5d1a1a'],
      ['#6b5b3a','#4a3d28'], ['#3a6b8c','#1a4a5d'], ['#5b3a6b','#3d284a']
    ];
    var trainsHtml = trainNames.map(function(t, idx) {
      var colors = trainColors[idx % trainColors.length];
      return '<div class="dt-train-card">'
        + '<div class="dt-train-card-img" style="background:linear-gradient(135deg,' + colors[0] + ',' + colors[1] + ');">'
        + '<div class="dt-train-card-name">' + escapeHtml(t) + '</div>'
        + '</div>'
        + '</div>';
    }).join('');
    document.getElementById('pkg-trains').innerHTML = trainsHtml;
    // Show scroll button if more than 3 trains
    var scrollBtn = document.getElementById('trains-scroll-btn');
    if (scrollBtn && trainNames.length > 3) {
      scrollBtn.style.display = 'flex';
    }
  }

  // === DEPARTURE DATES ===
  var depDates = pkg.departure_dates_display || '';
  if (depDates.trim()) {
    document.getElementById('section-departures').style.display = 'block';
    document.getElementById('pkg-departures').textContent = depDates;
  }

  // === STICKY BAR ===
  var stickyPrice = document.getElementById('sticky-price');
  if (pkg.estimated_price) {
    stickyPrice.innerHTML = '<span>From</span>\u00A3' + Number(pkg.estimated_price).toLocaleString();
  } else {
    stickyPrice.textContent = 'Price on request';
  }

  // Date and Price button
  document.getElementById('btn-dateprice').addEventListener('click', function() {
    var sec = document.getElementById('section-departures');
    if (sec && sec.style.display !== 'none') {
      sec.scrollIntoView({ behavior: 'smooth' });
    }
  });
}

/* ==================== ROUTE CITIES ==================== */
function buildRouteCities(pkg) {
  var start = pkg.start_location || '';
  var end = pkg.end_location || '';
  var cities = (pkg.cities_display || '').split(/[,|]/).map(function(c) { return c.trim(); }).filter(function(c) { return c; });

  var routeCities = [];
  if (start) routeCities.push(start);
  cities.forEach(function(c) {
    if (c !== start && c !== end && routeCities.indexOf(c) === -1) {
      routeCities.push(c);
    }
  });
  if (end && end !== start && routeCities.indexOf(end) === -1) routeCities.push(end);

  if (routeCities.length > 8) {
    routeCities = [
      routeCities[0], routeCities[1], routeCities[2],
      '...', routeCities[routeCities.length - 2], routeCities[routeCities.length - 1]
    ];
  }
  return routeCities;
}

/* ==================== BULLET SECTIONS ==================== */
function renderBulletSection(sectionId, listId, listArr, rawHtml) {
  var items = listArr || [];
  // If listArr is empty/short, try parsing from raw HTML
  if (items.length === 0 && rawHtml) {
    items = parseLiItems(rawHtml);
  }
  if (items.length === 0) return;

  document.getElementById(sectionId).style.display = 'block';
  document.getElementById(listId).innerHTML = items.map(function(h) {
    return '<li>' + escapeHtml(decodeEntities(h)) + '</li>';
  }).join('');
}

function parseLiItems(html) {
  if (/<li/i.test(html)) {
    var parser = new DOMParser();
    var doc = parser.parseFromString(html, 'text/html');
    doc.querySelectorAll('script,style,iframe,object,embed,form').forEach(function(n) { n.remove(); });
    var items = doc.querySelectorAll('li');
    if (items.length > 0) {
      return Array.from(items).map(function(li) { return li.textContent.trim(); }).filter(function(t) { return t; });
    }
  }
  // fallback: split by newlines
  return html.split(/\n/).map(function(l) { return l.replace(/^[\-\*\u2022]\s*/, '').trim(); }).filter(function(l) { return l; });
}

/* ==================== SALES TIPS ==================== */
function renderSalesTips(rawTips) {
  if (!rawTips || !rawTips.trim()) return;

  document.getElementById('section-salestips').style.display = 'block';
  var el = document.getElementById('pkg-salestips');

  var bullets = parseLiItems(rawTips);
  if (bullets.length === 0) {
    el.innerHTML = '<div class="dt-tip-item">' + escapeHtml(decodeEntities(rawTips)) + '</div>';
    return;
  }

  el.innerHTML = bullets.map(function(b) {
    return '<div class="dt-tip-item">' + escapeHtml(decodeEntities(b)) + '</div>';
  }).join('');
}

/* ==================== DAY BY DAY ==================== */
function renderDayByDay(rawDbd) {
  if (!rawDbd || !rawDbd.trim()) return;

  document.getElementById('section-daybyday').style.display = 'block';
  var container = document.getElementById('pkg-daybyday');

  // DB format: days are pipe-separated "Day 1 - Title - Body | Day 2 - Title - Body"
  // Also may contain <p> tags or HTML
  var cleanText = htmlToText(rawDbd);
  var days = parseDayByDayPipe(cleanText);

  if (days.length === 0) {
    // Fallback: show as plain paragraph
    container.innerHTML = '<div style="font-size:0.88rem;color:#4a5568;line-height:1.7;">'
      + escapeHtml(decodeEntities(cleanText)) + '</div>';
    return;
  }

  container.innerHTML = days.map(function(day, i) {
    return '<div class="dt-dbd-row" data-day="' + i + '">'
      + '<div class="dt-dbd-row-header" onclick="toggleDay(' + i + ')">'
      + '<div style="display:flex;align-items:center;">'
      + '<span class="dt-dbd-day-icon">&#128197;</span>'
      + '<span class="dt-dbd-day-num">' + day.num + '</span>'
      + '<span class="dt-dbd-day-title">' + escapeHtml(day.title) + '</span>'
      + '</div>'
      + '<button class="dt-dbd-expand-btn" type="button">VIEW DETAILS <span class="dt-exp-chevron">\u25BD</span></button>'
      + '</div>'
      + '<div class="dt-dbd-row-body">' + escapeHtml(day.body) + '</div>'
      + '</div>';
  }).join('');

  // OPEN ALL toggle
  var toggleBtn = document.getElementById('dbd-toggle-all');
  toggleBtn.addEventListener('click', function() {
    var rows = container.querySelectorAll('.dt-dbd-row');
    var allOpen = true;
    rows.forEach(function(r) { if (!r.classList.contains('open')) allOpen = false; });
    rows.forEach(function(r) {
      if (allOpen) r.classList.remove('open');
      else r.classList.add('open');
    });
    this.innerHTML = allOpen
      ? 'OPEN ALL <span class="dt-dbd-chevron">\u25BD</span>'
      : 'CLOSE ALL <span class="dt-dbd-chevron">\u25B3</span>';
  });
}

function toggleDay(idx) {
  var row = document.querySelector('.dt-dbd-row[data-day="' + idx + '"]');
  if (row) row.classList.toggle('open');
}

/* ==================== DAY BY DAY PARSER ==================== */
function parseDayByDayPipe(text) {
  // First split by pipe | which is the DB separator
  var segments = text.split('|').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
  var days = [];

  for (var i = 0; i < segments.length; i++) {
    var seg = segments[i];
    // Match "Day X - Title - Body" or "Day X: Title" or "Day X Title"
    var m = seg.match(/^Day\s+(\d+)\s*[-–—:]\s*(.*)/i);
    if (m) {
      var num = parseInt(m[1]);
      var rest = m[2];
      // Split title from body at the second " - "
      var titleBody = splitTitleBody(rest);
      days.push({
        num: num,
        title: decodeEntities(titleBody.title),
        body: decodeEntities(titleBody.body)
      });
    } else {
      // Not a Day X segment — might be continuation of previous day
      if (days.length > 0) {
        days[days.length - 1].body += ' ' + decodeEntities(seg);
      }
    }
  }

  // Fallback: if pipe split produced nothing, try regex on full text
  if (days.length === 0) {
    var dayPattern = /Day\s+(\d+)\s*[-–—:]\s*/gi;
    var match;
    var matches = [];
    while ((match = dayPattern.exec(text)) !== null) {
      matches.push({ index: match.index, end: match.index + match[0].length, num: parseInt(match[1]) });
    }
    for (var j = 0; j < matches.length; j++) {
      var start = matches[j].end;
      var end = j < matches.length - 1 ? matches[j + 1].index : text.length;
      var content = text.substring(start, end).trim();
      var tb = splitTitleBody(content);
      days.push({
        num: matches[j].num,
        title: decodeEntities(tb.title),
        body: decodeEntities(tb.body)
      });
    }
  }

  return days;
}

function splitTitleBody(str) {
  // "Your Journey Begins in Rome - Welcome to Rome! Upon arrival..."
  // Split at first " - " after the title
  var idx = str.indexOf(' - ');
  if (idx > 0 && idx < 80) {
    return { title: str.substring(0, idx).trim(), body: str.substring(idx + 3).trim() };
  }
  // Try splitting at first sentence end
  var sentEnd = str.search(/[.!?]\s/);
  if (sentEnd > 0 && sentEnd < 100) {
    return { title: str.substring(0, sentEnd + 1).trim(), body: str.substring(sentEnd + 2).trim() };
  }
  return { title: str.substring(0, 60).trim(), body: str.substring(60).trim() };
}

document.addEventListener('DOMContentLoaded', loadPackageDetail);
