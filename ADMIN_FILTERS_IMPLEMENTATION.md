# Admin Dashboard Filtering Features

## Overview
Added advanced filtering capabilities to the Admin Dashboard for both User Management and Report Management.

## Search & Filter Features

### 1. User Management
- **Search**: Username, Email, Phone Number (fuzzy match)
- **Advanced Filters**:
    - **Credits**: Range (Min/Max)
    - **Sessions**: Range (Min/Max)
    - **Total Tokens**: Range (Min/Max)
    - **24h Tokens**: Range (Min/Max)

### 2. Report Management
- **Search**: Report Title, Username, User Email
- **Advanced Filters**:
    - **Created Time**: Range (Start/End)
    - **Completed Time**: Range (Start/End)

### 3. Appeal Management
- **Search**: Title, Details, Username
- **Status Filter**: Existing functionality preserved

## Technical Implementation
- **Backend (`api/admin.py`)**:
    - Refactored `list_all_users` to use SQLAlchemy subqueries for efficient aggregation and filtering of `session_count` and `tokens_24h`.
    - Updated `list_all_reports` to accept date range parameters.
- **Frontend (`static/admin.html`)**:
    - Added "Advanced Filter" (高级筛选) toggle button.
    - Implemented filter panels with responsive grid layout.
    - Updated API calls to serialize and send new filter parameters.
