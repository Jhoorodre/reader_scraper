import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import axiosRetry from 'axios-retry';
import rateLimit from 'axios-rate-limit';
import https from 'https';
import { BASE_URL_PROXY, ProxyManager } from './proxy_manager';

interface RetryConfig {
    retries: number;
}

interface RateLimitConfig {
    perMilliseconds: number;
    maxRPS: number;
    maxRequests: number;
}

interface ProxyConfig {
    username: string;
    password: string;
}

export class CustomAxios {
    private instance: AxiosInstance;
    private enabledProxies = false;

    private axiosConfig: AxiosRequestConfig = {
        maxRedirects: 5,
        timeout: 1000 * 15,
    };

    private retryConfig: RetryConfig = {
        retries: 10,
    };

    private rateLimitConfig: RateLimitConfig = {
        perMilliseconds: 1000,
        maxRPS: 5,
        maxRequests: 3,
    };

    private proxyConfig: ProxyConfig = {
        username: 'eluylffn',
        password: 'i4tdqa6z5thv',
    };

    constructor(enabledProxies: boolean = false) {
        this.enabledProxies = enabledProxies;
        this.instance = axios.create(this.axiosConfig);

        // Configura retentativas
        axiosRetry(this.instance, {
            retries: this.retryConfig.retries,
            onRetry: async (count, error, config) => {
                if (count > this.retryConfig.retries) return Promise.reject(error);
                if (this.enabledProxies) {
                    const { host, port } = await ProxyManager.mutateProxy();
                    config.proxy = {
                        host,
                        port: parseInt(port),
                        auth: {
                            username: this.proxyConfig.username,
                            password: this.proxyConfig.password,
                        },
                    };
                }
            },
        });

        // Configura rate limiting
        rateLimit(this.instance, this.rateLimitConfig);

        // Configura interceptors
        this.instance.interceptors.request.use(this.handleRequest.bind(this));
        this.instance.interceptors.response.use(this.handleResponse.bind(this), this.handleError.bind(this));
    }

    /**
     * Interceptor de requisição: Adiciona proxy e headers à requisição, se habilitado.
     */
    private async handleRequest(config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> {
        if (this.enabledProxies) {
            const { host, port } = await ProxyManager.mutateProxy();
            config.proxy = {
                host,
                port: parseInt(port),
                auth: {
                    username: this.proxyConfig.username,
                    password: this.proxyConfig.password,
                },
            };
        }


        // Adiciona headers padrão
        //@ts-ignore
        config.headers = {
            ...config.headers,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://www.sussyscan.com',
            'Referer': 'https://www.sussyscan.com/',
        };

        return config;
    }

    /**
     * Interceptor de resposta: Retorna a resposta sem modificações.
     */
    private handleResponse(response: AxiosResponse): AxiosResponse {
        return response;
    }

    /**
     * Interceptor de erro: Bane o proxy em caso de erro 402 ou 403.
     */
    private async handleError(error: any): Promise<any> {
        if (error.response?.status === 402 || error.response?.status === 403) {
            const { host, port } = error.config.proxy || {};
            if (host && port) await ProxyManager.banProxy(host, port);
        }
        return Promise.reject(error);
    }

    /**
     * Retorna a instância configurada do Axios.
     */
    public getInstance(): AxiosInstance {
        return this.instance;
    }
}