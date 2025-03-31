const puppeteer = require('puppeteer');

async function fetchArtists() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'] // важно для VPS
  });

  const page = await browser.newPage();
  await page.goto('https://artsandculture.google.com/category/artist', { waitUntil: 'networkidle2' });

  const artists = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a'))
      .filter(a => a.href.includes('/entity/') && a.textContent.trim().length > 0)
      .map(a => ({
        name: a.textContent.trim(),
        link: a.href
      }));
  });

  console.log(`🔍 Найдено ${artists.length} художников:`);
  artists.slice(0, 10).forEach((artist, i) => {
    console.log(`${i + 1}. ${artist.name} — ${artist.link}`);
  });

  await browser.close();
}

fetchArtists();
