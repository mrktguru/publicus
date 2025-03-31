const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, 'artists.json');

(async () => {
  console.log('🌐 Открываем список художников...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox']
  });
  const page = await browser.newPage();
  await page.goto('https://artsandculture.google.com/category/artist', {
    waitUntil: 'networkidle2',
  });

  // Прокрутка страницы до конца
  let previousHeight = 0;
  let scrollStep = 1600;
  let maxScrolls = 30;
  for (let i = 0; i < maxScrolls; i++) {
    await page.evaluate((step) => {
      window.scrollBy(0, step);
    }, scrollStep);
    await new Promise(resolve => setTimeout(resolve, 1200));
    const currentHeight = await page.evaluate(() => document.body.scrollHeight);
    console.log(`🔽 Прокрутка... текущая высота: ${currentHeight}`);
    if (currentHeight === previousHeight) break;
    previousHeight = currentHeight;
  }

  // Извлечение данных о художниках
  const artists = await page.evaluate(() => {
    const anchors = Array.from(document.querySelectorAll('a'))
      .filter(a =>
        a.href.includes('/entity/') &&
        a.href.includes('?categoryId=artist') &&
        a.innerText.trim().length > 0
      );

    const seen = new Set();
    return anchors
      .filter(a => {
        if (seen.has(a.href)) return false;
        seen.add(a.href);
        return true;
      })
      .map(a => ({
        name: a.innerText.trim(),
        link: a.href
      }));
  });

  console.log(`✅ Найдено ${artists.length} художников.`);
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(artists, null, 2), 'utf-8');
  console.log(`💾 Сохранено в файл: ${OUTPUT_FILE}`);

  await browser.close();
})();
