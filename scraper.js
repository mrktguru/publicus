const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, 'artists.json');

async function fetchArtists() {
  console.log('🌐 Открываем страницу с художниками...');

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
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

  await browser.close();

  console.log(`✅ Найдено ${artists.length} художников.`);

  if (artists.length > 0) {
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(artists, null, 2), 'utf-8');
    console.log(`💾 Сохранено в файл: ${OUTPUT_FILE}`);

    console.log('\n🔹 Примеры:');
    artists.slice(0, 10).forEach((artist, i) => {
      console.log(`${i + 1}. ${artist.name} — ${artist.link}`);
    });
  } else {
    console.warn('⚠️ Художники не найдены. Возможно, нужно прокрутить страницу или обновить селекторы.');
  }
}

fetchArtists().catch(err => {
  console.error('❌ Ошибка в процессе парсинга:', err);
});
