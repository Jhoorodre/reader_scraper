import axios from 'axios';
import AsyncRetry from 'async-retry';
import { LRUCache } from 'lru-cache'

interface Proxy {
    host: string;
    port: string;
    used: boolean;
    error: boolean;
}

export const BASE_URL_PROXY = `${process.env.PROXY_URL}`;

// Configuração do LRU Cache
const cache = new LRUCache<string, Proxy[]>({
    max: 100, // Número máximo de itens no cache
    ttl: 1000 * 60 * 5, // 5 minutos de validade para cada item no cache
});

export class ProxyManager {
    // Obtém a lista de proxies
    static async getProxyList(): Promise<Proxy[]> {
        const cacheKey = 'proxyList';
        const cachedProxyList = cache.get(cacheKey);

        // Retorna a lista de proxies do cache, se disponível e válida
        if (cachedProxyList) {
            return cachedProxyList;
        }

        // Busca a lista de proxies da API
        const { data } = await AsyncRetry(
            () => axios.get(BASE_URL_PROXY, { timeout: 1000 * 60 * 10 }),
            { retries: 15, maxTimeout: 1000 * 60 * 10 }
        );

        const proxyListArray = data.split('\n');
        const list: Proxy[] = [];

        for (const proxyStr of proxyListArray) {
            const [host, port] = proxyStr.split(':');
            if (host && port) {
                list.push({ host, port, used: false, error: false });
            }
        }

        // Armazena a lista de proxies no cache
        cache.set(cacheKey, list);
        return list;
    }

    // Seleciona um proxy aleatório da lista
    static async mutateProxy(): Promise<{ host: string; port: string }> {
        let proxyList = await this.getProxyList();
        const possibleProxies = proxyList.filter(proxy => !proxy.used && !proxy.error);

        if (possibleProxies.length === 0) {
            // Reseta todos os proxies se nenhum estiver disponível
            proxyList = proxyList.map(proxy => ({ ...proxy, used: false }));
        }

        const proxy = possibleProxies[Math.floor(Math.random() * possibleProxies.length)] || proxyList[0];
        proxy.used = true;

        return { host: proxy.host, port: proxy.port };
    }

    // Bane um proxy (marca como erro)
    static async banProxy(host: string, port: string): Promise<void> {
        const proxyList = await this.getProxyList();
        const proxyIndex = proxyList.findIndex(proxy => proxy.host === host && proxy.port === port);

        if (proxyIndex !== -1) {
            proxyList[proxyIndex].error = true;

            // Atualiza a lista de proxies no cache
            const cacheKey = 'proxyList';
            cache.set(cacheKey, proxyList);
        }
    }
}