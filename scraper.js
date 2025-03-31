const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

const URL = 'https://artsandculture.google.com/category/artist';
const OUTPUT_FILE = path.join(__dirname, 'artists.json');

(async () => {
  console.log('🌐 Загружаем страницу художников...');

  try {
    const response = await axios.get(URL, {
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });

    const $ = cheerio.load(response.data);
    const artists = [];

    $('a[href*="/entity/"][href*="?categoryId=artist"]').each((i, el) => {
      const name = $(el).text().trim();
      const href = $(el).attr('href');
      const url = 'https://artsandculture.google.com' + href;

      if (name && url) {
        artists.push({ name, url });
      }
    });

    console.log(`✅ Найдено ${artists.length} художников.`);

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(artists, null, 2), 'utf-8');
    console.log(`💾 Сохранено в файл: ${OUTPUT_FILE}`);
  } catch (error) {
    console.error('❌ Ошибка при парсинге:', error.message);
  }
})();
