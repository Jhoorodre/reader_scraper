// Gerenciador de timeouts progressivos para ciclos de rentry
export class TimeoutManager {
    private static instance: TimeoutManager;
    private baseTimeouts: { [key: string]: number } = {};
    private currentCycle: number = 1;
    
    // Timeouts base em milissegundos
    private readonly DEFAULT_TIMEOUTS = {
        axios: 45000,        // 45s (aumentado de 15s para dar tempo ao bypass)
        proxy: 600000,       // 10min
        download: 60000,     // 60s (aumentado de 30s)
        request: 45000       // 45s (aumentado de 15s para dar tempo ao bypass)
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
}