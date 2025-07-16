import { ChapterLogger } from './src/utils/chapter_logger';

// Script para recriar logs de sucesso perdidos
console.log('🔧 Recriando logs de sucesso perdidos...');

const chapterLogger = new ChapterLogger();
chapterLogger.recreateSuccessLogsFromFiles();

console.log('✅ Logs de sucesso recriados com sucesso!');