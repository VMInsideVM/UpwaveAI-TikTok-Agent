# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a TikTok influencer recommendation system built with LangChain + Qwen3-VL-30B. It's an AI agent that helps users find suitable TikTok influencers for product promotion through natural language conversation.

The system uses:
- LangChain ReAct agent pattern for orchestrating tools
- Playwright for web scraping (connects to Chrome via CDP on port 9224)
- LLM-powered semantic category matching
- Multi-dimensional influencer filtering and sorting

## Development Commands

### Prerequisites
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start Chrome with remote debugging:
   ```bash
   # Windows
   chrome.exe --remote-debugging-port=9224

   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9224

   # Linux
   google-chrome --remote-debugging-port=9224
   ```

3. Configure `.env` file with API credentials:
   ```
   OPENAI_API_KEY="your-api-key"
   OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
   OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
   ```

### Running the Agent
```bash
# Normal mode (interactive CLI)
python run_agent.py

# Test mode (with preset test cases)
python run_agent.py --test
```

### Testing Individual Modules
```bash
# Test agent initialization
python agent.py

# Test LangChain tools
python agent_tools.py

# Test category matching
python category_matcher.py

# Test adjustment helper
python adjustment_helper.py
```

## Architecture

### Core Agent Flow (agent.py)

The `TikTokInfluencerAgent` class orchestrates the entire workflow:

1. **User Input** → LangChain ReAct agent parses intent
2. **Category Matching** → LLM infers product category (3-level semantic matching)
3. **URL Construction** → Builds search URL with filters
4. **Quantity Check** → Validates available influencer count
5. **Gap Analysis** → Suggests parameter adjustments if needed
6. **Data Scraping** → Playwright crawls multiple pages
7. **Excel Export** → Merges and deduplicates results

Key properties:
- `self.scraped_dataframes`: Stores scraped data for multi-sort scenarios
- `self.retry_count`: Tracks scraping retry attempts (max 3)
- Knowledge base loaded from `knowledge_base.md` (auto-reloaded, no restart needed)

### Tool System (agent_tools.py)

8 LangChain tools available to the agent:

1. **BuildURLTool** → Constructs search URL from filter parameters
2. **CategoryMatchTool** → Semantic product categorization (29 L1 categories)
3. **GetMaxPageTool** → Fetches max page count from pagination
4. **AnalyzeQuantityTool** → Evaluates if influencer count meets user needs
5. **SuggestAdjustmentsTool** → Generates parameter adjustment strategies
6. **GetSortSuffixTool** → Returns URL suffix for sorting dimensions
7. **ScrapeInfluencersTool** → Crawls influencer data into DataFrame
8. **ExportExcelTool** → Exports merged data to Excel

All tools use Pydantic models for input validation (e.g., `BuildURLInput`, `CategoryInput`).

### Category Matching System (category_matcher.py)

Two-stage semantic matching process:

**Stage 1: L1 Category Inference**
- LLM selects 1 of 29 main categories from product name
- Uses low temperature (0.1) for deterministic results

**Stage 2: Deep Semantic Matching**
- Loads category JSON from `categories/{main_category}.json`
- First finds all possible L3 candidates (semantic similarity)
- Then performs deep reasoning to select best match
- Falls back: L3 → L2 → L1

Example: "口红" (lipstick) → "美妆个护" (L1) → "唇部彩妆" (L2) → "口红" (L3)

Returns: `{level, category_name, category_id, url_suffix, reasoning}`

### Web Scraping (main.py)

Playwright-based scraping with global state:
- `initialize_playwright()`: Connects to existing Chrome instance (CDP)
- `navigate_to_url()`: Navigates with network idle wait
- `get_max_page_number()`: Scrapes pagination element
- `get_table_data_as_dataframe()`: Multi-page table scraping with data cleaning

**Important**:
- Always call `initialize_playwright()` before any scraping
- Data cleaning includes: unit conversion (万/亿), percentage parsing, duplicate removal
- Excludes columns: "近28天销量趋势", "操作"

### Adjustment Helper (adjustment_helper.py)

When influencer count is insufficient:

**Quantity Analysis**:
- Available count = max_pages × 5 (conservative estimate)
- Status: sufficient / acceptable (≥50%) / insufficient (<50%)

**Adjustment Priority**:
1. Widen follower range (50-150% increase expected)
2. Remove new_followers constraint (20-30% increase)
3. Remove affiliate_check (30-50% increase)
4. Remove auth_type limit (10-20% increase)
5. Remove account_type limit (5-15% increase)

**Never Modified**: country_name, product category

## Important Rules

### 1. Country Selection
Only these countries are supported (see `COUNTRY_OPTIONS` in main.py:40-56):
- 全部, 美国, 印度尼西亚, 英国, 越南, 泰国, 马来西亚, 菲律宾
- 西班牙, 墨西哥, 德国, 法国, 意大利, 巴西, 日本

Once country is set, it MUST NOT be changed during the session.

### 2. Category Matching
29 main categories are available in `categories/` folder. If category matching fails, the agent must politely end the conversation (cannot proceed without category).

### 3. Data Pipeline
- Multi-sort scenarios: Scrape separately for each dimension, then merge with deduplication
- Deduplication: Keep first occurrence (based on first column - usually influencer ID)
- Output: Single Excel file in `output/` directory with timestamp

### 4. Error Handling
- Scraping failures: Auto-retry up to 3 times with 3-second delay
- Category not found: Immediately terminate gracefully
- Insufficient quantity: Use adjustment helper, wait for user confirmation

## Knowledge Base

The `knowledge_base.md` file contains:
- All parameter definitions and examples
- Supported countries and categories
- Sorting dimension mapping (6 options: follower count, engagement rate, sales, etc.)
- Adjustment strategies and best practices

**The agent loads this file at initialization**. You can edit it without restarting the agent.

## Code Patterns

### Adding New Filter Parameters

1. Add function to `main.py` (e.g., `new_filter(param)`)
2. Create Tool class in `agent_tools.py`:
   ```python
   class NewFilterInput(BaseModel):
       param: str = Field(description="...")

   class NewFilterTool(BaseTool):
       name = "new_filter"
       description = "..."
       args_schema = NewFilterInput

       def _run(self, param: str) -> str:
           # Implementation
   ```
3. Add to `get_all_tools()` list
4. Document in `knowledge_base.md`

### Modifying Agent Behavior

Edit the system prompt in `agent.py:62-123`. This controls:
- Workflow steps
- Tool usage order
- Decision-making logic
- Response formatting

### Testing Pattern

Most modules have `if __name__ == "__main__"` blocks with test cases. Run directly:
```bash
python <module_name>.py
```

## File Structure

- `agent.py` - Main agent controller (LangChain ReAct)
- `agent_tools.py` - Tool definitions (8 tools)
- `category_matcher.py` - Semantic category matching
- `adjustment_helper.py` - Parameter adjustment logic
- `main.py` - Web scraping functions (Playwright)
- `run_agent.py` - CLI interface with interactive loop
- `knowledge_base.md` - Domain knowledge (editable at runtime)
- `categories/` - 29 JSON files for product categories
- `output/` - Excel export directory
- `.env` - API configuration (not tracked)

## Common Pitfalls

1. **Forgetting to initialize Playwright**: Always call `initialize_playwright()` before scraping
2. **Modifying immutable params**: Never change country_name or category after initial selection
3. **Missing category files**: Ensure all 29 JSON files exist in `categories/`
4. **Chrome not running**: Agent requires Chrome with CDP port 9224 open
5. **Token limits**: Knowledge base is truncated to 3000 chars to avoid context overflow (see agent.py:52)

## Supported Countries

US, ID, GB, VN, TH, MY, PH, ES, MX, DE, FR, IT, BR, JP (plus "全部" for all countries)
