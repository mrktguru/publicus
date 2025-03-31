const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const artistsFile = path.join(__dirname, 'artists.json');
const artworksFile = path.join(__dirname, 'artworks.json');

(async () => {
  const artists = JSON.parse(fs.readFileSync(artistsFile, 'utf-8'));
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  const artworks = {};

  console.log(`🔍 Всего художников: ${artists.length}\n`);

  for (const [index, artist] of artists.entries()) {
    console.log(`🎨 [${index + 1}/${artists.length}] Загружаем: ${artist.name}`);
    try {
      await page.goto(artist.link, { waitUntil: 'networkidle2', timeout: 30000 });

      const artistArtworks = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('a'))
          .filter(a => a.href.includes('/asset/'))
          .map(a => ({
            title: a.textContent.trim(),
            url: a.href
          }))
          .filter(item => item.title.length > 0);
      });

      console.log(`   ➕ Найдено: ${artistArtworks.length} картин\n`);
      artworks[artist.name] = artistArtworks;

    } catch (err) {
      console.warn(`   ⚠️ Ошибка при обработке ${artist.name}: ${err.message}\n`);
    }

    // Задержка между запросами (1 секунда)
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  fs.writeFileSync(artworksFile, JSON.stringify(artworks, null, 2), 'utf-8');
  console.log(`✅ Готово! Данные сохранены в: ${artworksFile}`);

  await browser.close();
})();
