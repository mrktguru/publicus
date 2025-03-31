const axios = require('axios');
const cheerio = require('cheerio');

async function fetchArtists() {
  try {
    const url = 'https://artsandculture.google.com/category/artist';
    const { data } = await axios.get(url);
    const $ = cheerio.load(data);

    const artists = [];

    $('a').each((i, el) => {
      const href = $(el).attr('href');
      const text = $(el).text();
      if (href && text && href.includes('/entity/')) {
        artists.push({ name: text.trim(), link: `https://artsandculture.google.com${href}` });
      }
    });

    console.log(`🔍 Найдено ${artists.length} художников:`);
    artists.slice(0, 10).forEach((artist, i) => {
      console.log(`${i + 1}. ${artist.name} — ${artist.link}`);
    });
  } catch (err) {
    console.error('❌ Ошибка при парсинге:', err.message);
  }
}

fetchArtists();
