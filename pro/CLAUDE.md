# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the crawler
```bash
# Install dependencies (Python 3.9.6 or 3.11+ recommended)
pip install -r requirements.txt
# or with uv package manager
uv run main.py --platform xhs --type search

# Basic usage
python main.py --platform xhs --type search
python main.py --platform xhs --type search --keywords "deepseek,chatgpt"
python main.py --platform dy --type creator
python main.py --platform bili --type detail

# With checkpoint (断点续爬)
python main.py --platform xhs --type search --enable_checkpoint
python main.py --platform xhs --type search --checkpoint_id <specific_id>
```

### Testing
No test framework is currently configured. Manual testing is done by running the crawler with different platforms and parameters.

## Architecture Overview

This is a **MediaCrawlerPro** system - a multi-platform social media crawler that extracts data from platforms like XiaoHongShu (小红书), Douyin (抖音), Kuaishou (快手), Bilibili, Weibo, Tieba, and Zhihu.

### Key Components

1. **Platform Crawlers** (`media_platform/`): Each platform has its own crawler implementation inheriting from `AbstractCrawler`
   - `xhs/` - XiaoHongShu crawler
   - `douyin/` - Douyin crawler  
   - `kuaishou/` - Kuaishou crawler
   - `bilibili/` - Bilibili crawler
   - `weibo/` - Weibo crawler
   - `tieba/` - Baidu Tieba crawler
   - `zhihu/` - Zhihu crawler

2. **Sign Service Integration**: The system requires a separate signing service (`MediaCrawlerPro-SignSrv`) running on localhost to generate platform-specific request signatures. This decoupled architecture allows for better maintainability.

3. **Account Pool & Proxy Management**:
   - Supports multiple account management via cookies stored in Excel or MySQL
   - IP proxy pool integration with Redis caching
   - Built-in retry mechanisms for stability

4. **Storage Options**:
   - Database (MySQL) - **Recommended** for deduplication and efficiency
   - CSV files
   - JSON files

5. **Checkpoint System**: Supports resumable crawling with checkpoints stored in files or Redis

## Configuration

### Main Configuration Files

- `config/base_config.py` - Core settings (platform, keywords, crawler type, storage options)
- `config/db_config.py` - Database connection settings (MySQL, Redis)  
- `config/proxy_config.py` - IP proxy pool configuration
- `config/sign_config.py` - Sign service endpoint configuration
- `config/account_pool/` - Account cookies storage (Excel or MySQL)

### Critical Configuration Variables

- `PLATFORM` - Target platform (xhs, dy, ks, bili, wb, tieba, zhihu)
- `CRAWLER_TYPE` - Type of crawling (search, detail, creator, homefeed)
- `SAVE_DATA_OPTION` - Storage type (db, csv, json)
- `ACCOUNT_POOL_SAVE_TYPE` - Account storage (xlsx, mysql)
- `ENABLE_CHECKPOINT` - Enable resumable crawling
- `MAX_CONCURRENCY_NUM` - Concurrent crawler count (keep low to avoid rate limiting)

## Development Guidelines

- The codebase follows an abstract factory pattern with platform-specific implementations
- All platform crawlers inherit from `base.base_crawler.AbstractCrawler`
- Request signing logic is externalized to a separate service for better decoupling
- Heavy use of async/await patterns for concurrent operations
- Built-in retry mechanisms and error handling for stability
- Database operations use connection pooling for efficiency

## Dependencies

- Python 3.9.6 or 3.11+ (specified in pyproject.toml)
- External services: MySQL, Redis, NodeJS (for sign service)
- Sign service must be running before starting the main crawler