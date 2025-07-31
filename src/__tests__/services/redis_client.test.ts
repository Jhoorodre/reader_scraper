import { RedisClient, RedisConfig } from '../../services/redis_client';

// Mock Redis
jest.mock('ioredis', () => {
    return class MockRedis {
        private storage = new Map<string, { value: string; ttl?: number; expiry?: number }>();
        private connected = false;
        
        constructor() {
            // Simulate async connection
            setTimeout(() => {
                this.connected = true;
                this.emit('connect');
                this.emit('ready');
            }, 10);
        }

        on(event: string, callback: Function) {
            // Store event listeners if needed
        }

        async connect() {
            this.connected = true;
            return Promise.resolve();
        }

        async disconnect() {
            this.connected = false;
            return Promise.resolve();
        }

        async ping() {
            if (!this.connected) throw new Error('Not connected');
            return 'PONG';
        }

        async setex(key: string, ttl: number, value: string) {
            this.storage.set(key, {
                value,
                ttl,
                expiry: Date.now() + (ttl * 1000)
            });
        }

        async set(key: string, value: string) {
            this.storage.set(key, { value });
        }

        async get(key: string) {
            const item = this.storage.get(key);
            if (!item) return null;
            
            // Check expiry
            if (item.expiry && Date.now() > item.expiry) {
                this.storage.delete(key);
                return null;
            }
            
            return item.value;
        }

        async del(...keys: string[]) {
            let deleted = 0;
            keys.forEach(key => {
                if (this.storage.delete(key)) deleted++;
            });
            return deleted;
        }

        async exists(key: string) {
            return this.storage.has(key) ? 1 : 0;
        }

        async expire(key: string, ttl: number) {
            const item = this.storage.get(key);
            if (!item) return 0;
            
            item.expiry = Date.now() + (ttl * 1000);
            this.storage.set(key, item);
            return 1;
        }

        async keys(pattern: string) {
            const regex = new RegExp(pattern.replace('*', '.*'));
            return Array.from(this.storage.keys()).filter(key => regex.test(key));
        }

        async incr(key: string) {
            const current = await this.get(key);
            const value = current ? parseInt(current) + 1 : 1;
            await this.set(key, value.toString());
            return value;
        }

        async rpush(key: string, ...values: string[]) {
            // Simple list implementation for testing
            const current = await this.get(key);
            const list = current ? JSON.parse(current) : [];
            list.push(...values);
            await this.set(key, JSON.stringify(list));
            return list.length;
        }

        async lrange(key: string, start: number, stop: number) {
            const current = await this.get(key);
            if (!current) return [];
            
            const list = JSON.parse(current);
            if (stop === -1) return list.slice(start);
            return list.slice(start, stop + 1);
        }

        async info(section: string) {
            return `# ${section}\nused_memory:1024\nkeyspace_hits:100\nkeyspace_misses:10`;
        }

        emit(event: string, ...args: any[]) {
            // Mock event emitter
        }
    };
});

describe('RedisClient', () => {
    let redisClient: RedisClient;
    let config: RedisConfig;

    beforeEach(() => {
        config = {
            host: 'localhost',
            port: 6379,
            password: undefined,
            db: 0,
            ttl: 300
        };
        
        // Reset singleton
        (RedisClient as any).instance = undefined;
    });

    afterEach(async () => {
        if (redisClient) {
            await redisClient.disconnect();
        }
    });

    describe('Initialization', () => {
        it('should create a singleton instance', () => {
            const instance1 = RedisClient.getInstance(config);
            const instance2 = RedisClient.getInstance();
            
            expect(instance1).toBe(instance2);
        });

        it('should throw error if no config provided on first initialization', () => {
            expect(() => RedisClient.getInstance()).toThrow(
                'RedisClient configuration is required for first initialization'
            );
        });

        it('should get default config from environment', () => {
            process.env.REDIS_HOST = 'test-host';
            process.env.REDIS_PORT = '6380';
            process.env.REDIS_DB = '1';
            process.env.REDIS_TTL = '600';

            const defaultConfig = RedisClient.getDefaultConfig();
            
            expect(defaultConfig).toEqual({
                host: 'test-host',
                port: 6380,
                password: undefined,
                db: 1,
                ttl: 600
            });

            // Cleanup
            delete process.env.REDIS_HOST;
            delete process.env.REDIS_PORT;
            delete process.env.REDIS_DB;
            delete process.env.REDIS_TTL;
        });
    });

    describe('Connection Management', () => {
        beforeEach(() => {
            redisClient = RedisClient.getInstance(config);
        });

        it('should connect successfully', async () => {
            await expect(redisClient.connect()).resolves.not.toThrow();
            expect(redisClient.getConnectionStatus()).toBe(true);
        });

        it('should disconnect successfully', async () => {
            await redisClient.connect();
            await expect(redisClient.disconnect()).resolves.not.toThrow();
        });
    });

    describe('Basic Operations', () => {
        beforeEach(async () => {
            redisClient = RedisClient.getInstance(config);
            await redisClient.connect();
        });

        it('should set and get values', async () => {
            const testData = { name: 'test', value: 123 };
            
            await redisClient.set('test-key', testData);
            const result = await redisClient.get('test-key');
            
            expect(result).toEqual(testData);
        });

        it('should handle null values', async () => {
            const result = await redisClient.get('non-existent-key');
            expect(result).toBeNull();
        });

        it('should set values with TTL', async () => {
            const testData = { temp: true };
            
            await redisClient.set('temp-key', testData, { ttl: 1 });
            const result = await redisClient.get('temp-key');
            
            expect(result).toEqual(testData);
        });

        it('should delete values', async () => {
            await redisClient.set('delete-me', 'test');
            
            const deleted = await redisClient.delete('delete-me');
            expect(deleted).toBe(true);
            
            const result = await redisClient.get('delete-me');
            expect(result).toBeNull();
        });

        it('should check if key exists', async () => {
            await redisClient.set('exists-test', 'value');
            
            const exists = await redisClient.exists('exists-test');
            expect(exists).toBe(true);
            
            const notExists = await redisClient.exists('not-exists');
            expect(notExists).toBe(false);
        });

        it('should set expiry on existing keys', async () => {
            await redisClient.set('expire-test', 'value');
            
            const result = await redisClient.expire('expire-test', 60);
            expect(result).toBe(true);
        });
    });

    describe('Namespaced Operations', () => {
        beforeEach(async () => {
            redisClient = RedisClient.getInstance(config);
            await redisClient.connect();
        });

        it('should handle namespaced keys', async () => {
            const testData = { namespaced: true };
            
            await redisClient.set('test', testData, { namespace: 'app1' });
            await redisClient.set('test', { namespaced: false }, { namespace: 'app2' });
            
            const result1 = await redisClient.get('test', { namespace: 'app1' });
            const result2 = await redisClient.get('test', { namespace: 'app2' });
            
            expect(result1).toEqual({ namespaced: true });
            expect(result2).toEqual({ namespaced: false });
        });

        it('should flush namespace', async () => {
            await redisClient.set('key1', 'value1', { namespace: 'test-ns' });
            await redisClient.set('key2', 'value2', { namespace: 'test-ns' });
            await redisClient.set('key3', 'value3', { namespace: 'other-ns' });
            
            await redisClient.flushNamespace('test-ns');
            
            const result1 = await redisClient.get('key1', { namespace: 'test-ns' });
            const result2 = await redisClient.get('key2', { namespace: 'test-ns' });
            const result3 = await redisClient.get('key3', { namespace: 'other-ns' });
            
            expect(result1).toBeNull();
            expect(result2).toBeNull();
            expect(result3).toBe('value3');
        });
    });

    describe('Advanced Operations', () => {
        beforeEach(async () => {
            redisClient = RedisClient.getInstance(config);
            await redisClient.connect();
        });

        it('should increment counters', async () => {
            const result1 = await redisClient.increment('counter');
            const result2 = await redisClient.increment('counter');
            
            expect(result1).toBe(1);
            expect(result2).toBe(2);
        });

        it('should handle lists', async () => {
            const testList = ['item1', 'item2', 'item3'];
            
            await redisClient.setList('test-list', testList);
            const result = await redisClient.getList('test-list');
            
            expect(result).toEqual(testList);
        });

        it('should return empty array for non-existent list', async () => {
            const result = await redisClient.getList('non-existent-list');
            expect(result).toEqual([]);
        });
    });

    describe('Health Check', () => {
        beforeEach(async () => {
            redisClient = RedisClient.getInstance(config);
            await redisClient.connect();
        });

        it('should perform health check', async () => {
            const health = await redisClient.healthCheck();
            
            expect(health.connected).toBe(true);
            expect(health.latency).toBeGreaterThanOrEqual(0);
            expect(health.memory).toBeDefined();
            expect(health.stats).toBeDefined();
        });
    });

    describe('Error Handling', () => {
        beforeEach(() => {
            redisClient = RedisClient.getInstance(config);
        });

        it('should handle connection errors gracefully', async () => {
            // Mock connection failure
            const mockRedis = (redisClient as any).redis;
            mockRedis.connect = jest.fn().mockRejectedValue(new Error('Connection failed'));
            
            await expect(redisClient.connect()).rejects.toThrow('Connection failed');
        });

        it('should return null on get errors', async () => {
            await redisClient.connect();
            
            // Mock get error
            const mockRedis = (redisClient as any).redis;
            mockRedis.get = jest.fn().mockRejectedValue(new Error('Get failed'));
            
            const result = await redisClient.get('test-key');
            expect(result).toBeNull();
        });

        it('should return false on operation errors', async () => {
            await redisClient.connect();
            
            // Mock delete error
            const mockRedis = (redisClient as any).redis;
            mockRedis.del = jest.fn().mockRejectedValue(new Error('Delete failed'));
            
            const result = await redisClient.delete('test-key');
            expect(result).toBe(false);
        });
    });
});