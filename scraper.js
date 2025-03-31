const puppeteer = require('puppeteer');
const fs = require('fs');

// Задержка между действиями
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  console.log('🌐 Открываем список художников...');
  await page.goto('https://artsandculture.google.com/category/artist', { waitUntil: 'networkidle2' });

  // Прокрутка страницы вниз до конца, чтобы подгрузились все художники
  let previousHeight;
  try {
    while (true) {
      previousHeight = await page.evaluate('document.body.scrollHeight');
      await page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
      await delay(1500);
      const newHeight = await page.evaluate('document.body.scrollHeight');
      if (newHeight === previousHeight) break;
    }
  } catch (e) {
    console.log('⚠️ Ошибка при скроллинге:', e);
  }

  console.log('🔍 Извлекаем художников...');
  const artists = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a'))
      .filter(a => a.href.includes('/entity/') && a.textContent.trim().length > 0)
      .map(a => ({
        name: a.textContent.trim(),
        link: a.href
      }));
  });

  console.log(`✅ Найдено ${artists.length} художников.`);
  artists.slice(0, 10).forEach((artist, i) => {
    console.log(`${i + 1}. ${artist.name} — ${artist.link}`);
  });

  // Сохраняем результат
  fs.writeFileSync('artists.json', JSON.stringify(artists, null, 2), 'utf-8');
  console.log('\n💾 Данные сохранены в artists.json');

  await browser.close();
})();
