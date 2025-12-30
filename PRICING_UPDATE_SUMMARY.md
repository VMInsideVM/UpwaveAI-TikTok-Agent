# Pricing and Credits Update Summary

## 1. Pricing Tier Updates
Modified `config/pricing.py`:
- **Standard Tier (`tier_599`)**: Price reduced from **599** to **549**.
- **Other Tiers**: Added explicit discount percentages.
    - Basic (`tier_299`): **-10%**
    - Professional (`tier_999`): **-20%**
    - Enterprise (`tier_1799`): **-30%**

## 2. API Updates
Modified `api/payment.py`:
- Updated `TierInfo` model to include an optional `discount` field.
- Updated `get_pricing_tiers` endpoint to return the discount information.

## 3. Frontend Updates
Modified `static/index.html`:
- **Credits Explanation**: Updated the text to clearly explain that **100 credits = 1 requested influencer**, resulting in **6 candidates** delivered (Tier 1: 1x, Tier 2: 2x, Tier 3: 3x).
- **Tier Cards**:
    - Added a red discount badge in the top-right corner for applicable tiers.
    - Removed the text description to keep the interface clean (Credits and Price only).

> **Note**: You must **restart the chatbot service** (`start_chatbot.py`) for the backend pricing and API changes to take effect.
