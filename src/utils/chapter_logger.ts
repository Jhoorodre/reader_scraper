import * as fs from 'fs';
import * as path from 'path';

interface ChapterLog {
    workName: string;
    workId: string;
    chapterNumber: string;
    chapterId: string;
    status: 'success' | 'failed';
    timestamp: string;
    pages?: number;
    attempts?: number;
    errorMessage?: string;
    downloadPath?: string;
}

interface WorkLog {
    workName: string;
    workId: string;
    workUrl?: string; // URL original da obra
    lastUpdate: string;
    chapters: ChapterLog[];
}

export class ChapterLogger {
    private logsDir = 'logs';
    private successDir = 'logs/success';
    private failedDir = 'logs/failed';
    
    constructor() {
        // Criar estrutura de diretórios
        if (!fs.existsSync(this.logsDir)) {
            fs.mkdirSync(this.logsDir, { recursive: true });
        }
        if (!fs.existsSync(this.successDir)) {
            fs.mkdirSync(this.successDir, { recursive: true });
        }
        if (!fs.existsSync(this.failedDir)) {
            fs.mkdirSync(this.failedDir, { recursive: true });
        }
        
        // Migrar logs antigos automaticamente se existirem
        this.migrateOldLogs();
    }
    
    private sanitizeFileName(name: string): string {
        return name.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_');
    }
    
    private getWorkLogPath(workName: string, type: 'success' | 'failed'): string {
        const sanitizedName = this.sanitizeFileName(workName);
        const baseDir = type === 'success' ? this.successDir : this.failedDir;
        return path.join(baseDir, `${sanitizedName}.json`);
    }
    
    // Carregar log da obra ou criar novo
    private loadWorkLog(workName: string, workId: string, type: 'success' | 'failed', workUrl?: string): WorkLog {
        const logPath = this.getWorkLogPath(workName, type);
        
        if (fs.existsSync(logPath)) {
            try {
                const content = fs.readFileSync(logPath, 'utf-8');
                const workLog: WorkLog = JSON.parse(content);
                return workLog;
            } catch (error) {
                console.warn(`⚠️ Erro ao ler log da obra ${workName} (${type}): ${error.message}`);
            }
        }
        
        // Criar novo log da obra
        return {
            workName,
            workId,
            workUrl,
            lastUpdate: new Date().toISOString(),
            chapters: []
        };
    }
    
    // Salvar log da obra
    private saveWorkLog(workLog: WorkLog, type: 'success' | 'failed'): void {
        const logPath = this.getWorkLogPath(workLog.workName, type);
        workLog.lastUpdate = new Date().toISOString();
        
        // Ordenar capítulos por número (decrescente)
        workLog.chapters.sort((a, b) => {
            const numA = parseFloat(a.chapterNumber.replace(/[^\d.]/g, ''));
            const numB = parseFloat(b.chapterNumber.replace(/[^\d.]/g, ''));
            return numB - numA; // Decrescente
        });
        
        fs.writeFileSync(logPath, JSON.stringify(workLog, null, 2), 'utf-8');
    }
    
    // Salvar log de capítulo com sucesso
    saveChapterSuccess(workName: string, workId: string, chapterNumber: string, chapterId: string, pages: number, downloadPath: string): void {
        // Remover do log de falhas se existir
        this.removeChapterFromFailedLog(workName, chapterNumber);
        
        // Carregar log de sucessos
        const successLog = this.loadWorkLog(workName, workId, 'success');
        
        // Remover entrada existente de sucesso (evitar duplicatas)
        successLog.chapters = successLog.chapters.filter(ch => ch.chapterNumber !== chapterNumber);
        
        // Adicionar novo log de sucesso
        const chapterLog: ChapterLog = {
            workName,
            workId,
            chapterNumber,
            chapterId,
            status: 'success',
            timestamp: new Date().toISOString(),
            pages,
            downloadPath
        };
        
        successLog.chapters.push(chapterLog);
        this.saveWorkLog(successLog, 'success');
        console.log(`✅ Log de sucesso salvo: ${chapterNumber}`);
    }
    
    // Salvar log de capítulo com falha
    saveChapterFailure(workName: string, workId: string, chapterNumber: string, chapterId: string, attempts: number, errorMessage: string): void {
        // Carregar log de falhas
        const failedLog = this.loadWorkLog(workName, workId, 'failed');
        
        // Remover entrada existente de falha (evitar duplicatas)
        failedLog.chapters = failedLog.chapters.filter(ch => ch.chapterNumber !== chapterNumber);
        
        // Adicionar novo log de falha
        const chapterLog: ChapterLog = {
            workName,
            workId,
            chapterNumber,
            chapterId,
            status: 'failed',
            timestamp: new Date().toISOString(),
            attempts,
            errorMessage
        };
        
        failedLog.chapters.push(chapterLog);
        this.saveWorkLog(failedLog, 'failed');
        console.log(`❌ Log de falha salvo: ${chapterNumber}`);
    }
    
    // Remover capítulo do log de falhas
    private removeChapterFromFailedLog(workName: string, chapterNumber: string): void {
        const failedLogPath = this.getWorkLogPath(workName, 'failed');
        
        if (fs.existsSync(failedLogPath)) {
            try {
                const content = fs.readFileSync(failedLogPath, 'utf-8');
                const failedLog: WorkLog = JSON.parse(content);
                
                const originalLength = failedLog.chapters.length;
                failedLog.chapters = failedLog.chapters.filter(ch => ch.chapterNumber !== chapterNumber);
                
                if (failedLog.chapters.length !== originalLength) {
                    if (failedLog.chapters.length === 0) {
                        // Remover arquivo se não há mais falhas
                        fs.unlinkSync(failedLogPath);
                        console.log(`🗑️ Arquivo de falhas removido: ${chapterNumber} foi o último capítulo falhado`);
                    } else {
                        this.saveWorkLog(failedLog, 'failed');
                        console.log(`🔄 Capítulo ${chapterNumber} removido das falhas`);
                    }
                }
            } catch (error) {
                console.warn(`⚠️ Erro ao remover ${chapterNumber} das falhas: ${error.message}`);
            }
        }
    }
    
    // Ler todos os logs de capítulos de uma obra
    readWorkChapters(workName: string): { successful: ChapterLog[], failed: ChapterLog[] } {
        const successPath = this.getWorkLogPath(workName, 'success');
        const failedPath = this.getWorkLogPath(workName, 'failed');
        const successful: ChapterLog[] = [];
        const failed: ChapterLog[] = [];
        
        // Ler logs de sucesso
        if (fs.existsSync(successPath)) {
            try {
                const content = fs.readFileSync(successPath, 'utf-8');
                const successLog: WorkLog = JSON.parse(content);
                successful.push(...successLog.chapters);
            } catch (error) {
                console.warn(`⚠️ Erro ao ler log de sucessos da obra ${workName}: ${error.message}`);
            }
        }
        
        // Ler logs de falhas
        if (fs.existsSync(failedPath)) {
            try {
                const content = fs.readFileSync(failedPath, 'utf-8');
                const failedLog: WorkLog = JSON.parse(content);
                failed.push(...failedLog.chapters);
            } catch (error) {
                console.warn(`⚠️ Erro ao ler log de falhas da obra ${workName}: ${error.message}`);
            }
        }
        
        return { successful, failed };
    }
    
    // Detectar capítulos novos baseado nos logs existentes
    detectNewChapters(workName: string, availableChapters: any[]): any[] {
        const { successful, failed } = this.readWorkChapters(workName);
        
        if (successful.length === 0) {
            console.log('📋 Primeiro download desta obra - baixando todos os capítulos');
            return availableChapters;
        }
        
        // Encontrar o maior número de capítulo baixado com sucesso
        const lastSuccessful = successful[0]; // Já está ordenado decrescente
        const lastChapterNum = parseFloat(lastSuccessful.chapterNumber.replace(/[^\d.]/g, ''));
        console.log(`📊 Último capítulo no log: ${lastSuccessful.chapterNumber} (${lastChapterNum})`);
        
        // Filtrar capítulos novos (número maior que o último baixado)
        const newChapters = availableChapters.filter(chapter => {
            const chapterNum = parseFloat(chapter.number.replace(/[^\d.]/g, ''));
            return chapterNum > lastChapterNum;
        });
        
        // Incluir capítulos que falharam anteriormente
        const failedChapterNumbers = failed.map(f => f.chapterNumber);
        const retriableChapters = availableChapters.filter(chapter => 
            failedChapterNumbers.includes(chapter.number)
        );
        
        const allToDownload = [...newChapters, ...retriableChapters];
        
        if (allToDownload.length > 0) {
            console.log(`🆕 Detectados ${newChapters.length} capítulos novos e ${retriableChapters.length} falhas para reprocessar`);
            allToDownload.forEach(ch => {
                const isNew = newChapters.includes(ch);
                console.log(`  ${isNew ? '🆕' : '🔄'} Capítulo ${ch.number}`);
            });
        } else {
            console.log('✅ Todos os capítulos já estão baixados - obra atualizada');
        }
        
        return allToDownload;
    }
    
    // Verificar se obra já tem logs
    hasWorkLogs(workName: string): boolean {
        const successPath = this.getWorkLogPath(workName, 'success');
        const failedPath = this.getWorkLogPath(workName, 'failed');
        const hasLogs = fs.existsSync(successPath) || fs.existsSync(failedPath);
        
        if (hasLogs) {
            console.log(`⚠️ AVISO: Obra "${workName}" já possui logs e será atualizada`);
            if (fs.existsSync(successPath)) console.log(`📁 Sucessos: ${successPath}`);
            if (fs.existsSync(failedPath)) console.log(`📁 Falhas: ${failedPath}`);
        }
        
        return hasLogs;
    }
    
    // Listar todas as obras com logs
    listAllWorks(): string[] {
        const works = new Set<string>();
        
        // Verificar pasta de sucessos
        if (fs.existsSync(this.successDir)) {
            fs.readdirSync(this.successDir)
                .filter(file => file.endsWith('.json'))
                .forEach(file => works.add(file.replace('.json', '').replace(/_/g, ' ')));
        }
        
        // Verificar pasta de falhas
        if (fs.existsSync(this.failedDir)) {
            fs.readdirSync(this.failedDir)
                .filter(file => file.endsWith('.json'))
                .forEach(file => works.add(file.replace('.json', '').replace(/_/g, ' ')));
        }
        
        return Array.from(works);
    }
    
    // Mostrar estatísticas da obra
    showWorkStats(workName: string): void {
        const { successful, failed } = this.readWorkChapters(workName);
        
        console.log(`📊 Estatísticas da obra: ${workName}`);
        console.log(`✅ Capítulos baixados: ${successful.length}`);
        console.log(`❌ Capítulos falhados: ${failed.length}`);
        console.log(`📈 Total: ${successful.length + failed.length}`);
        
        if (successful.length > 0) {
            const latest = successful[0]; // Maior número (decrescente)
            console.log(`🔢 Último capítulo baixado: ${latest.chapterNumber}`);
            console.log(`🕐 Última atualização: ${latest.timestamp}`);
        }
        
        if (failed.length > 0) {
            console.log(`🔄 Falhas para reprocessar:`);
            failed.forEach(f => console.log(`  ❌ Capítulo ${f.chapterNumber}: ${f.errorMessage}`));
        }
    }
    
    // Verificar se capítulo já foi baixado
    isChapterDownloaded(workName: string, chapterNumber: string): boolean {
        const { successful } = this.readWorkChapters(workName);
        return successful.some(ch => ch.chapterNumber === chapterNumber);
    }
    
    // Obter todas as falhas para rentry
    getAllFailedChapters(): { workName: string, chapters: ChapterLog[] }[] {
        const failedWorks: { workName: string, chapters: ChapterLog[] }[] = [];
        
        if (!fs.existsSync(this.failedDir)) {
            return failedWorks;
        }
        
        const files = fs.readdirSync(this.failedDir).filter(file => file.endsWith('.json'));
        
        for (const file of files) {
            try {
                const workName = file.replace('.json', '').replace(/_/g, ' ');
                const filePath = path.join(this.failedDir, file);
                const content = fs.readFileSync(filePath, 'utf-8');
                const failedLog: WorkLog = JSON.parse(content);
                
                if (failedLog.chapters.length > 0) {
                    failedWorks.push({
                        workName,
                        chapters: failedLog.chapters
                    });
                }
            } catch (error) {
                console.warn(`⚠️ Erro ao ler arquivo de falhas ${file}: ${error.message}`);
            }
        }
        
        return failedWorks;
    }
    
    // Obter falhas de uma obra específica
    getWorkFailedChapters(workName: string): ChapterLog[] {
        const failedPath = this.getWorkLogPath(workName, 'failed');
        
        if (!fs.existsSync(failedPath)) {
            return [];
        }
        
        try {
            const content = fs.readFileSync(failedPath, 'utf-8');
            const failedLog: WorkLog = JSON.parse(content);
            return failedLog.chapters;
        } catch (error) {
            console.warn(`⚠️ Erro ao ler falhas da obra ${workName}: ${error.message}`);
            return [];
        }
    }
    
    // Verificar se existe log de falhas
    hasFailedChapters(): boolean {
        if (!fs.existsSync(this.failedDir)) {
            return false;
        }
        
        const files = fs.readdirSync(this.failedDir).filter(file => file.endsWith('.json'));
        return files.length > 0;
    }
    
    // Migrar logs antigos (formato individual) para novo formato (JSON único)
    migrateOldLogs(): void {
        if (!fs.existsSync(this.logsDir)) {
            return;
        }
        
        const items = fs.readdirSync(this.logsDir, { withFileTypes: true });
        const directories = items.filter(item => item.isDirectory());
        
        for (const dir of directories) {
            const workName = dir.name.replace(/_/g, ' ');
            const oldWorkDir = path.join(this.logsDir, dir.name);
            const files = fs.readdirSync(oldWorkDir);
            
            console.log(`🔄 Migrando logs antigos da obra: ${workName}`);
            
            const chapters: ChapterLog[] = [];
            
            for (const file of files) {
                if (file.endsWith('.json')) {
                    try {
                        const filePath = path.join(oldWorkDir, file);
                        const content = fs.readFileSync(filePath, 'utf-8');
                        const oldLog: ChapterLog = JSON.parse(content);
                        chapters.push(oldLog);
                    } catch (error) {
                        console.warn(`⚠️ Erro ao migrar ${file}: ${error.message}`);
                    }
                }
            }
            
            if (chapters.length > 0) {
                // Separar sucessos e falhas
                const successChapters = chapters.filter(ch => ch.status === 'success');
                const failedChapters = chapters.filter(ch => ch.status === 'failed');
                
                // Criar logs de sucesso se existirem
                if (successChapters.length > 0) {
                    const successLog: WorkLog = {
                        workName,
                        workId: successChapters[0].workId,
                        lastUpdate: new Date().toISOString(),
                        chapters: successChapters
                    };
                    this.saveWorkLog(successLog, 'success');
                }
                
                // Criar logs de falha se existirem
                if (failedChapters.length > 0) {
                    const failedLog: WorkLog = {
                        workName,
                        workId: failedChapters[0].workId,
                        lastUpdate: new Date().toISOString(),
                        chapters: failedChapters
                    };
                    this.saveWorkLog(failedLog, 'failed');
                }
                
                console.log(`✅ Migração concluída: ${successChapters.length} sucessos, ${failedChapters.length} falhas migrados`);
                
                // Remover diretório antigo
                fs.rmSync(oldWorkDir, { recursive: true, force: true });
                console.log(`🗑️ Diretório antigo removido: ${oldWorkDir}`);
            }
        }
    }
}