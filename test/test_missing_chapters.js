const { SussyToonsProvider } = require('../src/providers/scans/sussytoons/index.js');
const { ChapterLogger } = require('../src/utils/chapter_logger.js');

(async () => {
  console.log('🔍 Testando detecção de capítulos faltantes...');
  
  const provider = new SussyToonsProvider();
  const chapterLogger = new ChapterLogger();
  
  // Testar algumas obras das 11 URLs
  const testUrls = [
    'https://sussytoons.wtf/obra/10733/arquiteto-de-dungeons',
    'https://sussytoons.wtf/obra/7568/imperador-de-aco', 
    'https://sussytoons.wtf/obra/11265/o-deus-da-espada-de-um-mundo-caido'
  ];
  
  for (const url of testUrls) {
    try {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`🔍 TESTANDO: ${url}`);
      console.log(`${'='.repeat(60)}`);
      
      const manga = await provider.getManga(url);
      console.log(`📚 Obra: ${manga.name}`);
      
      const chapters = await provider.getChapters(manga.id);
      console.log(`📖 Capítulos no site: ${chapters.length}`);
      if (chapters.length > 0) {
        const latest = chapters[0];
        const oldest = chapters[chapters.length - 1];
        console.log(`  📄 Mais recente: ${latest.number}`);
        console.log(`  📄 Mais antigo: ${oldest.number}`);
      }
      
      const selectedChapters = chapterLogger.detectNewChapters(manga.name, chapters);
      console.log(`🆕 Capítulos novos detectados: ${selectedChapters.length}`);
      
      if (selectedChapters.length > 0) {
        console.log('📋 Capítulos faltantes:');
        selectedChapters.slice(0, 5).forEach(ch => {
          console.log(`  🔴 ${ch.number}`);
        });
        if (selectedChapters.length > 5) {
          console.log(`  ... e mais ${selectedChapters.length - 5} capítulos`);
        }
      } else {
        console.log('✅ Nenhum capítulo faltando');
      }
      
    } catch (error) {
      console.error(`❌ Erro ao testar ${url}:`, error.message);
    }
  }
})();