import { RedisClient } from '../services/redis_client';
import { ProxyManager } from '../services/proxy_manager';
import logger from './logger';

export interface HealthStatus {
    status: 'healthy' | 'degraded' | 'unhealthy';
    timestamp: string;
    uptime: number;
    redis: {
        enabled: boolean;
        connected: boolean;
        latency?: number;
        cacheHits?: number;
        cacheMisses?: number;
        hitRate?: string;
    };
    proxy: {
        totalProxies: number;
        healthyProxies: number;
        errorProxies: number;
        avgResponseTime: number;
        health: 'good' | 'poor' | 'critical';
    };
    system: {
        nodeVersion: string;
        platform: string;
        arch: string;
        memoryUsage: NodeJS.MemoryUsage;
        loadAverage?: number[];
    };
}

export class HealthChecker {
    private static startTime = Date.now();

    static async getHealthStatus(): Promise<HealthStatus> {
        const timestamp = new Date().toISOString();
        const uptime = Date.now() - this.startTime;

        try {
            // Get Redis health
            const redisHealth = await ProxyManager.getRedisHealth();
            
            // Calculate cache hit rate
            let hitRate: string | undefined;
            if (redisHealth.cacheHits !== undefined && redisHealth.cacheMisses !== undefined) {
                const total = redisHealth.cacheHits + redisHealth.cacheMisses;
                hitRate = total > 0 ? `${((redisHealth.cacheHits / total) * 100).toFixed(1)}%` : '0%';
            }

            // Get proxy metrics
            const proxyMetrics = ProxyManager.getMetrics();

            // Get system info
            const systemInfo = {
                nodeVersion: process.version,
                platform: process.platform,
                arch: process.arch,
                memoryUsage: process.memoryUsage(),
                loadAverage: process.platform !== 'win32' ? require('os').loadavg() : undefined
            };

            // Determine overall health status
            let status: 'healthy' | 'degraded' | 'unhealthy';
            
            if (!redisHealth.connected && redisHealth.enabled) {
                status = 'degraded';
            } else if (proxyMetrics.health === 'critical') {
                status = 'unhealthy';
            } else if (proxyMetrics.health === 'poor') {
                status = 'degraded';
            } else {
                status = 'healthy';
            }

            const healthStatus: HealthStatus = {
                status,
                timestamp,
                uptime,
                redis: {
                    enabled: redisHealth.enabled,
                    connected: redisHealth.connected,
                    latency: redisHealth.latency,
                    cacheHits: redisHealth.cacheHits,
                    cacheMisses: redisHealth.cacheMisses,
                    hitRate
                },
                proxy: proxyMetrics,
                system: systemInfo
            };

            logger.debug('Health check completed', { status: healthStatus.status });
            return healthStatus;

        } catch (error) {
            logger.error('Health check failed', { error });
            
            return {
                status: 'unhealthy',
                timestamp,
                uptime,
                redis: {
                    enabled: false,
                    connected: false
                },
                proxy: {
                    totalProxies: 0,
                    healthyProxies: 0,
                    errorProxies: 0,
                    avgResponseTime: 0,
                    health: 'critical'
                },
                system: {
                    nodeVersion: process.version,
                    platform: process.platform,
                    arch: process.arch,
                    memoryUsage: process.memoryUsage()
                }
            };
        }
    }

    static async performDeepHealthCheck(): Promise<{
        overall: HealthStatus;
        details: {
            redisConnectivity: boolean;
            redisLatency: number | null;
            proxyListFetch: boolean;
            proxyListSize: number;
            memoryPressure: boolean;
        };
    }> {
        const overall = await this.getHealthStatus();
        const details = {
            redisConnectivity: overall.redis.connected,
            redisLatency: overall.redis.latency || null,
            proxyListFetch: false,
            proxyListSize: 0,
            memoryPressure: false
        };

        try {
            // Test proxy list fetch
            const proxies = await ProxyManager.getProxyList();
            details.proxyListFetch = true;
            details.proxyListSize = proxies.length;
        } catch (error) {
            logger.warn('Proxy list fetch failed during health check', { error });
        }

        // Check memory pressure (>80% of heap limit is concerning)
        const memUsage = process.memoryUsage();
        const heapUsedPercent = (memUsage.heapUsed / memUsage.heapTotal) * 100;
        details.memoryPressure = heapUsedPercent > 80;

        return { overall, details };
    }

    static getSimpleStatus(): { status: string; uptime: number } {
        return {
            status: 'ok',
            uptime: Date.now() - this.startTime
        };
    }
}