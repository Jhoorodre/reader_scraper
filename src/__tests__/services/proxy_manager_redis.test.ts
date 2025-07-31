import { ProxyManager } from '../../services/proxy_manager';
import { RedisClient } from '../../services/redis_client';
import axios from 'axios';

// Mock dependencies
jest.mock('axios');
jest.mock('../../services/redis_client');
jest.mock('../../services/timeout_manager', () => ({
    TimeoutManager: {
        getInstance: () => ({
            getTimeoutContext: () => ({}),
            getAdaptiveTimeout: () => 30000,
            recordError: jest.fn(),
            updateProxyHealth: jest.fn()
        })
    },
    ErrorType: {
        PROXY: 'PROXY'
    }
}));

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('ProxyManager with Redis Integration', () => {
    let mockRedisInstance: jest.Mocked<RedisClient>;
    
    beforeEach(() => {
        jest.clearAllMocks();
        
        // Mock Redis instance
        mockRedisInstance = {
            connect: jest.fn().mockResolvedValue(undefined),
            get: jest.fn(),
            set: jest.fn(),
            delete: jest.fn(),
            healthCheck: jest.fn(),
            flushNamespace: jest.fn(),
            getConnectionStatus: jest.fn().mockReturnValue(true)
        } as any;

        // Mock RedisClient static methods
        (RedisClient.getInstance as jest.Mock) = jest.fn().mockReturnValue(mockRedisInstance);
        (RedisClient.getDefaultConfig as jest.Mock) = jest.fn().mockReturnValue({
            host: 'localhost',
            port: 6379,
            password: undefined,
            db: 0,
            ttl: 300
        });

        // Reset ProxyManager internal state
        (ProxyManager as any).initialized = false;
        (ProxyManager as any).redisClient = undefined;

        // Mock environment variables
        process.env.PROXY_URL = 'http://test-proxy-api.com/proxies';
        process.env.REDIS_TTL = '300';
        
        // Mock BASE_URL_PROXY
        const proxyManagerModule = require('../../services/proxy_manager');
        proxyManagerModule.BASE_URL_PROXY = 'http://test-proxy-api.com/proxies';
    });

    describe('Redis Integration', () => {
        it('should initialize Redis client', async () => {
            mockRedisInstance.get.mockResolvedValue(null);
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080\n192.168.1.2:8080'
            });

            await ProxyManager.getProxyList();

            expect(RedisClient.getInstance).toHaveBeenCalledWith({
                host: 'localhost',
                port: 6379,
                password: undefined,
                db: 0,
                ttl: 300
            });
            expect(mockRedisInstance.connect).toHaveBeenCalled();
        });

        it('should fallback gracefully when Redis fails to initialize', async () => {
            mockRedisInstance.connect.mockRejectedValue(new Error('Redis connection failed'));
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080\n192.168.1.2:8080'
            });

            const proxies = await ProxyManager.getProxyList();

            expect(proxies).toHaveLength(2);
            expect(proxies[0]).toEqual({
                host: '192.168.1.1',
                port: '8080',
                used: false,
                error: false,
                errorCount: 0,
                lastError: 0,
                responseTime: 0
            });
        });
    });

    describe('Cache Operations', () => {
        beforeEach(async () => {
            // Ensure Redis is initialized
            await (ProxyManager as any).initialize();
        });

        it('should retrieve proxy list from Redis cache', async () => {
            const cachedProxies = [
                {
                    host: '192.168.1.1',
                    port: '8080',
                    used: false,
                    error: false,
                    errorCount: 0,
                    lastError: 0,
                    responseTime: 100
                }
            ];

            mockRedisInstance.get.mockResolvedValue(cachedProxies);

            const proxies = await ProxyManager.getProxyList();

            expect(mockRedisInstance.get).toHaveBeenCalledWith(
                'proxyList',
                { namespace: 'proxy_manager' }
            );
            expect(proxies).toEqual(cachedProxies);
            expect(mockedAxios.get).not.toHaveBeenCalled();
        });

        it('should fetch from API when cache is empty', async () => {
            mockRedisInstance.get.mockResolvedValue(null);
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080\n192.168.1.2:8080'
            });

            const proxies = await ProxyManager.getProxyList();

            expect(mockRedisInstance.get).toHaveBeenCalled();
            expect(mockedAxios.get).toHaveBeenCalledWith(
                process.env.PROXY_URL,
                { timeout: 30000 }
            );
            expect(proxies).toHaveLength(2);
        });

        it('should cache proxy list after fetching from API', async () => {
            mockRedisInstance.get.mockResolvedValue(null);
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080\n192.168.1.2:8080'
            });

            await ProxyManager.getProxyList();

            expect(mockRedisInstance.set).toHaveBeenCalledWith(
                'proxyList',
                expect.arrayContaining([
                    expect.objectContaining({
                        host: '192.168.1.1',
                        port: '8080'
                    }),
                    expect.objectContaining({
                        host: '192.168.1.2',
                        port: '8080'
                    })
                ]),
                {
                    namespace: 'proxy_manager',
                    ttl: 300
                }
            );
        });

        it('should handle Redis cache errors gracefully', async () => {
            mockRedisInstance.get.mockRejectedValue(new Error('Redis get failed'));
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080'
            });

            const proxies = await ProxyManager.getProxyList();

            expect(proxies).toHaveLength(1);
            expect(mockedAxios.get).toHaveBeenCalled();
        });
    });

    describe('Proxy Management with Redis', () => {
        beforeEach(async () => {
            await (ProxyManager as any).initialize();
            mockRedisInstance.get.mockResolvedValue([
                {
                    host: '192.168.1.1',
                    port: '8080',
                    used: false,
                    error: false,
                    errorCount: 0,
                    lastError: 0,
                    responseTime: 100
                },
                {
                    host: '192.168.1.2',
                    port: '8080',
                    used: false,
                    error: false,
                    errorCount: 0,
                    lastError: 0,
                    responseTime: 200
                }
            ]);
        });

        it('should update cache when banning proxy', async () => {
            await ProxyManager.banProxy('192.168.1.1', '8080', 500);

            expect(mockRedisInstance.set).toHaveBeenCalledWith(
                'proxyList',
                expect.arrayContaining([
                    expect.objectContaining({
                        host: '192.168.1.1',
                        port: '8080',
                        error: true,
                        errorCount: 1,
                        responseTime: 500
                    })
                ]),
                {
                    namespace: 'proxy_manager',
                    ttl: 300
                }
            );
        });

        it('should update cache when recording proxy success', async () => {
            await ProxyManager.recordProxySuccess('192.168.1.1', '8080', 50);

            expect(mockRedisInstance.set).toHaveBeenCalledWith(
                'proxyList',
                expect.arrayContaining([
                    expect.objectContaining({
                        host: '192.168.1.1',
                        port: '8080',
                        error: false,
                        responseTime: expect.any(Number)
                    })
                ]),
                {
                    namespace: 'proxy_manager',
                    ttl: 300
                }
            );
        });

        it('should update cache when forcing rotation', async () => {
            await ProxyManager.forceRotation();

            expect(mockRedisInstance.set).toHaveBeenCalledWith(
                'proxyList',
                expect.arrayContaining([
                    expect.objectContaining({
                        used: false
                    })
                ]),
                {
                    namespace: 'proxy_manager',
                    ttl: 300
                }
            );
        });
    });

    describe('Cache Management', () => {
        beforeEach(async () => {
            await (ProxyManager as any).initialize();
        });

        it('should refresh proxy list by clearing cache', async () => {
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080'
            });

            await ProxyManager.refreshProxyList();

            expect(mockRedisInstance.delete).toHaveBeenCalledWith(
                'proxyList',
                { namespace: 'proxy_manager' }
            );
            expect(mockedAxios.get).toHaveBeenCalled();
        });

        it('should clear all cached data', async () => {
            await ProxyManager.clearCache();

            expect(mockRedisInstance.flushNamespace).toHaveBeenCalledWith('proxy_manager');
        });
    });

    describe('Redis Health Monitoring', () => {
        beforeEach(async () => {
            await (ProxyManager as any).initialize();
        });

        it('should return Redis health status', async () => {
            mockRedisInstance.healthCheck.mockResolvedValue({
                connected: true,
                latency: 5,
                memory: { used_memory: '1024' },
                stats: { keyspace_hits: '100', keyspace_misses: '10' }
            });

            const health = await ProxyManager.getRedisHealth();

            expect(health).toEqual({
                enabled: true,
                connected: true,
                latency: 5,
                cacheHits: 100,
                cacheMisses: 10
            });
        });

        it('should handle Redis not initialized', async () => {
            (ProxyManager as any).initialized = false;

            const health = await ProxyManager.getRedisHealth();

            expect(health).toEqual({
                enabled: false,
                connected: false
            });
        });

        it('should handle Redis health check errors', async () => {
            mockRedisInstance.healthCheck.mockRejectedValue(new Error('Health check failed'));

            const health = await ProxyManager.getRedisHealth();

            expect(health).toEqual({
                enabled: true,
                connected: false
            });
        });
    });

    describe('Error Handling', () => {
        it('should handle cache set errors gracefully', async () => {
            mockRedisInstance.get.mockResolvedValue(null);
            mockRedisInstance.set.mockRejectedValue(new Error('Cache set failed'));
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080'
            });

            // Should not throw error
            await expect(ProxyManager.getProxyList()).resolves.toBeDefined();
        });

        it('should handle cache delete errors gracefully', async () => {
            mockRedisInstance.delete.mockRejectedValue(new Error('Cache delete failed'));
            mockedAxios.get.mockResolvedValue({
                data: '192.168.1.1:8080'
            });

            // Should not throw error
            await expect(ProxyManager.refreshProxyList()).resolves.toBe(undefined);
        });

        it('should handle namespace flush errors gracefully', async () => {
            mockRedisInstance.flushNamespace.mockRejectedValue(new Error('Flush failed'));

            // Should not throw error
            await expect(ProxyManager.clearCache()).resolves.toBe(undefined);
        });
    });
});