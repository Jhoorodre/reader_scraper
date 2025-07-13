import pino from 'pino';

// Configuração do logger
const logger = pino({
    level: process.env.LOG_LEVEL || 'info', // Nível de log padrão
    transport: {
        target: 'pino-pretty', // Formatação legível no terminal
        options: {
            colorize: true, // Adiciona cores aos logs
            translateTime: 'SYS:yyyy-mm-dd HH:MM:ss', // Formatação de data/hora
            ignore: 'pid,hostname', // Ignora campos específicos
        },
    },
});

export default logger;