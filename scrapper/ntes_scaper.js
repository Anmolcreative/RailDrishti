// scraper/ntes_scraper.js
// RailDrishti v2.0 NTES Scraper (Node.js + Puppeteer)
// Corridors: BPL-ET (WCR) | NDLS-MGS (NCR) | HWH-DHN (ER)
// Falls back to RailAPI.in after 3 retries with exponential back-off.
// Exposes /api/scraper/health for the React ScraperHealth component.

require('dotenv').config({ path: '../.env' });
const puppeteer = require('puppeteer');
const axios     = require('axios');
const express   = require('express');

const app  = express();
const PORT = process.env.SCRAPER_PORT || 3001;

//  Corridor train lists (match Corridor Control UI: BPL-ET zone WCR)
const CORRIDORS = {
  'BPL-ET':   ['TN001', 'TN002', 'TN003', 'TN004', 'TN005'],  // Bhopal-Itarsi
  'NDLS-MGS': ['TN006', 'TN007', 'TN008', 'TN009', 'TN010'],  // Delhi-Mughalsarai
  'HWH-DHN':  ['TN011', 'TN012', 'TN013'],                     // Howrah-Dhanbad
};

// CSS selectors externalised to ntes_selectors.json so they can be patched
// without touching scraper logic when NTES redesigns their DOM.
const selectors = require('./ntes_selectors.json');

let lastSuccessTs = null;
let activeSource  = 'Simulated';   // NTES | RailAPI | Simulated

/**
 * Scrape one train from NTES using Puppeteer.
 * @param {puppeteer.Browser} browser
 * @param {string} trainNo  e.g. "12001"
 * @returns {object} TrainStatus
 */
async function scrapeNTES(browser, trainNo) {
  const page = await browser.newPage();
  try {
    await page.goto(
      `https://enquiry.indianrail.gov.in/mntes/q?opt=TR&trainNo=${trainNo}`,
      { waitUntil: 'networkidle2', timeout: 15_000 }
    );
    const data = await page.evaluate((sel) => ({
      train_no:        document.querySelector(sel.train_no)?.innerText?.trim()       || '',
      train_name:      document.querySelector(sel.train_name)?.innerText?.trim()     || '',
      current_station: document.querySelector(sel.current_station)?.innerText?.trim()|| '',
      delay_min:       parseInt(document.querySelector(sel.delay_min)?.innerText || '0', 10),
      last_updated:    document.querySelector(sel.last_updated)?.innerText?.trim()   || new Date().toISOString(),
    }), selectors);

    return { ...data, source: 'NTES' };
  } finally {
    await page.close();
  }
}

/**
 * Fallback: fetch from RailAPI.in REST endpoint.
 * Expected fields: lat, lng, delay_mins, last_station_code, next_station_code, speed_kmh
 */
async function fetchRailAPI(trainNo) {
  const url  = `https://railapi.in/api/v2/trains/${trainNo}/live`;
  const resp = await axios.get(url, {
    headers: { 'X-API-Key': process.env.RAILAPI_KEY },
    timeout: 8_000,
  });
  const d = resp.data;
  return {
    train_no:        trainNo,
    train_name:      d.train_name     || trainNo,
    current_station: d.last_station_code || '',
    delay_min:       d.delay_mins     || 0,
    last_updated:    new Date().toISOString(),
    source:          'RailAPI',
  };
}

/**
 * Retry wrapper with exponential back-off (3 attempts).
 */
async function withRetry(fn, maxAttempts = 3) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxAttempts) throw err;
      const delay = 500 * Math.pow(2, attempt);   // 1 s, 2 s
      console.warn(`Attempt ${attempt} failed for train ${trainNo}  retrying in ${delay}ms`);
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

/**
 * Get status for one train: try NTES first, fall back to RailAPI.
 */
async function getTrainStatus(browser, trainNo) {
  try {
    const status = await withRetry(() => scrapeNTES(browser, trainNo));
    activeSource = 'NTES';
    lastSuccessTs = new Date().toISOString();
    return status;
  } catch (ntesErr) {
    console.warn(`NTES failed for ${trainNo}: ${ntesErr.message} trying RailAPI`);
    try {
      const status = await withRetry(() => fetchRailAPI(trainNo));
      activeSource = 'RailAPI';
      lastSuccessTs = new Date().toISOString();
      return status;
    } catch (apiErr) {
      console.error(`RailAPI also failed for ${trainNo}: ${apiErr.message}`);
      activeSource = 'Simulated';
     
      return {
        train_no:        trainNo,
        train_name:      trainNo,
        current_station: 'UNKNOWN',
        delay_min:       0,
        last_updated:    new Date().toISOString(),
        source:          'Simulated',
      };
    }
  }
}

/**
 * Scrape all corridors and return flat list of TrainStatus objects.
 * Output matches the schema documented in Phase 3 Step 4 of the ML guide.
 */
async function scrapeAllCorridors() {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const [corridor, trains] of Object.entries(CORRIDORS)) {
      for (const trainNo of trains) {
        const status = await getTrainStatus(browser, trainNo);
        results.push({ corridor, ...status });
      }
    }
  } finally {
    await browser.close();
  }
  return results;
}


app.get('/api/scraper/health', (req, res) => {
  res.json({
    status:           lastSuccessTs ? 'ok' : 'down',
    active_source:    activeSource,          // NTES | RailAPI | Simulated
    last_success_utc: lastSuccessTs,
    trains_tracked:   Object.values(CORRIDORS).flat().length,
  });
});


app.get('/api/scraper/run', async (req, res) => {
  try {
    const data = await scrapeAllCorridors();
    res.json({ ok: true, count: data.length, data });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`RailDrishti NTES Scraper listening on port ${PORT}`);
  console.log(`Health: http://localhost:${PORT}/api/scraper/health`);
});

module.exports = { scrapeAllCorridors, getTrainStatus };