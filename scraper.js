const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, 'artists.json');

(async () => {
  console.log('🌐 Открываем страницу с художниками...');

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.goto('https://artsandculture.google.com/category/artist', {
    waitUntil: 'networkidle2'
  });

  // Делаем паузу на подгрузку начального контента
  await new Promise(resolve => setTimeout(resolve, 3000));

  const artists = await page.evaluate(() => {
    const cards = document.querySelectorAll('.YVvGBb');
    const data = [];

    cards.forEach(card => {
      const linkEl = card.querySelector('a');
      const nameEl = card.querySelector('.kHMtLb');
      if (linkEl && nameEl) {
        data.push({
          name: nameEl.textContent.trim(),
          link: 'https://artsandculture.google.com' + linkEl.getAttribute('href')
        });
      }
    });

    return data;
  });

  console.log(`✅ Найдено ${artists.length} художников (без прокрутки).`);
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(artists, null, 2), 'utf-8');
  console.log(`💾 Сохранено в файл: ${OUTPUT_FILE}`);

  await browser.close();
})();
