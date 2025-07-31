import { ProxyManager } from '../../services/proxy_manager';
import axios from 'axios';

jest.mock('axios');
jest.mock('lru-cache');

describe('ProxyManager', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('should fetch and cache proxy list', async () => {
        const mockAxiosGet = jest.spyOn(axios, 'get').mockResolvedValue({ data: '127.0.0.1:8080\n192.168.1.1:8081' });

        const proxies = await ProxyManager.getProxyList();

        expect(mockAxiosGet).toHaveBeenCalledWith(expect.any(String), { timeout: expect.any(Number) });
        expect(proxies).toEqual([
            { host: '127.0.0.1', port: '8080', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
            { host: '192.168.1.1', port: '8081', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
        ]);
    });

    it('should select a random proxy', async () => {
        jest.spyOn(ProxyManager, 'getProxyList').mockResolvedValue([
            { host: '127.0.0.1', port: '8080', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
            { host: '192.168.1.1', port: '8081', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
        ]);

        const proxy = await ProxyManager.mutateProxy();

        expect(proxy).toHaveProperty('host');
        expect(proxy).toHaveProperty('port');
    });

    it('should ban a proxy', async () => {
        jest.spyOn(ProxyManager, 'getProxyList').mockResolvedValue([
            { host: '127.0.0.1', port: '8080', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
            { host: '192.168.1.1', port: '8081', used: false, error: false, errorCount: 0, lastError: 0, responseTime: 0 },
        ]);

        await ProxyManager.banProxy('127.0.0.1', '8080');

        const proxies = await ProxyManager.getProxyList();
        expect(proxies[0].error).toBe(true);
    });
});