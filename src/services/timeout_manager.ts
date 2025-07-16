// Gerenciador de timeouts progressivos para ciclos de rentry
export enum ErrorType {
    NETWORK = 'network',
    ANTI_BOT = 'anti_bot',
    TIMEOUT = 'timeout',
    PROXY = 'proxy',
    UNKNOWN = 'unknown'
}

export interface TimeoutContext {
    isAntiBotDetected?: boolean;
    errorHistory?: ErrorType[];
    proxyHealth?: 'good' | 'poor' | 'critical';
    consecutiveFailures?: number;
    avgResponseTime?: number;
}

export class TimeoutManager {
    private static instance: TimeoutManager;
    private baseTimeouts: { [key: string]: number } = {};
    private currentCycle: number = 1;
    private errorHistory: Map<string, ErrorType[]> = new Map();
    private responseTimeHistory: Map<string, number[]> = new Map();
    private lastProxyHealth: 'good' | 'poor' | 'critical' = 'good';
    
    // Multiplicadores adaptativos baseados em contexto
    private readonly ADAPTIVE_MULTIPLIERS = {
        [ErrorType.ANTI_BOT]: 2.5,
        [ErrorType.PROXY]: 1.8,
        [ErrorType.NETWORK]: 1.5,
        [ErrorType.TIMEOUT]: 1.3,
        [ErrorType.UNKNOWN]: 1.0
    };
    
    // Timeouts base em milissegundos - valores mais conservadores
    private readonly DEFAULT_TIMEOUTS = {
        axios: 30000,        // 30s (reduzido de 45s)
        proxy: 600000,       // 10min
        download: 45000,     // 45s (reduzido de 60s)
        request: 30000       // 30s (reduzido de 45s)
    };
    
    private constructor() {
        this.resetToDefaults();
    }
    
    public static getInstance(): TimeoutManager {
        if (!TimeoutManager.instance) {
            TimeoutManager.instance = new TimeoutManager();
        }
        return TimeoutManager.instance;
    }
    
    /**
     * Define o ciclo atual e calcula novos timeouts
     */
    public setCycle(cycle: number): void {
        this.currentCycle = cycle;
        this.updateTimeouts();
    }
    
    /**
     * Obtém o timeout atual para um tipo específico
     */
    public getTimeout(type: 'axios' | 'proxy' | 'download' | 'request'): number {
        return this.baseTimeouts[type];
    }

    /**
     * Obtém timeout adaptativo baseado no contexto
     */
    public getAdaptiveTimeout(type: 'axios' | 'proxy' | 'download' | 'request', context: TimeoutContext = {}): number {
        const baseTimeout = this.getTimeout(type);
        let multiplier = 1.0;

        // Aplicar multiplicador baseado no tipo de erro mais comum
        if (context.errorHistory && context.errorHistory.length > 0) {
            const mostCommonError = this.getMostCommonError(context.errorHistory);
            multiplier = this.ADAPTIVE_MULTIPLIERS[mostCommonError] || 1.0;
        }

        // Aumentar timeout se anti-bot foi detectado
        if (context.isAntiBotDetected) {
            multiplier *= 2.0;
        }

        // Ajustar baseado na saúde do proxy
        switch (context.proxyHealth) {
            case 'poor':
                multiplier *= 1.5;
                break;
            case 'critical':
                multiplier *= 2.0;
                break;
            default:
                break;
        }

        // Aumentar timeout baseado em falhas consecutivas
        if (context.consecutiveFailures && context.consecutiveFailures > 0) {
            multiplier *= Math.min(1 + (context.consecutiveFailures * 0.2), 3.0);
        }

        // Ajustar baseado no tempo de resposta médio
        if (context.avgResponseTime && context.avgResponseTime > baseTimeout * 0.8) {
            multiplier *= 1.3;
        }

        const adaptiveTimeout = Math.round(baseTimeout * multiplier);
        
        if (multiplier > 1.1) {
            console.log(`🧠 Timeout adaptativo ${type}: ${adaptiveTimeout/1000}s (${multiplier.toFixed(2)}x base)`);
        }

        return adaptiveTimeout;
    }
    
    /**
     * Calcula timeout progressivo baseado no ciclo
     * Ciclo 1: timeout padrão
     * Ciclo 2: +50% 
     * Ciclo 3: +100%
     * Ciclo 4: +150%
     * etc...
     */
    private calculateProgressiveTimeout(baseTimeout: number, cycle: number): number {
        if (cycle <= 1) {
            return baseTimeout; // Primeiro ciclo sempre usa timeout padrão
        }
        
        // Incremento de 50% a cada ciclo adicional
        const multiplier = 1 + ((cycle - 1) * 0.5);
        return Math.round(baseTimeout * multiplier);
    }
    
    /**
     * Atualiza todos os timeouts baseado no ciclo atual
     */
    private updateTimeouts(): void {
        Object.keys(this.DEFAULT_TIMEOUTS).forEach(key => {
            const baseTimeout = this.DEFAULT_TIMEOUTS[key as keyof typeof this.DEFAULT_TIMEOUTS];
            this.baseTimeouts[key] = this.calculateProgressiveTimeout(baseTimeout, this.currentCycle);
        });
        
        if (this.currentCycle > 1) {
            console.log(`🕐 Timeouts atualizados para Ciclo ${this.currentCycle}:`);
            console.log(`   - Axios: ${this.baseTimeouts.axios/1000}s (base: ${this.DEFAULT_TIMEOUTS.axios/1000}s)`);
            console.log(`   - Proxy: ${this.baseTimeouts.proxy/1000}s (base: ${this.DEFAULT_TIMEOUTS.proxy/1000}s)`);
            console.log(`   - Download: ${this.baseTimeouts.download/1000}s (base: ${this.DEFAULT_TIMEOUTS.download/1000}s)`);
            console.log(`   - Request: ${this.baseTimeouts.request/1000}s (base: ${this.DEFAULT_TIMEOUTS.request/1000}s)`);
        }
    }
    
    /**
     * Restaura todos os timeouts para os valores padrão
     */
    public resetToDefaults(): void {
        this.currentCycle = 1;
        this.baseTimeouts = { ...this.DEFAULT_TIMEOUTS };
        console.log('🔄 Timeouts restaurados para valores padrão');
    }
    
    /**
     * Obtém informações sobre os timeouts atuais
     */
    public getTimeoutInfo(): { cycle: number, timeouts: { [key: string]: number } } {
        return {
            cycle: this.currentCycle,
            timeouts: { ...this.baseTimeouts }
        };
    }
    
    /**
     * Calcula a porcentagem de aumento em relação ao timeout base
     */
    public getIncreasePercentage(): number {
        if (this.currentCycle <= 1) return 0;
        return (this.currentCycle - 1) * 50; // 50% por ciclo adicional
    }

    /**
     * Registra erro para histórico
     */
    public recordError(operation: string, errorType: ErrorType): void {
        if (!this.errorHistory.has(operation)) {
            this.errorHistory.set(operation, []);
        }
        
        const history = this.errorHistory.get(operation)!;
        history.push(errorType);
        
        // Manter apenas últimos 10 erros
        if (history.length > 10) {
            history.shift();
        }
    }

    /**
     * Registra tempo de resposta para histórico
     */
    public recordResponseTime(operation: string, responseTime: number): void {
        if (!this.responseTimeHistory.has(operation)) {
            this.responseTimeHistory.set(operation, []);
        }
        
        const history = this.responseTimeHistory.get(operation)!;
        history.push(responseTime);
        
        // Manter apenas últimos 10 tempos
        if (history.length > 10) {
            history.shift();
        }
    }

    /**
     * Obtém contexto de timeout para uma operação
     */
    public getTimeoutContext(operation: string): TimeoutContext {
        const errorHistory = this.errorHistory.get(operation) || [];
        const responseHistory = this.responseTimeHistory.get(operation) || [];
        
        const avgResponseTime = responseHistory.length > 0 
            ? responseHistory.reduce((a, b) => a + b, 0) / responseHistory.length
            : undefined;

        const consecutiveFailures = this.getConsecutiveFailures(errorHistory);
        const isAntiBotDetected = errorHistory.slice(-3).includes(ErrorType.ANTI_BOT);

        return {
            errorHistory,
            avgResponseTime,
            consecutiveFailures,
            isAntiBotDetected,
            proxyHealth: this.lastProxyHealth
        };
    }

    /**
     * Atualiza estado da saúde do proxy
     */
    public updateProxyHealth(health: 'good' | 'poor' | 'critical'): void {
        if (this.lastProxyHealth !== health) {
            console.log(`🔄 Saúde do proxy atualizada: ${this.lastProxyHealth} → ${health}`);
            this.lastProxyHealth = health;
        }
    }

    /**
     * Obtém o erro mais comum do histórico
     */
    private getMostCommonError(errors: ErrorType[]): ErrorType {
        const counts = errors.reduce((acc, error) => {
            acc[error] = (acc[error] || 0) + 1;
            return acc;
        }, {} as Record<ErrorType, number>);

        return Object.entries(counts)
            .sort(([,a], [,b]) => b - a)[0]?.[0] as ErrorType || ErrorType.UNKNOWN;
    }

    /**
     * Conta falhas consecutivas no final do histórico
     */
    private getConsecutiveFailures(errors: ErrorType[]): number {
        let consecutive = 0;
        for (let i = errors.length - 1; i >= 0; i--) {
            if (errors[i] !== ErrorType.UNKNOWN) {
                consecutive++;
            } else {
                break;
            }
        }
        return consecutive;
    }

    /**
     * Limpa histórico de uma operação
     */
    public clearHistory(operation: string): void {
        this.errorHistory.delete(operation);
        this.responseTimeHistory.delete(operation);
        console.log(`🧹 Histórico limpo para operação: ${operation}`);
    }
    
    /**
     * Verifica se ainda há falhas nos logs para determinar se deve continuar ciclos
     */
    public hasFailedChapters(): boolean {
        const fs = require('fs');
        const path = require('path');
        
        const failedDir = 'logs/failed';
        
        if (!fs.existsSync(failedDir)) {
            return false;
        }
        
        const files = fs.readdirSync(failedDir).filter((file: string) => file.endsWith('.json'));
        return files.length > 0;
    }
    
    /**
     * Aplica timeouts progressivos em todos os componentes da aplicação
     */
    public applyProgressiveTimeoutsToAll(): void {
        const context = this.getTimeoutContext('global');
        
        // Aplicar nos timeouts base
        this.updateTimeouts();
        
        console.log(`📊 Timeouts progressivos aplicados globalmente (Ciclo ${this.currentCycle})`);
        console.log(`   - Aumento: +${this.getIncreasePercentage()}%`);
        console.log(`   - Máximo de ciclos: 10`);
        console.log(`   - Falhas restantes: ${this.hasFailedChapters() ? 'Sim' : 'Não'}`);
    }
    
    /**
     * Obtém timeout para qualquer operação com contexto automático
     */
    public getTimeoutFor(operation: string): number {
        const context = this.getTimeoutContext(operation);
        
        // Mapear operações para tipos de timeout
        const operationMap: { [key: string]: 'axios' | 'proxy' | 'download' | 'request' } = {
            'scrape': 'request',
            'axios_request': 'axios',
            'proxy_fetch': 'proxy',
            'download_image': 'download',
            'chapter_processing': 'request',
            'provider_operation': 'request',
            'bypass_cloudflare': 'request'
        };
        
        const timeoutType = operationMap[operation] || 'request';
        return this.getAdaptiveTimeout(timeoutType, context);
    }
    
    /**
     * Força atualização de timeouts em todos os componentes
     */
    public forceUpdateAllComponents(): void {
        console.log(`🔄 Forçando atualização de timeouts em todos os componentes...`);
        
        // Notificar que os timeouts mudaram
        this.applyProgressiveTimeoutsToAll();
        
        // Log para debug
        console.log(`📋 Estado atual dos timeouts:`);
        Object.entries(this.baseTimeouts).forEach(([type, timeout]) => {
            console.log(`   ${type}: ${timeout/1000}s`);
        });
    }
}