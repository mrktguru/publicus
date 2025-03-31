const fs = require('fs');
const puppeteer = require('puppeteer');

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  console.log('🌐 Открываем список художников...');
  await page.goto('https://artsandculture.google.com/category/artist', { timeout: 60000 });

  const artists = await page.evaluate(() => {
    const blocks = document.querySelectorAll('article');
    return Array.from(blocks).map(block => {
      const name = block.querySelector('h3')?.innerText || '';
      const url = block.querySelector('a')?.href || '';
      const itemsText = block.innerText.match(/\d+[,\d]*\s+items/);
      const items = itemsText ? parseInt(itemsText[0].replace(/\D/g, '')) : 0;
      return { name, url, items };
    }).filter(a => a.name && a.url);
  });

  console.log(`✅ Найдено ${artists.length} художников.`);

  for (const [index, artist] of artists.entries()) {
    console.log(`\n🎨 ${index + 1}/${artists.length}: ${artist.name} (${artist.items} works)\n→ ${artist.url}`);
    try {
      await page.goto(artist.url, { timeout: 60000 });
      await page.waitForTimeout(3000);

      const paintings = await page.evaluate(() => {
        const cards = document.querySelectorAll('a[href*="/asset/"]');
        const seen = new Set();
        return Array.from(cards).map(card => {
          const title = card.querySelector('div[aria-hidden="true"]')?.innerText || '';
          const image = card.querySelector('img')?.src || '';
          const cleanTitle = title.trim();
          if (!cleanTitle || !image || seen.has(cleanTitle)) return null;
          seen.add(cleanTitle);
          return { title: cleanTitle, image };
        }).filter(Boolean);
      });

      artist.paintings = paintings;
      console.log(`🖼 Найдено ${paintings.length} картин.`);
    } catch (err) {
      console.warn(`⚠️ Ошибка при обработке ${artist.name}:`, err.message);
      artist.paintings = [];
    }

    // 🕒 Задержка между запросами
    await delay(3000);
  }

  await browser.close();

  // 💾 Сохраняем результат
  fs.writeFileSync('artists.json', JSON.stringify(artists, null, 2), 'utf-8');
  console.log('\n💾 Данные сохранены в artists.json');
})();
