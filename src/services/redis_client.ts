import Redis from 'ioredis';
import logger from '../utils/logger';

export interface RedisConfig {
    host: string;
    port: number;
    password?: string;
    db: number;
    ttl: number;
}

export interface CacheOptions {
    ttl?: number;
    namespace?: string;
}

export class RedisClient {
    private static instance: RedisClient;
    private redis: Redis;
    private config: RedisConfig;
    private isConnected: boolean = false;

    private constructor(config: RedisConfig) {
        this.config = config;
        this.redis = new Redis({
            host: config.host,
            port: config.port,
            password: config.password || undefined,
            db: config.db,
            maxRetriesPerRequest: 3,
            lazyConnect: true,
            keepAlive: 30000,
            connectTimeout: 10000,
        });

        this.setupEventHandlers();
    }

    static getInstance(config?: RedisConfig): RedisClient {
        if (!RedisClient.instance) {
            if (!config) {
                throw new Error('RedisClient configuration is required for first initialization');
            }
            RedisClient.instance = new RedisClient(config);
        }
        return RedisClient.instance;
    }

    static getDefaultConfig(): RedisConfig {
        return {
            host: process.env.REDIS_HOST || 'localhost',
            port: parseInt(process.env.REDIS_PORT || '6379'),
            password: process.env.REDIS_PASSWORD || undefined,
            db: parseInt(process.env.REDIS_DB || '0'),
            ttl: parseInt(process.env.REDIS_TTL || '300'), // 5 minutes default
        };
    }

    private setupEventHandlers(): void {
        this.redis.on('connect', () => {
            this.isConnected = true;
            logger.info('Redis connected successfully', {
                host: this.config.host,
                port: this.config.port,
                db: this.config.db
            });
        });

        this.redis.on('ready', () => {
            logger.info('Redis ready for operations');
        });

        this.redis.on('error', (error) => {
            this.isConnected = false;
            logger.error('Redis connection error', { error: error.message });
        });

        this.redis.on('close', () => {
            this.isConnected = false;
            logger.warn('Redis connection closed');
        });

        this.redis.on('reconnecting', () => {
            logger.info('Redis reconnecting...');
        });
    }

    async connect(): Promise<void> {
        try {
            await this.redis.connect();
            this.isConnected = true;
        } catch (error) {
            this.isConnected = false;
            logger.error('Failed to connect to Redis', { error });
            throw error;
        }
    }

    async disconnect(): Promise<void> {
        try {
            await this.redis.disconnect();
            this.isConnected = false;
            logger.info('Redis disconnected');
        } catch (error) {
            logger.error('Error disconnecting from Redis', { error });
            throw error;
        }
    }

    private formatKey(key: string, namespace?: string): string {
        const prefix = 'manga_scraper';
        const ns = namespace ? `${namespace}:` : '';
        return `${prefix}:${ns}${key}`;
    }

    async set<T>(key: string, value: T, options?: CacheOptions): Promise<void> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const serializedValue = JSON.stringify(value);
            const ttl = options?.ttl || this.config.ttl;

            if (ttl > 0) {
                await this.redis.setex(formattedKey, ttl, serializedValue);
            } else {
                await this.redis.set(formattedKey, serializedValue);
            }

            logger.debug('Redis SET operation', { key: formattedKey, ttl });
        } catch (error) {
            logger.error('Redis SET error', { key, error });
            throw error;
        }
    }

    async get<T>(key: string, options?: CacheOptions): Promise<T | null> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const value = await this.redis.get(formattedKey);

            if (value === null) {
                return null;
            }

            const parsedValue = JSON.parse(value) as T;
            logger.debug('Redis GET operation', { key: formattedKey, found: true });
            return parsedValue;
        } catch (error) {
            logger.error('Redis GET error', { key, error });
            return null; // Return null on error to allow fallback behavior
        }
    }

    async delete(key: string, options?: CacheOptions): Promise<boolean> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const result = await this.redis.del(formattedKey);
            
            logger.debug('Redis DELETE operation', { key: formattedKey, deleted: result > 0 });
            return result > 0;
        } catch (error) {
            logger.error('Redis DELETE error', { key, error });
            return false;
        }
    }

    async exists(key: string, options?: CacheOptions): Promise<boolean> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const result = await this.redis.exists(formattedKey);
            return result === 1;
        } catch (error) {
            logger.error('Redis EXISTS error', { key, error });
            return false;
        }
    }

    async expire(key: string, ttl: number, options?: CacheOptions): Promise<boolean> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const result = await this.redis.expire(formattedKey, ttl);
            return result === 1;
        } catch (error) {
            logger.error('Redis EXPIRE error', { key, ttl, error });
            return false;
        }
    }

    async keys(pattern: string, options?: CacheOptions): Promise<string[]> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedPattern = this.formatKey(pattern, options?.namespace);
            const keys = await this.redis.keys(formattedPattern);
            return keys;
        } catch (error) {
            logger.error('Redis KEYS error', { pattern, error });
            return [];
        }
    }

    async flushNamespace(namespace: string): Promise<void> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const pattern = this.formatKey('*', namespace);
            const keys = await this.redis.keys(pattern);
            
            if (keys.length > 0) {
                await this.redis.del(...keys);
                logger.info('Flushed Redis namespace', { namespace, keysDeleted: keys.length });
            }
        } catch (error) {
            logger.error('Redis namespace flush error', { namespace, error });
            throw error;
        }
    }

    async healthCheck(): Promise<{
        connected: boolean;
        latency?: number;
        memory?: any;
        stats?: any;
    }> {
        try {
            if (!this.isConnected) {
                await this.connect();
            }

            const start = Date.now();
            const pong = await this.redis.ping();
            const latency = Date.now() - start;

            if (pong !== 'PONG') {
                throw new Error('Invalid PING response');
            }

            // Get Redis info
            const info = await this.redis.info('memory');
            const memoryInfo = this.parseRedisInfo(info);

            const stats = await this.redis.info('stats');
            const statsInfo = this.parseRedisInfo(stats);

            return {
                connected: true,
                latency,
                memory: memoryInfo,
                stats: statsInfo
            };
        } catch (error) {
            logger.error('Redis health check failed', { error });
            return {
                connected: false
            };
        }
    }

    private parseRedisInfo(info: string): any {
        const result: any = {};
        const lines = info.split('\r\n');
        
        for (const line of lines) {
            if (line.includes(':')) {
                const [key, value] = line.split(':');
                result[key] = value;
            }
        }
        
        return result;
    }

    // Advanced operations for specific use cases
    async increment(key: string, options?: CacheOptions): Promise<number> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const result = await this.redis.incr(formattedKey);
            
            // Set TTL if specified
            if (options?.ttl) {
                await this.redis.expire(formattedKey, options.ttl);
            }
            
            return result;
        } catch (error) {
            logger.error('Redis INCREMENT error', { key, error });
            throw error;
        }
    }

    async setList<T>(key: string, values: T[], options?: CacheOptions): Promise<void> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const serializedValues = values.map(v => JSON.stringify(v));
            
            // Clear existing list and add new values
            await this.redis.del(formattedKey);
            if (serializedValues.length > 0) {
                await this.redis.rpush(formattedKey, ...serializedValues);
                
                if (options?.ttl) {
                    await this.redis.expire(formattedKey, options.ttl);
                }
            }
        } catch (error) {
            logger.error('Redis SET LIST error', { key, error });
            throw error;
        }
    }

    async getList<T>(key: string, options?: CacheOptions): Promise<T[]> {
        if (!this.isConnected) {
            await this.connect();
        }

        try {
            const formattedKey = this.formatKey(key, options?.namespace);
            const values = await this.redis.lrange(formattedKey, 0, -1);
            
            return values.map(v => JSON.parse(v) as T);
        } catch (error) {
            logger.error('Redis GET LIST error', { key, error });
            return [];
        }
    }

    getConnectionStatus(): boolean {
        return this.isConnected;
    }

    getConfig(): RedisConfig {
        return { ...this.config };
    }
}