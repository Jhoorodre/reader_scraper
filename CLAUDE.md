# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
# or
yarn install

# Setup environment
cp .env.example .env  # Configure proxy settings and other environment variables
```

### Running the System
```bash
# Start proxy server (Python) - Terminal 1
python3 app.py

# Run downloader (TypeScript) - Terminal 2
npx ts-node --transpileOnly src/consumer/sussy.ts
```

### Testing
```bash
# Run TypeScript tests
npm test
# or
npx jest

# Run specific test file
npx jest --testPathPattern=provider_repository.test.ts
```

### Development
```bash
# Development mode with pretty logging
npm run dev

# Production mode
npm run prod

# Debug mode
npm run debug

# Download from MangaDex
npm run dex
```

### Docker
```bash
# Build and run with Docker
docker-compose up --build
```

## Architecture Overview

This is a manga scraper system with a dual-architecture approach:

### Core Components

1. **Provider System** (`src/providers/`)
   - Abstract base provider (`base/base.ts`) implementing repository pattern
   - Specific provider implementations (`scans/sussytoons/`, `scans/seitacelestial/`)
   - Generic providers for common manga site types (`generic/madara.ts`)

2. **Proxy Service** (`app.py`)
   - Python Flask server running on port 3333
   - Uses `nodriver` (undetected Chrome driver) for anti-bot bypassing
   - Provides `/scrape` endpoint for HTML content retrieval
   - Handles Cloudflare protection and cookie management

3. **Download System** (`src/download/`)
   - Image download functionality with proxy support
   - Concurrent downloading with rate limiting
   - Error handling and retry mechanisms

4. **Consumer Scripts** (`src/consumer/`)
   - Main download orchestrators (sussy.ts, seita.ts, generic_wp.ts)
   - Interactive CLI for manga selection and download options
   - Batch processing with concurrency controls

### Key Services

- **ProxyManager** (`src/services/proxy_manager.ts`): Manages proxy rotation with LRU caching
- **Axios Service** (`src/services/axios.ts`): HTTP client configuration
- **Logger** (`src/utils/logger.ts`): Centralized logging utility
- **Folder Utils** (`src/utils/folder.ts`): Directory management

### Data Flow

1. Consumer script prompts user for manga URL
2. Provider fetches manga metadata and chapter list
3. For each chapter, provider gets page URLs
4. Downloads route through Python proxy service when needed
5. Images saved to `manga/[sanitized-name]/[chapter]/[page].jpg`

### Testing Structure

- Unit tests in `src/__tests__/` mirror the source structure
- Tests cover providers, services, and core functionality
- Uses Jest with TypeScript configuration

## Important Notes

- The system uses both TypeScript (main logic) and Python (proxy service)
- Proxy service must be running before starting any download consumers
- Downloads are organized by manga name and chapter number
- The system includes built-in rate limiting and retry mechanisms
- All manga names are sanitized for filesystem compatibility

## Environment Variables

Key environment variables (see .env.example when available):
- `PROXY_URL`: Proxy service endpoint for fetching proxy lists
- Proxy authentication credentials
- Chrome/Puppeteer configuration
- Logging and concurrency settings