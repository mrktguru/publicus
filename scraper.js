const puppeteer = require('puppeteer');
const fs = require('fs');

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new', // <-- используем headless режим
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  console.log('🌐 Открываем список художников...');
  await page.goto('https://artsandculture.google.com/category/artist', { waitUntil: 'networkidle2' });

  let previousHeight = 0;
  let currentHeight = 0;
  let scrollTries = 0;
  const maxScrollTries = 10;

  try {
    while (scrollTries < maxScrollTries) {
      currentHeight = await page.evaluate(() => document.body.scrollHeight);
      if (currentHeight === previousHeight) {
        scrollTries++;
        console.log(`🟡 Ничего нового. Попытка ${scrollTries}/${maxScrollTries}`);
      } else {
        scrollTries = 0;
        console.log(`🔽 Прокрутка... текущая высота: ${currentHeight}`);
      }

      previousHeight = currentHeight;
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await delay(2000);
    }
  } catch (e) {
    console.log('⚠️ Ошибка при прокрутке:', e);
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
  fs.writeFileSync('artists.json', JSON.stringify(artists, null, 2), 'utf-8');
  console.log('💾 Сохранено в artists.json');

  await browser.close();
})();
