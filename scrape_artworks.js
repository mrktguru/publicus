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

  for (const artist of artists) {
    console.log(`🎨 Загружаем картины: ${artist.name}`);
    await page.goto(artist.link, { waitUntil: 'networkidle2' });

    const artistArtworks = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('a'))
        .filter(a => a.href.includes('/asset/'))
        .map(a => ({
          title: a.textContent.trim(),
          url: a.href
        }));
    });

    console.log(`🔸 Найдено ${artistArtworks.length} картин у ${artist.name}`);
    artworks[artist.name] = artistArtworks;

    await new Promise(resolve => setTimeout(resolve, 1000)); // задержка между художниками
  }

  fs.writeFileSync(artworksFile, JSON.stringify(artworks, null, 2), 'utf-8');
  console.log(`✅ Сохранено в файл: ${artworksFile}`);

  await browser.close();
})();
