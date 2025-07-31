import axios from 'axios';
import AsyncRetry from 'async-retry';
import { TimeoutManager, ErrorType } from './timeout_manager';
import { RedisClient } from './redis_client';
import logger from '../utils/logger';

interface Proxy {
    host: string;
    port: string;
    used: boolean;
    error: boolean;
    errorCount: number;
    lastError: number;
    responseTime: number;
}

interface ProxyMetrics {
    totalProxies: number;
    healthyProxies: number;
    errorProxies: number;
    avgResponseTime: number;
    health: 'good' | 'poor' | 'critical';
}

export const BASE_URL_PROXY = `${process.env.PROXY_URL}`;

export class ProxyManager {
    private static redisClient: RedisClient;
    private static initialized: boolean = false;
    private static readonly CACHE_KEY = 'proxyList';
    private static readonly CACHE_NAMESPACE = 'proxy_manager';
    
    private static metrics: ProxyMetrics = {
        totalProxies: 0,
        healthyProxies: 0,
        errorProxies: 0,
        avgResponseTime: 0,
        health: 'good'
    };

    private static async initialize(): Promise<void> {
        if (!this.initialized) {
            try {
                const config = RedisClient.getDefaultConfig();
                this.redisClient = RedisClient.getInstance(config);
                await this.redisClient.connect();
                this.initialized = true;
                logger.info('ProxyManager Redis integration initialized');
            } catch (error) {
                logger.warn('Redis initialization failed, falling back to in-memory cache', { error });
                this.initialized = false;
            }
        }
    }
    
    // Obtém a lista de proxies
    static async getProxyList(): Promise<Proxy[]> {
        await this.initialize();

        // Try to get from Redis cache first
        if (this.initialized) {
            try {
                const cachedProxyList = await this.redisClient.get<Proxy[]>(
                    this.CACHE_KEY, 
                    { namespace: this.CACHE_NAMESPACE }
                );

                if (cachedProxyList && cachedProxyList.length > 0) {
                    this.updateMetrics(cachedProxyList);
                    logger.debug('Proxy list retrieved from Redis cache', { count: cachedProxyList.length });
                    return cachedProxyList;
                }
            } catch (error) {
                logger.warn('Failed to retrieve proxy list from Redis, fetching from API', { error });
            }
        }

        // Busca a lista de proxies da API
        const timeoutManager = TimeoutManager.getInstance();
        const context = timeoutManager.getTimeoutContext('proxy_fetch');
        const timeout = timeoutManager.getAdaptiveTimeout('proxy', context);
        
        try {
            const { data } = await AsyncRetry(
                () => axios.get(BASE_URL_PROXY, { timeout }),
                { retries: 15, maxTimeout: timeout }
            );

            const proxyListArray = data.split('\n');
            const list: Proxy[] = [];

            for (const proxyStr of proxyListArray) {
                const [host, port] = proxyStr.split(':');
                if (host && port) {
                    list.push({ 
                        host, 
                        port, 
                        used: false, 
                        error: false,
                        errorCount: 0,
                        lastError: 0,
                        responseTime: 0
                    });
                }
            }

            // Armazena a lista de proxies no cache
            await this.setCachedProxyList(list);
            this.updateMetrics(list);
            logger.info('Proxy list fetched and cached', { count: list.length });
            return list;
        } catch (error) {
            timeoutManager.recordError('proxy_fetch', ErrorType.PROXY);
            throw error;
        }
    }

    // Seleciona um proxy inteligente da lista
    static async mutateProxy(): Promise<{ host: string; port: string }> {
        let proxyList = await this.getProxyList();
        
        // Filtrar proxies saudáveis (não usados, sem erro ou com poucos erros)
        let possibleProxies = proxyList.filter(proxy => 
            !proxy.used && 
            (!proxy.error || proxy.errorCount < 3) &&
            (Date.now() - proxy.lastError > 60000) // 1 minuto de cooldown
        );

        if (possibleProxies.length === 0) {
            // Reseta proxies com menor número de erros
            const minErrors = Math.min(...proxyList.map(p => p.errorCount));
            possibleProxies = proxyList.filter(p => p.errorCount === minErrors);
            possibleProxies.forEach(proxy => proxy.used = false);
        }

        // Selecionar proxy com melhor performance (menor tempo de resposta)
        const sortedProxies = possibleProxies.sort((a, b) => {
            // Priorizar proxies com menor tempo de resposta e menos erros
            const scoreA = a.responseTime + (a.errorCount * 1000);
            const scoreB = b.responseTime + (b.errorCount * 1000);
            return scoreA - scoreB;
        });
        
        const proxy = sortedProxies[0] || proxyList[0];
        proxy.used = true;

        return { host: proxy.host, port: proxy.port };
    }

    // Bane um proxy (marca como erro)
    static async banProxy(host: string, port: string, responseTime?: number): Promise<void> {
        const proxyList = await this.getProxyList();
        const proxyIndex = proxyList.findIndex(proxy => proxy.host === host && proxy.port === port);

        if (proxyIndex !== -1) {
            const proxy = proxyList[proxyIndex];
            proxy.error = true;
            proxy.errorCount++;
            proxy.lastError = Date.now();
            
            if (responseTime) {
                proxy.responseTime = responseTime;
            }
            
            // Atualizar métricas do timeout manager
            const timeoutManager = TimeoutManager.getInstance();
            timeoutManager.recordError('proxy_usage', ErrorType.PROXY);
            
            console.log(`❌ Proxy banido: ${host}:${port} (${proxy.errorCount} erros)`);
            
            // Atualiza a lista de proxies no cache
            await this.setCachedProxyList(proxyList);
            
            this.updateMetrics(proxyList);
        }
    }
    
    // Registra sucesso de proxy
    static async recordProxySuccess(host: string, port: string, responseTime: number): Promise<void> {
        const proxyList = await this.getProxyList();
        const proxyIndex = proxyList.findIndex(proxy => proxy.host === host && proxy.port === port);

        if (proxyIndex !== -1) {
            const proxy = proxyList[proxyIndex];
            proxy.responseTime = (proxy.responseTime * 0.7) + (responseTime * 0.3); // Média móvel
            proxy.error = false;
            
            // Reduzir contador de erros gradualmente
            if (proxy.errorCount > 0) {
                proxy.errorCount = Math.max(0, proxy.errorCount - 1);
            }
            
            // Atualiza no cache
            await this.setCachedProxyList(proxyList);
            
            this.updateMetrics(proxyList);
        }
    }
    
    // Força rotação de proxy (para casos de anti-bot)
    static async forceRotation(): Promise<void> {
        const proxyList = await this.getProxyList();
        
        // Resetar todos os proxies usados
        proxyList.forEach(proxy => proxy.used = false);
        
        // Atualizar cache
        await this.setCachedProxyList(proxyList);
        
        console.log('🔄 Rotação de proxy forçada');
    }
    
    // Atualiza métricas do sistema
    private static updateMetrics(proxyList: Proxy[]): void {
        const totalProxies = proxyList.length;
        const errorProxies = proxyList.filter(p => p.error).length;
        const healthyProxies = totalProxies - errorProxies;
        const avgResponseTime = proxyList.reduce((acc, p) => acc + p.responseTime, 0) / totalProxies;
        
        let health: 'good' | 'poor' | 'critical';
        const healthyPercentage = healthyProxies / totalProxies;
        
        if (healthyPercentage > 0.7) {
            health = 'good';
        } else if (healthyPercentage > 0.3) {
            health = 'poor';
        } else {
            health = 'critical';
        }
        
        this.metrics = {
            totalProxies,
            healthyProxies,
            errorProxies,
            avgResponseTime,
            health
        };
        
        // Atualizar timeout manager com saúde do proxy
        const timeoutManager = TimeoutManager.getInstance();
        timeoutManager.updateProxyHealth(health);
    }
    
    // Obtém métricas atuais
    static getMetrics(): ProxyMetrics {
        return { ...this.metrics };
    }
    
    // Limpa cache e recarrega proxies
    static async refreshProxyList(): Promise<void> {
        await this.initialize();
        
        if (this.initialized) {
            try {
                await this.redisClient.delete(this.CACHE_KEY, { namespace: this.CACHE_NAMESPACE });
            } catch (error) {
                logger.warn('Failed to clear cache during refresh, continuing anyway', { error });
            }
        }
        
        await this.getProxyList();
        console.log('🔄 Lista de proxies atualizada');
    }
    
    // Obtém estatísticas detalhadas
    static async getDetailedStats(): Promise<{
        metrics: ProxyMetrics;
        topProxies: { host: string; port: string; responseTime: number; errorCount: number }[];
        worstProxies: { host: string; port: string; responseTime: number; errorCount: number }[];
    }> {
        const proxyList = await this.getProxyList();
        
        const sortedByPerformance = proxyList
            .map(p => ({ 
                host: p.host, 
                port: p.port, 
                responseTime: p.responseTime, 
                errorCount: p.errorCount 
            }))
            .sort((a, b) => (a.responseTime + a.errorCount * 1000) - (b.responseTime + b.errorCount * 1000));
        
        return {
            metrics: this.getMetrics(),
            topProxies: sortedByPerformance.slice(0, 5),
            worstProxies: sortedByPerformance.slice(-5).reverse()
        };
    }

    // Helper methods for Redis cache operations
    private static async setCachedProxyList(proxyList: Proxy[]): Promise<void> {
        if (this.initialized) {
            try {
                await this.redisClient.set(
                    this.CACHE_KEY, 
                    proxyList, 
                    { 
                        namespace: this.CACHE_NAMESPACE,
                        ttl: parseInt(process.env.REDIS_TTL || '300') // 5 minutes default
                    }
                );
                logger.debug('Proxy list cached in Redis', { count: proxyList.length });
            } catch (error) {
                logger.warn('Failed to cache proxy list in Redis', { error });
            }
        }
    }

    // Get Redis health status
    static async getRedisHealth(): Promise<{
        enabled: boolean;
        connected: boolean;
        latency?: number;
        cacheHits?: number;
        cacheMisses?: number;
    }> {
        if (!this.initialized) {
            return { enabled: false, connected: false };
        }

        try {
            const health = await this.redisClient.healthCheck();
            return {
                enabled: true,
                connected: health.connected,
                latency: health.latency,
                cacheHits: health.stats?.keyspace_hits ? parseInt(health.stats.keyspace_hits) : undefined,
                cacheMisses: health.stats?.keyspace_misses ? parseInt(health.stats.keyspace_misses) : undefined
            };
        } catch (error) {
            logger.error('Redis health check failed', { error });
            return { enabled: true, connected: false };
        }
    }

    // Clear all cached data
    static async clearCache(): Promise<void> {
        await this.initialize();
        
        if (this.initialized) {
            try {
                await this.redisClient.flushNamespace(this.CACHE_NAMESPACE);
                logger.info('ProxyManager cache cleared');
            } catch (error) {
                logger.error('Failed to clear ProxyManager cache', { error });
            }
        }
    }
}